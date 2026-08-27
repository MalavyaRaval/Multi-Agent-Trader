import os
import re
import json

import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_from_directory

from agents.technical_agent import TechnicalAgent
from agents.execution_agent import HOLD_REASON_LABELS
from agents.market_agent import MARKET_DATA_FEED, get_rate_limit_status, is_market_hours_now
from config import FINNHUB_API_KEY, GEMINI_API_KEY
from data.alpaca_client import has_alpaca_credentials
from llm.gemini_client import MODEL_NAME as GEMINI_MODEL_NAME
from indicators.ema import compute_ema_series
from indicators.macd import compute_macd_series
from indicators.bollinger import compute_bollinger_series
from indicators.rsi import compute_rsi_series
from market_data_agent import run_turn as run_market_data_agent_turn
from trading_agent import get_account_info as get_trading_account_info
from trading_agent import run_turn as run_trading_agent_turn
from orchestrator import get_orchestrator
from agents.portfolio_agent import PortfolioAgent
from memory.trade_history import TradeHistory
from agents.screener_agent import ScreenerAgent
from backtesting.engine import BacktestEngine
from backtesting.report import generate_report
from optimization.ensemble import StrategyEnsemble
from memory.vector_store import VectorStore
from memory.reflections import ReflectionEngine
from sizing import target_volatility_size, risk_parity_size, half_kelly
from reporting.daily_report import build_daily_report

from visualization.portfolio import (
    get_all_fills,
    get_stock_bars,
    get_range_start,
    get_portfolio_history,
    clamp_range_start_to_available_data,
    build_position_history,
    build_performance_dataframe,
    create_trade_markers_data,
    summarize_portfolio_period,
    utc_now,
    TIMEFRAME_BY_RANGE,
)

# Canonical chart-mode alias table for /api/portfolio_chart. Every accepted
# query-string spelling maps to exactly one of: return, normalized, price,
# value, pnl, marketcap. Downstream code only ever compares against these
# canonical tokens, never against alias spellings.
CHART_MODE_ALIASES = {
    "percent": "return",
    "pct": "return",
    "percent_change": "return",
    "percentage": "return",
    "return": "return",
    "normalized": "normalized",
    "normalized_price": "normalized",
    "price_index": "normalized",
    "price": "price",
    "actual_price": "price",
    "value": "value",
    "portfolio": "value",
    "portfolio_value": "value",
    "pnl": "pnl",
    "profit_loss": "pnl",
    "dollar_profit_loss": "pnl",
    "dollar_pnl": "pnl",
    "marketcap": "marketcap",
    "market_cap": "marketcap",
    "market_cap_adjusted": "marketcap",
    "marketcap_adjusted": "marketcap",
}

app = Flask(__name__)
technical_agent = TechnicalAgent()
portfolio_agent = PortfolioAgent()
orchestrator = get_orchestrator()
trade_history = TradeHistory()
screener = ScreenerAgent()
ensemble = StrategyEnsemble()
vector_store = VectorStore()
reflection_engine = ReflectionEngine()

# Keep track of previous interaction IDs for each agent
previous_trading_agent_interaction_id = None
previous_market_data_agent_interaction_id = None


def _extract_symbol(message: str) -> str:
    if not message:
        return "AAPL"
    matches = re.findall(r"\b([A-Z]{1,5})\b", message.upper())
    return matches[0] if matches else "AAPL"


def _format_technical_response(result: dict) -> str:
    if result.get("status") != "technical analysis ready":
        return result.get("error") or result.get("status") or "Technical analysis unavailable."

    signals = result.get("signals", {}) or {}
    parts = [f"Technical snapshot for {result['symbol']}:"]
    if signals.get("change_percent") is not None:
        parts.append(f"Change: {signals['change_percent']:+.2f}%")
    if signals.get("relative_volume") is not None:
        parts.append(f"Relative volume: {signals['relative_volume']:.2f}x")
    if signals.get("rsi_14") is not None:
        parts.append(f"RSI(14): {signals['rsi_14']:.2f}")
    if signals.get("ema_20") is not None:
        parts.append(f"EMA(20): {signals['ema_20']:.2f}")
    if signals.get("macd") is not None:
        parts.append(f"MACD: {signals['macd']:.2f}")
    return " | ".join(parts)


