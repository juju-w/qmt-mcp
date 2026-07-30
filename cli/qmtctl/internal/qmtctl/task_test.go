package qmtctl

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func modernTaskDiscover() map[string]any {
	return map[string]any{
		"resultType":        "complete",
		"supportedVersions": []string{"2026-07-28"},
		"capabilities": map[string]any{
			"tools": map[string]any{},
			"extensions": map[string]any{
				tasksExtensionID: map[string]any{},
			},
		},
		"serverInfo": map[string]any{"name": "tasks-test", "version": "1.0.0"},
		"ttlMs":      0,
		"cacheScope": "private",
	}
}

func taskWire(taskID, status string) map[string]any {
	return map[string]any{
		"resultType":     "complete",
		"taskId":         taskID,
		"status":         status,
		"createdAt":      "2026-07-31T00:00:00.000Z",
		"lastUpdatedAt":  "2026-07-31T00:00:00.000Z",
		"ttlMs":          60_000,
		"pollIntervalMs": 100,
	}
}

func createdTaskWire(taskID string) map[string]any {
	task := taskWire(taskID, "working")
	task["resultType"] = "task"
	return task
}

func TestClientWaitModeResolvesTaskToOriginalToolPayload(t *testing.T) {
	const taskID = "tsk_abcdefghijklmnopqrstuvwxyz0123456789ABCD"
	polls := 0
	startedAt := time.Now()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodDelete {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		switch request["method"] {
		case "server/discover":
			writeRPCResult(w, request["id"], modernTaskDiscover())
		case "tools/call":
			params := request["params"].(map[string]any)
			meta := params["_meta"].(map[string]any)
			caps := meta["io.modelcontextprotocol/clientCapabilities"].(map[string]any)
			extensions := caps["extensions"].(map[string]any)
			if _, ok := extensions[tasksExtensionID]; !ok {
				t.Fatal("qmtctl did not declare Tasks")
			}
			writeRPCResult(w, request["id"], createdTaskWire(taskID))
		case "tasks/get":
			polls++
			if firstPollDelay := time.Since(startedAt); polls == 1 && firstPollDelay < 90*time.Millisecond {
				t.Fatalf("first poll arrived before server guidance: %s", firstPollDelay)
			}
			if r.Header.Get("Mcp-Method") != "tasks/get" || r.Header.Get("Mcp-Name") != taskID {
				t.Fatalf("task routing headers = %q %q", r.Header.Get("Mcp-Method"), r.Header.Get("Mcp-Name"))
			}
			result := taskWire(taskID, "working")
			if polls >= 2 {
				result["status"] = "completed"
				result["result"] = map[string]any{
					"resultType":        "complete",
					"content":           []map[string]any{{"type": "text", "text": `{"ok":true,"value":42}`}},
					"structuredContent": map[string]any{"ok": true, "value": 42},
					"isError":           false,
				}
			}
			writeRPCResult(w, request["id"], result)
		default:
			t.Fatalf("unexpected method %v", request["method"])
		}
	}))
	defer server.Close()

	client := NewClient(server.URL, "", 2*time.Second, false)
	defer client.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	payload, err := client.CallTool(ctx, "qmt_long", map[string]any{})
	if err != nil {
		t.Fatal(err)
	}
	if string(payload) != `{"ok":true,"value":42}` {
		t.Fatalf("payload = %s", payload)
	}
	if polls != 2 {
		t.Fatalf("polls = %d, want 2", polls)
	}
}

