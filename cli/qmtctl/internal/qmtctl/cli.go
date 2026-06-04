package qmtctl

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"strconv"
	"strings"
	"time"
)

const defaultURL = "http://127.0.0.1:8765/mcp"

type globalOptions struct {
	url     string
	token   string
	jsonOut bool
	timeout time.Duration
	verbose bool
}

func Run(args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		usage(stderr)
		return 2
	}
	opts := globalOptions{
		url:     getenvDefault("QMT_MCP_URL", defaultURL),
		token:   os.Getenv("QMT_MCP_TOKEN"),
		timeout: 10 * time.Second,
	}
	cmdArgs, err := parseGlobals(args, &opts)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 2
	}
	if len(cmdArgs) == 0 {
		usage(stderr)
		return 2
	}
	ctx, cancel := context.WithTimeout(context.Background(), opts.timeout)
	defer cancel()
	client := NewClient(opts.url, opts.token, opts.timeout, opts.verbose)
	if err := dispatch(ctx, client, opts, cmdArgs, stdout); err != nil {
		printError(stderr, err, opts.jsonOut)
		return 1
	}
	return 0
}

func dispatch(ctx context.Context, client *Client, opts globalOptions, args []string, stdout io.Writer) error {
	switch args[0] {
	case "health":
		return runHealth(ctx, client, opts, stdout)
	case "tools":
		return runTools(ctx, client, opts, stdout)
	case "search":
		return runSearch(ctx, client, opts, args[1:], stdout)
	case "resolve":
		return runResolve(ctx, client, opts, args[1:], stdout)
	case "snapshot":
		return runSnapshot(ctx, client, opts, args[1:], stdout)
	case "bars":
		return runBars(ctx, client, opts, args[1:], stdout)
	case "cache":
		return runCache(ctx, client, opts, args[1:], stdout)
	case "account":
		return runAccount(ctx, client, opts, args[1:], stdout)
	case "smoke":
		return runSmoke(ctx, client, opts, args[1:], stdout)
	case "help", "-h", "--help":
		usage(stdout)
		return nil
	default:
		return fmt.Errorf("unknown command %q", args[0])
	}
}

func runHealth(ctx context.Context, client *Client, opts globalOptions, stdout io.Writer) error {
	doc, err := client.Health(ctx)
	if err != nil {
		return err
	}
	if opts.jsonOut {
		return writeJSON(stdout, doc)
	}
	printMapSummary(stdout, doc)
	return nil
}

func runTools(ctx context.Context, client *Client, opts globalOptions, stdout io.Writer) error {
	doc, err := client.ListTools(ctx)
	if err != nil {
		return err
	}
	if opts.jsonOut {
		return writeJSON(stdout, doc)
	}
	tools, _ := doc["tools"].([]any)
	for _, item := range tools {
		if tool, ok := item.(map[string]any); ok {
			fmt.Fprintf(stdout, "%s\n", tool["name"])
		}
	}
	if len(tools) == 0 {
		printMapSummary(stdout, doc)
	}
	return nil
}

func runSearch(ctx context.Context, client *Client, opts globalOptions, args []string, stdout io.Writer) error {
	fs := newFlagSet("search", &opts)
	limit := fs.Int("limit", 20, "result limit")
	rank := fs.String("rank", "combined", "rank mode")
	refresh := fs.String("refresh", "stale", "cache refresh mode")
	sectors := fs.String("sectors", "", "comma-separated sectors")
	types := fs.String("types", "", "comma-separated instrument types")
	if err := parseFlagSet(fs, args); err != nil {
		return err
	}
	query := strings.Join(fs.Args(), " ")
	if query == "" {
		return fmt.Errorf("search query is required")
	}
	payload, err := client.CallTool(ctx, "qmt_xtdata_search_instruments", map[string]any{
		"query":   query,
		"limit":   *limit,
		"rank_by": *rank,
		"refresh": *refresh,
		"sectors": splitCSV(*sectors),
		"types":   splitCSV(*types),
	})
	return writePayload(stdout, payload, opts, err)
}

func runResolve(ctx context.Context, client *Client, opts globalOptions, args []string, stdout io.Writer) error {
	fs := newFlagSet("resolve", &opts)
	rank := fs.String("rank", "combined", "rank mode")
	limit := fs.Int("limit", 5, "alternate limit")
	minScore := fs.Int("min-score", 70, "minimum score")
	preferTypes := fs.String("prefer-types", "", "comma-separated preferred types")
	if err := parseFlagSet(fs, args); err != nil {
		return err
	}
	query := strings.Join(fs.Args(), " ")
	if query == "" {
		return fmt.Errorf("resolve query is required")
	}
	payload, err := client.CallTool(ctx, "qmt_xtdata_resolve_instrument", map[string]any{
		"query":        query,
		"rank_by":      *rank,
		"limit":        *limit,
		"min_score":    *minScore,
		"prefer_types": splitCSV(*preferTypes),
	})
	return writePayload(stdout, payload, opts, err)
}

