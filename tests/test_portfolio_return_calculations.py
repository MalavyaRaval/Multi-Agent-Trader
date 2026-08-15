import pandas as pd

from visualization.portfolio import compute_range_return_pct


def test_compute_range_return_pct_uses_first_valid_equity_baseline():
    df = pd.DataFrame(
        {
            "equity": [0.0, 0.0, 1000.0, 1100.0, 1200.0],
            "profit_loss_pct": [None, None, None, None, None],
        }
    )

    result = compute_range_return_pct(df)

    assert result.tolist() == [0.0, 0.0, 0.0, 10.0, 20.0]


def test_compute_range_return_pct_ignores_placeholder_zeroes_and_preserves_real_values():
    df = pd.DataFrame(
        {
            "equity": [0.0, 0.0, 500.0, 550.0, 600.0],
            "profit_loss_pct": [0.0, 0.0, 0.0, 10.0, 20.0],
        }
    )

    result = compute_range_return_pct(df)

    assert result.tolist() == [0.0, 0.0, 0.0, 10.0, 20.0]


def test_get_portfolio_history_removes_placeholder_zero_rows_before_first_live_equity():
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime([
                "2026-06-16",
                "2026-06-17",
                "2026-06-18",
            ], utc=True),
            "equity": [0.0, 0.0, 1000.0],
            "profit_loss": [0.0, 0.0, 0.0],
            "profit_loss_pct": [0.0, 0.0, 0.0],
        }
    )

    trimmed = df.copy()
    first_valid_idx = trimmed.index[trimmed["equity"].gt(0)].min()
    trimmed = trimmed.loc[trimmed.index >= first_valid_idx].copy().reset_index(drop=True)

    assert len(trimmed) == 1
    assert trimmed.iloc[0]["equity"] == 1000.0
