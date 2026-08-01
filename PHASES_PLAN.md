# Product Improvement Plan — Multi-Agent Paper Trading Platform

> **Status:** Proposed for review — no phase below has been started.
> **Rewritten:** 2026-08-01
> **Purpose:** Turn the current Flask research prototype into a safer, more trustworthy, maintainable, and usable **paper-trading-only** product.

---

## 1. Product direction and non-negotiable guardrails

### Product objective

Build a reliable paper-trading research copilot that lets its owner:

1. research a symbol using transparent multi-agent analysis;
2. test strategies against realistic historical scenarios;
3. make deliberate paper orders with clear risk controls;
4. run a tightly constrained autonomous paper-trading loop; and
5. review real fills, P&L, decisions, risk events, and model performance over time.

### Non-negotiable rules for every implementation phase

- **Paper trading only.** All Alpaca trading clients must keep `paper=True`. This plan does not add a live-trading switch.
- **Research, not financial advice.** The UI and reports must make clear that signals are heuristic research outputs, not investment recommendations or profit promises.
- **Safety before automation.** No new autonomous capability is enabled until server-side risk controls, an emergency stop, and audit history are in place.
- **Server-side enforcement.** The browser can guide the user, but it must never be the only place that checks order size, loss limits, confirmation, or permissions.
- **Honest analytics.** The product must never display estimated/synthetic performance as realized P&L. Unknown data must be labeled unavailable.
- **Incremental modernization.** Preserve the working Flask foundation while separating responsibilities into focused modules. Do not rewrite the application wholesale unless a phase proves that necessary.
- **No secret exposure.** API keys, session secrets, provider responses containing credentials, and raw exception details must never be displayed, logged, or persisted.

---

## 2. Current-state assessment

The imported project already provides a useful foundation:

- Flask dashboard, API routes, and paper Alpaca connection
- multi-agent technical, fundamental, news, risk, portfolio, and execution analysis
- rule-based strategy voting and multi-timeframe analysis
- manual paper orders and an autonomous loop
- JSON-backed history, lightweight backtesting, screening, reporting, and semantic search

However, it is not yet safe or reliable enough to operate as a broad-access or continuously running paper-trading product.

### Priority issues to fix

| Priority | Gap | Why it matters |
|---|---|---|
| Critical | Anyone able to reach the dashboard can call order and autonomous-loop endpoints | Unauthorised users could create paper orders, start loops, and consume external API quota |
| Critical | Autonomous trades have no daily loss limit, drawdown limit, exposure cap, cooldown, market-hours check, or persistent kill switch | A flawed signal or loop could create repeated, uncontrolled paper-account losses |
| Critical | Browser strings are inserted with `innerHTML`; agent, provider, and history text can be untrusted | A malicious or malformed value can execute script in the dashboard |
| Critical | Manual orders lack a server-enforced preview/confirmation flow and robust input limits | Invalid, duplicate, or unexpectedly large orders can be submitted |
| High | The trade ledger is a process-local JSON file and performance statistics contain synthetic estimates | History can become inconsistent and analytics can mislead the user |
| High | The app uses Flask debug mode and has no production health/observability design | It is not appropriate for a stable deployed service |
| High | Backtests omit trading costs, realistic fills, benchmark comparison, and data-quality checks | Results can overstate expected strategy performance |
| High | API payloads are not centrally validated and raw exception messages reach clients | Bad input creates server errors and may reveal internal/provider details |
| Medium | Dashboard lacks charts, risk visibility, order status, filter/export, and accessible controls | Research results and account health are difficult to understand quickly |
| Medium | Existing tests are smoke-level and the test runner is not declared in project dependencies | Safety and regression risks are not caught before changes ship |

---

## 3. Delivery sequence

Phases are intentionally ordered by risk. A later phase does not begin until the acceptance checks for its dependencies pass.

```text
Phase 0  Baseline, product boundaries, and test harness
    ↓
Phase 1  Secure execution and risk-control foundation
    ↓
Phase 2  Durable data, trading lifecycle, and reconciliation
    ↓
Phase 3  Reliable backend, deployment, and observability
    ↓
Phase 4  Trustworthy research and backtesting
    ↓
Phase 5  Operator-first dashboard and visual analytics
    ↓
Phase 6  Strategy intelligence and controlled automation improvements
    ↓
Phase 7  Paper-trading pilot and release readiness
```

