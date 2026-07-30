package qmtctl

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os/exec"
	"runtime"
	"slices"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	mcpauth "github.com/modelcontextprotocol/go-sdk/auth"
	"github.com/modelcontextprotocol/go-sdk/oauthex"
	"golang.org/x/oauth2"
)

const oauthRefreshHTTPTimeout = 30 * time.Second

type oauthRegistration struct {
	mode                string
	clientID            string
	clientIDMetadataURL string
	dynamic             bool
}

type oauthLoginOptions struct {
	registration oauthRegistration
	scopes       []string
	noBrowser    bool
	out          io.Writer
}

type scopeUnionOAuthHandler struct {
	inner  *mcpauth.AuthorizationCodeHandler
	scopes []string
}

func (h *scopeUnionOAuthHandler) TokenSource(ctx context.Context) (oauth2.TokenSource, error) {
	return h.inner.TokenSource(ctx)
}

func (h *scopeUnionOAuthHandler) Authorize(
	ctx context.Context,
	request *http.Request,
	response *http.Response,
) error {
	if response.StatusCode == http.StatusForbidden {
		mergeStepUpScopes(response, h.scopes)
	}
	return h.inner.Authorize(ctx, request, response)
}

func mergeStepUpScopes(response *http.Response, retained []string) {
	headers := response.Header.Values("WWW-Authenticate")
	challenges, err := oauthex.ParseWWWAuthenticate(headers)
	if err != nil || len(challenges) != 1 {
		return
	}
	challenge := challenges[0]
	if challenge.Scheme != "bearer" || challenge.Params["error"] != "insufficient_scope" {
		return
	}
	scopes := append([]string(nil), retained...)
	scopes = append(scopes, strings.Fields(challenge.Params["scope"])...)
	sort.Strings(scopes)
	scopes = slices.Compact(scopes)
	challenge.Params["scope"] = strings.Join(scopes, " ")

	preferred := []string{"error", "scope", "resource_metadata", "resource"}
	var parts []string
	used := make(map[string]bool, len(challenge.Params))
	for _, key := range preferred {
		if value, ok := challenge.Params[key]; ok {
			parts = append(parts, key+"="+strconv.Quote(value))
			used[key] = true
		}
	}
	var remaining []string
	for key := range challenge.Params {
		if !used[key] {
			remaining = append(remaining, key)
		}
	}
	sort.Strings(remaining)
	for _, key := range remaining {
		parts = append(parts, key+"="+strconv.Quote(challenge.Params[key]))
	}
	response.Header.Set("WWW-Authenticate", "Bearer "+strings.Join(parts, ", "))
}

type loopbackCallback struct {
	listener  net.Listener
	server    *http.Server
	redirect  string
	noBrowser bool
	out       io.Writer
	closeOnce sync.Once
}

func newLoopbackCallback(noBrowser bool, out io.Writer) (*loopbackCallback, error) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, fmt.Errorf("listen for OAuth callback: %w", err)
	}
	return &loopbackCallback{
		listener:  listener,
		redirect:  "http://" + listener.Addr().String() + "/callback",
		noBrowser: noBrowser,
		out:       out,
	}, nil
}

func (c *loopbackCallback) Close() error {
	var err error
	c.closeOnce.Do(func() {
		if c.server != nil {
			ctx, cancel := context.WithTimeout(context.Background(), time.Second)
			defer cancel()
			err = c.server.Shutdown(ctx)
		} else {
			err = c.listener.Close()
		}
	})
	if errors.Is(err, net.ErrClosed) {
		return nil
	}
	return err
}

