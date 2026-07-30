package qmtctl

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"golang.org/x/oauth2"
)

const notificationTestTaskID = "tsk_abcdefghijklmnopqrstuvwxyz0123456789ABCD"

func taskNotification(taskID, status, updatedAt, subscriptionID string) map[string]any {
	task := taskWire(taskID, status)
	delete(task, "resultType")
	task["lastUpdatedAt"] = updatedAt
	task["_meta"] = map[string]any{subscriptionIDMetaKey: subscriptionID}
	switch status {
	case "completed":
		task["result"] = map[string]any{
			"resultType":        "complete",
			"content":           []map[string]any{{"type": "text", "text": `{"ok":true,"source":"push"}`}},
			"structuredContent": map[string]any{"ok": true, "source": "push"},
			"isError":           false,
		}
	case "failed":
		task["error"] = map[string]any{"code": -32603, "message": "failed"}
	case "input_required":
		task["inputRequests"] = map[string]any{
			"confirmation": map[string]any{
				"method": "elicitation/create",
				"params": map[string]any{"mode": "form", "message": "Confirm"},
			},
		}
	}
	return task
}

func subscriptionAck(subscriptionID string, taskIDs ...string) map[string]any {
	notifications := map[string]any{}
	if len(taskIDs) > 0 {
		notifications["taskIds"] = taskIDs
	}
	return map[string]any{
		"jsonrpc": "2.0",
		"method":  "notifications/subscriptions/acknowledged",
		"params": map[string]any{
			"notifications": notifications,
			"_meta":         map[string]any{subscriptionIDMetaKey: subscriptionID},
		},
	}
}

func taskNotificationEnvelope(params map[string]any) map[string]any {
	return map[string]any{
		"jsonrpc": "2.0",
		"method":  "notifications/tasks",
		"params":  params,
	}
}

func writeSSEFrames(t *testing.T, w http.ResponseWriter, frames ...map[string]any) {
	t.Helper()
	w.Header().Set("content-type", "text/event-stream")
	w.WriteHeader(http.StatusOK)
	flusher, ok := w.(http.Flusher)
	if !ok {
		t.Fatal("test response does not support flushing")
	}
	for _, frame := range frames {
		raw, err := json.Marshal(frame)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := fmt.Fprintf(w, "data: %s\n\n", raw); err != nil {
			return
		}
		flusher.Flush()
	}
}

func verifyListenRequest(t *testing.T, r *http.Request, request map[string]any) string {
	t.Helper()
	if r.Header.Get("Mcp-Protocol-Version") != stableTaskNotificationProtocol ||
		r.Header.Get("Mcp-Method") != "subscriptions/listen" {
		t.Fatalf(
			"listen headers = protocol %q method %q",
			r.Header.Get("Mcp-Protocol-Version"),
			r.Header.Get("Mcp-Method"),
		)
	}
	params := request["params"].(map[string]any)
	notifications := params["notifications"].(map[string]any)
	taskIDs := notifications["taskIds"].([]any)
	if len(taskIDs) != 1 || taskIDs[0] != notificationTestTaskID {
		t.Fatalf("listen taskIds = %#v", taskIDs)
	}
	meta := params["_meta"].(map[string]any)
	if meta[protocolVersionMetaKey] != stableTaskNotificationProtocol {
		t.Fatalf("listen protocol metadata = %#v", meta)
	}
	caps := meta[clientCapabilitiesMetaKey].(map[string]any)
	extensions := caps["extensions"].(map[string]any)
	if _, ok := extensions[tasksExtensionID]; !ok {
		t.Fatal("listen metadata did not declare Tasks")
	}
	return request["id"].(string)
}

func TestClientWaitPrefersTaskNotificationsWithoutPolling(t *testing.T) {
	polls := 0
	listens := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		switch request["method"] {
		case "server/discover":
			writeRPCResult(w, request["id"], modernTaskDiscover())
		case "tools/call":
			writeRPCResult(w, request["id"], createdTaskWire(notificationTestTaskID))
		case "subscriptions/listen":
			listens++
			subscriptionID := verifyListenRequest(t, r, request)
			writeSSEFrames(
				t,
				w,
				subscriptionAck(subscriptionID, notificationTestTaskID),
				taskNotificationEnvelope(
					taskNotification(
						notificationTestTaskID,
						"working",
						"2026-07-31T00:00:00.000Z",
						subscriptionID,
					),
				),
				taskNotificationEnvelope(
					taskNotification(
						notificationTestTaskID,
						"completed",
						"2026-07-31T00:00:01.000Z",
						subscriptionID,
					),
				),
			)
		case "tasks/get":
			polls++
			t.Fatal("notification-backed wait must not poll")
		default:
			t.Fatalf("unexpected method %v", request["method"])
		}
	}))
	defer server.Close()

	client := NewClient(server.URL, "static-token", 2*time.Second, false)
	defer client.Close()
	payload, err := client.CallTool(context.Background(), "qmt_long", map[string]any{})
	if err != nil {
		t.Fatal(err)
	}
	if string(payload) != `{"ok":true,"source":"push"}` {
		t.Fatalf("payload = %s", payload)
	}
	if listens != 1 || polls != 0 {
		t.Fatalf("listens=%d polls=%d", listens, polls)
	}
}