---

## Phase 0 — Establish a trustworthy baseline

**Status:** Planned
**Depends on:** None
**Goal:** Make the project safe to change by documenting behavior, stabilizing configuration, and creating a repeatable test baseline. This phase does not change strategy behavior or submit orders.

### What needs to be fixed

1. The project has only smoke tests; critical order, autonomous-loop, validation, and persistence behavior is not covered.
2. `pytest` is not declared as a project dependency or available as a direct command in the current environment.
3. Configuration is spread across modules, uses permissive defaults, and has no central schema for safe operating limits.
4. The existing documentation overstates maturity and does not clearly distinguish current limitations from verified functionality.

### How it will be implemented

1. **Create a test and tooling baseline**
   - Add a development/test dependency definition and a single documented test command.
   - Add isolated fixtures that use temporary storage and mocked Alpaca/Finnhub/Gemini clients; tests must never create an external order or modify the real trade ledger.
   - Add formatting/linting and dependency-audit commands appropriate for the Python stack.
   - Record the initial passing/failing state so later phases can demonstrate measurable improvement.

2. **Centralize configuration**
   - Introduce typed settings loaded once at startup, with explicit parsing and validation for booleans, numbers, URLs, time zones, limits, and secrets.
   - Fail startup with a clear operator-facing error when required paper-trading configuration is invalid.
   - Add safe defaults: paper mode locked on, autonomous mode disabled on startup, debug disabled by default, and conservative order/risk caps.
   - Keep `.env` out of source control and provide a sanitized `.env.example` plus a configuration reference.

3. **Document the real operating model**
   - Update `PROJECT_GUIDE.md` and `Readme.md` to distinguish implemented capabilities, planned capabilities, data-provider limitations, and paper-trading boundaries.
   - Document supported browser/API workflows and the exact meaning of every performance metric.

### Acceptance criteria

- A new developer can run one documented setup command and one documented test command.
- All baseline tests run without calling external services or touching real user history.
- Application startup validates settings and cannot accidentally switch to live trading.
- Documentation describes the product as a research/paper-trading tool and lists current limitations accurately.

### Likely implementation areas

- `config.py`, `requirements.txt`, `conftest.py`, `tests/`
- `app.py`, `agents/execution_agent.py`, `orchestrator.py`
- `Readme.md`, `PROJECT_GUIDE.md`, `replit.md`

---

## Phase 1 — Secure all trading actions and add hard risk controls

**Status:** Planned
**Depends on:** Phase 0
**Goal:** Ensure that only the intended operator can run research/trading actions and that no paper order can bypass consistent pre-trade risk rules.

### What needs to be fixed

1. Trading, chat-with-trading-tools, autonomous start/stop, and sensitive account routes have no access control.
2. POST routes assume valid JSON and do not consistently validate symbols, order sides, numeric values, or payload size.
3. Errors return raw internal exception messages to clients.
4. Dynamic dashboard text is inserted using unsafe HTML rendering.
5. Auto-trading only checks confidence and a limited duplicate-position rule. It lacks:
   - a persistent global emergency stop;
   - daily loss and account drawdown limits;
   - maximum order notional/quantity;
   - maximum position, gross exposure, and open-position limits;
   - duplicate-order prevention and per-symbol cooldowns;
   - market-hours and stale-data checks;
   - a minimum data-completeness/risk-quality threshold;
   - a single unified guard for manual and autonomous execution.
6. Manual orders can be submitted without a clear order preview and explicit confirmation.

### How it will be implemented

1. **Protect the application and sensitive routes**
   - Add an operator authentication layer using the existing session secret, with secure sessions, password hash stored only as a secret, logout, session expiry, and brute-force/rate limiting.
   - Restrict order placement, loop controls, account data, history export, and autonomous status to authenticated operators.
   - Require CSRF protection and same-origin checks for browser state-changing requests.
   - Apply per-route request rate limits for chat and provider-heavy analysis calls.
   - Add standard response security headers, including a Content Security Policy designed around external chart assets only when needed.

2. **Add a centralized API validation layer**
   - Parse request bodies defensively and return consistent `400` or `422` JSON responses for malformed input.
   - Validate symbols with an explicit format, normalize to uppercase, and reject invalid/unsupported symbols before provider calls.
   - Validate enums and finite numeric ranges for orders, backtests, loops, sizing, screening, search, and optimization.
   - Require exactly one order sizing method (`qty` or `notional`), plus configured minimum and maximum bounds.
   - Replace raw provider exceptions in responses with a safe user message, structured error code, and server-side correlation ID.

