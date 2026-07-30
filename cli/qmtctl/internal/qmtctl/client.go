package qmtctl

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"path"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	mcpauth "github.com/modelcontextprotocol/go-sdk/auth"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

type Client struct {
	baseURL                string
	token                  string
	httpClient             *http.Client
	notificationHTTPClient *http.Client
	requestTimeout         time.Duration
	taskMode               string
	verbose                bool
	session                *mcp.ClientSession
	oauth                  mcpauth.OAuthHandler
	oauthClose             io.Closer
	initOnce               sync.Once
	initErr                error
	notificationIDs        atomic.Uint64
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
	Data    any    `json:"data,omitempty"`
}

const maxToolListPages = 1000

const (
	tasksExtensionID = "io.modelcontextprotocol/tasks"
	taskModeWait     = "wait"
	taskModeDetach   = "detach"
	taskModeSync     = "sync"
)

func (e *AppError) Error() string {
	if e.Kind == "" {
		return e.Message
	}
	return fmt.Sprintf("%s: %s", e.Kind, e.Message)
}

func NewClient(baseURL, token string, timeout time.Duration, verbose bool) *Client {
	return &Client{
		baseURL:        strings.TrimRight(baseURL, "/"),
		token:          token,
		requestTimeout: timeout,
		taskMode:       taskModeWait,
		httpClient: &http.Client{
			Timeout: timeout,
		},
		verbose: verbose,
	}
}