@app.route("/")
def index():
    account_info = get_trading_account_info()
    return render_template("index.html", account_info=account_info)


@app.route("/favicon.ico")
def favicon():
    static_dir = os.path.join(app.root_path, "static")
    return send_from_directory(static_dir, "favicon.svg", mimetype="image/svg+xml")


@app.route("/chat", methods=["POST"])
def chat():
    global previous_trading_agent_interaction_id, previous_market_data_agent_interaction_id

    user_message = request.json.get("message")
    agent_id = request.json.get("agent_id")

    response_text = ""
    payload = {"response": response_text}

    if agent_id == "trading_agent":
        response_text, previous_trading_agent_interaction_id = run_trading_agent_turn(
            user_message, previous_trading_agent_interaction_id
        )
    elif agent_id == "market_data_collector":
        response_text, previous_market_data_agent_interaction_id = run_market_data_agent_turn(
            user_message, previous_market_data_agent_interaction_id
        )
    elif agent_id == "technical_agent":
        symbol = _extract_symbol(user_message)
        analysis_result = technical_agent.analyze(symbol=symbol)
        response_text = _format_technical_response(analysis_result)
        payload["technical_signals"] = analysis_result.get("signals")
        payload["symbol"] = analysis_result.get("symbol")
        payload["status"] = analysis_result.get("status")
    else:
        response_text = "Unknown agent."

    payload["response"] = response_text
    return jsonify(payload)


# ---------------------------------------------------------------------------
# Multi-agent orchestration endpoints
# ---------------------------------------------------------------------------

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """Trigger a full multi-agent analysis for a symbol."""
    symbol = request.json.get("symbol", "AAPL")
    result = orchestrator.analyze_symbol(symbol)
    return jsonify(result)