3. **Implement a server-side execution policy**
   - Create a dedicated risk/execution-policy service invoked by **every** manual and autonomous order path immediately before Alpaca submission.
   - Evaluate account equity, cash/buying power, current positions, gross exposure, per-symbol exposure, order notional, open-order count, and position-count caps.
   - Track starting equity and realized daily P&L in the application’s trading time zone; block new orders when daily loss or drawdown limits are breached.
   - Enforce a persistent emergency-stop flag, an autonomous-only pause flag, and an operator-visible reason for any block.
   - Enforce market-session policy, quote freshness, supported order type, data completeness, and a per-symbol cooldown/idempotency key.
   - Keep thresholds configurable but conservative by default. The dashboard may show these controls but cannot override server policy silently.

4. **Make manual execution deliberate**
   - Replace direct “Buy”/“Sell” submission with a preview endpoint that reports projected order details, all risk checks, and blocking reasons.
   - Require an explicit confirmation token tied to the preview, symbol, size, side, and short expiry before final submission.
   - Present a paper-trading acknowledgement in the UI and log the request, decision, operator, result, and order ID in the audit trail.

5. **Eliminate dashboard injection risks**
   - Replace untrusted `innerHTML` interpolation with DOM APIs and `textContent`, or a narrowly scoped vetted escaping function.
   - Treat chat messages, agent output, news headlines, history records, and provider errors as untrusted text.

### Acceptance criteria

- Unauthenticated requests cannot start/stop automation, submit orders, or access sensitive trading data.
- Invalid, oversized, duplicate, stale, or improperly confirmed orders never reach Alpaca.
- The same risk policy blocks unsafe manual and autonomous orders.
- The emergency stop remains active across a restart and is visible in the UI.
- Dashboard data containing HTML-like strings is rendered as text, never executable markup.
- API responses are consistent and do not expose secrets, stack traces, or raw provider internals.
- Automated tests cover all high-risk allow/block paths.

### Likely implementation areas

- `app.py`, `config.py`, `orchestrator.py`, `agents/execution_agent.py`
- New modules such as `services/auth.py`, `services/validation.py`, `services/risk_policy.py`, `services/audit.py`
- `templates/index.html` and new static JS/CSS assets
- `tests/test_auth*.py`, `tests/test_validation*.py`, `tests/test_execution_policy*.py`

---

## Phase 2 — Replace fragile history with durable trading records

**Status:** Planned
**Depends on:** Phase 1
**Goal:** Make every decision, order, risk event, fill, and performance figure traceable and durable.

### What needs to be fixed

1. Trade history is stored in one JSON file with only in-process locking; it is vulnerable to corruption, multi-worker inconsistency, and non-persistent deployment storage.
2. Current history statistics invent estimated win/loss values rather than computing realized performance from broker fills.
3. Submitted orders are logged, but order status, partial fills, cancellations, and broker-side changes are not reconciled.
4. Autonomous state and risk state are process-local, which is unreliable when the app restarts or scales.

### How it will be implemented

1. **Adopt a transactional persistence layer**
   - Replace JSON history with a relational database using SQLAlchemy and migrations.
   - Use Replit PostgreSQL for the running deployment after confirming the project’s data-retention needs; keep the migration isolated and reversible by exporting the existing JSON history first.
   - Store timestamps in UTC and convert only at display time.

2. **Define a durable trading domain model**
   - `analysis_runs`: symbol, inputs, provider freshness, strategy version, decision, confidence, rationale, and data-quality result.
   - `strategy_votes`: per-strategy decision, score, inputs summary, and version.
   - `orders`: requested order, validation result, risk decision, Alpaca ID, lifecycle state, requested size, and operator/autonomous source.
   - `fills`: broker-reported fill price, quantity, fees, timestamp, and realized P&L linkage.
   - `positions` and `equity_snapshots`: periodically reconciled account state for exposure and equity curves.
   - `risk_events`, `autonomous_runs`, `app_settings`, and `audit_events`: kill-switch actions, blocked orders, loop state, configuration changes, and security-relevant actions.