func (c *loopbackCallback) Fetch(ctx context.Context, args *mcpauth.AuthorizationArgs) (*mcpauth.AuthorizationResult, error) {
	type callbackResult struct {
		result *mcpauth.AuthorizationResult
		err    error
	}
	resultCh := make(chan callbackResult, 1)
	mux := http.NewServeMux()
	mux.HandleFunc("/callback", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "Method not allowed.", http.StatusMethodNotAllowed)
			return
		}
		query := r.URL.Query()
		if oauthError := query.Get("error"); oauthError != "" {
			http.Error(w, "Authorization failed. You can close this window.", http.StatusBadRequest)
			select {
			case resultCh <- callbackResult{err: fmt.Errorf("authorization failed: %s", oauthError)}:
			default:
			}
			return
		}
		code := query.Get("code")
		state := query.Get("state")
		if code == "" || state == "" {
			http.Error(w, "Missing authorization response fields.", http.StatusBadRequest)
			select {
			case resultCh <- callbackResult{err: errors.New("OAuth callback is missing code or state")}:
			default:
			}
			return
		}
		w.Header().Set("content-type", "text/html; charset=utf-8")
		_, _ = io.WriteString(w, "<!doctype html><title>qmtctl authorized</title><p>Authorization complete. You can close this window.</p>")
		select {
		case resultCh <- callbackResult{result: &mcpauth.AuthorizationResult{
			Code:  code,
			State: state,
			Iss:   query.Get("iss"),
		}}:
		default:
		}
	})
	c.server = &http.Server{
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() {
		if err := c.server.Serve(c.listener); err != nil && !errors.Is(err, http.ErrServerClosed) {
			resultCh <- callbackResult{err: err}
		}
	}()

	fmt.Fprintf(c.out, "Open this URL to authorize qmtctl:\n%s\n", args.URL)
	if !c.noBrowser {
		_ = openBrowser(args.URL)
	}
	select {
	case <-ctx.Done():
		_ = c.Close()
		return nil, ctx.Err()
	case outcome := <-resultCh:
		_ = c.Close()
		return outcome.result, outcome.err
	}
}

func openBrowser(rawURL string) error {
	var command *exec.Cmd
	switch runtime.GOOS {
	case "darwin":
		command = exec.Command("open", rawURL)
	case "windows":
		command = exec.Command("rundll32", "url.dll,FileProtocolHandler", rawURL)
	default:
		command = exec.Command("xdg-open", rawURL)
	}
	if err := command.Start(); err != nil {
		return err
	}
	return command.Process.Release()
}

func newOAuthLoginHandler(
	resource string,
	store *oauthSessionStore,
	options oauthLoginOptions,
) (*mcpauth.AuthorizationCodeHandler, io.Closer, error) {
	callback, err := newLoopbackCallback(options.noBrowser, options.out)
	if err != nil {
		return nil, nil, err
	}
	config := &mcpauth.AuthorizationCodeHandlerConfig{
		RedirectURL:              callback.redirect,
		AuthorizationCodeFetcher: callback.Fetch,
		RequestRefreshToken:      true,
		NewTokenSource: func(ctx context.Context, config *oauth2.Config, token *oauth2.Token) (oauth2.TokenSource, error) {
			save := func(updatedConfig *oauth2.Config, updatedToken *oauth2.Token) error {
				return store.Save(resource, updatedConfig, updatedToken, options.registration.mode)
			}
			if err := save(config, token); err != nil {
				return nil, err
			}
			return newSavingTokenSource(config.TokenSource(ctx, token), config, token, save), nil
		},
	}
	switch {
	case options.registration.clientIDMetadataURL != "":
		config.ClientIDMetadataDocumentConfig = &mcpauth.ClientIDMetadataDocumentConfig{
			URL: options.registration.clientIDMetadataURL,
		}
	case options.registration.clientID != "":
		config.PreregisteredClient = &oauthex.ClientCredentials{ClientID: options.registration.clientID}
	case options.registration.dynamic:
		config.DynamicClientRegistrationConfig = &mcpauth.DynamicClientRegistrationConfig{
			Metadata: &oauthex.ClientRegistrationMetadata{
				RedirectURIs:            []string{callback.redirect},
				TokenEndpointAuthMethod: "none",
				GrantTypes:              []string{"authorization_code", "refresh_token"},
				ResponseTypes:           []string{"code"},
				ClientName:              "qmtctl",
				Scope:                   strings.Join(options.scopes, " "),
				ApplicationType:         "native",
			},
		}
	default:
		_ = callback.Close()
		return nil, nil, errors.New("choose a client ID metadata URL, preregistered client ID, or dynamic registration")
	}
	handler, err := mcpauth.NewAuthorizationCodeHandler(config)
	if err != nil {
		_ = callback.Close()
		return nil, nil, err
	}
	return handler, callback, nil
}

