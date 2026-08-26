"""
optimization/ensemble.py

Strategy ensemble optimization.

Learns optimal voting weights for each strategy by evaluating
individual backtest performance. Better-performing strategies get
higher weight in the final decision.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from observability.run_tracker import now_iso


DEFAULT_WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "strategy_weights.json")


class StrategyEnsemble:
    """
    Manages adaptive strategy weights.

    - Loads previously computed weights from disk
    - Computes new weights from backtest results
    - Provides weighted aggregation of strategy votes
    """

    def __init__(self, weights_path: str = DEFAULT_WEIGHTS_PATH) -> None:
        self.weights_path = weights_path
        self.weights: Dict[str, float] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if os.path.exists(self.weights_path):
            try:
                with open(self.weights_path, "r") as f:
                    data = json.load(f)
                    self.weights = data.get("weights", {})
            except Exception:
                self.weights = {}

    def save(self) -> None:
        try:
            with open(self.weights_path, "w") as f:
                json.dump({"weights": self.weights, "updated_at": now_iso()}, f, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Weight computation
    # ------------------------------------------------------------------

    def compute_weights(
        self,
        backtest_results: List[Dict[str, Any]],
        metric: str = "sharpe",  # "sharpe", "win_rate", "return"
    ) -> Dict[str, float]:
        """
        Compute optimal strategy weights from backtest results.

        Args:
            backtest_results: List of dicts with keys:
                - strategy_name: str
                - total_return_pct: float
                - win_rate: float (0-100)
                - sharpe_ratio: float
                - max_drawdown_pct: float
                - total_trades: int
        """
        if not backtest_results:
            return {}

        # Filter to results with enough trades
        valid = [
            r for r in backtest_results
            if r.get("total_trades", 0) >= 5 and r.get("strategy_name")
        ]
        if not valid:
            return {}

        # Extract metric values
        values: Dict[str, float] = {}
        for r in valid:
            name = r["strategy_name"]
            if metric == "sharpe":
                val = r.get("sharpe_ratio", 0)
            elif metric == "win_rate":
                val = r.get("win_rate", 0) / 100.0
            elif metric == "return":
                val = r.get("total_return_pct", 0)
            else:
                val = r.get("sharpe_ratio", 0)

            # Penalize drawdown
            dd = r.get("max_drawdown_pct", 0)
            if dd > 20:
                val *= 0.5
            elif dd > 10:
                val *= 0.8

            values[name] = max(val, 0.0)

        if not values:
            return {}

        # Softmax normalization
        import math
        exp_sum = sum(math.exp(v) for v in values.values())
        if exp_sum == 0 or not math.isfinite(exp_sum):
            # Fall back to equal weights
            n = len(values)
            return {k: 1.0 / n for k in values}

        weights = {k: math.exp(v) / exp_sum for k, v in values.items()}

        # Ensure minimum weight so every strategy still has a voice
        min_weight = 0.05
        for k in weights:
            weights[k] = max(weights[k], min_weight)

        # Re-normalize
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}

        self.weights = weights
        self.save()
        return weights

    # ------------------------------------------------------------------
    # Voting
    # ------------------------------------------------------------------

    def aggregate(
        self,
        strategy_votes: List[Dict[str, Any]],
        default_weight: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Aggregate strategy votes using learned weights.

        Args:
            strategy_votes: List of dicts with keys:
                - name or strategy: strategy identifier
                - decision: "buy" | "sell" | "hold"
                - confidence: float (0-1)

        Returns:
            Dict with weighted_score, weighted_confidence, breakdown
        """
        weighted_score = 0.0
        total_weight = 0.0
        breakdown = []

        for vote in strategy_votes:
            name = vote.get("name") or vote.get("strategy", "unknown")
            decision = vote.get("decision", "hold")
            confidence = vote.get("confidence", 0)

            weight = self.weights.get(name, default_weight)

            if decision == "buy":
                contribution = confidence * weight
            elif decision == "sell":
                contribution = -confidence * weight
            else:
                contribution = 0.0

            weighted_score += contribution
            total_weight += weight

            breakdown.append({
                "strategy": name,
                "decision": decision,
                "confidence": confidence,
                "weight": round(weight, 4),
                "contribution": round(contribution, 4),
            })

        # Normalize score to roughly -1 .. 1 range
        if total_weight > 0:
            normalized_score = weighted_score / total_weight
        else:
            normalized_score = 0.0

        return {
            "weighted_score": round(normalized_score, 4),
            "weighted_confidence": round(abs(normalized_score), 4),
            "breakdown": breakdown,
            "weights_used": dict(self.weights),
        }

    def get_weights(self) -> Dict[str, float]:
        return dict(self.weights)