3. **Reconcile with Alpaca**
   - Implement an idempotent synchronization service that retrieves order status, fills, positions, and account equity from Alpaca paper APIs.
   - Reconcile on dashboard refresh, after an order submission, on the autonomous schedule, and through a controlled manual refresh action.
   - Clearly label data as `live`, `stale`, `unavailable`, or `reconciliation failed`.
   - Compute realized and unrealized P&L from broker information only; show `N/A` where it cannot be verified.

4. **Migrate safely**
   - Back up the current `memory/trade_history.json`.
   - Import valid historical records with a source tag and preserve malformed/unmappable records in a migration report rather than silently dropping them.
   - Remove the JSON ledger only after migration verification and rollback documentation are complete.

### Acceptance criteria

- A restart does not lose history, risk controls, loop state, or audit events.
- All submitted orders can be traced to a decision, risk result, source, and broker order ID.
- Realized P&L is calculated only from reconciled fills; no synthetic return is displayed as actual performance.
- Reconciliation is idempotent and handles pending, partial, filled, rejected, cancelled, and expired orders.
- Database migration, backup, and restore procedures are tested.

### Likely implementation areas

- New `db/` or `models/`, `repositories/`, `services/reconciliation.py`, migration files
- `memory/trade_history.py` replacement/migration adapter
- `agents/execution_agent.py`, `agents/portfolio_agent.py`, `orchestrator.py`
- `app.py`, dashboard history/account views, integration tests

---

## Phase 3 — Make the backend reliable in a real deployment

**Status:** Planned
**Depends on:** Phase 2
**Goal:** Run the service predictably under normal use, recover gracefully from provider failures, and provide the operator enough visibility to diagnose problems.

### What needs to be fixed

1. `app.py` launches Flask with debug mode enabled when run directly.
2. The current in-memory singleton message bus, interaction IDs, autonomous thread, and JSON state are incompatible with multiple production workers.
3. Page rendering calls external account APIs synchronously, so a provider problem can break dashboard loading.
4. There is no health endpoint, structured log format, error correlation, provider health state, or background-work ownership model.
5. Dependencies are version-ranged but not reproducibly locked.

### How it will be implemented

1. **Harden application startup and serving**
   - Move Flask construction to an application factory with explicit development, test, and production configuration.
   - Disable debug mode outside a deliberate local-development setting.
   - Use Gunicorn with a documented worker, timeout, and proxy configuration.
   - Add `/health/live` for process health and `/health/ready` for dependency readiness without exposing secrets.

2. **Separate web requests from background operations**
   - Do not rely on a web-process daemon thread as the sole owner of autonomous trading.
   - Use a durable scheduler/job design backed by the database, with a single-lease lock so only one scheduler instance may execute an autonomous cycle.
   - Persist run starts, heartbeats, failures, progress, and stop requests.
   - Keep polling/simple architecture initially; introduce a queue only if measured workload requires it.

3. **Improve provider resilience**
   - Use bounded retries with timeouts, circuit breakers, and cached last-known-good data where it is safe.
   - Make dashboard shell rendering independent of provider availability; fetch account/position cards asynchronously and show a provider status banner on failure.
   - Add service-level time budgets so one slow provider cannot stall the entire analysis pipeline.

4. **Add observability**
   - Use structured logs with request IDs, analysis IDs, order IDs, autonomous-run IDs, and sanitized provider result status.
   - Record error metrics, provider latency, risk blocks, order outcomes, and scheduler health.
   - Add an operator-only diagnostics screen that exposes safe status summaries, never secrets or raw credentials.

5. **Make builds reproducible**
   - Pin or lock dependencies after verifying compatibility.
   - Define CI checks for tests, static analysis, dependency audit, and a startup/health smoke test.

### Acceptance criteria

- Production starts with Gunicorn and no debug debugger.
- Dashboard shell remains usable when a provider is unavailable.
- Only one autonomous scheduler can actively submit order attempts at a time.
- Health endpoints, structured logs, and diagnostics identify common outages without leaking sensitive data.
- A clean environment can install pinned dependencies, run tests, and pass a startup health check.

### Likely implementation areas

- `app.py`, `config.py`, `Procfile`, Replit workflow configuration, `requirements*.txt`
- New `services/scheduler.py`, `services/provider_health.py`, `services/logging.py`
- `orchestrator.py`, templates/static assets, deployment documentation

---

## Phase 4 — Make research results and backtests trustworthy

