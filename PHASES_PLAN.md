# Multi-Agent Paper Trading System

# Project Plan & Observability Upgrade

**Project:** Multi-Agent AI Paper Trading System
**Broker:** Alpaca Paper Trading
**Primary data:** Alpaca Market Data API
**Additional data:** Finnhub
**LLM:** Google Gemini
**Backend:** Python + Flask
**Current loop:** Every 180 seconds
**Environment:** Alpaca Free/Basic + Paper Trading
**Status:** Research / development system — NOT production trading software

---

# 1. Project Goal

Transform the current multi-agent paper trading prototype into a **fully observable, testable, explainable trading research platform**.

The system should not simply say:

> HOLD — confidence 0.42

It should be possible to answer:

> Why did the system say HOLD?

And then drill down through:

```text
RUN #20260808-164800
│
├── Market Data
│   ├── Alpaca
│   ├── Feed: IEX
│   ├── Latest price
│   ├── Historical bars
│   ├── Data freshness
│   ├── Number of bars
│   ├── API latency
│   └── Errors/warnings
│
├── Technical Agent
│   ├── RSI
│   ├── MACD
│   ├── EMA20
│   ├── EMA50
│   ├── Bollinger Bands
│   ├── ATR
│   ├── Volume
│   └── Technical conclusion
│
├── Fundamental Agent
│   ├── Company profile
│   ├── PE
│   ├── EPS
│   ├── Beta
│   ├── Market cap
│   ├── Data source
│   ├── API status
│   └── Fundamental conclusion
│
├── News Agent
│   ├── Number of articles
│   ├── Article timestamps
│   ├── Headlines
│   ├── Sentiment calculation
│   └── News conclusion
│
├── Risk Agent
│   ├── ATR %
│   ├── Volatility
│   ├── RSI risk
│   ├── Position exposure
│   └── Risk conclusion
│
├── Portfolio Agent
│   ├── Account
│   ├── Cash
│   ├── Equity
│   ├── Buying power
│   ├── Existing position
│   └── P/L
│
├── Strategies
│   ├── Momentum → BUY/HOLD/SELL
│   ├── Trend → BUY/HOLD/SELL
│   ├── Mean Reversion → BUY/HOLD/SELL
│   ├── Breakout → BUY/HOLD/SELL
│   └── Swing → BUY/HOLD/SELL
│
├── Execution Agent
│   ├── Agent score
│   ├── Strategy score
│   ├── Combined score
│   ├── Confidence
│   ├── Risk gates
│   ├── Position gates
│   └── Final decision
│
└── Execution
    ├── Order submitted?
    ├── Order ID
    ├── Status
    ├── Fill
    └── Result
```

---

# 2. Current System Assessment

## Current strengths

The project already has a strong foundation.

### Existing components

* Alpaca paper trading
* Alpaca market data
* Finnhub fundamentals
* Finnhub news
* Gemini
* Flask dashboard
* 7 agents
* 5 strategies
* technical indicators
* portfolio tracking
* trade history
* autonomous loop
* backtesting
* semantic memory
* reflections
* position sizing
* strategy optimization
* API endpoints
* caching
* retry logic

This is considerably more than a basic trading bot.

---

# 3. Main Problem

The current architecture is much more sophisticated than its user interface.

The system performs many operations, but the dashboard mainly exposes the final result.

That creates an observability problem.

## Current

```text
API
 ↓
Agent
 ↓
Strategy
 ↓
Execution
 ↓
HOLD
```

## Desired

```text
API REQUEST
 ↓
API RESPONSE
 ↓
VALIDATION
 ↓
DATA QUALITY CHECK
 ↓
AGENT ANALYSIS
 ↓
INDICATORS
 ↓
RULE EVALUATIONS
 ↓
STRATEGY VOTES
 ↓
SCORE CALCULATION
 ↓
RISK GATES
 ↓
PORTFOLIO GATES
 ↓
FINAL DECISION
 ↓
ORDER DECISION
 ↓
ORDER RESULT
```

Every stage must be visible.

---

# 4. Important Alpaca Free-Tier Reality

The system should explicitly support the Alpaca Basic/Free data plan.

The free plan provides stock market data using the IEX feed.

It does NOT provide the same real-time consolidated SIP coverage as the paid Algo Trader Plus plan.

Alpaca currently documents:

* Basic: $0/month
* Stock coverage: US stocks and ETFs
* Real-time stock feed: IEX
* Historical stock data: available
* Historical API limit: 200 requests/minute
* Equity WebSocket: up to 30 symbols
* Paid Algo Trader Plus: consolidated US exchange coverage

The system therefore needs to know which feed it is using.

Do NOT allow the application to silently assume SIP.

## Required configuration

Add:

```env
ALPACA_DATA_FEED=iex
ALPACA_PAPER=true
```

The provider should explicitly pass the selected feed.

For example:

```python
feed = DataFeed.IEX
```

instead of relying on whatever default the SDK chooses.

Alpaca documents that the latest-bar endpoint defaults to IEX for users without the unlimited subscription.

Historical stock bars also support explicit timeframes and feed selection.

---

# 5. Phase 0 — Baseline Audit

Before adding features, determine exactly what currently works.

## Create