func TestExplicitTaskWaitUsesNotifications(t *testing.T) {
	gets := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		switch request["method"] {
		case "server/discover":
			writeRPCResult(w, request["id"], modernTaskDiscover())
		case "tasks/get":
			gets++
			writeRPCResult(w, request["id"], taskWire(notificationTestTaskID, "working"))
		case "subscriptions/listen":
			subscriptionID := verifyListenRequest(t, r, request)
			writeSSEFrames(
				t,
				w,
				subscriptionAck(subscriptionID, notificationTestTaskID),
				taskNotificationEnvelope(
					taskNotification(
						notificationTestTaskID,
						"completed",
						"2026-07-31T00:00:01.000Z",
						subscriptionID,
					),
				),
			)
		default:
			t.Fatalf("unexpected method %v", request["method"])
		}
	}))
	defer server.Close()

	client := NewClient(server.URL, "", 2*time.Second, false)
	defer client.Close()
	task, err := client.TaskWait(context.Background(), notificationTestTaskID)
	if err != nil {
		t.Fatal(err)
	}
	if task.Status != "completed" || gets != 1 {
		t.Fatalf("task=%#v gets=%d", task, gets)
	}
}

func TestTaskNotificationFallbacksToPolling(t *testing.T) {
	for _, mode := range []string{"unsupported", "unacknowledged", "malformed", "closed"} {
		t.Run(mode, func(t *testing.T) {
			polls := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				var request map[string]any
				if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
					t.Fatal(err)
				}
				switch request["method"] {
				case "server/discover":
					writeRPCResult(w, request["id"], modernTaskDiscover())
				case "tools/call":
					writeRPCResult(w, request["id"], createdTaskWire(notificationTestTaskID))
				case "subscriptions/listen":
					subscriptionID := verifyListenRequest(t, r, request)
					switch mode {
					case "unsupported":
						writeRPCError(w, request["id"], -32601, "Method not found")
					case "unacknowledged":
						writeSSEFrames(t, w, subscriptionAck(subscriptionID))
					case "malformed":
						w.Header().Set("content-type", "text/event-stream")
						_, _ = fmt.Fprint(w, "data: not-json\n\n")
					case "closed":
						writeSSEFrames(
							t,
							w,
							subscriptionAck(subscriptionID, notificationTestTaskID),
							taskNotificationEnvelope(
								taskNotification(
									notificationTestTaskID,
									"working",
									"2026-07-31T00:00:00.000Z",
									subscriptionID,
								),
							),
						)
					}
				case "tasks/get":
					polls++
					result := taskWire(notificationTestTaskID, "completed")
					result["result"] = map[string]any{
						"content": []map[string]any{{"type": "text", "text": `{"ok":true,"source":"poll"}`}},
					}
					writeRPCResult(w, request["id"], result)
				default:
					t.Fatalf("unexpected method %v", request["method"])
				}
			}))
			defer server.Close()

			client := NewClient(server.URL, "", 2*time.Second, false)
			defer client.Close()
			payload, err := client.CallTool(context.Background(), "qmt_long", map[string]any{})
			if err != nil {
				t.Fatal(err)
			}
			if string(payload) != `{"ok":true,"source":"poll"}` || polls != 1 {
				t.Fatalf("mode=%s payload=%s polls=%d", mode, payload, polls)
			}
		})
	}
}

