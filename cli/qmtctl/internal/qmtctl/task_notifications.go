package qmtctl

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

const (
	maxTaskNotificationFrame  = 16 * 1024 * 1024
	subscriptionIDMetaKey     = "io.modelcontextprotocol/subscriptionId"
	protocolVersionMetaKey    = "io.modelcontextprotocol/protocolVersion"
	clientInfoMetaKey         = "io.modelcontextprotocol/clientInfo"
	clientCapabilitiesMetaKey = "io.modelcontextprotocol/clientCapabilities"
)

type taskSubscriptionEnvelope struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Method  string          `json:"method,omitempty"`
	Params  json.RawMessage `json:"params,omitempty"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *TaskRPCError   `json:"error,omitempty"`
}

type taskSubscriptionAcknowledgement struct {
	Notifications struct {
		TaskIDs []string `json:"taskIds,omitempty"`
	} `json:"notifications"`
	Meta map[string]any `json:"_meta"`
}

func (c *Client) supportsTaskNotifications() bool {
	if c.session == nil {
		return false
	}
	result := c.session.InitializeResult()
	if result == nil || result.ProtocolVersion != modernProtocolVersion ||
		result.Capabilities == nil {
		return false
	}
	_, ok := result.Capabilities.Extensions[tasksExtensionID]
	return ok
}

func (c *Client) listenTask(
	ctx context.Context,
	originalMeta json.RawMessage,
	initial TaskInfo,
) (TaskInfo, bool, error) {
	if !c.supportsTaskNotifications() || c.notificationHTTPClient == nil {
		return initial, false, nil
	}

	subscriptionID := fmt.Sprintf("qmtctl-task-listen-%d", c.notificationIDs.Add(1))
	meta := taskSubscriptionMeta(originalMeta)
	body, err := json.Marshal(map[string]any{
		"jsonrpc": "2.0",
		"id":      subscriptionID,
		"method":  "subscriptions/listen",
		"params": map[string]any{
			"notifications": map[string]any{"taskIds": []string{initial.TaskID}},
			"_meta":         meta,
		},
	})
	if err != nil {
		return initial, false, nil
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL, bytes.NewReader(body))
	if err != nil {
		return initial, false, nil
	}
	request.Header.Set("Accept", "application/json, text/event-stream")
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Mcp-Protocol-Version", modernProtocolVersion)
	request.Header.Set("Mcp-Method", "subscriptions/listen")
	if err := c.addHeaders(ctx, request); err != nil {
		if ctx.Err() != nil {
			return initial, false, ctx.Err()
		}
		return initial, false, nil
	}

	response, err := c.notificationHTTPClient.Do(request)
	if err != nil {
		if ctx.Err() != nil {
			return initial, false, ctx.Err()
		}
		return initial, false, nil
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 ||
		!strings.Contains(response.Header.Get("Content-Type"), "text/event-stream") {
		return initial, false, nil
	}

	scanner := bufio.NewScanner(response.Body)
	scanner.Buffer(make([]byte, 64*1024), maxTaskNotificationFrame)
	current := initial
	acknowledged := false
	for {
		data, eventErr := nextSSEData(scanner)
		if eventErr != nil {
			if ctx.Err() != nil {
				return current, false, ctx.Err()
			}
			return current, false, nil
		}
		var envelope taskSubscriptionEnvelope
		if json.Unmarshal(data, &envelope) != nil || envelope.JSONRPC != "2.0" {
			return current, false, nil
		}

		if !acknowledged {
			if envelope.Method != "notifications/subscriptions/acknowledged" {
				return current, false, nil
			}
			var acknowledgement taskSubscriptionAcknowledgement
			if json.Unmarshal(envelope.Params, &acknowledgement) != nil ||
				!subscriptionMetaMatches(acknowledgement.Meta, subscriptionID) ||
				len(acknowledgement.Notifications.TaskIDs) != 1 ||
				acknowledgement.Notifications.TaskIDs[0] != initial.TaskID {
				return current, false, nil
			}
			acknowledged = true
			continue
		}

		if envelope.Method == "" {
			return current, false, nil
		}
		if envelope.Method != "notifications/tasks" {
			continue
		}
		var identity struct {
			TaskID string `json:"taskId"`
		}
		if json.Unmarshal(envelope.Params, &identity) != nil || identity.TaskID == "" {
			return current, false, nil
		}
		if identity.TaskID != initial.TaskID {
			continue
		}
		snapshot, snapshotMeta, valid := decodeTaskNotification(envelope.Params, initial.TaskID)
		if !valid || !subscriptionMetaMatches(snapshotMeta, subscriptionID) {
			return current, false, nil
		}
		if snapshot.CreatedAt != current.CreatedAt {
			return current, false, nil
		}
		if taskSnapshotOlder(snapshot, current) {
			continue
		}
		current = snapshot
		if taskStatusSettled(current.Status) {
			return current, true, nil
		}
	}
}

func taskSubscriptionMeta(original json.RawMessage) map[string]any {
	meta := make(map[string]any)
	if len(original) > 0 && string(original) != "null" {
		_ = json.Unmarshal(original, &meta)
	}
	meta[protocolVersionMetaKey] = modernProtocolVersion
	meta[clientInfoMetaKey] = map[string]any{"name": "qmtctl", "version": Version}
	meta[clientCapabilitiesMetaKey] = map[string]any{
		"extensions": map[string]any{tasksExtensionID: map[string]any{}},
	}
	return meta
}

func nextSSEData(scanner *bufio.Scanner) ([]byte, error) {
	var data []byte
	for scanner.Scan() {
		line := bytes.TrimSuffix(scanner.Bytes(), []byte("\r"))
		if len(line) == 0 {
			if len(data) > 0 {
				return data, nil
			}
			continue
		}
		if line[0] == ':' || !bytes.HasPrefix(line, []byte("data:")) {
			continue
		}
		value := line[len("data:"):]
		if len(value) > 0 && value[0] == ' ' {
			value = value[1:]
		}
		if len(data)+len(value)+1 > maxTaskNotificationFrame {
			return nil, fmt.Errorf("task notification SSE event exceeds %d bytes", maxTaskNotificationFrame)
		}
		if len(data) > 0 {
			data = append(data, '\n')
		}
		data = append(data, value...)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	if len(data) > 0 {
		return data, nil
	}
	return nil, io.EOF
}

func subscriptionMetaMatches(meta map[string]any, subscriptionID string) bool {
	value, ok := meta[subscriptionIDMetaKey].(string)
	return ok && value == subscriptionID
}

func decodeTaskNotification(raw json.RawMessage, taskID string) (TaskInfo, map[string]any, bool) {
	var fields map[string]json.RawMessage
	if json.Unmarshal(raw, &fields) != nil {
		return TaskInfo{}, nil, false
	}
	for _, name := range []string{
		"taskId",
		"status",
		"createdAt",
		"lastUpdatedAt",
		"ttlMs",
		"pollIntervalMs",
		"_meta",
	} {
		if _, ok := fields[name]; !ok {
			return TaskInfo{}, nil, false
		}
	}
	if _, forbidden := fields["resultType"]; forbidden {
		return TaskInfo{}, nil, false
	}

	var snapshot TaskInfo
	var meta map[string]any
	if json.Unmarshal(raw, &snapshot) != nil ||
		json.Unmarshal(fields["_meta"], &meta) != nil ||
		snapshot.TaskID != taskID ||
		snapshot.PollIntervalMS <= 0 {
		return TaskInfo{}, nil, false
	}
	created, createdErr := time.Parse(time.RFC3339Nano, snapshot.CreatedAt)
	updated, updatedErr := time.Parse(time.RFC3339Nano, snapshot.LastUpdatedAt)
	if createdErr != nil || updatedErr != nil || updated.Before(created) {
		return TaskInfo{}, nil, false
	}

	switch snapshot.Status {
	case "working", "cancelled":
	case "completed":
		if len(snapshot.Result) == 0 || string(snapshot.Result) == "null" {
			return TaskInfo{}, nil, false
		}
	case "failed":
		if snapshot.Error == nil {
			return TaskInfo{}, nil, false
		}
	case "input_required":
		var requests map[string]any
		if len(snapshot.InputRequests) == 0 ||
			json.Unmarshal(snapshot.InputRequests, &requests) != nil ||
			len(requests) == 0 {
			return TaskInfo{}, nil, false
		}
	default:
		return TaskInfo{}, nil, false
	}
	return snapshot, meta, true
}

func taskSnapshotOlder(candidate, current TaskInfo) bool {
	candidateTime, candidateErr := time.Parse(time.RFC3339Nano, candidate.LastUpdatedAt)
	currentTime, currentErr := time.Parse(time.RFC3339Nano, current.LastUpdatedAt)
	return candidateErr == nil && currentErr == nil && candidateTime.Before(currentTime)
}