```text
scripts/
    system_health_check.py
    test_alpaca_data.py
    test_finnhub.py
    test_gemini.py
    test_indicators.py
    test_pipeline.py
```

## Health check should test

### Alpaca

* API authentication
* paper account authentication
* account endpoint
* latest quote
* latest trade
* latest bar
* historical bars
* selected feed
* number of returned bars
* timestamp of newest bar
* API latency
* HTTP/status errors
* rate-limit response

### Finnhub

* API authentication
* company profile
* financial data
* news
* quote
* response freshness
* empty response handling

### Gemini

* API authentication
* model availability
* simple request
* response latency
* timeout handling

### Internal system

* indicator calculations
* strategy calculations
* execution calculation
* history storage
* memory storage
* Flask endpoints

---

# 6. System Health Dashboard

Add a new dashboard tab:

# SYSTEM HEALTH

Example:

```text
SYSTEM HEALTH
──────────────────────────────────────────────

Alpaca Trading       🟢 PASS
Paper Account        🟢 PASS
Alpaca Market Data   🟢 PASS
Feed                 IEX
Latest Data          16:47:32
Data Age             8 seconds

Historical Bars      🟢 PASS
Bars Received        250
Newest Bar           16:47
Oldest Bar           2026-07-31

Finnhub              🟢 PASS
Company Profile      🟢 PASS
Fundamentals         🟢 PASS
News                 🟢 PASS
Articles Returned    14

Gemini                🟢 PASS
Model                 Gemini
Response Time         1.4s

Database              🟢 PASS
Trade History         182 records
Analysis History      642 records

Cache                 🟢 PASS
```

If something fails:

```text
Finnhub News          🔴 FAIL
HTTP Status           429
Error                 Rate limit exceeded
Last Successful Call  16:38:21
```

---

# 7. Phase 1 — Create Run IDs

Every analysis must receive a unique ID.

Example:

```text
RUN-20260808-164800-AAPL
```

Every operation in that run uses the same ID.

Example:

```json
{
  "run_id": "RUN-20260808-164800-AAPL",
  "symbol": "AAPL",
  "started_at": "...",
  "status": "running"
}
```

This becomes the backbone of observability.

---

# 8. Phase 2 — Create an Event/Trace System

Create:

```text
observability/
    __init__.py
    events.py
    run_tracker.py
    logger.py
    metrics.py
    health.py
```

Every important operation emits an event.

Example:

```json
{
  "run_id": "RUN-20260808-164800-AAPL",
  "agent": "MarketAgent",
  "event": "api_call",
  "provider": "alpaca",
  "endpoint": "historical_bars",
  "symbol": "AAPL",
  "status": "success",
  "duration_ms": 241,
  "records": 250,
  "feed": "iex"
}
```

If it fails:

```json
{
  "run_id": "RUN-20260808-164800-AAPL",
  "agent": "MarketAgent",
  "event": "api_call",
  "provider": "alpaca",
  "endpoint": "historical_bars",
  "status": "error",
  "error_type": "HTTPError",
  "http_status": 403,
  "message": "Feed not available"
}
```

This is much more useful than:

```text
WARNING: API failed
```

---

# 9. Phase 3 — Agent Group Chat Interface

This should become the centerpiece of the dashboard.

Add:

# LIVE AGENT ROOM

Example:

```text
┌──────────────────────────────────────────────────────────────┐
│ RUN-20260808-164800-AAPL                         RUNNING 🟢  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ 🟦 ORCHESTRATOR                                             │
│ Starting analysis for AAPL.                                 │
│                                                              │
│ 🟩 MARKET AGENT                                             │
│ Requesting Alpaca market snapshot.                          │
│ Feed: IEX                                                   │
│ Timeframes: 1m, 5m, 15m, 1h, 1d                            │
│                                                              │
│ 🟩 MARKET AGENT                                             │
│ ✓ Received 250 historical bars.                             │
│ Latest price: $XXX.XX                                       │
│ Latest bar: 16:47:00                                        │
│ Data age: 12 seconds                                        │
│                                                              │
│ 🟨 TECHNICAL AGENT                                          │
│ Calculating indicators...                                   │
│                                                              │
│ 🟨 TECHNICAL AGENT                                          │
│ RSI(14): 53.2                                               │
│ MACD: bullish                                                │
│ EMA20 > EMA50: TRUE                                         │
│ Bollinger position: middle                                  │
│ ATR: 2.1%                                                   │
│ Volume ratio: 0.87x                                         │
│                                                              │
│ 🟪 FUNDAMENTAL AGENT                                        │
│ Requesting company fundamentals from Finnhub.               │
│                                                              │
│ 🟪 FUNDAMENTAL AGENT                                        │
│ ✓ PE: 27.4                                                  │
│ ✓ EPS: ...                                                  │
│ ✓ Beta: ...                                                 │
│ Fundamental score: +0.0                                    │
│                                                              │
│ 🟥 NEWS AGENT                                               │
│ Requesting recent news.                                     │
│                                                              │
│ 🟥 NEWS AGENT                                               │
│ ✓ 12 articles returned                                      │
│ Sentiment: neutral                                          │
│                                                              │
│ 🟧 RISK AGENT                                               │
│ ATR risk: LOW                                               │
│ RSI warning: NONE                                           │
│                                                              │
│ 🟦 STRATEGIES                                               │
│ Momentum: HOLD 0.20                                         │
│ Trend: BUY 0.55                                             │
│ Mean Reversion: HOLD 0.10                                  │
│ Breakout: HOLD 0.05                                         │
│ Swing: BUY 0.35                                             │
│                                                              │
│ 🟥 EXECUTION AGENT                                          │
│ Agent score: +0.20                                          │
│ Strategy score: +0.31                                      │
│ Combined score: +0.58                                      │
│ Confidence: 0.15                                            │
│                                                              │
│ 🟥 EXECUTION AGENT                                          │
│ FINAL DECISION: HOLD                                        │
│                                                              │
│ Reason: Signals are mixed and confidence is below the        │
│ autonomous execution threshold.                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

# 10. Do Not Show Hidden Chain-of-Thought

The dashboard should NOT attempt to expose private LLM chain-of-thought.

Instead, create a structured:

# Decision Trace

For every agent show:

* what it received
* what APIs it called
* what data came back
* what calculations it performed
* what rules it evaluated
* what output it produced
* what confidence it assigned
* what warnings/errors occurred

Example:

```text
TECHNICAL AGENT