**Status:** Planned
**Depends on:** Phases 1–3
**Goal:** Ensure historical research answers the question “what would have happened under defined assumptions?” rather than producing overly optimistic or ambiguous results.

### What needs to be fixed

1. Backtesting does not model slippage, commissions, bid/ask spread, partial fills, order delays, market session rules, or benchmark returns.
2. Backtest exit logic is simplified and needs explicit transaction assumptions, traceable strategy versions, and edge-case coverage.
3. Data quality/freshness is not visible enough in analysis and research outputs.
4. Rule-based strategy confidence is not calibrated against out-of-sample performance.
5. Current ensemble weighting needs verified outcomes before it can be treated as adaptive intelligence.

### How it will be implemented

1. **Refactor the backtesting engine around explicit assumptions**
   - Add a `BacktestConfig` with initial capital, sizing policy, costs, slippage, spread model, trading calendar, order execution timing, stop/target policy, and benchmark.
   - Record all assumptions alongside every backtest result and display them in the dashboard/export.
   - Prevent look-ahead bias by ensuring decisions use only bars available before the configured fill time.
   - Test corporate-action/data-gap handling and reject unreliable data windows with clear warnings.

2. **Model execution realistically**
   - Use next-bar or configurable fill logic, not same-bar assumptions without disclosure.
   - Apply configurable commissions/slippage/spread to entries and exits.
   - Model rejected/partial/unfilled orders when assumptions require it.
   - Distinguish closed realized P&L from mark-to-market open-position P&L.

3. **Expand performance analytics**
   - Add total/annualized return, volatility, Sharpe/Sortino, maximum drawdown, profit factor, win/loss expectancy, exposure time, turnover, and benchmark-relative performance.
   - Add date-window, symbol, strategy, and parameter breakdowns.
   - Highlight insufficient sample sizes and avoid giving false confidence to a short or sparse backtest.

4. **Create a research-validation workflow**
   - Add in-sample/out-of-sample split, rolling walk-forward evaluation, and parameter sensitivity checks.
   - Version every strategy and preserve its configuration with each analysis, backtest, and order decision.
   - Compare paper-trade performance with the same strategy’s expected/backtested behavior without conflating the two.

### Acceptance criteria

- Every backtest displays its execution/cost assumptions, data range, benchmark, and warnings.
- Tests demonstrate no obvious look-ahead bias under controlled historical fixtures.
- Performance metrics correctly handle no-trade, all-loss, open-position, and missing-data cases.
- Results can be exported/reproduced from a stored configuration and strategy version.
- Ensemble changes are not activated automatically without passing predefined out-of-sample criteria.

### Likely implementation areas

- `backtesting/engine.py`, `backtesting/report.py`, strategy modules, technical indicators
- New `backtesting/config.py`, `backtesting/execution.py`, `backtesting/metrics.py`
- Persistence models, `/api/backtest` validation, dashboard backtest presentation, tests

---

## Phase 5 — Deliver an operator-first, accessible dashboard

**Status:** Planned
**Depends on:** Phases 1–4
**Goal:** Replace the current dense, single-template dashboard experience with a clear operating console that explains what the system knows, what it did, and what it refuses to do.

### What needs to be fixed

1. The dashboard is a single large inline HTML/CSS/JavaScript file, making maintenance, content-security policy, and UI testing difficult.
2. There are no price, equity, drawdown, or trade-performance charts.
3. Manual orders have no preview/confirmation/risk experience; order lifecycle and blocked reasons are not easy to review.
4. Autonomous controls lack current status, configuration, heartbeat, pause/kill state, and safety-limit visibility.
5. Errors rely on `alert()` or appear silently; loading, empty, stale, and retry states are inconsistent.
6. The UI needs semantic tabs, keyboard support, screen-reader labels, responsive tables, filtering, pagination, and export.

### How it will be implemented

1. **Modularize frontend assets without an unnecessary framework rewrite**
   - Move CSS and JavaScript out of the template into versioned static assets.
   - Create small modules for API calls, common rendering, notifications, dashboard state, charts, and each view.
   - Use a shared API client that handles status codes, safe errors, timeouts, loading states, request cancellation, and retry behavior.