func TestClientDetachAndSyncModes(t *testing.T) {
	const taskID = "tsk_abcdefghijklmnopqrstuvwxyz0123456789ABCD"
	taskGets := 0
	var sawSyncWithoutTasks bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodDelete {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		switch request["method"] {
		case "server/discover":
			writeRPCResult(w, request["id"], modernTaskDiscover())
		case "tools/call":
			params := request["params"].(map[string]any)
			meta := params["_meta"].(map[string]any)
			caps := meta["io.modelcontextprotocol/clientCapabilities"].(map[string]any)
			_, hasTasks := caps["extensions"]
			if hasTasks {
				writeRPCResult(w, request["id"], createdTaskWire(taskID))
				return
			}
			sawSyncWithoutTasks = true
			result := toolResult(map[string]any{"ok": true, "mode": "sync"})
			result["resultType"] = "complete"
			writeRPCResult(w, request["id"], result)
		case "tasks/get":
			taskGets++
			t.Fatal("detach mode must not poll")
		default:
			t.Fatalf("unexpected method %v", request["method"])
		}
	}))
	defer server.Close()

	detached := NewClient(server.URL, "", 2*time.Second, false)
	if err := detached.SetTaskMode(taskModeDetach); err != nil {
		t.Fatal(err)
	}
	payload, err := detached.CallTool(context.Background(), "qmt_long", map[string]any{})
	detached.Close()
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(payload), taskID) || !strings.Contains(string(payload), `"ok":true`) {
		t.Fatalf("detach payload = %s", payload)
	}
	if taskGets != 0 {
		t.Fatalf("detach task gets = %d", taskGets)
	}

	synchronous := NewClient(server.URL, "", 2*time.Second, false)
	if err := synchronous.SetTaskMode(taskModeSync); err != nil {
		t.Fatal(err)
	}
	payload, err = synchronous.CallTool(context.Background(), "qmt_long", map[string]any{})
	synchronous.Close()
	if err != nil {
		t.Fatal(err)
	}
	if !sawSyncWithoutTasks || !strings.Contains(string(payload), `"mode":"sync"`) {
		t.Fatalf("sync payload = %s, sawSync=%v", payload, sawSyncWithoutTasks)
	}
}

func TestClientExplicitTaskMethodsUseCustomSDKDispatch(t *testing.T) {
	const taskID = "tsk_abcdefghijklmnopqrstuvwxyz0123456789ABCD"
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodDelete {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		switch request["method"] {
		case "server/discover":
			writeRPCResult(w, request["id"], modernTaskDiscover())
		case "tasks/get":
			if r.Header.Get("Mcp-Method") != "tasks/get" || r.Header.Get("Mcp-Name") != taskID {
				t.Fatalf("task headers = %q %q", r.Header.Get("Mcp-Method"), r.Header.Get("Mcp-Name"))
			}
			result := taskWire(taskID, "completed")
			result["result"] = map[string]any{"content": []map[string]any{{"type": "text", "text": "done"}}}
			writeRPCResult(w, request["id"], result)
		case "tasks/cancel", "tasks/update":
			method := request["method"].(string)
			if r.Header.Get("Mcp-Method") != method || r.Header.Get("Mcp-Name") != taskID {
				t.Fatalf("task headers = %q %q", r.Header.Get("Mcp-Method"), r.Header.Get("Mcp-Name"))
			}
			writeRPCResult(w, request["id"], map[string]any{"resultType": "complete"})
		default:
			t.Fatalf("unexpected method %v", request["method"])
		}
	}))
	defer server.Close()

	client := NewClient(server.URL, "", 2*time.Second, false)
	defer client.Close()
	task, err := client.TaskGet(context.Background(), taskID)
	if err != nil || task.Status != "completed" {
		t.Fatalf("TaskGet = %#v, %v", task, err)
	}
	if _, err := client.TaskUpdate(context.Background(), taskID, map[string]any{"confirm": true}); err != nil {
		t.Fatal(err)
	}
	if _, err := client.TaskCancel(context.Background(), taskID); err != nil {
		t.Fatal(err)
	}
}