INPUT
250 AAPL bars

CALCULATIONS
RSI(14)
MACD(12,26,9)
EMA(20)
EMA(50)
Bollinger(20,2)
ATR(14)
Volume ratio

RULES
EMA20 > EMA50       TRUE
RSI > 70            FALSE
RSI < 30            FALSE
MACD > Signal       TRUE
Price > BB Middle   TRUE
Volume > 1.5x       FALSE

RESULT
Bullish technical bias

CONFIDENCE
0.64

DATA QUALITY
PASS
```

This is transparent and debuggable.

---

# 11. Phase 4 — API Call Inspector

Every external API call should be visible.

Create an API Inspector panel.

```text
API CALLS

Time       Provider   Endpoint          Status   Latency
----------------------------------------------------------
16:48:02   Alpaca     latest_quote      200      124ms
16:48:02   Alpaca     historical_bars   200      241ms
16:48:03   Finnhub    profile           200      310ms
16:48:03   Finnhub    news              200      422ms
16:48:04   Gemini     generate          200      1.4s
```

Click an event:

```text
ALPACA
Endpoint: historical_bars
Symbol: AAPL
Feed: IEX
Timeframe: 1Day
Start: ...
End: ...
Records: 250
Status: 200
Latency: 241ms

DATA QUALITY
✓ Authentication
✓ Response
✓ Records
✓ Timestamp
✓ Required OHLCV fields
```

---

# 12. Phase 5 — Data Quality System

An API returning HTTP 200 does NOT necessarily mean the data is usable.

Every dataset should be validated.

## Market data checks

```text
✓ Data exists
✓ Correct symbol
✓ At least N bars
✓ Timestamps valid
✓ Timestamps ordered
✓ No duplicate timestamps
✓ Open is valid
✓ High >= Low
✓ Close is valid
✓ Volume is non-negative
✓ Latest bar is sufficiently fresh
```

Result:

```json
{
  "status": "PASS",
  "bars": 250,
  "missing_values": 0,
  "duplicates": 0,
  "freshness_seconds": 14
}
```

---

# 13. Phase 6 — Explain Every HOLD

This is one of the highest-priority changes.

The system should never return:

```text
HOLD
```

by itself.

Instead:

```text
HOLD

Confidence: 0.31

Why:
- Momentum is neutral
- Trend is mildly bullish
- Mean reversion is neutral
- News sentiment is neutral
- Fundamentals provide no strong catalyst
- Risk is acceptable
- Overall score does not exceed BUY threshold

BUY threshold: +1.5
Current score: +0.58

SELL threshold: -1.5
Current score: +0.58
```

---

# 14. Strategy Decision Cards

Each strategy should become independently inspectable.

## Momentum

```text
MOMENTUM STRATEGY

Price Change       +1.2%
Volume Ratio       0.87x
RSI                 53.2
MACD                Bullish

Rules:
Price momentum      PASS
Volume confirmation FAIL
RSI alignment       PASS
MACD alignment      PASS

Vote: BUY
Confidence: 0.55
```

Do this for all five strategies.

---

# 15. Phase 7 — Score Calculation Transparency

The current execution formula should be displayed.

Current architecture:

```text
agent_score
strategy_score

combined =
    agent_score * 0.6
    +
    strategy_score * 1.5
```

Expose the calculation.

Example:

```text
AGENT SCORE

Technical       +0.40
Fundamental     +0.00
News            +0.10
Risk            -0.05
Portfolio       +0.00

Agent Score     +0.45

× 0.60
= +0.27


STRATEGY SCORE

Momentum        +0.20
Trend           +0.55
Mean Reversion  +0.10
Breakout        +0.05
Swing           +0.35

Strategy Score  +0.25

× 1.50
= +0.38


TOTAL
+0.27 + +0.38
= +0.65

BUY threshold:  +1.50
SELL threshold: -1.50

RESULT: HOLD
```

This will probably reveal why you're seeing so many HOLD decisions.

---

# 16. Phase 8 — Find Out Why HOLD Happens

Add statistics.

Dashboard:

```text
DECISION STATISTICS
────────────────────────────