func (c *Client) SetTaskMode(mode string) error {
	switch mode {
	case taskModeWait, taskModeDetach, taskModeSync:
		c.taskMode = mode
		return nil
	default:
		return fmt.Errorf("invalid task mode %q (want wait, detach, or sync)", mode)
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
	var tools []*mcp.Tool
	seenCursors := make(map[string]struct{})
	seenTools := make(map[string]struct{})
	cursor := ""
	var combined map[string]any
	for page := 0; page < maxToolListPages; page++ {
		var params *mcp.ListToolsParams
		if cursor != "" {
			params = &mcp.ListToolsParams{Cursor: cursor}
		}
		result, err := c.session.ListTools(ctx, params)
		if err != nil {
			return nil, sdkError(err)
		}
		if page == 0 {
			wire, err := json.Marshal(result)
			if err != nil {
				return nil, &AppError{
					Kind:    "protocol",
					Message: fmt.Sprintf("cannot encode MCP tools result: %v", err),
				}
			}
			if err := json.Unmarshal(wire, &combined); err != nil {
				return nil, &AppError{
					Kind:    "protocol",
					Message: fmt.Sprintf("cannot decode MCP tools result: %v", err),
				}
			}
		}
		for _, tool := range result.Tools {
			if tool == nil || tool.Name == "" {
				return nil, &AppError{Kind: "protocol", Message: "tools/list returned a tool without a name"}
			}
			if _, exists := seenTools[tool.Name]; exists {
				return nil, &AppError{
					Kind:    "protocol",
					Message: fmt.Sprintf("tools/list returned duplicate tool %q across pages", tool.Name),
				}
			}
			seenTools[tool.Name] = struct{}{}
			tools = append(tools, tool)
		}
		if result.NextCursor == "" {
			wire, err := json.Marshal(tools)
			if err != nil {
				return nil, &AppError{
					Kind:    "protocol",
					Message: fmt.Sprintf("cannot encode aggregated MCP tools: %v", err),
				}
			}
			var aggregated []any
			if err := json.Unmarshal(wire, &aggregated); err != nil {
				return nil, &AppError{
					Kind:    "protocol",
					Message: fmt.Sprintf("cannot decode aggregated MCP tools: %v", err),
				}
			}
			combined["tools"] = aggregated
			delete(combined, "nextCursor")
			return combined, nil
		}
		if _, exists := seenCursors[result.NextCursor]; exists {
			return nil, &AppError{Kind: "protocol", Message: "tools/list pagination cursor cycle"}
		}
		seenCursors[result.NextCursor] = struct{}{}
		cursor = result.NextCursor
	}
	return nil, &AppError{
		Kind:    "protocol",
		Message: fmt.Sprintf("tools/list pagination exceeded %d pages", maxToolListPages),
	}
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
		c.notificationHTTPClient = &http.Client{
			Transport:     baseTransport,
			CheckRedirect: c.httpClient.CheckRedirect,
			Jar:           c.httpClient.Jar,
		}
		timedTransport := requestTimeoutRoundTripper{
			base:    baseTransport,
			timeout: c.requestTimeout,
		}
		authTransport := bearerRoundTripper{token: c.token, base: timedTransport}
		taskTransport := &taskRoundTripper{
			client: c,
			base:   authTransport,
			mode:   c.taskMode,
		}
		mcpHTTPClient := &http.Client{
			Transport:     taskTransport,
			CheckRedirect: c.httpClient.CheckRedirect,
			Jar:           c.httpClient.Jar,
		}
		capabilities := &mcp.ClientCapabilities{}
		if c.taskMode != taskModeSync {
			capabilities.AddExtension(tasksExtensionID, nil)
		}
		sdkClient := mcp.NewClient(
			&mcp.Implementation{Name: "qmtctl", Version: Version},
			&mcp.ClientOptions{Capabilities: capabilities},
		)
		for _, method := range []string{"tasks/get", "tasks/update", "tasks/cancel"} {
			var err error
			switch method {
			case "tasks/get":
				err = mcp.AddSendingCustomMethod[*TaskGetParams, *TaskInfo](sdkClient, method)
			case "tasks/update":
				err = mcp.AddSendingCustomMethod[*TaskUpdateParams, *TaskAck](sdkClient, method)
			case "tasks/cancel":
				err = mcp.AddSendingCustomMethod[*TaskGetParams, *TaskAck](sdkClient, method)
			}
			if err != nil {
				c.initErr = err
				return
			}
		}
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
	var inputRequired *TaskInputRequiredError
	if errors.As(err, &inputRequired) {
		return &AppError{
			Kind:    "task_input_required",
			Message: inputRequired.Error(),
			Data: map[string]any{
				"taskId":        inputRequired.TaskID,
				"inputRequests": decodeBrief(inputRequired.InputRequests),
			},
		}
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

type timeoutBody struct {
	io.ReadCloser
	cancel context.CancelFunc
}

func (b *timeoutBody) Close() error {
	err := b.ReadCloser.Close()
	b.cancel()
	return err
}

type requestTimeoutRoundTripper struct {
	base    http.RoundTripper
	timeout time.Duration
}

func (t requestTimeoutRoundTripper) RoundTrip(req *http.Request) (*http.Response, error) {
	if t.timeout <= 0 {
		return t.base.RoundTrip(req)
	}
	ctx, cancel := context.WithTimeout(req.Context(), t.timeout)
	resp, err := t.base.RoundTrip(req.Clone(ctx))
	if err != nil {
		cancel()
		return nil, err
	}
	resp.Body = &timeoutBody{ReadCloser: resp.Body, cancel: cancel}
	return resp, nil
}

type taskRoundTripper struct {
	client *Client
	base   http.RoundTripper
	mode   string
	ids    atomic.Uint64
}

type rpcWireRequest struct {
	Method string `json:"method"`
	Params struct {
		Name   string          `json:"name"`
		TaskID string          `json:"taskId"`
		Meta   json.RawMessage `json:"_meta"`
	} `json:"params"`
}

type rpcWireResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *TaskRPCError   `json:"error,omitempty"`
}

func (t *taskRoundTripper) RoundTrip(req *http.Request) (*http.Response, error) {
	wireReq, forwarded, err := readAndRestoreRequest(req)
	if err != nil {
		return nil, err
	}
	if strings.HasPrefix(wireReq.Method, "tasks/") && wireReq.Params.TaskID != "" {
		forwarded.Header.Set("Mcp-Method", wireReq.Method)
		forwarded.Header.Set("Mcp-Name", wireReq.Params.TaskID)
	}
	resp, err := t.base.RoundTrip(forwarded)
	if err != nil || wireReq.Method != "tools/call" || t.mode == taskModeSync ||
		resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return resp, err
	}
	envelope, err := readRPCResponse(resp)
	if err != nil {
		return nil, err
	}
	var created TaskInfo
	if len(envelope.Result) == 0 || json.Unmarshal(envelope.Result, &created) != nil ||
		created.ResultType != "task" || created.TaskID == "" {
		return replaceRPCResponse(resp, envelope)
	}
	if t.mode == taskModeDetach {
		handle, err := detachedToolResult(created)
		if err != nil {
			return nil, err
		}
		envelope.Result = handle
		return replaceRPCResponse(resp, envelope)
	}
	terminal, err := t.wait(req.Context(), wireReq.Params.Meta, created)
	if err != nil {
		envelope.Result = nil
		envelope.Error = taskError(created.TaskID, err)
		return replaceRPCResponse(resp, envelope)
	}
	switch terminal.Status {
	case "completed":
		envelope.Result = terminal.Result
		envelope.Error = nil
	case "failed":
		envelope.Result = nil
		envelope.Error = terminal.Error
		if envelope.Error == nil {
			envelope.Error = &TaskRPCError{Code: -32603, Message: "Task failed without an error payload"}
		}
	case "cancelled":
		envelope.Result = nil
		envelope.Error = &TaskRPCError{
			Code:    -32800,
			Message: fmt.Sprintf("Task %s was cancelled", terminal.TaskID),
		}
	case "input_required":
		return nil, &TaskInputRequiredError{
			TaskID:        terminal.TaskID,
			InputRequests: terminal.InputRequests,
		}
	default:
		envelope.Result = nil
		envelope.Error = &TaskRPCError{Code: -32603, Message: "Task returned an invalid terminal status"}
	}
	return replaceRPCResponse(resp, envelope)
}

func (t *taskRoundTripper) wait(ctx context.Context, meta json.RawMessage, task TaskInfo) (TaskInfo, error) {
	current := task
	if taskStatusSettled(current.Status) {
		return current, nil
	}
	if current.Status != "working" {
		return TaskInfo{}, invalidTaskStatus(current.TaskID, current.Status)
	}
	if pushed, settled, err := t.client.listenTask(ctx, meta, current); err != nil {
		return TaskInfo{}, err
	} else {
		current = pushed
		if settled {
			return current, nil
		}
	}
	for {
		if taskStatusSettled(current.Status) {
			return current, nil
		}
		if current.Status != "working" {
			return TaskInfo{}, invalidTaskStatus(current.TaskID, current.Status)
		}
		if err := waitForTaskPoll(ctx, current.PollIntervalMS); err != nil {
			return TaskInfo{}, err
		}
		next, err := t.poll(ctx, meta, current.TaskID)
		if err != nil {
			return TaskInfo{}, err
		}
		current = next
	}
}

func waitForTaskPoll(ctx context.Context, intervalMS int64) error {
	delay := time.Duration(intervalMS) * time.Millisecond
	if delay < 100*time.Millisecond {
		delay = 100 * time.Millisecond
	}
	if delay > time.Minute {
		delay = time.Minute
	}
	timer := time.NewTimer(delay)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

func (t *taskRoundTripper) poll(
	ctx context.Context,
	meta json.RawMessage,
	taskID string,
) (TaskInfo, error) {
	params := map[string]any{"taskId": taskID}
	if len(meta) > 0 && string(meta) != "null" {
		var value any
		if err := json.Unmarshal(meta, &value); err != nil {
			return TaskInfo{}, fmt.Errorf("cannot decode MCP request metadata: %w", err)
		}
		params["_meta"] = value
	}
	body, err := json.Marshal(map[string]any{
		"jsonrpc": "2.0",
		"id":      fmt.Sprintf("qmtctl-task-%d", t.ids.Add(1)),
		"method":  "tasks/get",
		"params":  params,
	})
	if err != nil {
		return TaskInfo{}, err
	}
	pollReq, err := http.NewRequestWithContext(ctx, http.MethodPost, t.client.baseURL, bytes.NewReader(body))
	if err != nil {
		return TaskInfo{}, err
	}
	pollReq.Header.Set("Content-Type", "application/json")
	pollReq.Header.Set("Accept", "application/json, text/event-stream")
	pollReq.Header.Set("Mcp-Method", "tasks/get")
	pollReq.Header.Set("Mcp-Name", taskID)
	if err := t.client.addHeaders(ctx, pollReq); err != nil {
		return TaskInfo{}, err
	}
	resp, err := t.base.RoundTrip(pollReq)
	if err != nil {
		return TaskInfo{}, err
	}
	envelope, err := readRPCResponse(resp)
	if err != nil {
		return TaskInfo{}, err
	}
	if envelope.Error != nil {
		return TaskInfo{}, envelope.Error
	}
	var task TaskInfo
	if err := json.Unmarshal(envelope.Result, &task); err != nil {
		return TaskInfo{}, fmt.Errorf("cannot decode tasks/get result: %w", err)
	}
	if task.TaskID != taskID {
		return TaskInfo{}, fmt.Errorf("tasks/get returned task %q, want %q", task.TaskID, taskID)
	}
	return task, nil
}

func readAndRestoreRequest(req *http.Request) (rpcWireRequest, *http.Request, error) {
	var wire rpcWireRequest
	if req.Body == nil {
		return wire, req, nil
	}
	body, err := io.ReadAll(io.LimitReader(req.Body, 8*1024*1024+1))
	if err != nil {
		return wire, nil, err
	}
	if len(body) > 8*1024*1024 {
		return wire, nil, fmt.Errorf("MCP request exceeds 8 MiB")
	}
	clone := req.Clone(req.Context())
	clone.Header = req.Header.Clone()
	clone.Body = io.NopCloser(bytes.NewReader(body))
	clone.ContentLength = int64(len(body))
	req.Body = io.NopCloser(bytes.NewReader(body))
	if len(body) > 0 {
		_ = json.Unmarshal(body, &wire)
	}
	return wire, clone, nil
}

func readRPCResponse(resp *http.Response) (rpcWireResponse, error) {
	var envelope rpcWireResponse
	if resp == nil {
		return envelope, fmt.Errorf("empty MCP HTTP response")
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 16*1024*1024+1))
	if err != nil {
		return envelope, err
	}
	if len(body) > 16*1024*1024 {
		return envelope, fmt.Errorf("MCP response exceeds 16 MiB")
	}
	if strings.Contains(resp.Header.Get("Content-Type"), "text/event-stream") {
		body, err = firstSSEData(body)
		if err != nil {
			return envelope, err
		}
	}
	if err := json.Unmarshal(body, &envelope); err != nil {
		return envelope, fmt.Errorf("cannot decode MCP response: %w", err)
	}
	return envelope, nil
}

func firstSSEData(body []byte) ([]byte, error) {
	for _, line := range bytes.Split(body, []byte("\n")) {
		if bytes.HasPrefix(line, []byte("data:")) {
			value := bytes.TrimSpace(bytes.TrimPrefix(line, []byte("data:")))
			if len(value) > 0 {
				return value, nil
			}
		}
	}
	return nil, fmt.Errorf("MCP SSE response did not contain a data event")
}

func replaceRPCResponse(resp *http.Response, envelope rpcWireResponse) (*http.Response, error) {
	body, err := json.Marshal(envelope)
	if err != nil {
		return nil, err
	}
	resp.Body = io.NopCloser(bytes.NewReader(body))
	resp.ContentLength = int64(len(body))
	resp.Header.Del("Content-Encoding")
	resp.Header.Set("Content-Type", "application/json")
	resp.Header.Set("Content-Length", fmt.Sprint(len(body)))
	return resp, nil
}

func detachedToolResult(task TaskInfo) (json.RawMessage, error) {
	payload, err := json.Marshal(task)
	if err != nil {
		return nil, err
	}
	var structured map[string]any
	if err := json.Unmarshal(payload, &structured); err != nil {
		return nil, err
	}
	structured["ok"] = true
	text, err := json.Marshal(structured)
	if err != nil {
		return nil, err
	}
	return json.Marshal(map[string]any{
		"resultType":        "complete",
		"content":           []map[string]any{{"type": "text", "text": string(text)}},
		"structuredContent": structured,
		"isError":           false,
	})
}

func taskError(taskID string, err error) *TaskRPCError {
	if typed, ok := err.(*TaskRPCError); ok {
		return typed
	}
	data, _ := json.Marshal(map[string]string{"taskId": taskID})
	return &TaskRPCError{
		Code:    -32603,
		Message: fmt.Sprintf("Task %s wait stopped: %v", taskID, err),
		Data:    data,
	}
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
