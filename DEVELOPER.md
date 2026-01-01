# Developer Guide

## Live Yahoo probe workflow
The repository includes a non-blocking GitHub Actions workflow named **Live data probe** to monitor real Yahoo Finance availability and latency.

- **Triggers**: runs hourly via cron and can be launched manually with `workflow_dispatch` inputs.
- **Command**: executes `python -m stock_dashboard.cli --tickers AAPL --verbose` with a short timeout to exercise the real Yahoo endpoint and gather stdout/stderr plus duration.
- **Outputs**: writes a JSON report (`probe-report.json`) and a text log (`probe-output.log`), uploads them as artifacts, and posts a concise job summary. An optional webhook (`secrets.LIVE_PROBE_WEBHOOK`) can receive the JSON payload for Slack or another notification endpoint.
- **Non-blocking**: this workflow is alerting-only and separate from required CI checks to avoid gating merges; failures highlight data freshness issues rather than code regressions.

## Choosing live vs. smoke mode
- **Live checks (default)**: keep `smoke_mode` as `false` when you want to validate external availability, detect rate limiting, or confirm latency to Yahoo. Use this for scheduled probes and manual runs during suspected outages.
- **Smoke mode**: set the manual dispatch input `smoke_mode` to `true` to export `SMOKE_TEST=1`, which swaps to stubbed data. Prefer this when validating workflow wiring, diagnosing unrelated CI flakiness, or when rate limits are already breached.
- **Timeout tuning**: adjust the `timeout_seconds` input during manual runs if you need a slightly longer window for slow responses; keep it short by default to minimize queue time and to surface hangs quickly.

## Webhook/SaaS notifications
Configure `secrets.LIVE_PROBE_WEBHOOK` with your Slack Incoming Webhook (or similar) URL to receive JSON payloads matching `probe-report.json`. The payload includes command, tickers, smoke-mode flag, duration, and outcome; downstream alerting rules can page only on `outcome != "success"` or on latency thresholds.