Last 100 analyses

BUY       7%
SELL      3%
HOLD     90%

HOLD REASONS

Below confidence threshold      42
Mixed strategy signals           28
No technical catalyst            14
Risk gate                        9
Insufficient data                4
Existing position                3
```

This is extremely important.

You may discover that the system isn't "bad at trading."

It may simply be that your thresholds make BUY/SELL mathematically rare.

---

# 17. Phase 9 — Autonomous Loop Monitor

The 180-second loop should have its own dashboard.

```text
AUTONOMOUS TRADING

Status: RUNNING 🟢

Interval: 180 seconds

Symbols:
AAPL

Last Run:
16:48:00

Next Run:
16:51:00

Runs:
Today: 42

Successful:
40

Warnings:
1

Errors:
1

BUY:
3

SELL:
1

HOLD:
36
```

Click:

```text
RUN #41
AAPL
16:45:00
Duration: 3.7 seconds
Status: WARNING

Market Data       PASS
Technical         PASS
Fundamentals      PASS
News              WARNING
Risk              PASS
Portfolio         PASS
Strategies        PASS
Execution         PASS

Warning:
Finnhub returned no new articles.
```

---

# 18. Phase 10 — Run Detail Page

Clicking any run should open a complete report.

Route:

```text
/run/<run_id>
```

Sections:

1. Overview
2. API Calls
3. Market Data
4. Technical Analysis
5. Fundamentals
6. News
7. Risk
8. Portfolio
9. Strategies
10. Execution
11. Order
12. Errors
13. Timing
14. Decision Trace

---

# 19. Phase 11 — Persistent Run History

Do not only keep the communication log in memory.

Create:

```text
memory/
    runs/
        2026-08-08/
            RUN-20260808-164800-AAPL.json
            RUN-20260808-164500-AAPL.json
```

Or preferably use SQLite:

```text
data/trading_system.db
```

Tables:

```text
runs
events
api_calls
agent_results
strategy_votes
decisions
orders
errors
```

SQLite would be a major improvement over large JSON files once the project grows.

---

# 20. Phase 12 — Error Tracking

Create a centralized error system.

Every error should contain:

```json
{
  "run_id": "...",
  "agent": "NewsAgent",
  "provider": "Finnhub",
  "error_type": "RateLimitError",
  "status_code": 429,
  "message": "...",
  "timestamp": "...",
  "retry_count": 3,
  "recovered": false
}
```

Dashboard:

```text
ERRORS

🔴 16:42 Finnhub 429
🟡 16:38 Alpaca timeout
🟡 15:31 Gemini retry
🟢 15:31 Gemini recovered
```

---

# 21. Phase 13 — Data Source Registry

Create one place describing every external source.

```text
DATA SOURCES

ALPACA
Purpose:
Market prices / bars / quotes / trades / account / orders

Feed:
IEX

Status:
CONNECTED

FINNHUB
Purpose:
Fundamentals / company profile / news

Status:
CONNECTED

GEMINI
Purpose:
Natural-language reasoning / reflections

Status:
CONNECTED
```

This lets you immediately identify missing services.

---

# 22. Phase 14 — Market Data Improvements

Prioritize this before adding more agents.

## Add

* explicit IEX configuration
* data freshness
* feed reporting
* bar-count validation
* missing-bar detection
* timestamp validation
* pagination
* request timing
* rate-limit tracking
* response caching
* stale-cache detection
* market-hours awareness

Alpaca's historical bars endpoint supports multiple timeframes from minute through month-level intervals.

The API also uses pagination through `next_page_token`, so historical-data retrieval should not assume one request contains everything.

---

# 23. Phase 15 — Stop Repeating Identical Data

Because the loop runs every 180 seconds, determine whether the system is actually getting new information.

Each run should show:

```text
PREVIOUS RUN
Price: $XXX.XX
Bar timestamp: 16:45:00

CURRENT RUN
Price: $XXX.XX
Bar timestamp: 16:48:00

DATA CHANGED
YES

NEW BARS
3
```

If:

```text
NEW BARS: 0
```

the system should report:

```text
⚠ Market data unchanged since previous run.
```

This will help identify stale data and caching problems.

---

# 24. Phase 16 — Technical Analysis Improvements

Add more diagnostic information.

Current:

```text
RSI = 53
```

Desired:

```text
RSI(14)
Value: 53.2
Previous: 49.8
Direction: rising
Zone: neutral

Rule:
RSI < 30 → oversold       FALSE
RSI > 70 → overbought     FALSE

Signal:
NEUTRAL
```

Do the same for:

* MACD
* EMA
* Bollinger Bands
* ATR
* Volume

---

# 25. Phase 17 — Fundamentals Improvements

Current fundamentals are too shallow.

Eventually add:

* revenue growth
* EPS growth
* earnings surprises
* profit margins
* debt/equity
* free cash flow
* price/sales
* price/book
* forward PE
* dividend information
* analyst estimates
* earnings date

But do NOT add all of this before observability is finished.

First make sure the current data is actually arriving correctly.

---

# 26. Phase 18 — News Improvements

Current keyword sentiment is extremely basic.

Eventually add:

* article timestamp
* source
* headline
* URL
* company relevance
* sentiment
* sentiment strength
* article count
* recent vs old news
* duplicate detection

Example:

```text
NEWS

