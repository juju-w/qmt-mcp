# Contract: Audit Logging

## Default Sink

Audit records are appended to a JSONL file by default. Postgres is not required
for feature 002.

Recommended default location:

```text
/broker/logs/mcp-audit.jsonl
```

The exact path may be overridden by environment/config, but the sink must be
writable before accepted calls proceed.

## Record Shape

```json
{
  "ts": "2026-06-03T12:00:00.000+08:00",
  "request_id": "req_...",
  "broker_id": "guangda-jinyangguang",
  "tool": "qmt_health",
  "family": "core",
  "account_id": null,
  "args_summary": {},
  "outcome": "ok",
  "error_type": null,
  "latency_ms": 12
}
```

## Sanitization Rules

- Never log bearer tokens.
- Never log request headers in full.
- Never log raw environment variables.
- Never log QMT credentials, passwords, captcha text, cookies, or session blobs.
- For list arguments, log counts and a bounded sample only.
- For account arguments, log the account id only after allow-list validation.

## Failure Policy

- If audit sink initialization fails, startup fails closed or health reports
  `audit:error` and accepted tool calls are refused with `persistence`.
- If an append fails during a call, the call returns a `persistence` error unless
  a later feature explicitly configures best-effort audit mode.