2. **Build a clear dashboard information hierarchy**
   - Persistent header: paper-trading badge, market/provider status, last refresh, authenticated operator, and emergency-stop state.
   - Overview: equity, daily realized/unrealized P&L, drawdown, exposure, cash/buying power, open orders, and risk-limit utilization.
   - Research: price/volume chart with technical overlays, multi-agent evidence cards, strategy-vote breakdown, data freshness, and signal confidence rationale.
   - Orders: preview/confirm workflow, pending/fill/reject/cancel timeline, audit detail, and reconciliation status.
   - Automation: configured symbols, cadence, last/next run, heartbeat, per-symbol cooldown, current guard result, pause, resume, and global stop controls.
   - Performance: equity curve, drawdown chart, realized P&L, benchmark comparison, trade list, filters, search, pagination, and CSV export.
   - Backtesting: configuration form, assumptions panel, comparable results table, and equity/drawdown/trade charts.

3. **Use accessible and resilient interaction patterns**
   - Use real buttons and form controls with labels, ARIA tab behavior, keyboard navigation, focus management, and accessible status announcements.
   - Ensure charts have textual summaries and tables have responsive/mobile alternatives.
   - Sanitize all dynamic content by design and render a visible empty/error/stale state for every data view.

4. **Add frontend quality checks**
   - Add browser-level tests for authentication, API error display, keyboard tab navigation, order preview/confirmation, emergency stop, and primary charts.
   - Test desktop and narrow mobile/tablet layouts.

### Acceptance criteria

- The operator can understand account health, risk status, autonomous state, and order status without reading raw logs.
- Every trade action shows a clear preview, explicit confirmation, outcome, and audit link.
- Charts use broker/reconciled or clearly labeled backtest data and update safely.
- The dashboard works with keyboard navigation and presents meaningful empty/error/stale states.
- Browser tests cover the primary research, manual-order, automation, and performance workflows.

### Likely implementation areas

- `templates/index.html` split into templates and `static/css/`, `static/js/`
- New/expanded API endpoints in `app.py` or route modules
- Chart library dependency after license/size review
- Browser tests and accessibility checks

---

## Phase 6 — Improve analysis quality and controlled automation

**Status:** Planned
**Depends on:** Phases 1–5
**Goal:** Improve signal transparency and usefulness only after safety, durable history, and reliable measurement are in place.

### What needs to be fixed

1. News sentiment is keyword-based and fundamental/news inputs can be missing or stale.
2. Strategy logic and confidence are heuristic-driven but need versioning, evaluation, and understandable explanations.
3. Multi-timeframe analysis, sizing, screener, reflections, and ensemble weighting are present but not yet integrated into a controlled decision-quality workflow.
4. Users need a clearer distinction between a research idea, a trade recommendation, a blocked order, and a completed paper trade.

### How it will be implemented

1. **Improve data quality before adding complexity**
   - Add provider data timestamps, source labels, cached/stale status, input completeness score, and known limitations to all analyses.
   - Add configurable watchlists and market-universe constraints rather than attempting an unbounded screener.
   - Integrate existing SEC/economic-calendar placeholders only after data-source reliability and licensing are reviewed.

2. **Version and explain strategies**
   - Give every strategy a stable ID, version, parameter set, decision rationale, required inputs, and failure/abstention reason.
   - Display how each agent and strategy contributed to the final decision, including conflicting evidence.
   - Require sufficient data quality and a consensus/risk threshold before a recommendation can advance to an order preview.

3. **Make sizing policy explicit**
   - Treat volatility targeting, risk parity, and Kelly calculations as recommendations subject to the same portfolio risk caps.
   - Prevent sizing from relying on synthetic win-rate data; use reconciled historical outcomes only.
   - Add tests for missing/invalid prices, ATR, equity, short history, and limit conflicts.

4. **Use learning features cautiously**
   - Keep ensemble weight changes in a “proposed” state until validated by stored out-of-sample backtests and reviewed by the operator.
   - Keep Gemini reflections as a labeled narrative/journaling feature, never as an unbounded authority to place orders.
   - Add trade-journal prompts that compare original thesis, risk conditions, fill outcome, and post-trade evidence.

5. **Add optional operator notifications**
   - Provide configurable in-app notifications first for safety blocks, provider failures, fills, daily limits, and autonomous-loop state changes.
   - Evaluate email/Slack/mobile integrations only after the core audit and permission model supports them.

### Acceptance criteria

