package qmtctl

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"path"
	"strings"
	"sync"
	"time"

	mcpauth "github.com/modelcontextprotocol/go-sdk/auth"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

type Client struct {
	baseURL    string
	token      string
	httpClient *http.Client
	verbose    bool
	session    *mcp.ClientSession
	oauth      mcpauth.OAuthHandler
	oauthClose io.Closer
	initOnce   sync.Once
	initErr    error
}

type ToolCallResult struct {
	Content []struct {
		Type string          `json:"type"`
		Text string          `json:"text"`
		Data json.RawMessage `json:"data,omitempty"`
	} `json:"content"`
	StructuredContent json.RawMessage `json:"structuredContent,omitempty"`
	IsError           bool            `json:"isError,omitempty"`
}

type AppError struct {
	Kind    string `json:"error_type"`
	Message string `json:"message"`
	Status  int    `json:"status,omitempty"`
}

func (e *AppError) Error() string {
	if e.Kind == "" {
		return e.Message
	}
	return fmt.Sprintf("%s: %s", e.Kind, e.Message)
}

func NewClient(baseURL, token string, timeout time.Duration, verbose bool) *Client {
	return &Client{
		baseURL: strings.TrimRight(baseURL, "/"),
		token:   token,
		httpClient: &http.Client{
			Timeout: timeout,
		},
		verbose: verbose,
	}
}

func (c *Client) SetOAuthHandler(handler mcpauth.OAuthHandler, closer io.Closer) {
	c.oauth = handler
	c.oauthClose = closer
}

func (c *Client) Health(ctx context.Context) (map[string]any, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, healthURL(c.baseURL), nil)
	if err != nil {
		return nil, err
	}
	if err := c.addHeaders(ctx, req); err != nil {
		return nil, err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, &AppError{Kind: "network", Message: err.Error()}
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, errorFromBody(resp.StatusCode, body)
	}
	var doc map[string]any
	if err := json.Unmarshal(body, &doc); err != nil {
		return nil, &AppError{Kind: "protocol", Message: "health endpoint returned invalid JSON"}
	}
	return doc, nil
}

func (c *Client) OAuthMetadata(ctx context.Context) (map[string]any, error) {
	var lastErr error
	for _, metadataURL := range oauthMetadataURLs(c.baseURL) {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, metadataURL, nil)
		if err != nil {
			return nil, err
		}
		req.Header.Set("accept", "application/json")
		resp, err := c.httpClient.Do(req)
		if err != nil {
			return nil, &AppError{Kind: "network", Message: err.Error()}
		}
		body, readErr := io.ReadAll(resp.Body)
		resp.Body.Close()
		if readErr != nil {
			return nil, readErr
		}
		if resp.StatusCode == http.StatusNotFound {
			lastErr = errorFromBody(resp.StatusCode, body)
			continue
		}
		if resp.StatusCode < 200 || resp.StatusCode >= 300 {
			return nil, errorFromBody(resp.StatusCode, body)
		}
		var doc map[string]any
		if err := json.Unmarshal(body, &doc); err != nil {
			return nil, &AppError{Kind: "protocol", Message: "OAuth metadata endpoint returned invalid JSON"}
		}
		if resource, _ := doc["resource"].(string); strings.TrimSpace(resource) == "" {
			return nil, &AppError{Kind: "protocol", Message: "OAuth metadata did not include resource"}
		}
		return doc, nil
	}
	if lastErr != nil {
		return nil, lastErr
	}
	return nil, &AppError{Kind: "protocol", Message: "cannot derive OAuth metadata URL"}
}

func (c *Client) ListTools(ctx context.Context) (map[string]any, error) {
	if err := c.ensureInitialized(ctx); err != nil {
		return nil, err
	}
	result, err := c.session.ListTools(ctx, nil)
	if err != nil {
		return nil, sdkError(err)
	}
	wire, err := json.Marshal(result)
	if err != nil {
		return nil, &AppError{Kind: "protocol", Message: fmt.Sprintf("cannot encode MCP tools result: %v", err)}
	}
	var out map[string]any
	if err := json.Unmarshal(wire, &out); err != nil {
		return nil, &AppError{Kind: "protocol", Message: fmt.Sprintf("cannot decode MCP tools result: %v", err)}
	}
	return out, nil
}

func (c *Client) CallTool(ctx context.Context, name string, args map[string]any) (json.RawMessage, error) {
	if err := c.ensureInitialized(ctx); err != nil {
		return nil, err
	}
	sdkResult, err := c.session.CallTool(ctx, &mcp.CallToolParams{Name: name, Arguments: args})
	if err != nil {
		return nil, sdkError(err)
	}
	wire, err := json.Marshal(sdkResult)
	if err != nil {
		return nil, &AppError{Kind: "protocol", Message: fmt.Sprintf("cannot encode MCP tool result: %v", err)}
	}
	var result ToolCallResult
	if err := json.Unmarshal(wire, &result); err != nil {
		return nil, &AppError{Kind: "protocol", Message: fmt.Sprintf("cannot decode MCP tool result: %v", err)}
	}
	payload, err := unwrapToolResult(result)
	if err != nil {
		return nil, err
	}
	if isErrorEnvelope(payload) {
		return nil, envelopeError(payload)
	}
	return payload, nil
}