func runSnapshot(ctx context.Context, client *Client, opts globalOptions, args []string, stdout io.Writer) error {
	fs := newFlagSet("snapshot", &opts)
	fields := fs.String("fields", "", "comma-separated fields")
	if err := parseFlagSet(fs, args); err != nil {
		return err
	}
	codes := splitPositionals(fs.Args())
	if len(codes) == 0 {
		return fmt.Errorf("snapshot requires at least one code")
	}
	payload, err := client.CallTool(ctx, "qmt_xtdata_snapshot", map[string]any{
		"codes":  codes,
		"fields": splitCSV(*fields),
	})
	return writePayload(stdout, payload, opts, err)
}

func runBars(ctx context.Context, client *Client, opts globalOptions, args []string, stdout io.Writer) error {
	fs := newFlagSet("bars", &opts)
	period := fs.String("period", "1d", "bar period")
	start := fs.String("start", "", "start YYYYMMDD")
	end := fs.String("end", "", "end YYYYMMDD")
	count := fs.Int("count", -1, "bar count")
	fields := fs.String("fields", "", "comma-separated fields")
	dividend := fs.String("dividend", "none", "dividend type")
	if err := parseFlagSet(fs, args); err != nil {
		return err
	}
	codes := splitPositionals(fs.Args())
	if len(codes) == 0 {
		return fmt.Errorf("bars requires at least one code")
	}
	payload, err := client.CallTool(ctx, "qmt_xtdata_bars", map[string]any{
		"codes":         codes,
		"period":        *period,
		"start_time":    *start,
		"end_time":      *end,
		"count":         *count,
		"fields":        splitCSV(*fields),
		"dividend_type": *dividend,
	})
	return writePayload(stdout, payload, opts, err)
}

func runCache(ctx context.Context, client *Client, opts globalOptions, args []string, stdout io.Writer) error {
	if len(args) == 0 {
		return fmt.Errorf("cache subcommand is required: status or refresh")
	}
	switch args[0] {
	case "status":
		fs := newFlagSet("cache status", &opts)
		if err := parseFlagSet(fs, args[1:]); err != nil {
			return err
		}
		payload, err := client.CallTool(ctx, "qmt_xtdata_instrument_cache_status", map[string]any{})
		return writePayload(stdout, payload, opts, err)
	case "refresh":
		fs := newFlagSet("cache refresh", &opts)
		sectors := fs.String("sectors", "", "comma-separated sectors")
		force := fs.Bool("force", false, "force refresh")
		maxCodes := fs.Int("max-codes", 20000, "max instruments")
		refreshMetrics := fs.Bool("refresh-metrics", true, "refresh liquidity metrics")
		if err := parseFlagSet(fs, args[1:]); err != nil {
			return err
		}
		payload, err := client.CallTool(ctx, "qmt_xtdata_refresh_instrument_cache", map[string]any{
			"sectors":         splitCSV(*sectors),
			"force":           *force,
			"max_codes":       *maxCodes,
			"refresh_metrics": *refreshMetrics,
		})
		return writePayload(stdout, payload, opts, err)
	default:
		return fmt.Errorf("unknown cache subcommand %q", args[0])
	}
}