func TestTaskNotificationsIgnoreForeignAndOlderSnapshots(t *testing.T) {
	polls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		switch request["method"] {
		case "server/discover":
			writeRPCResult(w, request["id"], modernTaskDiscover())
		case "tools/call":
			created := createdTaskWire(notificationTestTaskID)
			created["lastUpdatedAt"] = "2026-07-31T00:00:02.000Z"
			writeRPCResult(w, request["id"], created)
		case "subscriptions/listen":
			subscriptionID := verifyListenRequest(t, r, request)
			writeSSEFrames(
				t,
				w,
				subscriptionAck(subscriptionID, notificationTestTaskID),
				taskNotificationEnvelope(
					taskNotification(
						"tsk_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd",
						"completed",
						"2026-07-31T00:00:04.000Z",
						subscriptionID,
					),
				),
				taskNotificationEnvelope(
					taskNotification(
						notificationTestTaskID,
						"working",
						"2026-07-31T00:00:01.000Z",
						subscriptionID,
					),
				),
				taskNotificationEnvelope(
					taskNotification(
						notificationTestTaskID,
						"completed",
						"2026-07-31T00:00:03.000Z",
						subscriptionID,
					),
				),
			)
		case "tasks/get":
			polls++
			t.Fatal("valid terminal notification must not poll")
		default:
			t.Fatalf("unexpected method %v", request["method"])
		}
	}))
	defer server.Close()

	client := NewClient(server.URL, "", 2*time.Second, false)
	defer client.Close()
	payload, err := client.CallTool(context.Background(), "qmt_long", map[string]any{})
	if err != nil {
		t.Fatal(err)
	}
	if string(payload) != `{"ok":true,"source":"push"}` || polls != 0 {
		t.Fatalf("payload=%s polls=%d", payload, polls)
	}
}

type rotatingOAuthHandler struct {
	calls atomic.Int64
}

func (h *rotatingOAuthHandler) TokenSource(context.Context) (oauth2.TokenSource, error) {
	number := h.calls.Add(1)
	token := &oauth2.Token{
		AccessToken: "fresh-token-" + strconv.FormatInt(number, 10),
		TokenType:   "Bearer",
		Expiry:      time.Now().Add(time.Minute),
	}
	return oauth2.StaticTokenSource(token), nil
}

func (*rotatingOAuthHandler) Authorize(context.Context, *http.Request, *http.Response) error {
	return nil
}

func TestTaskNotificationRefreshesOAuthBeforeListening(t *testing.T) {
	var listenAuthorization string
	handler := &rotatingOAuthHandler{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		switch request["method"] {
		case "server/discover":
			writeRPCResult(w, request["id"], modernTaskDiscover())
		case "tools/call":
			writeRPCResult(w, request["id"], createdTaskWire(notificationTestTaskID))
		case "subscriptions/listen":
			listenAuthorization = r.Header.Get("Authorization")
			subscriptionID := verifyListenRequest(t, r, request)
			writeSSEFrames(
				t,
				w,
				subscriptionAck(subscriptionID, notificationTestTaskID),
				taskNotificationEnvelope(
					taskNotification(
						notificationTestTaskID,
						"completed",
						"2026-07-31T00:00:01.000Z",
						subscriptionID,
					),
				),
			)
		default:
			t.Fatalf("unexpected method %v", request["method"])
		}
	}))
	defer server.Close()

	client := NewClient(server.URL, "", 2*time.Second, false)
	client.SetOAuthHandler(handler, nil)
	defer client.Close()
	if _, err := client.CallTool(context.Background(), "qmt_long", map[string]any{}); err != nil {
		t.Fatal(err)
	}
	if handler.calls.Load() < 2 || !strings.HasPrefix(listenAuthorization, "Bearer fresh-token-") {
		t.Fatalf("oauth calls=%d listen authorization=%q", handler.calls.Load(), listenAuthorization)
	}
}

func TestTaskNotificationHonorsOverallCancellation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		switch request["method"] {
		case "server/discover":
			writeRPCResult(w, request["id"], modernTaskDiscover())
		case "tools/call":
			writeRPCResult(w, request["id"], createdTaskWire(notificationTestTaskID))
		case "subscriptions/listen":
			subscriptionID := verifyListenRequest(t, r, request)
			writeSSEFrames(t, w, subscriptionAck(subscriptionID, notificationTestTaskID))
			<-r.Context().Done()
		case "notifications/cancelled":
			w.WriteHeader(http.StatusAccepted)
		default:
			t.Fatalf("unexpected method %v", request["method"])
		}
	}))
	defer server.Close()

	client := NewClient(server.URL, "", 2*time.Second, false)
	defer client.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 150*time.Millisecond)
	defer cancel()
	_, err := client.CallTool(ctx, "qmt_long", map[string]any{})
	if err == nil || !strings.Contains(err.Error(), "deadline exceeded") {
		t.Fatalf("CallTool error = %v", err)
	}
}