func (c *Client) ensureInitialized(ctx context.Context) error {
	c.initOnce.Do(func() {
		baseTransport := c.httpClient.Transport
		if baseTransport == nil {
			baseTransport = http.DefaultTransport
		}
		mcpHTTPClient := &http.Client{
			Transport:     bearerRoundTripper{token: c.token, base: baseTransport},
			CheckRedirect: c.httpClient.CheckRedirect,
			Jar:           c.httpClient.Jar,
			Timeout:       c.httpClient.Timeout,
		}
		sdkClient := mcp.NewClient(
			&mcp.Implementation{Name: "qmtctl", Version: Version},
			&mcp.ClientOptions{Capabilities: &mcp.ClientCapabilities{}},
		)
		c.session, c.initErr = sdkClient.Connect(
			ctx,
			&mcp.StreamableClientTransport{
				Endpoint:             c.baseURL,
				HTTPClient:           mcpHTTPClient,
				OAuthHandler:         c.oauth,
				DisableStandaloneSSE: true,
			},
			nil,
		)
		if c.initErr != nil {
			c.initErr = sdkError(c.initErr)
		}
	})
	return c.initErr
}

func (c *Client) Close() error {
	var closeErr error
	if c.session == nil {
		if c.oauthClose != nil {
			return c.oauthClose.Close()
		}
		return nil
	}
	closeErr = c.session.Close()
	if c.oauthClose != nil {
		if err := c.oauthClose.Close(); closeErr == nil {
			closeErr = err
		}
	}
	return closeErr
}

func sdkError(err error) error {
	if err == nil {
		return nil
	}
	return &AppError{Kind: "mcp", Message: err.Error()}
}

func (c *Client) addHeaders(ctx context.Context, req *http.Request) error {
	if c.token != "" {
		req.Header.Set("authorization", "Bearer "+c.token)
		return nil
	}
	if c.oauth == nil {
		return nil
	}
	source, err := c.oauth.TokenSource(ctx)
	if err != nil || source == nil {
		return err
	}
	token, err := source.Token()
	if err != nil {
		return err
	}
	req.Header.Set("authorization", "Bearer "+token.AccessToken)
	return nil
}

type bearerRoundTripper struct {
	token string
	base  http.RoundTripper
}

func (t bearerRoundTripper) RoundTrip(req *http.Request) (*http.Response, error) {
	if t.token == "" {
		return t.base.RoundTrip(req)
	}
	clone := req.Clone(req.Context())
	clone.Header = req.Header.Clone()
	clone.Header.Set("authorization", "Bearer "+t.token)
	return t.base.RoundTrip(clone)
}

func unwrapToolResult(result ToolCallResult) (json.RawMessage, error) {
	if len(result.StructuredContent) > 0 && string(result.StructuredContent) != "null" {
		return result.StructuredContent, nil
	}
	for _, item := range result.Content {
		switch {
		case len(item.Data) > 0:
			return item.Data, nil
		case item.Type == "text" && strings.TrimSpace(item.Text) != "":
			text := strings.TrimSpace(item.Text)
			if json.Valid([]byte(text)) {
				return json.RawMessage(text), nil
			}
			encoded, _ := json.Marshal(map[string]any{"ok": true, "text": text})
			return encoded, nil
		}
	}
	if result.IsError {
		return nil, &AppError{Kind: "mcp", Message: "tool returned an error without content"}
	}
	return json.RawMessage(`{"ok":true}`), nil
}

func isErrorEnvelope(payload json.RawMessage) bool {
	var doc map[string]any
	if json.Unmarshal(payload, &doc) != nil {
		return false
	}
	ok, hasOK := doc["ok"].(bool)
	_, hasType := doc["error_type"]
	return hasOK && !ok && hasType
}

func envelopeError(payload json.RawMessage) error {
	var doc struct {
		ErrorType string `json:"error_type"`
		Message   string `json:"message"`
	}
	_ = json.Unmarshal(payload, &doc)
	if doc.Message == "" {
		doc.Message = "tool returned ok=false"
	}
	return &AppError{Kind: doc.ErrorType, Message: doc.Message}
}

func errorFromBody(status int, body []byte) error {
	var doc map[string]any
	if json.Unmarshal(body, &doc) == nil {
		kind, _ := doc["error_type"].(string)
		message, _ := doc["message"].(string)
		if message == "" {
			message, _ = doc["error"].(string)
		}
		if message != "" {
			return &AppError{Kind: kindOrHTTP(kind), Message: message, Status: status}
		}
	}
	return &AppError{Kind: "http", Message: strings.TrimSpace(string(body)), Status: status}
}

func kindOrHTTP(kind string) string {
	if kind == "" {
		return "http"
	}
	return kind
}

func healthURL(base string) string {
	u, err := url.Parse(base)
	if err != nil {
		return strings.TrimRight(base, "/") + "/healthz"
	}
	if strings.HasSuffix(u.Path, "/mcp") {
		u.Path = strings.TrimSuffix(u.Path, "/mcp") + "/healthz"
	} else {
		u.Path = path.Join(u.Path, "healthz")
	}
	return u.String()
}

func oauthMetadataURLs(base string) []string {
	u, err := url.Parse(base)
	if err != nil || u.Scheme == "" || u.Host == "" {
		return []string{strings.TrimRight(base, "/") + "/.well-known/oauth-protected-resource"}
	}
	resourcePath := strings.Trim(u.Path, "/")
	u.RawPath = ""
	u.RawQuery = ""
	u.Fragment = ""

	var urls []string
	if resourcePath != "" {
		u.Path = "/.well-known/oauth-protected-resource/" + resourcePath
		urls = append(urls, u.String())
	}
	u.Path = "/.well-known/oauth-protected-resource"
	root := u.String()
	if len(urls) == 0 || urls[len(urls)-1] != root {
		urls = append(urls, root)
	}
	return urls
}