14 articles
9 positive
3 neutral
2 negative

Weighted sentiment: +0.42

Most recent:
16:31

Oldest:
08:14

News freshness:
GOOD
```

---

# 27. Phase 19 — Strategy Improvements

Do not immediately add more strategies.

First make the five strategies measurable.

For each strategy track:

```text
Total signals
BUY
SELL
HOLD
Average confidence
Win rate
Average return
Maximum drawdown
Profit factor
```

Example:

```text
MOMENTUM

Signals: 420
BUY: 172
SELL: 83
HOLD: 165

Backtest return: +7.2%
Win rate: 54%
Max drawdown: -9.1%
```

This allows you to determine which strategies actually contribute value.

---

# 28. Phase 20 — Backtesting Realism

Upgrade the backtester.

Add:

* slippage
* spread
* commissions/fees
* partial fills
* realistic fills
* market-hours constraints
* delayed execution
* position limits
* stop losses
* take profits
* maximum position size
* portfolio-level risk

Avoid using future information.

The backtest must guarantee:

```text
Decision timestamp
        ↓
ONLY DATA AVAILABLE AT THAT TIME
        ↓
Signal
        ↓
Execution
```

---

# 29. Phase 21 — Walk-Forward Testing

Do not optimize on the entire historical dataset.

Use:

```text
TRAIN
2022 ───── 2024

VALIDATION
2025

TEST
2026
```

Then rotate the windows.

This reduces overfitting.

---

# 30. Phase 22 — Risk Controls

Before autonomous trading becomes more sophisticated, add hard safety limits.

Required:

```text
MAX_POSITION_NOTIONAL
MAX_DAILY_LOSS
MAX_DRAWDOWN
MAX_TRADES_PER_DAY
MAX_SYMBOL_EXPOSURE
MAX_PORTFOLIO_EXPOSURE
```

Example:

```env
MAX_POSITION_NOTIONAL=500
MAX_DAILY_LOSS=100
MAX_DRAWDOWN=0.05
MAX_TRADES_PER_DAY=10
```

---

# 31. Phase 23 — Kill Switch

Add:

```text
EMERGENCY STOP
```

The system should immediately stop autonomous trading.

Also automatically stop if:

```text
Daily loss limit reached
Too many API failures
Market data becomes stale
Account API unavailable
Unexpected position detected
Repeated order rejection
System error rate too high
```

---

# 32. Phase 24 — Order Lifecycle Tracking

Currently the system focuses heavily on the decision.

The order lifecycle needs equal visibility.

Track:

```text
Decision
 ↓
Order Created
 ↓
Submitted
 ↓
Accepted
 ↓
Partially Filled
 ↓
Filled
```

or:

```text
Submitted
 ↓
Rejected
```

Show:

```text
ORDER

Symbol: AAPL
Side: BUY
Quantity: 10
Notional: $1,850

Order ID:
xxxxxxxx

Status:
FILLED

Submitted:
16:49:02

Filled:
16:49:04

Fill Price:
$185.00
```

---

# 33. Phase 25 — Agent Performance

Eventually track whether individual agents are useful.

Example:

```text
AGENT PERFORMANCE

Technical Agent
Accuracy: 56%

Fundamental Agent
Accuracy: 52%

News Agent
Accuracy: 54%

Momentum Strategy
Accuracy: 57%

Trend Strategy
Accuracy: 55%

Mean Reversion
Accuracy: 49%
```

Do not assume an agent is useful because its reasoning sounds intelligent.

Measure it.

---

# 34. Phase 26 — Decision Calibration

Confidence currently appears to be:

```text
confidence = abs(score) / 4
```

That does not automatically mean:

```text
0.75 confidence = 75% probability of winning
```

Eventually calibrate confidence using historical outcomes.

For example:

```text
Predicted confidence: 0.70
Actual win rate: 0.54
```

Then the system knows its confidence is poorly calibrated.

---

# 35. Phase 27 — Dashboard Layout

Recommended final dashboard:

```text
┌──────────────────────────────────────────────────────────────┐
│ MULTI-AGENT TRADING CONTROL CENTER                           │
├──────────────────────────────────────────────────────────────┤
│ Account │ System Health │ Loop │ AAPL │ Last Decision       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│                 LIVE AGENT GROUP CHAT                        │
│                                                              │
│  ORCHESTRATOR                                                │
│  MARKET AGENT                                                │
│  TECHNICAL AGENT                                             │
│  FUNDAMENTAL AGENT                                           │
│  NEWS AGENT                                                  │
│  RISK AGENT                                                  │
│  PORTFOLIO AGENT                                             │
│  STRATEGIES                                                  │
│  EXECUTION AGENT                                             │
│                                                              │
├───────────────────────────┬──────────────────────────────────┤
│ API MONITOR               │ DECISION TRACE                  │
│                           │                                  │
│ Alpaca       🟢           │ Score: +0.65                    │
│ Finnhub      🟢           │ Confidence: 0.16               │
│ Gemini       🟢           │                                  │
│                           │ BUY: +1.50                      │
│ Calls: 7                   │ SELL: -1.50                    │
│ Errors: 0                  │                                  │
├───────────────────────────┴──────────────────────────────────┤
│ STRATEGY VOTES                                               │
│                                                              │
│ Momentum       HOLD                                          │
│ Trend          BUY                                           │
│ Mean Reversion HOLD                                          │
│ Breakout       HOLD                                          │
│ Swing          BUY                                           │
├──────────────────────────────────────────────────────────────┤
│ FINAL DECISION: HOLD                                        │
└──────────────────────────────────────────────────────────────┘
```

---

# 36. Phase 28 — Run Report

Every completed run should produce a report.

Example:

```text
RUN REPORT
AAPL
2026-08-08 16:48

