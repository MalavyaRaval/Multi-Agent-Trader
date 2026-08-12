import re
import json

from flask import Flask, jsonify, render_template, request

from agents.technical_agent import TechnicalAgent
from market_data_agent import run_turn as run_market_data_agent_turn
from trading_agent import get_account_info as get_trading_account_info
from trading_agent import run_turn as run_trading_agent_turn
from orchestrator import get_orchestrator
from agents.portfolio_agent import PortfolioAgent
from memory.trade_history import TradeHistory
from agents.screener_agent import ScreenerAgent
from backtesting.engine import BacktestEngine
from backtesting.report import generate_report
from indicators.multiframe import analyze_multiframe
from optimization.ensemble import StrategyEnsemble
from memory.vector_store import VectorStore
from memory.reflections import ReflectionEngine
from sizing import target_volatility_size, risk_parity_size, half_kelly
from reporting.daily_report import build_daily_report

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
        import pandas as pd
        import numpy as np

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

        # Moving Averages
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        
        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - macd_signal

        # Bollinger Bands
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        bb_upper = sma20 + (std20 * 2)
        bb_lower = sma20 - (std20 * 2)

        # RSI (Wilder / EMA style)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / (loss.replace(0, 1e-9))
        rsi_series = 100 - (100 / (1 + rs))

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
    """Return health & connectivity status for all APIs."""
    import os
    alpaca_key = bool(os.getenv("ALPACA_API_KEY"))
    alpaca_secret = bool(os.getenv("ALPACA_SECRET_KEY"))
    finnhub_key = bool(os.getenv("FINNHUB_API_KEY"))
    gemini_key = bool(os.getenv("GEMINI_API_KEY"))

    alpaca_status = "ok" if (alpaca_key and alpaca_secret) else "missing_keys"
    finnhub_status = "ok" if finnhub_key else "missing_key"
    gemini_status = "ok" if gemini_key else "missing_key"

    return jsonify({
        "status": "ok",
        "services": {
            "alpaca": {
                "name": "Alpaca Market & Trading API",
                "status": alpaca_status,
                "mode": "Paper Trading (Zero Risk)",
                "keys_configured": alpaca_key and alpaca_secret,
            },
            "finnhub": {
                "name": "Finnhub Fundamentals & News API",
                "status": finnhub_status,
                "keys_configured": finnhub_key,
                "note": "Optional. When missing, fundamental & news agents degrade gracefully to neutral.",
            },
            "gemini": {
                "name": "Google Gemini LLM Engine",
                "status": gemini_status,
                "keys_configured": gemini_key,
                "model": "gemini-3.1-flash-lite",
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
    app.run(host="0.0.0.0", port=5000, debug=True)
