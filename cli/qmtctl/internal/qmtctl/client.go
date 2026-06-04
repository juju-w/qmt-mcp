package qmtctl

import (
	"bytes"
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
)

type Client struct {
	baseURL    string
	token      string
	httpClient *http.Client
	verbose    bool
	sessionID  string
	initOnce   sync.Once
	initErr    error
}

type rpcRequest struct {
	JSONRPC string         `json:"jsonrpc"`
	ID      int64          `json:"id"`
	Method  string         `json:"method"`
	Params  map[string]any `json:"params,omitempty"`
}

type rpcResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      int64           `json:"id"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *rpcError       `json:"error,omitempty"`
}

type rpcError struct {
	Code    int             `json:"code"`
	Message string          `json:"message"`
	Data    json.RawMessage `json:"data,omitempty"`
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

func (c *Client) Health(ctx context.Context) (map[string]any, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, healthURL(c.baseURL), nil)
	if err != nil {
		return nil, err
	}
	c.addHeaders(req)
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

func (c *Client) ListTools(ctx context.Context) (map[string]any, error) {
	if err := c.ensureInitialized(ctx); err != nil {
		return nil, err
	}
	var out map[string]any
	err := c.rpc(ctx, "tools/list", nil, &out)
	return out, err
}

func (c *Client) CallTool(ctx context.Context, name string, args map[string]any) (json.RawMessage, error) {
	if err := c.ensureInitialized(ctx); err != nil {
		return nil, err
	}
	params := map[string]any{"name": name, "arguments": args}
	var result ToolCallResult
	if err := c.rpc(ctx, "tools/call", params, &result); err != nil {
		return nil, err
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
		params := map[string]any{
			"protocolVersion": "2025-03-26",
			"capabilities":    map[string]any{},
			"clientInfo": map[string]any{
				"name":    "qmtctl",
				"version": "0.1.0",
			},
		}
		var out map[string]any
		if err := c.rpcNoInit(ctx, "initialize", params, &out); err != nil {
			c.initErr = err
			return
		}
		_ = c.rpcNoInit(ctx, "notifications/initialized", nil, nil)
	})
	return c.initErr
}

func (c *Client) rpc(ctx context.Context, method string, params map[string]any, out any) error {
	return c.rpcNoInit(ctx, method, params, out)
}

func (c *Client) rpcNoInit(ctx context.Context, method string, params map[string]any, out any) error {
	body, err := json.Marshal(rpcRequest{JSONRPC: "2.0", ID: time.Now().UnixNano(), Method: method, Params: params})
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL, bytes.NewReader(body))
	if err != nil {
		return err
	}
	c.addHeaders(req)
	req.Header.Set("content-type", "application/json")
	req.Header.Set("accept", "application/json, text/event-stream")
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return &AppError{Kind: "network", Message: err.Error()}
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return errorFromBody(resp.StatusCode, respBody)
	}
	if sessionID := resp.Header.Get("mcp-session-id"); sessionID != "" {
		c.sessionID = sessionID
	}
	respBody = normalizeRPCBody(resp.Header.Get("content-type"), respBody)
	if out == nil && len(bytes.TrimSpace(respBody)) == 0 {
		return nil
	}
	var msg rpcResponse
	if err := json.Unmarshal(respBody, &msg); err != nil {
		return &AppError{Kind: "protocol", Message: "MCP endpoint returned invalid JSON"}
	}
	if msg.Error != nil {
		return &AppError{Kind: "mcp", Message: msg.Error.Message, Status: msg.Error.Code}
	}
	if out == nil {
		return nil
	}
	if len(msg.Result) == 0 {
		return &AppError{Kind: "protocol", Message: "MCP response did not include result"}
	}
	if err := json.Unmarshal(msg.Result, out); err != nil {
		return &AppError{Kind: "protocol", Message: fmt.Sprintf("cannot decode MCP result: %v", err)}
	}
	return nil
}

func (c *Client) addHeaders(req *http.Request) {
	if c.token != "" {
		req.Header.Set("authorization", "Bearer "+c.token)
	}
	if c.sessionID != "" {
		req.Header.Set("mcp-session-id", c.sessionID)
	}
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

func normalizeRPCBody(contentType string, body []byte) []byte {
	if !strings.Contains(strings.ToLower(contentType), "text/event-stream") {
		return body
	}
	for _, line := range strings.Split(string(body), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "data:") {
			return []byte(strings.TrimSpace(strings.TrimPrefix(line, "data:")))
		}
	}
	return body
}
