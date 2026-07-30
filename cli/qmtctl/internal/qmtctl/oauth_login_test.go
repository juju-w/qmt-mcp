package qmtctl

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	mcpauth "github.com/modelcontextprotocol/go-sdk/auth"
	"github.com/modelcontextprotocol/go-sdk/oauthex"
	"golang.org/x/oauth2"
)

type lockedBuffer struct {
	mu sync.Mutex
	bytes.Buffer
}

func (b *lockedBuffer) Write(data []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.Buffer.Write(data)
}

func (b *lockedBuffer) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.Buffer.String()
}

func TestLoopbackCallbackReturnsCodeStateAndIssuer(t *testing.T) {
	var output lockedBuffer
	callback, err := newLoopbackCallback(true, &output)
	if err != nil {
		t.Fatal(err)
	}
	defer callback.Close()

	resultCh := make(chan *mcpauth.AuthorizationResult, 1)
	errCh := make(chan error, 1)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	go func() {
		result, err := callback.Fetch(ctx, &mcpauth.AuthorizationArgs{URL: "https://auth.example.com/authorize"})
		if err != nil {
			errCh <- err
			return
		}
		resultCh <- result
	}()

	var response *http.Response
	for deadline := time.Now().Add(2 * time.Second); time.Now().Before(deadline); {
		response, err = http.Get(callback.redirect + "?code=code-1&state=state-1&iss=https%3A%2F%2Fauth.example.com")
		if err == nil {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if err != nil {
		t.Fatal(err)
	}
	_ = response.Body.Close()
	select {
	case err := <-errCh:
		t.Fatal(err)
	case result := <-resultCh:
		if result.Code != "code-1" || result.State != "state-1" || result.Iss != "https://auth.example.com" {
			t.Fatalf("result = %#v", result)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timed out waiting for callback result")
	}
	if !strings.Contains(output.String(), "https://auth.example.com/authorize") {
		t.Fatalf("authorization URL was not printed: %s", output.String())
	}
}

func TestAuthLoginPKCEResourceScopesAndPersistence(t *testing.T) {
	t.Setenv("QMT_MCP_ACCESS_TOKEN", "")
	t.Setenv("QMT_MCP_TOKEN", "static-must-not-mask-oauth-login")
	var server *httptest.Server
	var authorizationQuery url.Values
	var tokenForm url.Values
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/.well-known/oauth-protected-resource/mcp", "/.well-known/oauth-protected-resource":
			w.Header().Set("content-type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"resource":              server.URL + "/mcp",
				"authorization_servers": []string{server.URL},
				"scopes_supported":      []string{"qmt:read", "qmt:market"},
			})
		case "/.well-known/oauth-authorization-server", "/.well-known/openid-configuration":
			w.Header().Set("content-type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"issuer":                                server.URL,
				"authorization_endpoint":                server.URL + "/authorize",
				"token_endpoint":                        server.URL + "/token",
				"code_challenge_methods_supported":      []string{"S256"},
				"token_endpoint_auth_methods_supported": []string{"none"},
				"scopes_supported":                      []string{"qmt:read", "qmt:market", "offline_access"},
				"client_id_metadata_document_supported": true,
			})
		case "/authorize":
			authorizationQuery = r.URL.Query()
			redirect, err := url.Parse(authorizationQuery.Get("redirect_uri"))
			if err != nil {
				t.Errorf("redirect_uri: %v", err)
				http.Error(w, "bad redirect", http.StatusBadRequest)
				return
			}
			query := redirect.Query()
			query.Set("code", "auth-code")
			query.Set("state", authorizationQuery.Get("state"))
			redirect.RawQuery = query.Encode()
			http.Redirect(w, r, redirect.String(), http.StatusFound)
		case "/token":
			if err := r.ParseForm(); err != nil {
				t.Errorf("parse token form: %v", err)
			}
			tokenForm = r.Form
			w.Header().Set("content-type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"access_token":  "oauth-access",
				"refresh_token": "oauth-refresh",
				"token_type":    "Bearer",
				"expires_in":    3600,
				"scope":         "qmt:read qmt:market",
			})
		case "/mcp":
			if r.Header.Get("authorization") != "Bearer oauth-access" {
				w.Header().Set(
					"www-authenticate",
					fmt.Sprintf(
						`Bearer resource_metadata=%q, scope="qmt:read", resource=%q`,
						server.URL+"/.well-known/oauth-protected-resource/mcp",
						server.URL+"/mcp",
					),
				)
				http.Error(w, "unauthorized", http.StatusUnauthorized)
				return
			}
			if r.Method == http.MethodDelete {
				w.WriteHeader(http.StatusNoContent)
				return
			}
			var request map[string]any
			if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
				t.Errorf("decode MCP request: %v", err)
				return
			}
			switch request["method"] {
			case "server/discover":
				writeRPCError(w, request["id"], -32601, "Method not found")
			case "initialize":
				writeRPCResult(w, request["id"], map[string]any{
					"protocolVersion": "2025-11-25",
					"capabilities":    map[string]any{"tools": map[string]any{}},
					"serverInfo":      map[string]any{"name": "oauth-fixture", "version": "1.0.0"},
				})
			case "notifications/initialized":
				w.WriteHeader(http.StatusAccepted)
			case "tools/list":
				writeRPCResult(w, request["id"], map[string]any{"tools": []any{}})
			default:
				t.Errorf("unexpected method %v", request["method"])
			}
		default:
			http.NotFound(w, r)
		}
	})
	server = httptest.NewServer(handler)
	defer server.Close()

	storePath := filepath.Join(t.TempDir(), "oauth.json")
	var stdout, stderr lockedBuffer
	done := make(chan int, 1)
	go func() {
		done <- Run(
			[]string{
				"--url", server.URL + "/mcp",
				"--auth-store", storePath,
				"--json",
				"auth", "login",
				"--client-id-metadata-url", "https://client.example.com/qmtctl.json",
				"--scope", "qmt:market",
				"--no-browser",
				"--login-timeout", "5s",
			},
			&stdout,
			&stderr,
		)
	}()

	var authorizationURL string
	for deadline := time.Now().Add(3 * time.Second); time.Now().Before(deadline); {
		for _, line := range strings.Split(stderr.String(), "\n") {
			if strings.HasPrefix(line, server.URL+"/authorize?") {
				authorizationURL = line
				break
			}
		}
		if authorizationURL != "" {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if authorizationURL == "" {
		t.Fatalf("authorization URL not printed; stderr=%s", stderr.String())
	}
	response, err := http.Get(authorizationURL)
	if err != nil {
		t.Fatal(err)
	}
	_ = response.Body.Close()
	select {
	case code := <-done:
		if code != 0 {
			t.Fatalf("exit %d stdout=%s stderr=%s", code, stdout.String(), stderr.String())
		}
	case <-time.After(5 * time.Second):
		t.Fatal("qmtctl login did not finish")
	}

	if authorizationQuery.Get("resource") != server.URL+"/mcp" {
		t.Fatalf("authorization resource = %q", authorizationQuery.Get("resource"))
	}
	if authorizationQuery.Get("client_id") != "https://client.example.com/qmtctl.json" {
		t.Fatalf("authorization client_id = %q", authorizationQuery.Get("client_id"))
	}
	if authorizationQuery.Get("code_challenge_method") != "S256" || authorizationQuery.Get("code_challenge") == "" {
		t.Fatalf("PKCE query = %#v", authorizationQuery)
	}
	if got := strings.Fields(authorizationQuery.Get("scope")); !containsAll(got, "qmt:read", "qmt:market") {
		t.Fatalf("authorization scopes = %#v", got)
	}
	if tokenForm.Get("resource") != server.URL+"/mcp" || tokenForm.Get("code_verifier") == "" {
		t.Fatalf("token form = %#v", tokenForm)
	}
	store, err := newOAuthSessionStore(storePath)
	if err != nil {
		t.Fatal(err)
	}
	_, token, session, err := store.Load(server.URL + "/mcp")
	if err != nil {
		t.Fatal(err)
	}
	if token.AccessToken != "oauth-access" || token.RefreshToken != "oauth-refresh" {
		t.Fatal("OAuth tokens were not persisted")
	}
	if session.Registration != "client_id_metadata" || !containsAll(session.Scopes, "qmt:read", "qmt:market") {
		t.Fatalf("session = %#v", session)
	}
	if strings.Contains(stdout.String(), "oauth-access") || strings.Contains(stdout.String(), "oauth-refresh") {
		t.Fatalf("stdout leaked tokens: %s", stdout.String())
	}
}

func TestAuthLoginRejectsMismatchedCallbackStateBeforeTokenExchange(t *testing.T) {
	var server *httptest.Server
	var output lockedBuffer
	var tokenRequests int
	server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/.well-known/oauth-protected-resource/mcp", "/.well-known/oauth-protected-resource":
			w.Header().Set("content-type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"resource":              server.URL + "/mcp",
				"authorization_servers": []string{server.URL},
			})
		case "/.well-known/oauth-authorization-server", "/.well-known/openid-configuration":
			w.Header().Set("content-type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"issuer":                                server.URL,
				"authorization_endpoint":                server.URL + "/authorize",
				"token_endpoint":                        server.URL + "/token",
				"code_challenge_methods_supported":      []string{"S256"},
				"token_endpoint_auth_methods_supported": []string{"none"},
				"client_id_metadata_document_supported": true,
			})
		case "/token":
			tokenRequests++
			http.Error(w, "must not exchange a mismatched callback", http.StatusBadRequest)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	storePath := filepath.Join(t.TempDir(), "oauth.json")
	store, err := newOAuthSessionStore(storePath)
	if err != nil {
		t.Fatal(err)
	}
	handler, closer, err := newOAuthLoginHandler(
		server.URL+"/mcp",
		store,
		oauthLoginOptions{
			registration: oauthRegistration{
				mode:                "client_id_metadata",
				clientIDMetadataURL: "https://client.example.com/qmtctl.json",
			},
			scopes:    []string{"qmt:read"},
			noBrowser: true,
			out:       &output,
		},
	)
	if err != nil {
		t.Fatal(err)
	}
	defer closer.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	resultCh := make(chan error, 1)
	go func() {
		resultCh <- authorizeOAuthScopes(ctx, handler, server.URL+"/mcp", []string{"qmt:read"})
	}()

	var authorizationURL string
	for deadline := time.Now().Add(3 * time.Second); time.Now().Before(deadline); {
		select {
		case err := <-resultCh:
			t.Fatalf("authorization failed before callback: %v", err)
		default:
		}
		for _, line := range strings.Split(output.String(), "\n") {
			if strings.HasPrefix(line, server.URL+"/authorize?") {
				authorizationURL = line
				break
			}
		}
		if authorizationURL != "" {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if authorizationURL == "" {
		t.Fatalf("authorization URL not printed: %s", output.String())
	}
	parsedAuthorizationURL, err := url.Parse(authorizationURL)
	if err != nil {
		t.Fatal(err)
	}
	redirectURL, err := url.Parse(parsedAuthorizationURL.Query().Get("redirect_uri"))
	if err != nil {
		t.Fatal(err)
	}
	query := redirectURL.Query()
	query.Set("code", "must-not-exchange")
	query.Set("state", "wrong-state")
	redirectURL.RawQuery = query.Encode()
	response, err := http.Get(redirectURL.String())
	if err != nil {
		t.Fatal(err)
	}
	_ = response.Body.Close()

	select {
	case err := <-resultCh:
		if err == nil || !strings.Contains(err.Error(), "state mismatch") {
			t.Fatalf("authorization error = %v", err)
		}
	case <-ctx.Done():
		t.Fatal(ctx.Err())
	}
	if tokenRequests != 0 {
		t.Fatalf("token endpoint requests = %d", tokenRequests)
	}
	if _, _, _, err := store.Load(server.URL + "/mcp"); !errors.Is(err, ErrOAuthSessionNotFound) {
		t.Fatalf("mismatched callback persisted a session: %v", err)
	}
}

func TestOAuthLoginHandlerAcceptsAllPublicRegistrationModes(t *testing.T) {
	store, err := newOAuthSessionStore(filepath.Join(t.TempDir(), "oauth.json"))
	if err != nil {
		t.Fatal(err)
	}
	cases := []oauthRegistration{
		{mode: "client_id_metadata", clientIDMetadataURL: "https://client.example.com/qmtctl.json"},
		{mode: "preregistered", clientID: "qmtctl-public"},
		{mode: "dynamic", dynamic: true},
	}
	for _, registration := range cases {
		t.Run(registration.mode, func(t *testing.T) {
			handler, closer, err := newOAuthLoginHandler(
				"https://qmt.example.com/mcp",
				store,
				oauthLoginOptions{
					registration: registration,
					scopes:       []string{"qmt:read"},
					noBrowser:    true,
					out:          &lockedBuffer{},
				},
			)
			if err != nil {
				t.Fatal(err)
			}
			if handler == nil {
				t.Fatal("handler is nil")
			}
			if err := closer.Close(); err != nil {
				t.Fatal(err)
			}
		})
	}
}

func TestMergeStepUpScopesRetainsPreviouslyGrantedScopes(t *testing.T) {
	response := &http.Response{
		StatusCode: http.StatusForbidden,
		Header: http.Header{
			"Www-Authenticate": []string{
				`Bearer error="insufficient_scope", scope="qmt:market", ` +
					`resource_metadata="https://qmt.example.com/.well-known/oauth-protected-resource/mcp", ` +
					`resource="https://qmt.example.com/mcp"`,
			},
		},
	}
	mergeStepUpScopes(response, []string{"qmt:read", "offline_access"})
	challenges, err := oauthex.ParseWWWAuthenticate(response.Header.Values("WWW-Authenticate"))
	if err != nil {
		t.Fatal(err)
	}
	if len(challenges) != 1 {
		t.Fatalf("challenges = %#v", challenges)
	}
	if got := strings.Fields(challenges[0].Params["scope"]); !containsAll(
		got,
		"qmt:read",
		"qmt:market",
		"offline_access",
	) {
		t.Fatalf("merged scopes = %#v", got)
	}
}

func TestSavedOAuthSessionStepsUpAndPersistsScopes(t *testing.T) {
	var server *httptest.Server
	var authorizationQuery url.Values
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/.well-known/oauth-protected-resource/mcp", "/.well-known/oauth-protected-resource":
			w.Header().Set("content-type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"resource":              server.URL + "/mcp",
				"authorization_servers": []string{server.URL},
				"scopes_supported":      []string{"qmt:read", "qmt:market"},
			})
		case "/.well-known/oauth-authorization-server", "/.well-known/openid-configuration":
			w.Header().Set("content-type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"issuer":                                server.URL,
				"authorization_endpoint":                server.URL + "/authorize",
				"token_endpoint":                        server.URL + "/token",
				"code_challenge_methods_supported":      []string{"S256"},
				"token_endpoint_auth_methods_supported": []string{"none"},
				"scopes_supported":                      []string{"qmt:read", "qmt:market"},
				"client_id_metadata_document_supported": true,
			})
		case "/authorize":
			authorizationQuery = r.URL.Query()
			redirect, err := url.Parse(authorizationQuery.Get("redirect_uri"))
			if err != nil {
				t.Errorf("redirect_uri: %v", err)
				http.Error(w, "bad redirect", http.StatusBadRequest)
				return
			}
			query := redirect.Query()
			query.Set("code", "step-up-code")
			query.Set("state", authorizationQuery.Get("state"))
			redirect.RawQuery = query.Encode()
			http.Redirect(w, r, redirect.String(), http.StatusFound)
		case "/token":
			w.Header().Set("content-type", "application/json")
			if err := r.ParseForm(); err != nil {
				t.Errorf("parse token form: %v", err)
			}
			if r.Form.Get("resource") != server.URL+"/mcp" || r.Form.Get("code_verifier") == "" {
				t.Errorf("step-up token form = %#v", r.Form)
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"access_token":  "new-access",
				"refresh_token": "new-refresh",
				"token_type":    "Bearer",
				"expires_in":    3600,
				"scope":         "qmt:read qmt:market",
			})
		case "/mcp":
			if r.Method == http.MethodDelete {
				w.WriteHeader(http.StatusNoContent)
				return
			}
			var request map[string]any
			if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
				t.Errorf("decode MCP request: %v", err)
				return
			}
			bearer := r.Header.Get("authorization")
			if request["method"] == "tools/call" && bearer == "Bearer old-access" {
				w.Header().Set(
					"www-authenticate",
					fmt.Sprintf(
						`Bearer error="insufficient_scope", scope="qmt:market", resource_metadata=%q, resource=%q`,
						server.URL+"/.well-known/oauth-protected-resource/mcp",
						server.URL+"/mcp",
					),
				)
				http.Error(w, "insufficient scope", http.StatusForbidden)
				return
			}
			if bearer != "Bearer old-access" && bearer != "Bearer new-access" {
				http.Error(w, "unauthorized", http.StatusUnauthorized)
				return
			}
			switch request["method"] {
			case "server/discover":
				writeRPCError(w, request["id"], -32601, "Method not found")
			case "initialize":
				writeRPCResult(w, request["id"], map[string]any{
					"protocolVersion": "2025-11-25",
					"capabilities":    map[string]any{"tools": map[string]any{}},
					"serverInfo":      map[string]any{"name": "step-up-fixture", "version": "1.0.0"},
				})
			case "notifications/initialized":
				w.WriteHeader(http.StatusAccepted)
			case "tools/call":
				writeRPCResult(w, request["id"], toolResult(map[string]any{"ok": true, "data": []any{}}))
			default:
				t.Errorf("unexpected method %v", request["method"])
			}
		default:
			http.NotFound(w, r)
		}
	})
	server = httptest.NewServer(handler)
	defer server.Close()

	store, err := newOAuthSessionStore(filepath.Join(t.TempDir(), "oauth.json"))
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Save(
		server.URL+"/mcp",
		&oauth2.Config{
			ClientID: "https://client.example.com/qmtctl.json",
			Endpoint: oauth2.Endpoint{
				AuthURL:   server.URL + "/authorize",
				TokenURL:  server.URL + "/token",
				AuthStyle: oauth2.AuthStyleInParams,
			},
			Scopes: []string{"qmt:read"},
		},
		&oauth2.Token{
			AccessToken:  "old-access",
			RefreshToken: "old-refresh",
			TokenType:    "Bearer",
			Expiry:       time.Now().Add(time.Hour),
		},
		"client_id_metadata",
	); err != nil {
		t.Fatal(err)
	}

	var output lockedBuffer
	oauthHandler, closer, _, err := newRestoredOAuthHandler(server.URL+"/mcp", store, true, &output)
	if err != nil {
		t.Fatal(err)
	}
	client := NewClient(server.URL+"/mcp", "", 5*time.Second, false)
	client.SetOAuthHandler(oauthHandler, closer)
	defer client.Close()

	type callResult struct {
		payload json.RawMessage
		err     error
	}
	done := make(chan callResult, 1)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	go func() {
		payload, err := client.CallTool(ctx, "qmt_xtdata_snapshot", map[string]any{"codes": []string{"510300.SH"}})
		done <- callResult{payload: payload, err: err}
	}()

	var authorizationURL string
	for deadline := time.Now().Add(5 * time.Second); time.Now().Before(deadline); {
		select {
		case result := <-done:
			t.Fatalf("tool call finished before step-up: err=%v payload=%s", result.err, result.payload)
		default:
		}
		for _, line := range strings.Split(output.String(), "\n") {
			if strings.HasPrefix(line, server.URL+"/authorize?") {
				authorizationURL = line
				break
			}
		}
		if authorizationURL != "" {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if authorizationURL == "" {
		t.Fatalf("step-up URL not printed: %s", output.String())
	}
	response, err := http.Get(authorizationURL)
	if err != nil {
		t.Fatal(err)
	}
	_ = response.Body.Close()

	select {
	case result := <-done:
		if result.err != nil {
			t.Fatal(result.err)
		}
		if !strings.Contains(string(result.payload), `"ok":true`) {
			t.Fatalf("payload = %s", result.payload)
		}
	case <-ctx.Done():
		t.Fatal(ctx.Err())
	}
	if got := strings.Fields(authorizationQuery.Get("scope")); !containsAll(got, "qmt:read", "qmt:market") {
		t.Fatalf("step-up scopes = %#v", got)
	}
	_, refreshed, session, err := store.Load(server.URL + "/mcp")
	if err != nil {
		t.Fatal(err)
	}
	if refreshed.AccessToken != "new-access" || refreshed.RefreshToken != "new-refresh" {
		t.Fatalf("step-up token was not persisted: %#v", refreshed)
	}
	if !containsAll(session.Scopes, "qmt:read", "qmt:market") {
		t.Fatalf("saved scopes = %#v", session.Scopes)
	}
}

func containsAll(values []string, expected ...string) bool {
	set := make(map[string]bool, len(values))
	for _, value := range values {
		set[value] = true
	}
	for _, value := range expected {
		if !set[value] {
			return false
		}
	}
	return true
}