func runAccount(ctx context.Context, client *Client, opts globalOptions, args []string, stdout io.Writer) error {
	if len(args) == 0 {
		return fmt.Errorf("account subcommand is required: asset, positions, orders, trades, status, statistics, purchase-limit, or ipo")
	}
	switch args[0] {
	case "asset":
		return runAccountScopedTool(ctx, client, opts, args[1:], stdout, "account asset", "qmt_xttrade_asset", nil)
	case "positions":
		return runAccountScopedTool(ctx, client, opts, args[1:], stdout, "account positions", "qmt_xttrade_positions", nil)
	case "orders":
		fs := newFlagSet("account orders", &opts)
		account := fs.String("account", "", "allow-listed account id")
		cancelableOnly := fs.Bool("cancelable-only", false, "only cancelable orders")
		if err := parseFlagSet(fs, args[1:]); err != nil {
			return err
		}
		aid := accountID(*account, fs.Args())
		if aid == "" {
			return fmt.Errorf("account orders requires --account")
		}
		payload, err := client.CallTool(ctx, "qmt_xttrade_orders", map[string]any{
			"account_id":      aid,
			"cancelable_only": *cancelableOnly,
		})
		return writePayload(stdout, payload, opts, err)
	case "trades":
		return runAccountScopedTool(ctx, client, opts, args[1:], stdout, "account trades", "qmt_xttrade_trades", nil)
	case "status":
		return runAccountScopedTool(ctx, client, opts, args[1:], stdout, "account status", "qmt_xttrade_account_status", nil)
	case "statistics", "position-statistics":
		return runAccountScopedTool(ctx, client, opts, args[1:], stdout, "account statistics", "qmt_xttrade_position_statistics", nil)
	case "purchase-limit", "new-purchase-limit":
		return runAccountScopedTool(ctx, client, opts, args[1:], stdout, "account purchase-limit", "qmt_xttrade_new_purchase_limit", nil)
	case "ipo", "ipo-data":
		fs := newFlagSet("account ipo", &opts)
		if err := parseFlagSet(fs, args[1:]); err != nil {
			return err
		}
		payload, err := client.CallTool(ctx, "qmt_xttrade_ipo_data", map[string]any{})
		return writePayload(stdout, payload, opts, err)
	default:
		return fmt.Errorf("unknown account subcommand %q", args[0])
	}
}

func runAccountScopedTool(
	ctx context.Context,
	client *Client,
	opts globalOptions,
	args []string,
	stdout io.Writer,
	flagName string,
	toolName string,
	extra map[string]any,
) error {
	fs := newFlagSet(flagName, &opts)
	account := fs.String("account", "", "allow-listed account id")
	if err := parseFlagSet(fs, args); err != nil {
		return err
	}
	aid := accountID(*account, fs.Args())
	if aid == "" {
		return fmt.Errorf("%s requires --account", flagName)
	}
	payloadArgs := map[string]any{"account_id": aid}
	for key, value := range extra {
		payloadArgs[key] = value
	}
	payload, err := client.CallTool(ctx, toolName, payloadArgs)
	return writePayload(stdout, payload, opts, err)
}

func runSmoke(ctx context.Context, client *Client, opts globalOptions, args []string, stdout io.Writer) error {
	fs := newFlagSet("smoke", &opts)
	query := fs.String("query", "纳指", "search query used for smoke")
	code := fs.String("code", "", "optional code for snapshot smoke")
	if err := parseFlagSet(fs, args); err != nil {
		return err
	}
	report := map[string]any{"ok": true, "checks": []any{}}
	addCheck := func(name string, err error, detail any) {
		status := map[string]any{"name": name, "ok": err == nil}
		if err != nil {
			status["error"] = err.Error()
			report["ok"] = false
		}
		if detail != nil {
			status["detail"] = detail
		}
		report["checks"] = append(report["checks"].([]any), status)
	}
	health, err := client.Health(ctx)
	addCheck("health", err, health)
	tools, err := client.ListTools(ctx)
	addCheck("tools", err, summarizeTools(tools))
	if err == nil {
		payload, searchErr := client.CallTool(ctx, "qmt_xtdata_search_instruments", map[string]any{"query": *query, "limit": 3, "refresh": "never"})
		addCheck("instrument_search", searchErr, decodeBrief(payload))
	}
	if *code != "" {
		payload, snapErr := client.CallTool(ctx, "qmt_xtdata_snapshot", map[string]any{"codes": []string{*code}})
		addCheck("xtdata_snapshot", snapErr, decodeBrief(payload))
	}
	if opts.jsonOut {
		return writeJSON(stdout, report)
	}
	for _, item := range report["checks"].([]any) {
		check := item.(map[string]any)
		state := "ok"
		if check["ok"] != true {
			state = "fail"
		}
		fmt.Fprintf(stdout, "%s: %s\n", check["name"], state)
		if errText, ok := check["error"].(string); ok {
			fmt.Fprintf(stdout, "  %s\n", errText)
		}
	}
	if report["ok"] != true {
		return &AppError{Kind: "smoke", Message: "one or more smoke checks failed"}
	}
	return nil
}

func writePayload(stdout io.Writer, payload json.RawMessage, opts globalOptions, err error) error {
	if err != nil {
		return err
	}
	if opts.jsonOut {
		return writeRawJSON(stdout, payload)
	}
	return printToolPayload(stdout, payload)
}