@app.route("/api/chart_data", methods=["POST"])
def api_chart_data():
    """Fetch OHLC bars and indicator series for frontend Chart.js charts."""
    data = request.json or {}
    symbol = data.get("symbol", "AAPL").upper()
    days = data.get("days", 90)
    try:
        from agents.market_agent import MarketAgent

        market = MarketAgent()
        snapshot = market.snapshot(symbol, timeframe="1d", days=days)
        bars = getattr(snapshot, "bars", None)
        if bars is None:
            return jsonify({"status": "error", "error": "No bar data available"}), 404

        frame = technical_agent._coerce_to_frame(bars)
        if frame.empty:
            return jsonify({"status": "error", "error": "Empty bar data"}), 404

        close = pd.to_numeric(frame.get("close", pd.Series(dtype=float)), errors="coerce")
        high = pd.to_numeric(frame.get("high", close), errors="coerce")
        low = pd.to_numeric(frame.get("low", close), errors="coerce")
        open_p = pd.to_numeric(frame.get("open", close), errors="coerce")
        volume = pd.to_numeric(frame.get("volume", pd.Series(0, index=close.index)), errors="coerce")

        # Same indicator math the technical agent uses for live signals, so the
        # chart panel and the trading decisions never disagree on indicator values.
        ema20 = compute_ema_series(close, 20)
        ema50 = compute_ema_series(close, 50)
        macd_line, macd_signal, macd_hist = compute_macd_series(close)
        bb_upper, bb_lower, _bb_mid = compute_bollinger_series(close, 20)
        rsi_series = compute_rsi_series(close, 14)

        # Dates
        dates = []
        if "timestamp" in frame.columns:
            dates = [str(ts)[:10] for ts in frame["timestamp"]]
        elif isinstance(frame.index, pd.DatetimeIndex):
            dates = [str(ts)[:10] for ts in frame.index]
        else:
            dates = [f"Day {i+1}" for i in range(len(frame))]

        def clean_series(s):
            return [None if (pd.isna(x) or np.isinf(x)) else round(float(x), 2) for x in s]

        return jsonify({
            "status": "ok",
            "symbol": symbol,
            "dates": dates,
            "close": clean_series(close),
            "open": clean_series(open_p),
            "high": clean_series(high),
            "low": clean_series(low),
            "volume": clean_series(volume),
            "rsi": clean_series(rsi_series),
            "ema20": clean_series(ema20),
            "ema50": clean_series(ema50),
            "macd": clean_series(macd_line),
            "macd_signal": clean_series(macd_signal),
            "macd_hist": clean_series(macd_hist),
            "bollinger_upper": clean_series(bb_upper),
            "bollinger_lower": clean_series(bb_lower),
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/diagnostics", methods=["GET"])
def api_diagnostics():
    """PHASES_PLAN.md Phase 13 -- Data Source Registry: one place describing
    every external source (purpose, feed, connection status) so a missing
    service is immediately visible instead of discovered mid-analysis."""
    alpaca_configured = has_alpaca_credentials()
    finnhub_key = bool(FINNHUB_API_KEY)
    gemini_key = bool(GEMINI_API_KEY)

    alpaca_status = "connected" if alpaca_configured else "missing_keys"
    finnhub_status = "connected" if finnhub_key else "missing_key"
    gemini_status = "connected" if gemini_key else "missing_key"

    return jsonify({
        "status": "ok",
        "services": {
            "alpaca": {
                "name": "Alpaca Market & Trading API",
                "purpose": "Market prices / bars / quotes / trades / account / orders",
                "feed": MARKET_DATA_FEED.value.upper(),
                "status": alpaca_status,
                "mode": "Paper Trading (Zero Risk)",
                "keys_configured": alpaca_configured,
                "market_hours_open": is_market_hours_now(),
                "rate_limit": get_rate_limit_status(),
            },
            "finnhub": {
                "name": "Finnhub Fundamentals & News API",
                "purpose": "Fundamentals / company profile / news",
                "status": finnhub_status,
                "keys_configured": finnhub_key,
                "note": "Optional. When missing, fundamental & news agents degrade gracefully to neutral.",
            },
            "gemini": {
                "name": "Google Gemini LLM Engine",
                "purpose": "Natural-language reasoning / reflections",
                "status": gemini_status,
                "keys_configured": gemini_key,
                "model": GEMINI_MODEL_NAME,
                "note": "Used for chat, trade reflections, and executive reasoning synthesis.",
            },
        }
    })


@app.route("/api/messages", methods=["GET"])
def api_messages():
    """Poll for new inter-agent messages with optional filtering."""
    since = request.args.get("since", type=int, default=0)
    session_id = request.args.get("session_id")
    category = request.args.get("category")
    symbol = request.args.get("symbol")
    messages = orchestrator.bus.get_messages(
        since_index=since, session_id=session_id, category=category, symbol=symbol
    )
    return jsonify({"messages": messages, "next_index": since + len(messages)})


@app.route("/api/sessions", methods=["GET"])
def api_sessions():
    """Get list of all analysis sessions recorded."""
    sessions = orchestrator.bus.get_sessions()
    return jsonify({"sessions": sessions})


@app.route("/api/runs", methods=["GET"])
def api_runs():
    """PHASES_PLAN.md Phase 10 -- lightweight index of recent runs (for a run list)."""
    limit = request.args.get("limit", type=int, default=50)
    return jsonify({"runs": orchestrator.list_recent_runs(limit=limit)})


@app.route("/api/run/<run_id>", methods=["GET"])
def api_run_detail(run_id):
    """PHASES_PLAN.md Phase 10 -- full 14-section detail for one run."""
    detail = orchestrator.get_run_detail(run_id)
    if detail is None:
        return jsonify({"status": "error", "error": f"Run {run_id} not found."}), 404
    return jsonify(detail)


@app.route("/api/errors", methods=["GET"])
def api_errors():
    """PHASES_PLAN.md Phase 12 -- Error Tracking: recent errors across all runs."""
    limit = request.args.get("limit", type=int, default=50)
    return jsonify({"errors": orchestrator.list_recent_errors(limit=limit)})


@app.route("/run/<run_id>")
def run_detail_page(run_id):
    """PHASES_PLAN.md Phase 10 -- Run Detail Page."""
    detail = orchestrator.get_run_detail(run_id)
    return render_template("run_detail.html", run_id=run_id, detail=detail)


@app.route("/api/api_calls", methods=["GET"])
def api_api_calls():
    """Return the recorded API events for a run or the most recent active run."""
    run_id = request.args.get("run_id") or getattr(orchestrator, "run_tracker", None)._active_run_id
    if not run_id:
        return jsonify({"run_id": None, "calls": [], "count": 0})

    calls = orchestrator.run_tracker.get_events(run_id)
    api_calls = [
        call for call in calls if call.get("event") == "api_call"
    ]
    return jsonify({
        "run_id": run_id,
        "calls": api_calls,
        "count": len(api_calls),
    })


@app.route("/api/account", methods=["GET"])
def api_account():
    """Get current Alpaca paper account info."""
    try:
        info = portfolio_agent.get_account_summary()
        return jsonify(info or {})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/positions", methods=["GET"])
def api_positions():
    """Get current positions."""
    try:
        result = portfolio_agent.analyze("")
        return jsonify({
            "all_positions": result.get("all_positions", []),
            "account": result.get("account", {}),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/autonomous/start", methods=["POST"])
def api_autonomous_start():
    """Start the autonomous trading loop."""
    symbols = request.json.get("symbols", ["AAPL", "TSLA", "GOOGL"])
    interval = request.json.get("interval_seconds", 300)
    orchestrator.start_autonomous(symbols, interval)
    return jsonify({"status": "started", "symbols": symbols, "interval_seconds": interval})


@app.route("/api/autonomous/stop", methods=["POST"])
def api_autonomous_stop():
    """Stop the autonomous trading loop."""
    orchestrator.stop_autonomous()
    return jsonify({"status": "stopped"})


@app.route("/api/autonomous/status", methods=["GET"])
def api_autonomous_status():
    """PHASES_PLAN.md Phase 9 -- Autonomous Loop Monitor."""
    return jsonify(orchestrator.get_autonomous_status())


@app.route("/api/execute", methods=["POST"])
def api_execute():
    """Execute a trade directly via the execution agent."""
    symbol = request.json.get("symbol", "AAPL")
    side = request.json.get("side", "buy")
    qty = request.json.get("qty")
    notional = request.json.get("notional")
    from agents.execution_agent import ExecutionAgent
    exec_agent = ExecutionAgent()
    result = exec_agent.place_order(symbol, side, qty=qty, notional=notional)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Trade history endpoints
# ---------------------------------------------------------------------------

@app.route("/api/history", methods=["GET"])
def api_history():
    """Get trade and analysis history."""
    limit = request.args.get("limit", type=int, default=50)
    return jsonify(trade_history.get_all(limit=limit))


@app.route("/api/history/stats", methods=["GET"])
def api_history_stats():
    """Get trade history statistics."""
    return jsonify(trade_history.get_stats())


@app.route("/api/stats/decisions", methods=["GET"])
def api_decision_stats():
    """PHASES_PLAN.md Phase 8 -- Find Out Why HOLD Happens.

    BUY/SELL/HOLD breakdown over the last N analyses, and a count per HOLD
    reason bucket, so mostly-HOLD behavior can be explained (mathematically
    rare BUY/SELL thresholds vs. genuinely bad signals) instead of guessed at.
    """
    limit = request.args.get("limit", type=int, default=100)
    try:
        stats = trade_history.get_decision_stats(limit=limit)
        stats["hold_reason_labels"] = {
            code: HOLD_REASON_LABELS.get(code, code)
            for code in stats["hold_reason_counts"]
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Screener endpoints
# ---------------------------------------------------------------------------

@app.route("/api/screen", methods=["POST"])
def api_screen():
    """Run the screener to find top candidates."""
    symbols = request.json.get("symbols")
    top_n = request.json.get("top_n", 10)
    try:
        result = screener.screen(symbols=symbols, top_n=top_n)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Backtesting endpoints
# ---------------------------------------------------------------------------

@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    """Run a backtest on a symbol."""
    symbol = request.json.get("symbol", "AAPL")
    days = request.json.get("days", 252)
    initial_cash = request.json.get("initial_cash", 10000)
    position_size_pct = request.json.get("position_size_pct", 0.1)
    stop_loss_pct = request.json.get("stop_loss_pct", 0.05)
    take_profit_pct = request.json.get("take_profit_pct", 0.10)

    try:
        engine = BacktestEngine(
            initial_cash=initial_cash,
            position_size_pct=position_size_pct,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        )
        result = engine.run(symbol, days=days)
        report = generate_report(engine.to_dict(result))
        return jsonify(report)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Phase 4: Multi-timeframe, ensemble optimization, sizing, vector search
# ---------------------------------------------------------------------------

@app.route("/api/multiframe", methods=["POST"])
def api_multiframe():
    """Run multi-timeframe analysis for a symbol."""
    symbol = request.json.get("symbol", "AAPL")
    auto_execute = request.json.get("auto_execute", False)
    try:
        result = orchestrator.analyze_symbol_multiframe(symbol, auto_execute=auto_execute)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/optimize", methods=["POST"])
def api_optimize():
    """Compute optimal strategy ensemble weights from backtest results."""
    results = request.json.get("results", [])
    metric = request.json.get("metric", "sharpe")  # "sharpe", "win_rate", "return"
    try:
        weights = ensemble.compute_weights(results, metric=metric)
        return jsonify({"status": "ok", "weights": weights, "metric": metric})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/portfolio_chart", methods=["GET"])
def api_portfolio_chart():
    """Return portfolio/position history for the frontend chart."""

    def build_portfolio_payload(portfolio_history, chart_mode):
        portfolio_data = []

        if portfolio_history.empty:
            return portfolio_data

        # chart_mode has already been canonicalized via CHART_MODE_ALIASES by the caller.
        if chart_mode == "value":
            value_column = "equity"
        elif chart_mode == "pnl":
            value_column = "pnl"
        elif chart_mode == "normalized":
            value_column = "normalized"
        elif chart_mode == "marketcap":
            value_column = "market_cap_adj"
        else:
            value_column = "return_pct"

        baseline_equity = None
        if "equity" in portfolio_history.columns:
            valid = portfolio_history["equity"].replace([None, np.nan], pd.NA)
            valid = pd.to_numeric(valid, errors="coerce").dropna()
            if not valid.empty:
                baseline_equity = float(valid.iloc[0])

        for _, row in portfolio_history.iterrows():
            equity = float(row["equity"]) if "equity" in row and pd.notna(row["equity"]) else 0.0
            return_pct = (
                None if pd.isna(row["return_pct"]) else float(row["return_pct"])
            )

            normalized_value = None
            if baseline_equity not in (None, 0):
                normalized_value = (equity / baseline_equity) * 100.0

            pnl_value = None
            if baseline_equity is not None:
                pnl_value = equity - baseline_equity

            value = {
                "equity": equity,
                "return_pct": return_pct,
                "pnl": pnl_value,
                "normalized": normalized_value,
                "market_cap_adj": normalized_value,
            }.get(value_column)

            portfolio_data.append({
                "timestamp": row["timestamp"].isoformat(),
                "equity": equity,
                "return_pct": return_pct,
                "value": (
                    None if value is None or pd.isna(value) else float(value)
                ),
            })

        return portfolio_data

    def chart_response(
        *,
        selected_range,
        chart_mode,
        timeframe=None,
        portfolio_data=None,
        portfolio_history=None,
        symbols=None,
        positions=None,
        trades=None,
    ):
        summary = summarize_portfolio_period(
            portfolio_history
            if portfolio_history is not None
            else pd.DataFrame()
        )

        payload = {
            "status": "ok",
            "range": selected_range,
            "mode": chart_mode,
            "portfolio": portfolio_data or [],
            "positions": positions or [],
            "trades": trades or [],
            "symbols": symbols or [],
            "current_value": summary["current_value"],
            "period_return_pct": summary["period_return_pct"],
            "period_start_equity": summary["period_start_equity"],
        }

        if timeframe is not None:
            payload["timeframe"] = timeframe

        return jsonify(payload)

    try:
        selected_range = request.args.get(
            "range",
            "1M",
        )
        selected_range = (selected_range or "1M").upper()

        chart_mode = str(
            request.args.get(
                "mode",
                "return",
            ) or "return"
        ).lower()

        chart_mode = CHART_MODE_ALIASES.get(chart_mode, "return")

        symbols_param = request.args.get(
            "symbols",
            "",
        )

        selected_symbols = [
            s.strip().upper()
            for s in symbols_param.split(",")
            if s.strip()
        ]

        if selected_range not in TIMEFRAME_BY_RANGE:
            return jsonify({
                "status": "error",
                "error": f"Invalid range: {selected_range}",
            }), 400

        if not has_alpaca_credentials():
            return jsonify({
                "status": "not_configured",
                "error": (
                    "Add ALPACA_API_KEY and ALPACA_SECRET_KEY to load "
                    "live portfolio performance."
                ),
                "range": selected_range,
                "mode": chart_mode,
                "portfolio": [],
                "positions": [],
                "trades": [],
                "symbols": [],
                "current_value": None,
                "period_return_pct": None,
                "period_start_equity": None,
            })

        fills = get_all_fills()

        range_end = utc_now()

        requested_range_start = get_range_start(
            selected_range,
            None,
        )

        timeframe = TIMEFRAME_BY_RANGE[
            selected_range
        ]

        portfolio_history = get_portfolio_history(
            requested_range_start,
            range_end,
            timeframe,
        )

        range_start = clamp_range_start_to_available_data(
            requested_start=requested_range_start,
            portfolio_df=portfolio_history,
        )

        portfolio_data = build_portfolio_payload(
            portfolio_history,
            chart_mode,
        )

        if not selected_symbols and not fills.empty:
            selected_symbols = sorted(
                fills["symbol"]
                .dropna()
                .unique()
                .tolist()
            )

        if not selected_symbols:
            return chart_response(
                selected_range=selected_range,
                chart_mode=chart_mode,
                timeframe=timeframe,
                portfolio_data=portfolio_data,
                portfolio_history=portfolio_history,
            )

        bars = get_stock_bars(
            selected_symbols,
            range_start,
            range_end,
            timeframe,
        )

        if bars.empty:
            return chart_response(
                selected_range=selected_range,
                chart_mode=chart_mode,
                timeframe=timeframe,
                portfolio_data=portfolio_data,
                portfolio_history=portfolio_history,
                symbols=selected_symbols,
            )

        position_history = build_position_history(
            fills,
            bars,
            selected_symbols,
        )

        if position_history.empty:
            return chart_response(
                selected_range=selected_range,
                chart_mode=chart_mode,
                timeframe=timeframe,
                portfolio_data=portfolio_data,
                portfolio_history=portfolio_history,
                symbols=selected_symbols,
            )

        performance_history = build_performance_dataframe(
            position_history,
            fills,
            selected_symbols,
        )

        positions = []
        trades = []

        for symbol in selected_symbols:

            symbol_fills = (
                fills[fills["symbol"] == symbol].copy()
                if not fills.empty
                else pd.DataFrame()
            )

            # chart_mode has already been canonicalized via CHART_MODE_ALIASES above.
            if chart_mode == "value":

                df = position_history[
                    position_history["symbol"] == symbol
                ].copy()

                if df.empty:
                    continue

                df.loc[
                    df["qty"].abs() < 1e-10,
                    "market_value",
                ] = np.nan

                value_column = "market_value"

            elif chart_mode == "price":

                df = position_history[
                    position_history["symbol"] == symbol
                ].copy()

                if df.empty:
                    continue

                if "close" in df.columns:
                    value_column = "close"
                else:
                    value_column = "market_value"

            elif chart_mode == "normalized":

                df = position_history[
                    position_history["symbol"] == symbol
                ].copy()

                if df.empty:
                    continue

                if "close" in df.columns:
                    first_close = pd.to_numeric(df["close"], errors="coerce").dropna()
                    if not first_close.empty:
                        baseline = float(first_close.iloc[0])
                        if baseline:
                            df["normalized_price"] = (pd.to_numeric(df["close"], errors="coerce") / baseline) * 100.0
                            value_column = "normalized_price"
                        else:
                            value_column = "close"
                    else:
                        value_column = "close"
                else:
                    value_column = "market_value"

            elif chart_mode == "pnl":

                df = position_history[
                    position_history["symbol"] == symbol
                ].copy()

                if df.empty:
                    continue

                owned = df["qty"].abs() > 1e-10
                if owned.any():
                    baseline_market_value = float(df.loc[owned, "market_value"].iloc[0])
                    df["pnl_value"] = df["market_value"] - baseline_market_value
                    value_column = "pnl_value"
                else:
                    value_column = "market_value"

            elif chart_mode == "marketcap":

                df = position_history[
                    position_history["symbol"] == symbol
                ].copy()

                if df.empty:
                    continue

                if "close" in df.columns:
                    first_close = pd.to_numeric(df["close"], errors="coerce").dropna()
                    if not first_close.empty:
                        baseline = float(first_close.iloc[0])
                        if baseline:
                            df["market_cap_adj"] = (pd.to_numeric(df["close"], errors="coerce") / baseline) * 100.0
                            value_column = "market_cap_adj"
                        else:
                            value_column = "close"
                    else:
                        value_column = "close"
                else:
                    value_column = "market_value"

            else:

                if performance_history.empty:
                    continue

                df = performance_history[
                    performance_history["symbol"] == symbol
                ].copy()

                if df.empty:
                    continue

                value_column = "return_pct"

            line = []

            for _, row in df.iterrows():

                value = row[value_column]

                line.append({
                    "timestamp": row["timestamp"].isoformat(),
                    "value": (
                        None
                        if pd.isna(value)
                        else float(value)
                    ),
                })

            positions.append({
                "symbol": symbol,
                "data": line,
            })

            if symbol_fills.empty:
                continue

            markers = create_trade_markers_data(
                symbol_fills=symbol_fills,
                line_df=df,
                value_column=value_column,
                symbol=symbol,
                range_start=range_start,
                range_end=range_end,
            )

            trades.extend(markers)

        return chart_response(
            selected_range=selected_range,
            chart_mode=chart_mode,
            timeframe=timeframe,
            portfolio_data=portfolio_data,
            portfolio_history=portfolio_history,
            symbols=selected_symbols,
            positions=positions,
            trades=trades,
        )

    except Exception as e:

        return jsonify({
            "status": "error",
            "error": str(e),
        }), 500


@app.route("/api/weights", methods=["GET"])
def api_weights():
    """Get current ensemble strategy weights."""
    return jsonify({"weights": ensemble.get_weights()})


@app.route("/api/reflection", methods=["POST"])
def api_reflection():
    """Generate a reflection summary from recent trades."""
    trades = request.json.get("trades", []) or []
    try:
        result = reflection_engine.reflect_on_period(trades)
        return jsonify(result)
    except Exception as e:
        return jsonify({"reflection": f"Reflection failed: {e}", "patterns": []}), 500


@app.route("/api/report/daily", methods=["GET"])
def api_daily_report():
    """Return a simple daily summary report from the current trade history."""
    try:
        report = build_daily_report(trade_history.get_all(limit=200))
        return jsonify(report)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e), "report_type": "daily"}), 500


@app.route("/api/sizing", methods=["POST"])
def api_sizing():
    """Calculate recommended position size for a symbol."""
    data = request.json or {}
    equity = data.get("equity")
    price = data.get("price")
    atr = data.get("atr")
    method = data.get("method", "vol_target")  # "vol_target", "risk_parity", "kelly"

    try:
        if not equity or equity <= 0 or not price or price <= 0:
            return jsonify({"status": "error", "error": "equity and price required"}), 400

        shares = None
        if method == "vol_target" and atr and atr > 0:
            shares = target_volatility_size(equity, price, atr)
        elif method == "risk_parity" and atr and atr > 0:
            shares = risk_parity_size(equity, price, atr)
        elif method == "kelly":
            win_rate = data.get("win_rate", 0.5)
            avg_win = data.get("avg_win", 100)
            avg_loss = data.get("avg_loss", 50)
            shares = half_kelly(equity, win_rate, avg_win, avg_loss, price)

        if shares is not None:
            notional = shares * price
            return jsonify({
                "status": "ok",
                "shares": shares,
                "notional": round(notional, 2),
                "method": method,
            })
        return jsonify({"status": "no_size", "reason": "Conditions not met for sizing"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/search", methods=["POST"])
def api_search():
    """Semantic search over trade history / stored documents."""
    query = request.json.get("query", "")
    top_k = request.json.get("top_k", 5)
    try:
        # Build vector store from trade history on demand
        history = trade_history.get_all(limit=200)
        vector_store.clear()
        for h in history:
            text = f"{h.get('symbol', '')} {h.get('action', '')} {h.get('reason', '')}"
            vector_store.add(text, **h)
        results = vector_store.search(query, top_k=top_k)
        return jsonify({"query": query, "results": results})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="0.0.0.0", port=port, debug=debug)