func newRestoredOAuthHandler(
	resource string,
	store *oauthSessionStore,
	noBrowser bool,
	out io.Writer,
) (mcpauth.OAuthHandler, io.Closer, storedOAuthSession, error) {
	config, token, session, err := store.Load(resource)
	if err != nil {
		return nil, nil, storedOAuthSession{}, err
	}
	callback, err := newLoopbackCallback(noBrowser, out)
	if err != nil {
		return nil, nil, storedOAuthSession{}, err
	}
	refreshContext := context.WithValue(
		context.Background(),
		oauth2.HTTPClient,
		&http.Client{Timeout: oauthRefreshHTTPTimeout},
	)
	save := func(updatedConfig *oauth2.Config, updatedToken *oauth2.Token) error {
		return store.Save(resource, updatedConfig, updatedToken, session.Registration)
	}
	initial := newSavingTokenSource(config.TokenSource(refreshContext, token), config, token, save)
	handlerConfig := &mcpauth.AuthorizationCodeHandlerConfig{
		RedirectURL:              callback.redirect,
		AuthorizationCodeFetcher: callback.Fetch,
		RequestRefreshToken:      true,
		InitialTokenSource:       initial,
		NewTokenSource: func(ctx context.Context, updatedConfig *oauth2.Config, updatedToken *oauth2.Token) (oauth2.TokenSource, error) {
			if err := save(updatedConfig, updatedToken); err != nil {
				return nil, err
			}
			return newSavingTokenSource(
				updatedConfig.TokenSource(ctx, updatedToken),
				updatedConfig,
				updatedToken,
				save,
			), nil
		},
	}
	if session.Registration == "client_id_metadata" {
		handlerConfig.ClientIDMetadataDocumentConfig = &mcpauth.ClientIDMetadataDocumentConfig{
			URL: config.ClientID,
		}
	} else {
		// A dynamically registered client already has a durable client ID. Reuse
		// it instead of creating another registration during scope step-up.
		handlerConfig.PreregisteredClient = &oauthex.ClientCredentials{ClientID: config.ClientID}
	}
	handler, err := mcpauth.NewAuthorizationCodeHandler(handlerConfig)
	if err != nil {
		_ = callback.Close()
		return nil, nil, storedOAuthSession{}, err
	}
	return &scopeUnionOAuthHandler{
		inner:  handler,
		scopes: append([]string(nil), session.Scopes...),
	}, callback, session, nil
}

func authorizeOAuthScopes(
	ctx context.Context,
	handler *mcpauth.AuthorizationCodeHandler,
	resource string,
	scopes []string,
) error {
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, resource, nil)
	if err != nil {
		return err
	}
	metadataURLs := oauthMetadataURLs(resource)
	if len(metadataURLs) == 0 {
		return errors.New("cannot derive OAuth protected resource metadata URL")
	}
	challenge := fmt.Sprintf(
		`Bearer resource_metadata=%q, scope=%q`,
		metadataURLs[0],
		strings.Join(scopes, " "),
	)
	response := &http.Response{
		StatusCode: http.StatusUnauthorized,
		Header:     http.Header{"Www-Authenticate": []string{challenge}},
		Body:       io.NopCloser(strings.NewReader("")),
		Request:    request,
	}
	return handler.Authorize(ctx, request, response)
}

func parseAbsoluteURL(raw string) (*url.URL, error) {
	parsed, err := url.Parse(raw)
	if err != nil || !slices.Contains([]string{"http", "https"}, strings.ToLower(parsed.Scheme)) || parsed.Host == "" {
		return nil, fmt.Errorf("invalid absolute URL %q", raw)
	}
	return parsed, nil
}