func TestRunTaskGetAndDetachEnvironment(t *testing.T) {
	const taskID = "tsk_abcdefghijklmnopqrstuvwxyz0123456789ABCD"
	taskGets := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodDelete {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		switch request["method"] {
		case "server/discover":
			writeRPCResult(w, request["id"], modernTaskDiscover())
		case "tasks/get":
			taskGets++
			writeRPCResult(w, request["id"], taskWire(taskID, "working"))
		case "tools/call":
			writeRPCResult(w, request["id"], createdTaskWire(taskID))
		default:
			t.Fatalf("unexpected method %v", request["method"])
		}
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	code := Run(
		[]string{"--url", server.URL, "--json", "task", "get", taskID},
		&stdout,
		&stderr,
	)
	if code != 0 || !strings.Contains(stdout.String(), `"status": "working"`) {
		t.Fatalf("task get exit=%d stdout=%s stderr=%s", code, stdout.String(), stderr.String())
	}
	if taskGets != 1 {
		t.Fatalf("task gets = %d", taskGets)
	}

	t.Setenv("QMTCTL_TASK_MODE", taskModeDetach)
	stdout.Reset()
	stderr.Reset()
	code = Run(
		[]string{"--url", server.URL, "--json", "cache", "refresh", "--force"},
		&stdout,
		&stderr,
	)
	if code != 0 || !strings.Contains(stdout.String(), taskID) {
		t.Fatalf("detach exit=%d stdout=%s stderr=%s", code, stdout.String(), stderr.String())
	}
	if taskGets != 1 {
		t.Fatalf("detach unexpectedly polled; task gets = %d", taskGets)
	}
}

func TestRunRejectsInvalidTaskMode(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := Run([]string{"--task-mode", "surprise", "health"}, &stdout, &stderr)
	if code != 2 || !strings.Contains(stderr.String(), "invalid task mode") {
		t.Fatalf("exit=%d stderr=%s", code, stderr.String())
	}
}

func TestRunRejectsNonPositiveTaskTimeout(t *testing.T) {
	for _, args := range [][]string{
		{"--task-timeout", "0s", "health"},
		{"--task-timeout=-1s", "health"},
	} {
		var stdout, stderr bytes.Buffer
		code := Run(args, &stdout, &stderr)
		if code != 2 || !strings.Contains(stderr.String(), "greater than zero") {
			t.Fatalf("args=%v exit=%d stderr=%s", args, code, stderr.String())
		}
	}
}

func TestParseTaskInputResponsesEnforcesBounds(t *testing.T) {
	valid, err := parseTaskInputResponses(
		`{"confirmation":{"action":"accept","content":{"confirm":true}}}`,
	)
	if err != nil || len(valid) != 1 {
		t.Fatalf("valid responses = %#v, %v", valid, err)
	}

	for _, raw := range []string{
		`null`,
		`[]`,
		`{"":{"action":"accept"}}`,
		`{"` + strings.Repeat("x", maxTaskInputKeyBytes+1) + `":{"action":"accept"}}`,
		strings.Repeat(" ", maxTaskInputBatchBytes+1),
	} {
		if _, err := parseTaskInputResponses(raw); err == nil {
			t.Fatalf("parseTaskInputResponses(%d bytes) unexpectedly succeeded", len(raw))
		}
	}

	tooMany := make(map[string]any, maxTaskInputItems+1)
	for i := 0; i <= maxTaskInputItems; i++ {
		tooMany[fmt.Sprintf("request-%d", i)] = map[string]any{"action": "accept"}
	}
	raw, err := json.Marshal(tooMany)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := parseTaskInputResponses(string(raw)); err == nil {
		t.Fatal("oversized response map unexpectedly succeeded")
	}
}

func TestClientWaitModePreservesInputRequiredDetails(t *testing.T) {
	const taskID = "tsk_abcdefghijklmnopqrstuvwxyz0123456789ABCD"
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodDelete {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		switch request["method"] {
		case "server/discover":
			writeRPCResult(w, request["id"], modernTaskDiscover())
		case "tools/call":
			writeRPCResult(w, request["id"], createdTaskWire(taskID))
		case "tasks/get":
			result := taskWire(taskID, "input_required")
			result["inputRequests"] = map[string]any{
				"confirmation": map[string]any{
					"method": "elicitation/create",
					"params": map[string]any{"mode": "form", "message": "Confirm"},
				},
			}
			writeRPCResult(w, request["id"], result)
		default:
			t.Fatalf("unexpected method %v", request["method"])
		}
	}))
	defer server.Close()

	client := NewClient(server.URL, "", 2*time.Second, false)
	defer client.Close()
	_, err := client.CallTool(context.Background(), "qmt_long", map[string]any{})
	var appErr *AppError
	if !errors.As(err, &appErr) {
		t.Fatalf("CallTool error = %T %v", err, err)
	}
	if appErr.Kind != "task_input_required" {
		t.Fatalf("error kind = %q", appErr.Kind)
	}
	detail, marshalErr := json.Marshal(appErr.Data)
	if marshalErr != nil {
		t.Fatal(marshalErr)
	}
	if !bytes.Contains(detail, []byte(taskID)) ||
		!bytes.Contains(detail, []byte("elicitation/create")) {
		t.Fatalf("error data = %s", detail)
	}

	var human bytes.Buffer
	printError(&human, appErr, false)
	if !strings.Contains(human.String(), taskID) ||
		!strings.Contains(human.String(), "elicitation/create") {
		t.Fatalf("human error = %s", human.String())
	}

	var asJSON bytes.Buffer
	printError(&asJSON, appErr, true)
	if !strings.Contains(asJSON.String(), `"error_type": "task_input_required"`) ||
		!strings.Contains(asJSON.String(), `"inputRequests"`) {
		t.Fatalf("JSON error = %s", asJSON.String())
	}
}
