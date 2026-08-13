// Command conformance adapts the production qmtctl client to the official MCP
// client conformance runner. It is test-only and is not included in releases.
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/juju-w/qmt-mcp/cli/qmtctl/internal/qmtctl"
)

func main() {
	if len(os.Args) != 2 {
		log.Fatalf("usage: %s <server-url>", os.Args[0])
	}
	scenario := os.Getenv("MCP_CONFORMANCE_SCENARIO")
	if scenario == "" {
		log.Fatal("MCP_CONFORMANCE_SCENARIO is required")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 25*time.Second)
	defer cancel()
	client := qmtctl.NewClient(os.Args[1], "", 20*time.Second, false)
	defer client.Close()

	var err error
	switch scenario {
	case "request-metadata":
		_, err = client.ListTools(ctx)
	case "tools_call":
		err = callNamedTool(ctx, client, "add_numbers", map[string]any{"a": 5, "b": 3})
	case "http-standard-headers":
		err = callFirstTool(ctx, client)
	default:
		err = fmt.Errorf("unsupported conformance scenario %q", scenario)
	}
	if err != nil {
		log.Fatalf("scenario %q failed: %v", scenario, err)
	}
}

func callNamedTool(ctx context.Context, client *qmtctl.Client, name string, args map[string]any) error {
	tools, err := client.ListTools(ctx)
	if err != nil {
		return err
	}
	for _, item := range toolItems(tools) {
		if item["name"] == name {
			_, err = client.CallTool(ctx, name, args)
			return err
		}
	}
	return fmt.Errorf("tool %q was not listed", name)
}

func callFirstTool(ctx context.Context, client *qmtctl.Client) error {
	tools, err := client.ListTools(ctx)
	if err != nil {
		return err
	}
	items := toolItems(tools)
	if len(items) == 0 {
		return nil
	}
	name, _ := items[0]["name"].(string)
	if name == "" {
		return fmt.Errorf("first listed tool has no name")
	}
	_, err = client.CallTool(ctx, name, map[string]any{})
	return err
}

func toolItems(result map[string]any) []map[string]any {
	raw, _ := result["tools"].([]any)
	items := make([]map[string]any, 0, len(raw))
	for _, item := range raw {
		if tool, ok := item.(map[string]any); ok {
			items = append(items, tool)
		}
	}
	return items
}