func parseGlobals(args []string, opts *globalOptions) ([]string, error) {
	out := make([]string, 0, len(args))
	for i := 0; i < len(args); i++ {
		arg := args[i]
		switch {
		case arg == "--json":
			opts.jsonOut = true
		case arg == "--verbose":
			opts.verbose = true
		case arg == "--url" || arg == "--token" || arg == "--timeout":
			if i+1 >= len(args) {
				return nil, fmt.Errorf("%s requires a value", arg)
			}
			i++
			if err := setGlobalValue(opts, arg, args[i]); err != nil {
				return nil, err
			}
		case strings.HasPrefix(arg, "--url=") || strings.HasPrefix(arg, "--token=") || strings.HasPrefix(arg, "--timeout="):
			parts := strings.SplitN(arg, "=", 2)
			if err := setGlobalValue(opts, parts[0], parts[1]); err != nil {
				return nil, err
			}
		default:
			out = append(out, arg)
		}
	}
	return out, nil
}

func setGlobalValue(opts *globalOptions, name, value string) error {
	switch name {
	case "--url":
		opts.url = value
	case "--token":
		opts.token = value
	case "--timeout":
		d, err := parseDuration(value)
		if err != nil {
			return err
		}
		opts.timeout = d
	}
	return nil
}

func newFlagSet(name string, opts *globalOptions) *flag.FlagSet {
	fs := flag.NewFlagSet(name, flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	fs.BoolVar(&opts.jsonOut, "json", opts.jsonOut, "write JSON")
	fs.StringVar(&opts.url, "url", opts.url, "MCP URL")
	fs.StringVar(&opts.token, "token", opts.token, "MCP token")
	fs.DurationVar(&opts.timeout, "timeout", opts.timeout, "timeout")
	fs.BoolVar(&opts.verbose, "verbose", opts.verbose, "verbose output")
	return fs
}

func parseFlagSet(fs *flag.FlagSet, args []string) error {
	return fs.Parse(interspersedFlags(args))
}

func interspersedFlags(args []string) []string {
	boolFlags := map[string]bool{
		"--json":            true,
		"--verbose":         true,
		"--force":           true,
		"--refresh-metrics": true,
		"--cancelable-only": true,
	}
	var flags []string
	var positionals []string
	for i := 0; i < len(args); i++ {
		arg := args[i]
		if !strings.HasPrefix(arg, "--") || arg == "--" {
			positionals = append(positionals, arg)
			continue
		}
		flags = append(flags, arg)
		if strings.Contains(arg, "=") || boolFlags[arg] {
			continue
		}
		if i+1 < len(args) {
			i++
			flags = append(flags, args[i])
		}
	}
	return append(flags, positionals...)
}

func parseDuration(value string) (time.Duration, error) {
	if d, err := time.ParseDuration(value); err == nil {
		return d, nil
	}
	seconds, err := strconv.Atoi(value)
	if err != nil {
		return 0, fmt.Errorf("invalid timeout %q", value)
	}
	return time.Duration(seconds) * time.Second, nil
}

func splitCSV(value string) []string {
	if strings.TrimSpace(value) == "" {
		return nil
	}
	parts := strings.Split(value, ",")
	out := make([]string, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part != "" {
			out = append(out, part)
		}
	}
	return out
}

func splitPositionals(args []string) []string {
	var out []string
	for _, arg := range args {
		out = append(out, splitCSV(arg)...)
	}
	return out
}

func accountID(flagValue string, args []string) string {
	if strings.TrimSpace(flagValue) != "" {
		return strings.TrimSpace(flagValue)
	}
	if len(args) > 0 {
		return strings.TrimSpace(args[0])
	}
	return ""
}

func summarizeTools(tools map[string]any) any {
	raw, _ := tools["tools"].([]any)
	return map[string]any{"count": len(raw)}
}

func decodeBrief(raw json.RawMessage) any {
	if len(raw) == 0 {
		return nil
	}
	var doc any
	if json.Unmarshal(raw, &doc) == nil {
		return doc
	}
	return string(raw)
}

func printError(stderr io.Writer, err error, asJSON bool) {
	appErr := &AppError{Kind: "error", Message: err.Error()}
	if typed, ok := err.(*AppError); ok {
		appErr = typed
	}
	if asJSON {
		_ = writeJSON(stderr, appErr)
		return
	}
	if appErr.Kind != "" {
		fmt.Fprintf(stderr, "%s: %s\n", appErr.Kind, appErr.Message)
		return
	}
	fmt.Fprintln(stderr, appErr.Message)
}

func usage(w io.Writer) {
	fmt.Fprintln(w, "usage: qmtctl [--url URL] [--token TOKEN] [--json] [--timeout 10s] <command>")
	fmt.Fprintln(w, "commands: health, tools, search, resolve, snapshot, bars, cache status, cache refresh, account, smoke")
}

func getenvDefault(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}