STATUS
SUCCESS

DURATION
4.82 seconds

DATA
Alpaca IEX
250 bars
Freshness: 8 seconds

FUNDAMENTALS
Finnhub
PASS

NEWS
Finnhub
12 articles
Neutral

TECHNICAL
Bullish: 3
Bearish: 1
Neutral: 4

STRATEGIES

Momentum       HOLD
Trend          BUY
Mean Reversion HOLD
Breakout       HOLD
Swing          BUY

RISK
LOW

PORTFOLIO
No existing AAPL position

FINAL
HOLD

SCORE
+0.65

BUY THRESHOLD
+1.50

SELL THRESHOLD
-1.50

ORDER
NONE

REASON
Insufficient signal strength.
```

---

# 37. Phase 29 — Daily System Report

Add:

```text
/api/report/daily
```

Report:

```text
DAILY SYSTEM REPORT

Runs: 480
Successful: 472
Warnings: 6
Errors: 2

BUY: 21
SELL: 12
HOLD: 439

API HEALTH
Alpaca: 99.8%
Finnhub: 98.2%
Gemini: 99.4%

Average analysis time:
4.2 seconds

Average data age:
11 seconds

Orders:
14

Filled:
13

Rejected:
1

Paper P/L:
+$42.13
```

---

# 38. Phase 30 — Automated Testing

Add unit tests for:

```text
Indicators
Strategies
Risk
Execution
Data validation
Caching
API error handling
Order handling
Autonomous loop
```

Add integration tests:

```text
Alpaca → MarketAgent
MarketAgent → TechnicalAgent
All agents → ExecutionAgent
ExecutionAgent → Paper Alpaca
```

---

# 39. Phase 31 — Failure Simulation

This is critical.

Intentionally simulate:

```text
Alpaca unavailable
Finnhub unavailable
Gemini unavailable
HTTP 401
HTTP 403
HTTP 429
Timeout
Empty response
Malformed JSON
Missing price
Missing bars
Stale data
Duplicate bars
```

The system should remain operational and explain what happened.

---

# 40. Phase 32 — Replace Silent Failures

Bad:

```python
except Exception:
    return {}
```

Better:

```python
except Exception as e:
    event_logger.error(
        run_id=run_id,
        agent="NewsAgent",
        provider="Finnhub",
        error=str(e)
    )

    return {
        "status": "error",
        "error": str(e)
    }
```

Never silently convert a failed data source into neutral data.

Otherwise:

```text
API FAILURE
```

can accidentally become:

```text
NEUTRAL SIGNAL
```

and contaminate the trading decision.

---

# 41. Phase 33 — Data Availability Gates

Every agent should report:

```text
AVAILABLE
PARTIAL
STALE
EMPTY
ERROR
```

Example:

```text
Market Data: PASS
Technical: PASS
Fundamentals: PARTIAL
News: ERROR
Risk: PASS
Portfolio: PASS
```

Then ExecutionAgent can enforce:

```text
If critical data is unavailable:
    DO NOT AUTOTRADE
```

This is safer than treating missing data as HOLD.

---

# 42. Phase 34 — Decision Confidence Gates

Before an autonomous trade:

```text
Data Quality       PASS
Market Freshness   PASS
Risk               PASS
Portfolio          PASS
Strategy Agreement PASS
Confidence         >= threshold
Daily Loss         < limit
Trade Count        < limit
Kill Switch        OFF
```

Only then:

```text
ALLOW ORDER
```

---

# 43. Phase 35 — Free-Tier Optimization

Because the project is currently using free services, optimize API usage before paying for anything.

## Use caching

Cache:

* historical bars
* company profiles
* fundamentals
* news
* indicators

But display cache age.

Example:

```text
Finnhub Profile
Source: CACHE
Age: 31 minutes
```

instead of pretending it is fresh.

## Batch requests

Where supported, request multiple symbols together.

## Avoid redundant calls

If MarketAgent already downloaded bars, TechnicalAgent should use those bars instead of requesting them again.

---

# 44. Phase 36 — Market Data Architecture

Use:

```text
                    MARKET DATA
                         │
              ┌──────────┴──────────┐
              │                     │
           Alpaca                Finnhub
              │                     │
         IEX market data       Fundamentals
              │                 News
              │
              ▼
       MarketDataProvider
              │
       ┌──────┴───────┐
       │              │
     Cache        Validation
       │              │
       └──────┬───────┘
              │
          MarketSnapshot
              │
      ┌───────┼────────┐
      ▼       ▼        ▼
 Technical  Risk    Strategies
