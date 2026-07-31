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
from agents.portfolio_agent import PortfolioAgent

load_dotenv()


class MessageBus:
    """Thread-safe message bus for inter-agent communication."""

    def __init__(self) -> None:
        self._messages: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []

    def publish(self, from_agent: str, to_agent: str, message: str, data: Optional[Dict] = None) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "from": from_agent,
            "to": to_agent,
            "message": message,
            "data": data or {},
        }
        with self._lock:
            self._messages.append(entry)
        for sub in self._subscribers:
            try:
                sub(entry)
            except Exception:
                pass

    def get_messages(self, since_index: int = 0) -> List[Dict[str, Any]]:
        with self._lock:
            return self._messages[since_index:].copy()

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
        """Run the full multi-agent analysis pipeline on a symbol."""
        symbol = symbol.upper()
        self.bus.publish("orchestrator", "all", f"Starting multi-agent analysis for {symbol}")

        analyses: Dict[str, Dict] = {}

        # 1. Market data
        self.bus.publish("orchestrator", "market_agent", f"Fetching market data for {symbol}")
        try:
            snapshot = self.market.snapshot(symbol, timeframe="1d", days=200)
            self.bus.publish(
                "market_agent", "orchestrator",
                f"Market snapshot ready. Last price: {snapshot.trade.price if snapshot.trade else 'N/A'}",
                {"price": snapshot.trade.price if snapshot.trade else None, "metrics": snapshot.metrics}
            )
            analyses["market"] = {"metrics": snapshot.metrics} if snapshot else {}
        except Exception as e:
            self.bus.publish("market_agent", "orchestrator", f"Market data failed: {e}", {"error": str(e)})
            analyses["market"] = {}
            snapshot = None

        # 2. Technical analysis
        self.bus.publish("orchestrator", "technical_agent", f"Running technical analysis on {symbol}")
        try:
            tech = self.technical.analyze(symbol)
            analyses["technical"] = tech
            status = tech.get("status", "unknown")
            signals = tech.get("signals", {})
            summary = f"RSI: {signals.get('rsi_14', 'N/A')}, MACD: {signals.get('macd', 'N/A')}"
            self.bus.publish("technical_agent", "orchestrator", f"Technical analysis complete. {summary}", tech)
        except Exception as e:
            analyses["technical"] = {"status": "error", "error": str(e)}
            self.bus.publish("technical_agent", "orchestrator", f"Technical analysis failed: {e}")

        # 3. Fundamental analysis
        self.bus.publish("orchestrator", "fundamental_agent", f"Running fundamental analysis on {symbol}")
        try:
            fund = self.fundamental.analyze(symbol)
            analyses["fundamental"] = fund
            self.bus.publish("fundamental_agent", "orchestrator", f"Fundamental analysis: {fund.get('status', 'done')}", fund)
        except Exception as e:
            analyses["fundamental"] = {"status": "error", "error": str(e)}
            self.bus.publish("fundamental_agent", "orchestrator", f"Fundamental analysis failed: {e}")

        # 4. News analysis
        self.bus.publish("orchestrator", "news_agent", f"Checking news sentiment for {symbol}")
        try:
            news = self.news.analyze(symbol)
            analyses["news"] = news
            self.bus.publish("news_agent", "orchestrator", f"News sentiment: {news.get('sentiment', 'neutral')}", news)
        except Exception as e:
            analyses["news"] = {"status": "error", "error": str(e)}
            self.bus.publish("news_agent", "orchestrator", f"News analysis failed: {e}")

        # 5. Risk analysis
        self.bus.publish("orchestrator", "risk_agent", f"Evaluating risk for {symbol}")
        try:
            risk = self.risk.analyze(symbol)
            analyses["risk"] = risk
            self.bus.publish("risk_agent", "orchestrator", f"Risk assessment: {risk.get('risk_level', 'unknown')}", risk)
        except Exception as e:
            analyses["risk"] = {"status": "error", "error": str(e)}
            self.bus.publish("risk_agent", "orchestrator", f"Risk analysis failed: {e}")

        # 6. Portfolio check
        self.bus.publish("orchestrator", "portfolio_agent", f"Checking portfolio for {symbol}")
        try:
            port = self.portfolio.analyze(symbol)
            analyses["portfolio"] = port
            self.bus.publish("portfolio_agent", "orchestrator", f"Portfolio check: {port.get('status', 'done')}", port)
        except Exception as e:
            analyses["portfolio"] = {"status": "error", "error": str(e)}
            self.bus.publish("portfolio_agent", "orchestrator", f"Portfolio check failed: {e}")

        # 7. Execution decision
        self.bus.publish("orchestrator", "execution_agent", f"Evaluating trade decision for {symbol}")
        exec_decision: Dict[str, Any] = {}
        try:
            exec_decision = self.execution.analyze(symbol, context=analyses)
            analyses["execution"] = exec_decision
            action = exec_decision.get("action", "hold")
            confidence = exec_decision.get("confidence", 0.0)
            self.bus.publish("execution_agent", "orchestrator", f"Execution decision: {action.upper()} (confidence: {confidence:.0%})", exec_decision)
            if action in ("buy", "sell"):
                self.bus.publish("execution_agent", "user", f"TRADE RECOMMENDATION: {action.upper()} {symbol}", exec_decision)
        except Exception as e:
            analyses["execution"] = {"status": "error", "error": str(e)}
            self.bus.publish("execution_agent", "orchestrator", f"Execution decision failed: {e}")

        # 8. Auto-execution (only in autonomous mode)
        auto_result = None
        if auto_execute and exec_decision.get("action") in ("buy", "sell"):
            try:
                auto_result = self.execution.maybe_auto_trade(symbol, exec_decision, context=analyses)
                if auto_result:
                    self.bus.publish("execution_agent", "orchestrator", f"Auto-trade result: {auto_result.get('status', 'unknown')}", auto_result)
                    if auto_result.get("status") == "submitted":
                        self.bus.publish("execution_agent", "user", f"AUTO-TRADE EXECUTED: {auto_result.get('side', '').upper()} {symbol} — Order {auto_result.get('order_id', 'N/A')}", auto_result)
            except Exception as e:
                self.bus.publish("execution_agent", "orchestrator", f"Auto-trade failed: {e}")

        result = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "analyses": analyses,
            "auto_trade": auto_result,
            "messages": self.bus.get_messages(),
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
        return self._last_analysis

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