- Each recommendation exposes the source data age, input gaps, strategy version, evidence, and risk-policy result.
- Sizing and ensemble features never bypass Phase 1 risk limits.
- No automated strategy-weight change is applied without recorded validation and explicit operator review.
- Agent-generated narrative is clearly separated from deterministic execution controls.

### Likely implementation areas

- `agents/`, `strategies/`, `optimization/`, `sizing/`, `memory/reflections.py`
- Research/configuration persistence, analysis APIs, dashboard evidence views, tests

---

## Phase 7 — Paper-trading pilot and release readiness

**Status:** Planned
**Depends on:** Phases 0–6
**Goal:** Demonstrate that the product operates safely and consistently in paper trading before treating autonomous mode as a routine workflow.

### What needs to be fixed

1. There is no documented release gate, paper-pilot protocol, rollback procedure, or operating playbook.
2. Current behavior has not been validated over a meaningful period with real provider outages, restarts, partial fills, risk blocks, and different market conditions.

### How it will be implemented

1. **Define a controlled paper-trading pilot**
   - Begin with research-only mode, then manual paper-order mode, then a restricted autonomous pilot with a small symbol allowlist and conservative caps.
   - Require daily review of provider health, blocked actions, order reconciliation, P&L, drawdown, and unexpected scheduler behavior.
   - Keep automation paused by default after every deployment until the operator deliberately resumes it.

2. **Define release gates**
   - 100% passing backend, security, and browser test suites.
   - Successful migration/backup/restore rehearsal.
   - Confirmed emergency-stop behavior across restart.
   - No unresolved critical/high security findings.
   - Documented handling for missing data, provider outages, reconciliation mismatches, and failed scheduled runs.
   - A minimum paper-trading observation window selected by the operator; results must be evaluated for safety and process adherence, not merely profitability.

3. **Create operating and recovery playbooks**
   - Startup/shutdown and deployment checklist.
   - Credential rotation and access-revocation process.
   - How to pause automation, investigate an order, reconcile account state, restore history, and roll back a failed release.
   - Incident log template and post-incident review process.

### Acceptance criteria

- The system passes a paper-trading pilot without untraceable orders or bypassed risk controls.
- Every important operator action has an audited record and a documented recovery path.
- The operator can stop automation immediately, restart safely, and reconcile broker/account state afterward.
- The project has a repeatable release checklist and known-issue register.

---

## 4. Explicitly deferred or out of scope

These items are intentionally **not** part of the initial improvement program:

- Live-money trading, broker live-account routing, or a `paper=False` setting
- Guaranteed-return claims, financial-advice workflows, or autonomous portfolio management for third parties
- Multi-user investment accounts or delegated trading permissions
- A rewrite to a different frontend framework solely for aesthetics
- Machine-learning/LLM control of execution before the deterministic safety and research-validation phases are complete
- Additional brokers before Alpaca paper-trading reconciliation and controls are reliable

Any future live-trading discussion would require a separate risk, compliance, security, and operator-approval plan.

---

## 5. Recommended first execution package after approval

The first implementation package should include **Phase 0 plus the risk-critical core of Phase 1** in this order:

1. Add reproducible test tooling, isolated provider mocks, typed configuration, and safe defaults.
2. Turn off debug serving and centralize safe error handling.
3. Add authentication/session protection, CSRF/origin checks, and schema validation for all routes.
4. Replace unsafe dynamic HTML rendering and add security headers.
5. Add the execution-policy service: paper-mode assertion, order bounds, daily loss/drawdown, exposure limits, data freshness, cooldown/idempotency, and persistent kill switch.
6. Replace direct manual submission with preview and confirmation.
7. Add automated tests proving that unsafe orders and unauthorised requests cannot reach Alpaca.

### Why this package comes first

The current application can interact with a real paper brokerage account. Improving charts, strategy sophistication, or visual polish before execution security and risk limits would make the interface more appealing without making it safer or more trustworthy.

---

## 6. Completion definition for the full plan

The improvement program is complete when the product:

- remains explicitly paper-trading-only;
- requires authenticated, confirmed, validated actions for every order;
- enforces durable risk limits and a persistent emergency stop server-side;
- reconciles and reports broker-backed orders/fills/P&L honestly;
- runs predictably through restarts and provider failures;
- produces reproducible, assumption-labeled research and backtests;
- offers an accessible dashboard with clear risk, research, order, automation, and performance views; and
- has automated tests, deployment checks, operating playbooks, and a successful controlled paper-trading pilot.