```

---

# 45. Phase 37 — Architecture Cleanup

Eventually consolidate duplicate Alpaca code.

Current:

```text
data/providers/alpaca.py
data/alpaca_data.py
trading_agent.py
market_data_agent.py
```

Create one canonical Alpaca service:

```text
services/
    alpaca_service.py
    finnhub_service.py
    gemini_service.py
```

Agents should use services.

Agents should NOT each implement their own API behavior.

---

# 46. Phase 38 — Separate Research From Execution

Create two modes.

## Research Mode

```text
Analyze
Backtest
Compare strategies
Generate reports
No orders
```

## Paper Trading Mode

```text
Analyze
Risk check
Decision
Order
Track fill
```

Eventually:

```text
LIVE MODE
```

should remain disabled until the system has passed extensive testing.

---

# 47. Phase 39 — New Recommended Project Structure

Eventually:

```text
project/
│
├── app.py
├── config.py
├── requirements.txt
│
├── agents/
│   ├── market_agent.py
│   ├── technical_agent.py
│   ├── fundamental_agent.py
│   ├── news_agent.py
│   ├── risk_agent.py
│   ├── portfolio_agent.py
│   └── execution_agent.py
│
├── strategies/
│   ├── momentum.py
│   ├── trend_following.py
│   ├── mean_reversion.py
│   ├── breakout.py
│   └── swing.py
│
├── services/
│   ├── alpaca_service.py
│   ├── finnhub_service.py
│   └── gemini_service.py
│
├── data/
│   ├── models.py
│   ├── cache.py
│   ├── validation.py
│   └── database.py
│
├── observability/
│   ├── events.py
│   ├── run_tracker.py
│   ├── metrics.py
│   ├── health.py
│   └── logger.py
│
├── backtesting/
│   ├── engine.py
│   ├── execution.py
│   ├── slippage.py
│   └── metrics.py
│
├── memory/
│   ├── trade_history.py
│   ├── reflections.py
│   └── vector_store.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── failure/
│
├── scripts/
│   ├── health_check.py
│   ├── test_alpaca.py
│   └── test_pipeline.py
│
└── templates/
    ├── index.html
    ├── run.html
    └── health.html
```

---

# 48. Priority Roadmap

Do NOT implement everything simultaneously.

## PRIORITY 1 — OBSERVABILITY

Must do first.

```text
[ ] Run IDs
[ ] Event logger
[ ] API call logging
[ ] Agent event logging
[ ] Error logging
[ ] Data quality logging
[ ] Decision trace
[ ] Group chat UI
[ ] Run history
```

---

## PRIORITY 2 — MARKET DATA CORRECTNESS

```text
[ ] Explicit IEX configuration
[ ] Feed displayed in UI
[ ] Data freshness
[ ] Bar validation
[ ] Empty response detection
[ ] Stale data detection
[ ] Pagination
[ ] Cache age
[ ] API latency
```

---

## PRIORITY 3 — EXPLAINABLE DECISIONS

```text
[ ] Explain HOLD
[ ] Show strategy votes
[ ] Show strategy rules
[ ] Show agent scores
[ ] Show execution formula
[ ] Show thresholds
[ ] Show risk gates
[ ] Show portfolio gates
```

---

## PRIORITY 4 — SYSTEM HEALTH

```text
[ ] Alpaca health
[ ] Finnhub health
[ ] Gemini health
[ ] API rate-limit monitoring
[ ] Error dashboard
[ ] Autonomous-loop monitor
[ ] Daily system report
```

---

## PRIORITY 5 — SAFETY

```text
[ ] Daily loss limit
[ ] Maximum drawdown
[ ] Maximum position size
[ ] Maximum trades/day
[ ] Kill switch
[ ] Stale-data trade blocker
[ ] API-failure trade blocker
```

---

## PRIORITY 6 — BACKTESTING

```text
[ ] Slippage
[ ] Spread
[ ] Realistic fills
[ ] Trading hours
[ ] Position limits
[ ] Walk-forward testing
[ ] Out-of-sample testing
[ ] Strategy performance statistics
```

---

## PRIORITY 7 — STRATEGY IMPROVEMENT

```text
[ ] Strategy performance tracking
[ ] Signal quality analysis
[ ] Confidence calibration
[ ] Better news analysis
[ ] Better fundamentals
[ ] Macro data
[ ] SEC filings
```

---

# 49. Definition of Done

The project should NOT be considered "working" simply because:

```text
python app.py
```

works.

The system is considered operational when:

### Data

```text
✓ Alpaca connected
✓ Correct feed identified
✓ Market data validated
✓ Data freshness known
✓ No silent API failures
```

### Agents

```text
✓ Every agent reports status
✓ Every agent reports inputs
✓ Every agent reports outputs
✓ Errors are visible
✓ Missing data is visible
```

### Strategies

```text
✓ Every strategy reports vote
✓ Every strategy reports confidence
✓ Rule evaluations are visible
✓ Strategy performance is measured
```

### Execution

```text
✓ Score calculation visible
✓ Threshold visible
✓ Risk gates visible
✓ Portfolio gates visible
✓ Decision explanation visible
```

### Orders

```text
✓ Submitted orders tracked
✓ Rejected orders tracked
✓ Filled orders tracked
✓ Order IDs stored
✓ Fill prices stored
```

### Autonomous Loop

```text
✓ Current run visible
✓ Previous run visible
✓ Next run visible
✓ Errors visible
✓ API calls visible
✓ Run duration visible
```

---

# 50. First Implementation Sprint

Do not start by adding more trading strategies.

Implement this exact sprint first:

## Sprint 1

### Step 1

Create:

```text
observability/events.py
```

### Step 2

Create:

```text
RunContext
```

containing:

```python
run_id
symbol
started_at
status
events
errors
```

### Step 3

Modify every agent:

```python
analyze(symbol, context)
```

instead of:

```python
analyze(symbol)
```

### Step 4

Log every external API call.

### Step 5

Log every agent start/end.

### Step 6

Log every strategy vote.

### Step 7

Log every score calculation.

### Step 8

Log every order attempt.

### Step 9

Store the completed run.

### Step 10

Build the Group Chat UI.

---

# 51. The First Dashboard Goal

The first version does not need to look beautiful.

It needs to answer these questions immediately:

```text
1. Is Alpaca working?

