from unittest.mock import Mock

import pandas as pd
import pytest

from visualization.portfolio import (
    calculate_position_period_return,
    compute_range_return_pct,
    get_stock_bars,
    summarize_portfolio_period,
)


def test_compute_range_return_pct_uses_first_valid_equity_baseline():
    df = pd.DataFrame(
        {
            "equity": [0.0, 0.0, 1000.0, 1100.0, 1200.0],
            "profit_loss_pct": [None, None, None, None, None],
        }
    )

    result = compute_range_return_pct(df)

    assert result.tolist() == [0.0, 0.0, 0.0, 10.0, 20.0]


def test_compute_range_return_pct_ignores_alpaca_profit_loss_pct():
    df = pd.DataFrame(
        {
            "equity": [0.0, 0.0, 500.0, 550.0, 600.0],
            "profit_loss_pct": [0.0, 0.0, 0.0, 10.0, 20.0],
        }
    )

    result = compute_range_return_pct(df)

    assert result.tolist() == [0.0, 0.0, 0.0, 10.0, 20.0]


def test_summarize_portfolio_period():
    df = pd.DataFrame(
        {
            "equity": [1000.0, 1100.0, 1050.0],
            "return_pct": [0.0, 10.0, 5.0],
        }
    )

    summary = summarize_portfolio_period(df)

    assert summary["current_value"] == 1050.0
    assert summary["period_return_pct"] == 5.0
    assert summary["period_start_equity"] == 1000.0


def test_calculate_position_period_return_uses_first_owned_bar_as_baseline():
    position_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL", "AAPL", "AAPL"],
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01",
                    "2026-01-02",
                    "2026-01-03",
                    "2026-01-04",
                ],
                utc=True,
            ),
            "qty": [0.0, 10.0, 10.0, 0.0],
            "close": [100.0, 100.0, 110.0, 105.0],
            "market_value": [0.0, 1000.0, 1100.0, 0.0],
        }
    )

    result = calculate_position_period_return(
        position_df,
        "AAPL",
    )

    assert pd.isna(result.iloc[0]["return_pct"])
    assert result.iloc[1]["return_pct"] == 0.0
    assert result.iloc[2]["return_pct"] == pytest.approx(10.0)
    assert pd.isna(result.iloc[3]["return_pct"])


def test_get_stock_bars_falls_back_to_sip_when_iex_has_no_data(monkeypatch):
    feed_calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        feed_calls.append(params["feed"])

        if params["feed"] == "iex":
            return Mock(
                raise_for_status=lambda: None,
                json=lambda: {"bars": []},
            )

        return Mock(
            raise_for_status=lambda: None,
            json=lambda: {
                "bars": [
                    {"t": "2026-08-14T20:15:00Z", "c": 123.45},
                    {"t": "2026-08-14T20:20:00Z", "c": 124.00},
                ]
            },
        )

    monkeypatch.setattr("visualization.portfolio.requests.get", fake_get)

    result = get_stock_bars(
        ["AAPL"],
        pd.Timestamp("2026-08-14T20:00:00Z"),
        pd.Timestamp("2026-08-15T20:00:00Z"),
        "5Min",
    )

    assert feed_calls[:2] == ["iex", "sip"]
    assert len(result) == 2
    assert set(result["symbol"]) == {"AAPL"}
