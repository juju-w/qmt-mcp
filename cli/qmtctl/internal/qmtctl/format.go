package qmtctl

import (
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strings"
)

func writeJSON(w io.Writer, v any) error {
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", "  ")
	return enc.Encode(v)
}

func writeRawJSON(w io.Writer, raw json.RawMessage) error {
	var value any
	if err := json.Unmarshal(raw, &value); err != nil {
		_, err = fmt.Fprintln(w, string(raw))
		return err
	}
	return writeJSON(w, value)
}

func printMapSummary(w io.Writer, doc map[string]any) {
	keys := make([]string, 0, len(doc))
	for key := range doc {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		switch v := doc[key].(type) {
		case string:
			fmt.Fprintf(w, "%s: %s\n", key, v)
		case bool, float64:
			fmt.Fprintf(w, "%s: %v\n", key, v)
		}
	}
}

func printToolPayload(w io.Writer, raw json.RawMessage) error {
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		return writeRawJSON(w, raw)
	}
	if ok, okSet := doc["ok"].(bool); okSet {
		fmt.Fprintf(w, "ok: %v\n", ok)
	}
	for _, key := range []string{"query", "code", "account_id", "period", "source", "state", "record_count", "sector_count", "updated_at", "resolved", "cancelable_only"} {
		if value, found := doc[key]; found {
			fmt.Fprintf(w, "%s: %v\n", key, value)
		}
	}
	for _, key := range []string{"asset", "positions", "orders", "trades", "statistics", "status", "limits", "ipo", "best", "results", "rows", "data", "tools", "families"} {
		if value, found := doc[key]; found {
			renderBriefValue(w, key, value)
		}
	}
	return nil
}

func renderBriefValue(w io.Writer, key string, value any) {
	switch v := value.(type) {
	case []any:
		fmt.Fprintf(w, "%s: %d item(s)\n", key, len(v))
		for i, item := range v {
			if i >= 5 {
				fmt.Fprintf(w, "  ... %d more\n", len(v)-i)
				break
			}
			fmt.Fprintf(w, "  - %s\n", compact(item))
		}
	case map[string]any:
		fmt.Fprintf(w, "%s: %s\n", key, compact(v))
	default:
		fmt.Fprintf(w, "%s: %v\n", key, value)
	}
}

func compact(value any) string {
	raw, err := json.Marshal(value)
	if err != nil {
		return fmt.Sprint(value)
	}
	text := string(raw)
	if len([]rune(text)) > 180 {
		r := []rune(text)
		return string(r[:180]) + "..."
	}
	return strings.ReplaceAll(text, "\n", " ")
}
