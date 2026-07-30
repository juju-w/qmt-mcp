package qmtctl

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const (
	maxTaskInputItems      = 16
	maxTaskInputKeyBytes   = 128
	maxTaskInputBatchBytes = 65_536
)

type TaskGetParams struct {
	mcp.ParamsBase
	TaskID string `json:"taskId"`
}

type TaskUpdateParams struct {
	mcp.ParamsBase
	TaskID         string         `json:"taskId"`
	InputResponses map[string]any `json:"inputResponses"`
}

type TaskRPCError struct {
	Code    int             `json:"code"`
	Message string          `json:"message"`
	Data    json.RawMessage `json:"data,omitempty"`
}

type TaskInputRequiredError struct {
	TaskID        string
	InputRequests json.RawMessage
}

func (e *TaskInputRequiredError) Error() string {
	return fmt.Sprintf(
		"task %s requires input; review data and run qmtctl task update --responses-json",
		e.TaskID,
	)
}

func (e *TaskRPCError) Error() string {
	return fmt.Sprintf("MCP %d: %s", e.Code, e.Message)
}

func parseTaskInputResponses(raw string) (map[string]any, error) {
	if len([]byte(raw)) > maxTaskInputBatchBytes {
		return nil, fmt.Errorf("--responses-json exceeds %d bytes", maxTaskInputBatchBytes)
	}
	var responses map[string]any
	if err := json.Unmarshal([]byte(raw), &responses); err != nil {
		return nil, fmt.Errorf("invalid --responses-json: %w", err)
	}
	if responses == nil {
		return nil, fmt.Errorf("--responses-json must be a JSON object")
	}
	if len(responses) > maxTaskInputItems {
		return nil, fmt.Errorf("--responses-json exceeds %d entries", maxTaskInputItems)
	}
	for key := range responses {
		if key == "" || len([]byte(key)) > maxTaskInputKeyBytes {
			return nil, fmt.Errorf("--responses-json contains an invalid request ID")
		}
	}
	return responses, nil
}

type TaskInfo struct {
	mcp.ResultBase
	ResultType     string          `json:"resultType"`
	TaskID         string          `json:"taskId"`
	Status         string          `json:"status"`
	StatusMessage  string          `json:"statusMessage,omitempty"`
	CreatedAt      string          `json:"createdAt"`
	LastUpdatedAt  string          `json:"lastUpdatedAt"`
	TTLMS          *int64          `json:"ttlMs"`
	PollIntervalMS int64           `json:"pollIntervalMs,omitempty"`
	Result         json.RawMessage `json:"result,omitempty"`
	Error          *TaskRPCError   `json:"error,omitempty"`
	InputRequests  json.RawMessage `json:"inputRequests,omitempty"`
}

type TaskAck struct {
	mcp.ResultBase
	ResultType string `json:"resultType"`
}

func (c *Client) TaskGet(ctx context.Context, taskID string) (*TaskInfo, error) {
	if err := c.ensureTaskSupport(ctx); err != nil {
		return nil, err
	}
	result, err := mcp.CallCustomMethod[*TaskGetParams, *TaskInfo](
		ctx,
		c.session,
		"tasks/get",
		&TaskGetParams{TaskID: taskID},
	)
	if err != nil {
		return nil, sdkError(err)
	}
	return result, nil
}

func (c *Client) TaskUpdate(
	ctx context.Context,
	taskID string,
	responses map[string]any,
) (*TaskAck, error) {
	if err := c.ensureTaskSupport(ctx); err != nil {
		return nil, err
	}
	result, err := mcp.CallCustomMethod[*TaskUpdateParams, *TaskAck](
		ctx,
		c.session,
		"tasks/update",
		&TaskUpdateParams{TaskID: taskID, InputResponses: responses},
	)
	if err != nil {
		return nil, sdkError(err)
	}
	return result, nil
}

func (c *Client) TaskCancel(ctx context.Context, taskID string) (*TaskAck, error) {
	if err := c.ensureTaskSupport(ctx); err != nil {
		return nil, err
	}
	result, err := mcp.CallCustomMethod[*TaskGetParams, *TaskAck](
		ctx,
		c.session,
		"tasks/cancel",
		&TaskGetParams{TaskID: taskID},
	)
	if err != nil {
		return nil, sdkError(err)
	}
	return result, nil
}

func (c *Client) TaskWait(ctx context.Context, taskID string) (*TaskInfo, error) {
	for {
		task, err := c.TaskGet(ctx, taskID)
		if err != nil {
			return nil, err
		}
		switch task.Status {
		case "completed", "failed", "cancelled", "input_required":
			return task, nil
		case "working":
		default:
			return nil, &AppError{
				Kind:    "protocol",
				Message: fmt.Sprintf("task %s returned invalid status %q", taskID, task.Status),
			}
		}
		delay := time.Duration(task.PollIntervalMS) * time.Millisecond
		if delay < 100*time.Millisecond {
			delay = 100 * time.Millisecond
		}
		if delay > time.Minute {
			delay = time.Minute
		}
		timer := time.NewTimer(delay)
		select {
		case <-ctx.Done():
			timer.Stop()
			return nil, ctx.Err()
		case <-timer.C:
		}
	}
}

func (c *Client) ensureTaskSupport(ctx context.Context) error {
	if c.taskMode == taskModeSync {
		return &AppError{Kind: "config", Message: "task commands require --task-mode wait or detach"}
	}
	if err := c.ensureInitialized(ctx); err != nil {
		return err
	}
	result := c.session.InitializeResult()
	if result == nil || result.Capabilities == nil {
		return &AppError{Kind: "mcp", Message: "server did not advertise MCP Tasks"}
	}
	if _, ok := result.Capabilities.Extensions[tasksExtensionID]; !ok {
		return &AppError{Kind: "mcp", Message: "server does not support MCP Tasks"}
	}
	return nil
}
