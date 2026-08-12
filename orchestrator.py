"""
orchestrator.py

Central coordinator for the multi-agent trading system.

- Runs agents in sequence: Market -> [Technical, Fundamental, News, Risk] -> Portfolio -> Execution
- Logs all inter-agent communication to a MessageBus
- Supports both manual trigger (user asks for analysis) and autonomous loop
- Auto-executes trades in autonomous mode when confidence exceeds threshold
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv

from agents.market_agent import MarketAgent
from agents.technical_agent import TechnicalAgent
from agents.fundamental_agent import FundamentalAgent
from agents.news_agent import NewsAgent
from agents.risk_agent import RiskAgent
from agents.execution_agent import ExecutionAgent
from agents.portfolio_agent import PortfolioAgent
from indicators.multiframe import analyze_multiframe

load_dotenv()


class MessageBus:
    """Thread-safe message bus for inter-agent communication and diagnostic telemetry."""

    def __init__(self) -> None:
        self._messages: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []

    def publish(
        self,
        from_agent: str,
        to_agent: str,
        message: str,
        data: Optional[Dict] = None,
        session_id: Optional[str] = None,
        category: str = "agent_dialogue",  # "api_diagnostic", "agent_dialogue", "decision_monologue"
        status_code: str = "ok",  # "ok", "warning", "error"
        symbol: Optional[str] = None,
    ) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "from": from_agent,
            "to": to_agent,
            "message": message,
            "data": data or {},
            "session_id": session_id or "",
            "category": category,
            "status_code": status_code,
            "symbol": symbol or "",
        }
        with self._lock:
            self._messages.append(entry)
        for sub in self._subscribers:
            try:
                sub(entry)
            except Exception:
                pass

    def get_messages(
        self,
        since_index: int = 0,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            msgs = self._messages[since_index:].copy()

        if session_id:
            msgs = [m for m in msgs if m.get("session_id") == session_id]
        if category:
            msgs = [m for m in msgs if m.get("category") == category]
        if symbol:
            msgs = [m for m in msgs if m.get("symbol", "").upper() == symbol.upper()]
        return msgs

    def get_sessions(self) -> List[Dict[str, Any]]:
        """Return unique analysis sessions with metadata."""
        with self._lock:
            sessions: Dict[str, Dict[str, Any]] = {}
            for m in self._messages:
                sid = m.get("session_id")
                if sid and sid not in sessions:
                    sessions[sid] = {
                        "session_id": sid,
                        "symbol": m.get("symbol", ""),
                        "timestamp": m.get("timestamp", ""),
                        "initial_message": m.get("message", ""),
                    }
            return list(sessions.values())

    def message_count(self) -> int:
        with self._lock:
            return len(self._messages)

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._subscribers.append(callback)

    def clear(self) -> None:
        with self._lock:
            self._messages.clear()


class Orchestrator:
    """Coordinates all trading agents and logs their communication."""

    def __init__(self) -> None:
        self.bus = MessageBus()
        self.market = MarketAgent()
        self.technical = TechnicalAgent()
        self.fundamental = FundamentalAgent()
        self.news = NewsAgent()
        self.risk = RiskAgent()
        self.execution = ExecutionAgent()
        self.portfolio = PortfolioAgent()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_analysis: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_symbol(self, symbol: str, auto_execute: bool = False) -> Dict[str, Any]:
        """Run the full multi-agent analysis pipeline on a symbol with rich telemetry."""
        symbol = symbol.upper()
        session_id = f"{symbol}_{int(time.time()*1000)}"

        self.bus.publish(
            "orchestrator", "all",
            f"🚀 Initiating Multi-Agent Analysis Pipeline for {symbol} [Session: {session_id}]",
            session_id=session_id, symbol=symbol, category="decision_monologue"
        )

        analyses: Dict[str, Dict] = {}

        # 1. Market data
        self.bus.publish(
            "orchestrator", "market_agent",
            f"Market Agent: Requesting OHLCV bars & price snapshot for {symbol} from Alpaca API...",
            session_id=session_id, symbol=symbol, category="api_diagnostic"
        )
        try:
            snapshot = self.market.snapshot(symbol, timeframe="1d", days=200)
            if snapshot and snapshot.trade:
                last_price = snapshot.trade.price
                rel_vol = snapshot.metrics.get("relative_volume", 1.0)
                spread = snapshot.metrics.get("spread", 0.0)

                price_str = f"${last_price:.2f}" if last_price is not None else "N/A"
                rel_vol_str = f"{rel_vol:.2f}x" if rel_vol is not None else "N/A"
                spread_str = f"${spread:.2f}" if spread is not None else "N/A"

                self.bus.publish(
                    "market_agent", "technical_agent",
                    f"📊 Market Snapshot Delivered: Last Price={price_str}, Relative Volume={rel_vol_str}, Bid/Ask Spread={spread_str}",
                    {"price": last_price, "metrics": snapshot.metrics if snapshot else {}},
                    session_id=session_id, symbol=symbol, category="agent_dialogue"
                )
            else:
                self.bus.publish(
                    "market_agent", "orchestrator",
                    "⚠️ API WARNING: Market snapshot returned incomplete quote/trade data.",
                    session_id=session_id, symbol=symbol, category="api_diagnostic", status_code="warning"
                )
            analyses["market"] = {"metrics": snapshot.metrics} if snapshot and snapshot.metrics else {}
        except Exception as e:
            self.bus.publish(
                "market_agent", "orchestrator",
                f"❌ API ERROR: Market Data fetch failed: {e}",
                {"error": str(e)},
                session_id=session_id, symbol=symbol, category="api_diagnostic", status_code="error"
            )
            analyses["market"] = {}
            snapshot = None

        # 2. Technical analysis
        self.bus.publish(
            "orchestrator", "technical_agent",
            f"Technical Agent: Computing RSI(14), MACD, EMA20/50, Bollinger Bands, ATR(14)...",
            session_id=session_id, symbol=symbol, category="agent_dialogue"
        )
        try:
            tech = self.technical.analyze(symbol)
            analyses["technical"] = tech
            signals = tech.get("signals", {})
            rsi = signals.get('rsi_14')
            macd = signals.get('macd')
            macd_sig = signals.get('macd_signal')
            ema20 = signals.get('ema_20')
            ema50 = signals.get('ema_50')
            atr = signals.get('atr_14')

            rsi_str = f"{rsi:.1f}" if rsi is not None else "N/A"
            macd_str = f"{macd:.2f}" if macd is not None else "N/A"
            atr_str = f"{atr:.2f}" if atr is not None else "N/A"

            trend = "UPTREND (EMA20 > EMA50)" if (ema20 or 0) > (ema50 or 0) else "DOWNTREND (EMA20 <= EMA50)"
            summary = f"RSI(14)={rsi_str}, MACD={macd_str}, Trend={trend}, ATR={atr_str}"
            
            self.bus.publish(
                "technical_agent", "execution_agent",
                f"📈 Technical Indicators Computed: {summary}",
                tech,
                session_id=session_id, symbol=symbol, category="agent_dialogue"
            )
        except Exception as e:
            analyses["technical"] = {"status": "error", "error": str(e)}
            self.bus.publish(
                "technical_agent", "orchestrator",
                f"❌ Technical Analysis Failed: {e}",
                session_id=session_id, symbol=symbol, category="api_diagnostic", status_code="error"
            )

        # 3. Fundamental analysis
        self.bus.publish(
            "orchestrator", "fundamental_agent",
            f"Fundamental Agent: Querying Finnhub company profile & fundamentals for {symbol}...",
            session_id=session_id, symbol=symbol, category="api_diagnostic"
        )
        try:
            fund = self.fundamental.analyze(symbol)
            analyses["fundamental"] = fund
            co = fund.get("data", {}).get("company", {})
            if co:
                pe = co.get("pe_ratio")
                eps = co.get("eps")
                beta = co.get("beta")
                score = fund.get("score", 0)
                self.bus.publish(
                    "fundamental_agent", "execution_agent",
                    f"🏦 Fundamental Profile: Industry={co.get('industry', 'N/A')}, P/E={pe if pe is not None else 'N/A'}, EPS={eps if eps is not None else 'N/A'}, Beta={beta if beta is not None else 'N/A'}. Valuation Score={score}",
                    fund,
                    session_id=session_id, symbol=symbol, category="agent_dialogue"
                )
            else:
                self.bus.publish(
                    "fundamental_agent", "orchestrator",
                    "🟡 API NOTICE: Finnhub API Key not set or company profile unavailable. Fundamental Agent degrading gracefully to neutral.",
                    fund,
                    session_id=session_id, symbol=symbol, category="api_diagnostic", status_code="warning"
                )
        except Exception as e:
            analyses["fundamental"] = {"status": "error", "error": str(e)}
            self.bus.publish(
                "fundamental_agent", "orchestrator",
                f"Fundamental analysis failed: {e}",
                session_id=session_id, symbol=symbol, category="api_diagnostic", status_code="error"
            )

        # 4. News analysis
        self.bus.publish(
            "orchestrator", "news_agent",
            f"News Agent: Scanning recent company news & sentiment for {symbol} via Finnhub...",
            session_id=session_id, symbol=symbol, category="api_diagnostic"
        )
        try:
            news = self.news.analyze(symbol)
            analyses["news"] = news
            articles = news.get("articles", [])
            sentiment = news.get("sentiment", "neutral")
            if news.get("status", "").startswith("news analysis skipped"):
                self.bus.publish(
                    "news_agent", "orchestrator",
                    "🟡 API NOTICE: Finnhub API Key missing. News sentiment scanner skipped (defaulting to NEUTRAL).",
                    news,
                    session_id=session_id, symbol=symbol, category="api_diagnostic", status_code="warning"
                )
            else:
                self.bus.publish(
                    "news_agent", "execution_agent",
                    f"📰 Scanned {len(articles)} headlines. Keyword Sentiment: {sentiment.upper()} (Score: {news.get('sentiment_score', 0)})",
                    news,
                    session_id=session_id, symbol=symbol, category="agent_dialogue"
                )
        except Exception as e:
            analyses["news"] = {"status": "error", "error": str(e)}
            self.bus.publish(
                "news_agent", "orchestrator",
                f"News analysis failed: {e}",
                session_id=session_id, symbol=symbol, category="api_diagnostic", status_code="error"
            )

        # 5. Risk analysis
        self.bus.publish(
            "orchestrator", "risk_agent",
            f"Risk Agent: Evaluating ATR volatility & RSI overbought/oversold boundaries for {symbol}...",
            session_id=session_id, symbol=symbol, category="agent_dialogue"
        )
        try:
            risk = self.risk.analyze(symbol)
            analyses["risk"] = risk
            risk_level = risk.get("risk_level", "medium")
            atr_pct = risk.get("checks", {}).get("atr_percent")
            rsi_warn = risk.get("checks", {}).get("rsi_warning", "None")

            atr_vol_str = f"{atr_pct:.2f}%" if atr_pct is not None else "N/A"

            self.bus.publish(
                "risk_agent", "execution_agent",
                f"🛡️ Risk Assessment: Level={risk_level.upper()}, ATR Volatility={atr_vol_str} of price. RSI Warning: {rsi_warn}",
                risk,
                session_id=session_id, symbol=symbol, category="agent_dialogue"
            )
        except Exception as e:
            analyses["risk"] = {"status": "error", "error": str(e)}
            self.bus.publish(
                "risk_agent", "orchestrator",
                f"Risk analysis failed: {e}",
                session_id=session_id, symbol=symbol, category="api_diagnostic", status_code="error"
            )

        # 6. Portfolio check
        self.bus.publish(
            "orchestrator", "portfolio_agent",
            f"Portfolio Agent: Checking Alpaca account cash & position state for {symbol}...",
            session_id=session_id, symbol=symbol, category="agent_dialogue"
        )
        try:
            port = self.portfolio.analyze(symbol)
            analyses["portfolio"] = port
            pos = port.get("position")
            pos_text = f"{pos.get('qty', 0)} shares @ ${float(pos.get('avg_entry_price', 0)):.2f}" if pos else "Flat (0 shares)"
            self.bus.publish(
                "portfolio_agent", "execution_agent",
                f"💼 Portfolio State for {symbol}: Position={pos_text}",
                port,
                session_id=session_id, symbol=symbol, category="agent_dialogue"
            )
        except Exception as e:
            analyses["portfolio"] = {"status": "error", "error": str(e)}
            self.bus.publish(
                "portfolio_agent", "orchestrator",
                f"Portfolio check failed: {e}",
                session_id=session_id, symbol=symbol, category="api_diagnostic", status_code="error"
            )

        # 7. Execution decision
        self.bus.publish(
            "orchestrator", "execution_agent",
            f"Execution Agent: Evaluating 5 strategy hypothesis voters & weighting agent inputs...",
            session_id=session_id, symbol=symbol, category="decision_monologue"
        )
        exec_decision: Dict[str, Any] = {}
        try:
            exec_decision = self.execution.analyze(symbol, context=analyses)
            analyses["execution"] = exec_decision

            # Log monologue for individual strategy votes
            for vote in exec_decision.get("strategy_votes", []):
                strat_name = vote.get("strategy", vote.get("name", "Voter"))
                dec = vote.get("decision", "hold").upper()
                c_pct = (vote.get("confidence", 0) * 100)
                reason_text = vote.get("reason", "No reason provided")
                self.bus.publish(
                    "execution_agent", "orchestrator",
                    f"🗳️ Strategy [{strat_name}]: Voted {dec} (Confidence: {c_pct:.0f}%). Rationale: {reason_text}",
                    vote,
                    session_id=session_id, symbol=symbol, category="decision_monologue"
                )

            action = exec_decision.get("action", "hold")
            confidence = exec_decision.get("confidence", 0.0)
            raw_score = exec_decision.get("raw_score", 0.0)
            reasoning = exec_decision.get("detailed_reasoning", {})
            exec_summary = reasoning.get("executive_summary", exec_decision.get("reason", ""))

            self.bus.publish(
                "execution_agent", "all",
                f"🎯 FINAL DECISION: {action.upper()} {symbol} (Confidence: {confidence:.0%}, Combined Score: {raw_score:+.2f}). Rationale: {exec_summary}",
                exec_decision,
                session_id=session_id, symbol=symbol, category="decision_monologue"
            )

            if action in ("buy", "sell"):
                self.bus.publish(
                    "execution_agent", "user",
                    f"🔔 TRADE RECOMMENDATION: {action.upper()} {symbol} (Confidence: {confidence:.0%})",
                    exec_decision,
                    session_id=session_id, symbol=symbol, category="decision_monologue"
                )
        except Exception as e:
            analyses["execution"] = {"status": "error", "error": str(e)}
            self.bus.publish(
                "execution_agent", "orchestrator",
                f"Execution decision failed: {e}",
                session_id=session_id, symbol=symbol, category="api_diagnostic", status_code="error"
            )

        # 8. Auto-execution (only in autonomous mode)
        auto_result = None
        if auto_execute and exec_decision.get("action") in ("buy", "sell"):
            try:
                auto_result = self.execution.maybe_auto_trade(symbol, exec_decision, context=analyses)
                if auto_result:
                    self.bus.publish(
                        "execution_agent", "orchestrator",
                        f"⚡ Auto-Trade Execution Result: {auto_result.get('status', 'unknown')}",
                        auto_result,
                        session_id=session_id, symbol=symbol, category="decision_monologue"
                    )
                    if auto_result.get("status") == "submitted":
                        self.bus.publish(
                            "execution_agent", "user",
                            f"🚀 AUTO-TRADE EXECUTED: {auto_result.get('side', '').upper()} {symbol} — Order ID: {auto_result.get('order_id', 'N/A')}",
                            auto_result,
                            session_id=session_id, symbol=symbol, category="decision_monologue"
                        )
            except Exception as e:
                self.bus.publish(
                    "execution_agent", "orchestrator",
                    f"Auto-trade failed: {e}",
                    session_id=session_id, symbol=symbol, category="api_diagnostic", status_code="error"
                )

        result = {
            "session_id": session_id,
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "analyses": analyses,
            "auto_trade": auto_result,
            "messages": self.bus.get_messages(session_id=session_id),
        }
        self._last_analysis = result
        return result

    def get_messages(self, since_index: int = 0) -> List[Dict[str, Any]]:
        return self.bus.get_messages(since_index)

    def get_last_analysis(self) -> Optional[Dict[str, Any]]:
        return self._last_analysis

    def analyze_symbol_multiframe(self, symbol: str, auto_execute: bool = False) -> Dict[str, Any]:
        """Run the full pipeline including multi-timeframe analysis."""
        symbol = symbol.upper()
        self.bus.publish("orchestrator", "all", f"Starting multi-timeframe analysis for {symbol}")

        # Run standard analysis first
        result = self.analyze_symbol(symbol, auto_execute=False)

        # Add multiframe overlay
        self.bus.publish("orchestrator", "multiframe", f"Running multi-timeframe analysis for {symbol}")
        try:
            mfa = analyze_multiframe(symbol)
            result["multiframe"] = mfa
            self.bus.publish(
                "multiframe", "orchestrator",
                f"Multiframe signal: {mfa.get('overall_signal', 'neutral').upper()} (alignment: {mfa.get('alignment_score', 0):.2f})",
                mfa,
            )

            # Inject multiframe signal into execution context for re-evaluation
            analyses = result.get("analyses", {})
            analyses["multiframe"] = mfa

            # Re-run execution with multiframe context
            self.bus.publish("orchestrator", "execution_agent", f"Re-evaluating with multiframe context for {symbol}")
            try:
                exec_decision = self.execution.analyze(symbol, context=analyses)
                result["analyses"]["execution"] = exec_decision
                action = exec_decision.get("action", "hold")
                confidence = exec_decision.get("confidence", 0.0)
                self.bus.publish("execution_agent", "orchestrator", f"Multiframe execution decision: {action.upper()} (confidence: {confidence:.0%})", exec_decision)
            except Exception as e:
                self.bus.publish("execution_agent", "orchestrator", f"Multiframe execution decision failed: {e}")

            # Auto-execute if requested
            if auto_execute:
                exec_decision = result["analyses"].get("execution", {})
                if exec_decision.get("action") in ("buy", "sell"):
                    try:
                        auto_result = self.execution.maybe_auto_trade(symbol, exec_decision, context=analyses)
                        result["auto_trade"] = auto_result
                        if auto_result:
                            self.bus.publish("execution_agent", "orchestrator", f"Multiframe auto-trade result: {auto_result.get('status', 'unknown')}", auto_result)
                            if auto_result.get("status") == "submitted":
                                self.bus.publish("execution_agent", "user", f"MULTIFRAME AUTO-TRADE: {auto_result.get('side', '').upper()} {symbol}", auto_result)
                    except Exception as e:
                        self.bus.publish("execution_agent", "orchestrator", f"Multiframe auto-trade failed: {e}")

        except Exception as e:
            result["multiframe"] = {"status": "error", "error": str(e)}
            self.bus.publish("multiframe", "orchestrator", f"Multiframe analysis failed: {e}")

        result["messages"] = self.bus.get_messages()
        self._last_analysis = result
        return result

    # ------------------------------------------------------------------
    # Autonomous loop
    # ------------------------------------------------------------------

    def start_autonomous(self, symbols: List[str], interval_seconds: int = 300) -> None:
        """Start a background thread that analyzes symbols on a schedule."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._autonomous_loop, args=(symbols, interval_seconds), daemon=True)
        self._thread.start()
        self.bus.publish("orchestrator", "user", f"Autonomous trading loop started for {symbols} every {interval_seconds}s")

    def stop_autonomous(self) -> None:
        self._running = False
        self.bus.publish("orchestrator", "user", "Autonomous trading loop stopped")

    def _autonomous_loop(self, symbols: List[str], interval_seconds: int) -> None:
        while self._running:
            for symbol in symbols:
                if not self._running:
                    break
                self.analyze_symbol(symbol, auto_execute=True)
                time.sleep(5)  # small gap between symbols
            if self._running:
                time.sleep(interval_seconds)


# Singleton orchestrator instance for the web app
_default_orchestrator: Optional[Orchestrator] = None
_orchestrator_lock = threading.Lock()


def get_orchestrator() -> Orchestrator:
    global _default_orchestrator
    with _orchestrator_lock:
        if _default_orchestrator is None:
            _default_orchestrator = Orchestrator()
        return _default_orchestrator
