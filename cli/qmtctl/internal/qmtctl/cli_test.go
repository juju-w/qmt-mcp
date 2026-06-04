package qmtctl

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
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

func TestSearchCallsExpectedMCPTool(t *testing.T) {
	var called bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/healthz":
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
		case "/mcp":
			var req map[string]any
			if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
				t.Fatal(err)
			}
			switch req["method"] {
			case "initialize":
				w.Header().Set("mcp-session-id", "abc")
				writeRPCResult(w, req["id"], map[string]any{"protocolVersion": "2025-03-26"})
			case "notifications/initialized":
				writeRPCResult(w, req["id"], map[string]any{})
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
	code := Run([]string{"--url", server.URL + "/mcp", "search", "纳指", "--rank", "liquidity"}, &stdout, &stderr)
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
		var req map[string]any
		_ = json.NewDecoder(r.Body).Decode(&req)
		switch req["method"] {
		case "initialize", "notifications/initialized":
			writeRPCResult(w, req["id"], map[string]any{})
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
		var req map[string]any
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Fatal(err)
		}
		switch req["method"] {
		case "initialize", "notifications/initialized":
			writeRPCResult(w, req["id"], map[string]any{})
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
		var req map[string]any
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Fatal(err)
		}
		switch req["method"] {
		case "initialize", "notifications/initialized":
			writeRPCResult(w, req["id"], map[string]any{})
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
		var req map[string]any
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Fatal(err)
		}
		switch req["method"] {
		case "initialize", "notifications/initialized":
			writeRPCResult(w, req["id"], map[string]any{})
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
		var req map[string]any
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Fatal(err)
		}
		switch req["method"] {
		case "initialize", "notifications/initialized":
			writeRPCResult(w, req["id"], map[string]any{})
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

func writeRPCResult(w http.ResponseWriter, id any, result any) {
	_ = json.NewEncoder(w).Encode(map[string]any{"jsonrpc": "2.0", "id": id, "result": result})
}

func toolResult(payload map[string]any) map[string]any {
	raw, _ := json.Marshal(payload)
	return map[string]any{
		"content": []any{map[string]any{"type": "text", "text": string(raw)}},
	}
}
