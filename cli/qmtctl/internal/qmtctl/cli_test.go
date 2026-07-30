package qmtctl

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestHealthUsesBearerTokenAndJSON(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/healthz" {
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		if got := r.Header.Get("authorization"); got != "Bearer s3cret" {
			t.Fatalf("authorization header = %q", got)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"server": "live", "ok": true})
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{"--url", server.URL + "/mcp", "--token", "s3cret", "--json", "health"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if !strings.Contains(stdout.String(), `"server": "live"`) {
		t.Fatalf("unexpected stdout: %s", stdout.String())
	}
}

func TestVersionReportsInjectedVersion(t *testing.T) {
	previous := Version
	Version = "1.2.3"
	t.Cleanup(func() { Version = previous })

	var stdout, stderr bytes.Buffer
	code := Run([]string{"version"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if stdout.String() != "qmtctl 1.2.3\n" {
		t.Fatalf("unexpected stdout: %q", stdout.String())
	}
}

func TestHealthUsesOAuthAccessTokenEnvironment(t *testing.T) {
	t.Setenv("QMT_MCP_TOKEN", "static-token")
	t.Setenv("QMT_MCP_ACCESS_TOKEN", "oauth-access-token")
	brokenStore := filepath.Join(t.TempDir(), "broken-oauth-store.json")
	if err := os.WriteFile(brokenStore, []byte("not-json"), 0o600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("QMTCTL_AUTH_STORE", brokenStore)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("authorization"); got != "Bearer oauth-access-token" {
			t.Fatalf("authorization header = %q", got)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{"--url", server.URL + "/mcp", "health"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
}

func TestAuthDiscoverUsesPathAwareMetadataWithoutBearer(t *testing.T) {
	t.Setenv("QMT_MCP_ACCESS_TOKEN", "must-not-be-sent")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/.well-known/oauth-protected-resource/mcp" {
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		if got := r.Header.Get("authorization"); got != "" {
			t.Fatalf("metadata request leaked authorization header %q", got)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"resource":              serverURL(r) + "/mcp",
			"authorization_servers": []string{"https://auth.example.com"},
			"scopes_supported":      []string{"qmt:read"},
		})
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{"--url", server.URL + "/mcp", "--json", "auth", "discover"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if !strings.Contains(stdout.String(), `"authorization_servers"`) {
		t.Fatalf("unexpected stdout: %s", stdout.String())
	}
}

func TestToolsAggregatesModernGzipPages(t *testing.T) {
	var cursors []string
	var gzipResponses int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodDelete {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		var req map[string]any
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Fatalf("decode MCP request: %v", err)
		}
		switch req["method"] {
		case "server/discover":
			writeMaybeGzipRPCResult(t, w, r, req["id"], map[string]any{
				"resultType":        "complete",
				"supportedVersions": []string{"2026-07-28"},
				"capabilities":      map[string]any{"tools": map[string]any{}},
				"ttlMs":             0,
				"cacheScope":        "private",
			})
			gzipResponses++
		case "tools/list":
			params := req["params"].(map[string]any)
			cursor, _ := params["cursor"].(string)
			cursors = append(cursors, cursor)
			var result map[string]any
			switch cursor {
			case "":
				result = toolPage("cursor-1", "alpha")
			case "cursor-1":
				result = toolPage("cursor-2", "bravo")
			case "cursor-2":
				result = toolPage("", "charlie")
			default:
				t.Fatalf("unexpected cursor %q", cursor)
			}
			writeMaybeGzipRPCResult(t, w, r, req["id"], result)
			gzipResponses++
		default:
			t.Fatalf("unexpected method %v", req["method"])
		}
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{"--url", server.URL, "--json", "tools"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if got := strings.Join(cursors, ","); got != ",cursor-1,cursor-2" {
		t.Fatalf("cursors = %q", got)
	}
	for _, name := range []string{"alpha", "bravo", "charlie"} {
		if !strings.Contains(stdout.String(), `"name": "`+name+`"`) {
			t.Fatalf("missing %s in stdout: %s", name, stdout.String())
		}
	}
	if gzipResponses != 4 {
		t.Fatalf("gzip responses = %d", gzipResponses)
	}
	var result map[string]any
	if err := json.Unmarshal(stdout.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result["resultType"] != "complete" {
		t.Fatalf("metadata was not preserved: %#v", result)
	}
	for _, key := range []string{"ttlMs", "cacheScope"} {
		if _, found := result[key]; !found {
			t.Fatalf("metadata key %q was not preserved: %#v", key, result)
		}
	}
	if _, found := result["nextCursor"]; found {
		t.Fatalf("consumed cursor leaked into aggregate: %#v", result)
	}
}

func TestToolsRejectsPaginationCursorCycle(t *testing.T) {
	var listCalls int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		req, ok := readToolRequest(t, w, r)
		if !ok {
			return
		}
		if req["method"] != "tools/list" {
			t.Fatalf("unexpected method %v", req["method"])
		}
		listCalls++
		writeRPCResult(w, req["id"], toolPage("repeated", "tool-"+string(rune('a'+listCalls-1))))
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{"--url", server.URL, "tools"}, &stdout, &stderr)
	if code != 1 {
		t.Fatalf("exit %d stdout=%s stderr=%s", code, stdout.String(), stderr.String())
	}
	if listCalls != 2 {
		t.Fatalf("list calls = %d", listCalls)
	}
	if !strings.Contains(stderr.String(), "pagination cursor cycle") {
		t.Fatalf("unexpected stderr: %s", stderr.String())
	}
}

func TestToolsRejectsDuplicateNamesAcrossPages(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		req, ok := readToolRequest(t, w, r)
		if !ok {
			return
		}
		params, _ := req["params"].(map[string]any)
		cursor, _ := params["cursor"].(string)
		next := "second"
		if cursor == "second" {
			next = ""
		}
		writeRPCResult(w, req["id"], toolPage(next, "duplicate"))
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{"--url", server.URL, "tools"}, &stdout, &stderr)
	if code != 1 {
		t.Fatalf("exit %d stdout=%s stderr=%s", code, stdout.String(), stderr.String())
	}
	if !strings.Contains(stderr.String(), `duplicate tool "duplicate"`) {
		t.Fatalf("unexpected stderr: %s", stderr.String())
	}
}

func TestSearchCallsExpectedMCPTool(t *testing.T) {
	var called bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/healthz":
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
		case "/mcp":
			if got := r.Header.Get("authorization"); got != "Bearer s3cret" {
				t.Fatalf("authorization header = %q", got)
			}
			req, ok := readToolRequest(t, w, r)
			if !ok {
				return
			}
			switch req["method"] {
			case "tools/call":
				params := req["params"].(map[string]any)
				if params["name"] != "qmt_xtdata_search_instruments" {
					t.Fatalf("tool name = %v", params["name"])
				}
				args := params["arguments"].(map[string]any)
				if args["query"] != "纳指" || args["rank_by"] != "liquidity" {
					t.Fatalf("arguments = %#v", args)
				}
				called = true
				writeRPCResult(w, req["id"], toolResult(map[string]any{
					"ok":      true,
					"query":   "纳指",
					"results": []any{map[string]any{"code": "513100.SH", "name": "纳指ETF"}},
				}))
			default:
				t.Fatalf("unexpected method %v", req["method"])
			}
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run(
		[]string{"--url", server.URL + "/mcp", "--token", "s3cret", "search", "纳指", "--rank", "liquidity"},
		&stdout,
		&stderr,
	)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if !called {
		t.Fatal("tools/call was not reached")
	}
	if !strings.Contains(stdout.String(), "results: 1 item") {
		t.Fatalf("unexpected stdout: %s", stdout.String())
	}
}

func TestToolErrorEnvelopeReturnsNonZero(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		req, ok := readToolRequest(t, w, r)
		if !ok {
			return
		}
		switch req["method"] {
		case "tools/call":
			writeRPCResult(w, req["id"], toolResult(map[string]any{
				"ok":         false,
				"error_type": "not_ready",
				"message":    "xtdata is not ready",
			}))
		}
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{"--url", server.URL, "snapshot", "510300.SH"}, &stdout, &stderr)
	if code != 1 {
		t.Fatalf("exit %d stdout=%s stderr=%s", code, stdout.String(), stderr.String())
	}
	if strings.Contains(stderr.String(), "s3cret") {
		t.Fatalf("stderr leaked token: %s", stderr.String())
	}
	if !strings.Contains(stderr.String(), "not_ready: xtdata is not ready") {
		t.Fatalf("unexpected stderr: %s", stderr.String())
	}
}

func TestAccountPositionsCallsExpectedMCPTool(t *testing.T) {
	var called bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		req, ok := readToolRequest(t, w, r)
		if !ok {
			return
		}
		switch req["method"] {
		case "tools/call":
			params := req["params"].(map[string]any)
			if params["name"] != "qmt_xttrade_positions" {
				t.Fatalf("tool name = %v", params["name"])
			}
			args := params["arguments"].(map[string]any)
			if args["account_id"] != "123456789" {
				t.Fatalf("arguments = %#v", args)
			}
			called = true
			writeRPCResult(w, req["id"], toolResult(map[string]any{
				"ok":         true,
				"account_id": "123456789",
				"positions":  []any{map[string]any{"code": "510300.SH", "volume": 100}},
			}))
		default:
			t.Fatalf("unexpected method %v", req["method"])
		}
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{"--url", server.URL, "account", "positions", "--account", "123456789"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if !called {
		t.Fatal("tools/call was not reached")
	}
	if !strings.Contains(stdout.String(), "positions: 1 item") {
		t.Fatalf("unexpected stdout: %s", stdout.String())
	}
}

func TestSnapshotCachePolicyCallsExpectedMCPTool(t *testing.T) {
	var called bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		req, ok := readToolRequest(t, w, r)
		if !ok {
			return
		}
		switch req["method"] {
		case "tools/call":
			params := req["params"].(map[string]any)
			if params["name"] != "qmt_xtdata_snapshot" {
				t.Fatalf("tool name = %v", params["name"])
			}
			args := params["arguments"].(map[string]any)
			if args["cache_policy"] != "cache_only" {
				t.Fatalf("arguments = %#v", args)
			}
			called = true
			writeRPCResult(w, req["id"], toolResult(map[string]any{"ok": true, "data": []any{}}))
		default:
			t.Fatalf("unexpected method %v", req["method"])
		}
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{"--url", server.URL, "snapshot", "510300.SH", "--cache-only"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if !called {
		t.Fatal("tools/call was not reached")
	}
}

func TestSubscriptionAddCallsExpectedMCPTool(t *testing.T) {
	var called bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		req, ok := readToolRequest(t, w, r)
		if !ok {
			return
		}
		switch req["method"] {
		case "tools/call":
			params := req["params"].(map[string]any)
			if params["name"] != "qmt_xtdata_quote_subscribe" {
				t.Fatalf("tool name = %v", params["name"])
			}
			args := params["arguments"].(map[string]any)
			if args["subscription_id"] != "strategy1" || args["backend_preference"] != "auto" {
				t.Fatalf("arguments = %#v", args)
			}
			codes := args["codes"].([]any)
			if len(codes) != 2 || codes[0] != "510300.SH" || codes[1] != "510500.SH" {
				t.Fatalf("codes = %#v", codes)
			}
			called = true
			writeRPCResult(w, req["id"], toolResult(map[string]any{"ok": true, "subscription": map[string]any{"id": "strategy1"}}))
		default:
			t.Fatalf("unexpected method %v", req["method"])
		}
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{"--url", server.URL, "subscription", "add", "--id", "strategy1", "510300.SH,510500.SH"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if !called {
		t.Fatal("tools/call was not reached")
	}
}

func TestPortfolioRiskCallsExpectedMCPTool(t *testing.T) {
	var called bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		req, ok := readToolRequest(t, w, r)
		if !ok {
			return
		}
		switch req["method"] {
		case "tools/call":
			params := req["params"].(map[string]any)
			if params["name"] != "qmt_portfolio_risk_checks" {
				t.Fatalf("tool name = %v", params["name"])
			}
			args := params["arguments"].(map[string]any)
			if args["account_id"] != "123456789" || args["quote_policy"] != "live" {
				t.Fatalf("arguments = %#v", args)
			}
			thresholds := args["thresholds"].(map[string]any)
			if thresholds["max_single_position_weight"] != 0.25 {
				t.Fatalf("thresholds = %#v", thresholds)
			}
			called = true
			writeRPCResult(w, req["id"], toolResult(map[string]any{"ok": true, "checks": []any{}}))
		default:
			t.Fatalf("unexpected method %v", req["method"])
		}
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{
		"--url", server.URL,
		"portfolio", "risk",
		"--account", "123456789",
		"--quote-policy", "live",
		"--max-single-weight", "0.25",
	}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if !called {
		t.Fatal("tools/call was not reached")
	}
}

func TestOptionVixInputsCallsExpectedMCPTool(t *testing.T) {
	var called bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		req, ok := readToolRequest(t, w, r)
		if !ok {
			return
		}
		switch req["method"] {
		case "tools/call":
			params := req["params"].(map[string]any)
			if params["name"] != "qmt_xtdata_volatility_index_inputs" {
				t.Fatalf("tool name = %v", params["name"])
			}
			args := params["arguments"].(map[string]any)
			if args["family"] != "300ETF" {
				t.Fatalf("arguments = %#v", args)
			}
			called = true
			writeRPCResult(w, req["id"], toolResult(map[string]any{"ok": true, "rows": []any{}}))
		default:
			t.Fatalf("unexpected method %v", req["method"])
		}
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{"--url", server.URL, "option", "vix-inputs", "--family", "300ETF"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if !called {
		t.Fatal("tools/call was not reached")
	}
}

func TestRefIpoCallsExpectedMCPTool(t *testing.T) {
	var called bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		req, ok := readToolRequest(t, w, r)
		if !ok {
			return
		}
		switch req["method"] {
		case "tools/call":
			params := req["params"].(map[string]any)
			if params["name"] != "qmt_xtdata_ipo_info" {
				t.Fatalf("tool name = %v", params["name"])
			}
			args := params["arguments"].(map[string]any)
			if args["start_time"] != "20250101" || args["end_time"] != "20250131" {
				t.Fatalf("arguments = %#v", args)
			}
			called = true
			writeRPCResult(w, req["id"], toolResult(map[string]any{"ok": true, "rows": []any{}}))
		default:
			t.Fatalf("unexpected method %v", req["method"])
		}
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{"--url", server.URL, "ref", "ipo", "--start", "20250101", "--end", "20250131"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if !called {
		t.Fatal("tools/call was not reached")
	}
}

func TestSectorImportJSONCallsExpectedMCPTool(t *testing.T) {
	tmp := t.TempDir()
	path := filepath.Join(tmp, "signal.json")
	if err := os.WriteFile(path, []byte(`{"holdings":[{"thscode":"510300.SH"}],"top_candidates":[{"thscode":"510500.SH"}]}`), 0o644); err != nil {
		t.Fatal(err)
	}
	var called bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		req, ok := readToolRequest(t, w, r)
		if !ok {
			return
		}
		switch req["method"] {
		case "tools/call":
			params := req["params"].(map[string]any)
			if params["name"] != "qmt_xtdata_sector_add_codes" {
				t.Fatalf("tool name = %v", params["name"])
			}
			args := params["arguments"].(map[string]any)
			if args["sector"] != "MCP/strategy1/latest-signal" {
				t.Fatalf("arguments = %#v", args)
			}
			codes := args["codes"].([]any)
			if len(codes) != 2 || codes[0] != "510300.SH" || codes[1] != "510500.SH" {
				t.Fatalf("codes = %#v", codes)
			}
			called = true
			writeRPCResult(w, req["id"], toolResult(map[string]any{"ok": true}))
		default:
			t.Fatalf("unexpected method %v", req["method"])
		}
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{
		"--url", server.URL,
		"sector", "import-json",
		"--sector", "MCP/strategy1/latest-signal",
		"--file", path,
	}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if !called {
		t.Fatal("tools/call was not reached")
	}
}

func TestFormulaCallCallsExpectedMCPTool(t *testing.T) {
	var called bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		req, ok := readToolRequest(t, w, r)
		if !ok {
			return
		}
		switch req["method"] {
		case "tools/call":
			params := req["params"].(map[string]any)
			if params["name"] != "qmt_xtdata_formula_call" {
				t.Fatalf("tool name = %v", params["name"])
			}
			args := params["arguments"].(map[string]any)
			if args["formula_name"] != "VIX_HELPER" || args["code"] != "510300.SH" {
				t.Fatalf("arguments = %#v", args)
			}
			called = true
			writeRPCResult(w, req["id"], toolResult(map[string]any{"ok": true, "result": map[string]any{}}))
		default:
			t.Fatalf("unexpected method %v", req["method"])
		}
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run([]string{
		"--url", server.URL,
		"formula", "call",
		"--formula", "VIX_HELPER",
		"--code", "510300.SH",
	}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if !called {
		t.Fatal("tools/call was not reached")
	}
}

func writeRPCResult(w http.ResponseWriter, id any, result any) {
	w.Header().Set("content-type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{"jsonrpc": "2.0", "id": id, "result": result})
}

func writeMaybeGzipRPCResult(t *testing.T, w http.ResponseWriter, r *http.Request, id any, result any) {
	t.Helper()
	if !strings.Contains(r.Header.Get("accept-encoding"), "gzip") {
		t.Fatalf("request did not advertise gzip: %q", r.Header.Get("accept-encoding"))
	}
	raw, err := json.Marshal(map[string]any{"jsonrpc": "2.0", "id": id, "result": result})
	if err != nil {
		t.Fatal(err)
	}
	w.Header().Set("content-type", "application/json")
	w.Header().Set("content-encoding", "gzip")
	writer := gzip.NewWriter(w)
	if _, err := writer.Write(raw); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
}

func writeRPCError(w http.ResponseWriter, id any, code int, message string) {
	w.Header().Set("content-type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{
		"jsonrpc": "2.0",
		"id":      id,
		"error":   map[string]any{"code": code, "message": message},
	})
}

func readToolRequest(t *testing.T, w http.ResponseWriter, r *http.Request) (map[string]any, bool) {
	t.Helper()
	if r.Method == http.MethodDelete {
		w.WriteHeader(http.StatusNoContent)
		return nil, false
	}
	var req map[string]any
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		t.Errorf("decode MCP request: %v", err)
		return nil, false
	}
	switch req["method"] {
	case "server/discover":
		writeRPCError(w, req["id"], -32601, "Method not found")
		return nil, false
	case "initialize":
		writeRPCResult(w, req["id"], map[string]any{
			"protocolVersion": "2025-11-25",
			"capabilities":    map[string]any{"tools": map[string]any{}},
			"serverInfo":      map[string]any{"name": "qmtctl-test", "version": "1.0.0"},
		})
		return nil, false
	case "notifications/initialized":
		w.WriteHeader(http.StatusAccepted)
		return nil, false
	}
	return req, true
}

func toolResult(payload map[string]any) map[string]any {
	raw, _ := json.Marshal(payload)
	return map[string]any{
		"content": []any{map[string]any{"type": "text", "text": string(raw)}},
	}
}

func toolPage(nextCursor, names string) map[string]any {
	tools := make([]any, 0)
	for _, name := range strings.Fields(names) {
		tools = append(tools, map[string]any{
			"name":        name,
			"description": name + " tool",
			"inputSchema": map[string]any{"type": "object"},
		})
	}
	result := map[string]any{
		"resultType": "complete",
		"tools":      tools,
	}
	if nextCursor != "" {
		result["nextCursor"] = nextCursor
	}
	return result
}

func serverURL(r *http.Request) string {
	return "http://" + r.Host
}