2. Which market-data feed am I using?

3. Did Alpaca actually return data?

4. How many bars did I receive?

5. How old is the data?

6. Did TechnicalAgent calculate indicators?

7. Did Finnhub return fundamentals?

8. Did Finnhub return news?

9. Did RiskAgent find anything?

10. What did every strategy vote?

11. What score did each strategy produce?

12. How was the final score calculated?

13. Why was the result HOLD?

14. Was an order considered?

15. If no order happened, why?

16. Did anything fail?

17. How long did the whole run take?
```

If the dashboard can answer all 17 questions, the project becomes dramatically easier to debug.

---

# 52. Final Architecture

The ultimate system should look like this:

```text
                         USER
                          │
                          ▼
                 ┌─────────────────┐
                 │    DASHBOARD    │
                 └────────┬────────┘
                          │
              ┌───────────┴────────────┐
              │                        │
              ▼                        ▼
       LIVE GROUP CHAT          SYSTEM HEALTH
              │                        │
              └───────────┬────────────┘
                          ▼
                    ORCHESTRATOR
                          │
                   RUN CONTEXT
                          │
          ┌───────────────┼────────────────┐
          │               │                │
          ▼               ▼                ▼
     DATA SOURCES       AGENTS         PORTFOLIO
          │               │                │
   ┌──────┼──────┐   ┌────┼─────┐          │
   │      │      │   │    │     │          │
Alpaca Finnhub Gemini Tech News Risk      Alpaca
   │      │      │   │    │     │          │
   └──────┴──────┴───┴────┴─────┴──────────┘
                          │
                          ▼
                     STRATEGIES
                          │
                          ▼
                  EXECUTION ENGINE
                          │
                  ┌───────┴───────┐
                  │               │
               NO TRADE         TRADE
                  │               │
                  ▼               ▼
              REPORT          ALPACA PAPER
                                  │
                                  ▼
                              ORDER EVENT
                                  │
                                  ▼
                             TRADE HISTORY

ALL COMPONENTS
       │
       ▼
 OBSERVABILITY
       │
 ┌─────┼───────────┐
 ▼     ▼           ▼
Events API Logs  Errors
       │
       ▼
 RUN DATABASE
       │
       ▼
 HISTORICAL REPORTS
```

---

# 53. Long-Term Vision

The goal is not simply:

> "Build an AI that trades."

The better goal is:

> **Build a research system where every trading decision can be reconstructed, tested, measured, and challenged.**

That means the system should eventually allow you to select any historical run and reconstruct:

```text
What did the system know?
        ↓
Where did that information come from?
        ↓
Was the information fresh?
        ↓
What calculations were performed?
        ↓
What rules fired?
        ↓
What did each strategy vote?
        ↓
How were votes combined?
        ↓
What risk controls were applied?
        ↓
Why was the final decision made?
        ↓
Was an order submitted?
        ↓
What happened to that order?
        ↓
What happened afterward?
        ↓
Was the decision actually good?
```

That is the real next stage of this project.

---

# 54. Immediate Recommendation

**Do not buy Alpaca's paid market-data plan yet.**

First:

1. Explicitly configure the free IEX feed.
2. Verify that your MarketAgent is actually receiving data.
3. Add run IDs.
4. Add API-call logging.
5. Add data-quality checks.
6. Build the agent group-chat interface.
7. Make every strategy expose its vote and rule results.
8. Make the HOLD decision mathematically transparent.
9. Add a system-health page.
10. Run the system for several days and collect statistics.
11. Only then decide whether better market-data coverage is actually necessary.

Alpaca's current documentation confirms that the free/basic plan is sufficient for initial development and research, while the paid plan is mainly valuable when you need full consolidated real-time stock coverage and higher data limits.

For your current project, **better observability will probably teach you more than paying for better data right now.**

---

# 55. Success Metric

The final test should be:

> Pick any HOLD decision from three days ago.

Then the system should be able to show you the complete run and answer:

**"Why did you HOLD?"**

without you opening the Python source code.

That is the milestone this project should work toward.
