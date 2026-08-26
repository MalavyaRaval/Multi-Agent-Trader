"""
Portfolio visualization data layer.

Fetches Alpaca account history, fills, historical prices,
reconstructs historical positions, calculates position returns,
and creates trade-marker coordinates.

This module contains NO Flask or Streamlit UI code.
It is intended to be consumed by Flask API endpoints.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

TRADING_URL = "https://paper-api.alpaca.markets/v2"
DATA_URL = "https://data.alpaca.markets/v2"

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}


# ============================================================
# CONSTANTS
# ============================================================

RANGE_DAYS = {
    "1D": 1,
    "1W": 7,
    "1M": 30,
    "2M": 60,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
}

TIMEFRAME_BY_RANGE = {
    "1D": "5Min",
    "1W": "15Min",
    "1M": "1D",
    "2M": "1D",
    "3M": "1D",
    "6M": "1D",
    "1Y": "1D",
    "ALL": "1D",
    "All": "1D",
}


# ============================================================
# ALPACA CLIENT
# ============================================================

_trading_client = None


def get_trading_client():
    """Return the shared Alpaca paper trading client."""

    global _trading_client

    if _trading_client is None:

        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            raise RuntimeError(
                "Missing ALPACA_API_KEY or ALPACA_SECRET_KEY."
            )

        _trading_client = TradingClient(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            paper=True,
        )

    return _trading_client


# ============================================================
# GENERAL HELPERS
# ============================================================

def compute_range_return_pct(df):
    """
    Compute return relative to the first actual portfolio-history
    observation in the selected/effective range.

    For a new account, the first available equity observation becomes
    the 0% baseline. This is important for ranges such as 2M, 3M,
    6M, and 1Y when the account itself is younger than the requested
    range.

    Example:

        Requested range: 1Y
        Account history: 45 days

        First available equity = $10,000
        Current equity = $10,800

        Return = +8.0%

    We do NOT manufacture data for the missing 11+ months.
    """

    if df is None or df.empty:
        return pd.Series(
            dtype=float,
            index=df.index if df is not None else None,
        )

    work = df.copy()

    if "timestamp" in work.columns:
        work = work.sort_values(
            "timestamp"
        ).reset_index(drop=True)
    else:
        work = work.reset_index(drop=True)

    equity = pd.to_numeric(
        work["equity"],
        errors="coerce",
    )

    result = pd.Series(
        0.0,
        index=work.index,
        dtype=float,
    )

    valid_equity_mask = (
        equity.notna()
        & equity.gt(0)
    )

    if not valid_equity_mask.any():
        return result

    first_valid_position = (
        valid_equity_mask
        .to_numpy()
        .nonzero()[0][0]
    )

    baseline_equity = float(
        equity.iloc[first_valid_position]
    )

    if abs(baseline_equity) < 1e-10:
        return result

    result.loc[valid_equity_mask] = (
        equity.loc[valid_equity_mask]
        / baseline_equity
        - 1.0
    ) * 100.0

    return result.round(8)


def summarize_portfolio_period(portfolio_df):
    """Derive headline metrics from a portfolio history dataframe."""

    empty_summary = {
        "current_value": 0.0,
        "period_return_pct": 0.0,
        "period_start_equity": 0.0,
    }

    if portfolio_df is None or portfolio_df.empty:
        return empty_summary

    positive_equity = portfolio_df.loc[
        portfolio_df["equity"].gt(0)
    ]

    if positive_equity.empty:
        return empty_summary

    last_row = portfolio_df.iloc[-1]

    return {
        "current_value": safe_float(
            last_row.get("equity"),
            0.0,
        ),
        "period_return_pct": safe_float(
            last_row.get("return_pct"),
            0.0,
        ),
        "period_start_equity": safe_float(
            positive_equity.iloc[0]["equity"],
            0.0,
        ),
    }


def utc_now():
    """Return current UTC timestamp."""

    return pd.Timestamp.now(tz="UTC")


def normalize_timestamp(timestamp):
    """Normalize any timestamp to timezone-aware UTC."""

    timestamp = pd.Timestamp(timestamp)

    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")

    return timestamp.tz_convert("UTC")


def empty_fills_dataframe():

    return pd.DataFrame(
        columns=[
            "timestamp",
            "symbol",
            "side",
            "qty",
            "price",
            "id",
        ]
    )


def get_range_start(
    selected_range: str,
    first_trade_time=None,
):
    """
    Calculate beginning of selected chart range.
    """

    selected_range = str(
        selected_range or "1D"
    ).upper()

    now = utc_now()

    if selected_range == "ALL":

        if first_trade_time is not None:

            timestamp = normalize_timestamp(
                first_trade_time
            )

            return timestamp

        # If there are no trades, provide a sensible
        # fallback window.
        return now - pd.Timedelta(days=365)

    if selected_range not in RANGE_DAYS:
        raise ValueError(
            f"Unsupported portfolio range: {selected_range}"
        )

    return now - pd.Timedelta(
        days=RANGE_DAYS[selected_range]
    )

def clamp_range_start_to_available_data(
    requested_start,
    portfolio_df,
):
    """
    Clamp the requested chart start to the first actual portfolio
    history point available from Alpaca.

    Example:
        Requested 1Y start = 2025-08-15
        Account history begins = 2026-07-01

        Effective start = 2026-07-01

    This prevents a new account from pretending that it has a full
    1Y / 6M / 3M / 2M history when Alpaca does not have those points.
    """

    requested_start = normalize_timestamp(
        requested_start
    )

    if (
        portfolio_df is None
        or portfolio_df.empty
        or "timestamp" not in portfolio_df.columns
    ):
        return requested_start

    valid_timestamps = (
        pd.to_datetime(
            portfolio_df["timestamp"],
            utc=True,
            errors="coerce",
        )
        .dropna()
    )

    if valid_timestamps.empty:
        return requested_start

    first_available = valid_timestamps.min()

    return max(
        requested_start,
        normalize_timestamp(first_available),
    )


def safe_float(value, default=None):
    """Safely convert a value to float."""

    try:

        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


# ============================================================
# ACCOUNT
# ============================================================

def get_account():

    account = get_trading_client().get_account()

    return {
        "equity": safe_float(account.equity, 0.0),
        "cash": safe_float(account.cash, 0.0),
        "buying_power": safe_float(
            account.buying_power,
            0.0,
        ),
        "last_equity": safe_float(
            account.last_equity,
            0.0,
        ),
    }


# ============================================================
# CURRENT POSITIONS
# ============================================================

def get_current_positions():

    positions = get_trading_client().get_all_positions()

    rows = []

    for position in positions:

        try:

            rows.append(
                {
                    "symbol": position.symbol,
                    "qty": safe_float(position.qty, 0.0),
                    "avg_entry": safe_float(
                        position.avg_entry_price,
                        0.0,
                    ),
                    "current_price": safe_float(
                        position.current_price,
                        0.0,
                    ),
                    "market_value": safe_float(
                        position.market_value,
                        0.0,
                    ),
                    "unrealized_pl": safe_float(
                        position.unrealized_pl,
                        0.0,
                    ),
                    "unrealized_plpc": safe_float(
                        position.unrealized_plpc,
                        0.0,
                    ) * 100,
                }
            )

        except Exception:
            continue

    return rows


# ============================================================
# ACCOUNT FILLS
# ============================================================

def get_all_fills():

    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        raise RuntimeError(
            "Missing Alpaca API credentials."
        )

    rows = []
    page_token = None

    while True:

        params = {
            "activity_types": "FILL",
            "direction": "asc",
            "page_size": 100,
        }

        if page_token:
            params["page_token"] = page_token

        response = requests.get(
            f"{TRADING_URL}/account/activities",
            headers=HEADERS,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        page = response.json()

        if not page:
            break

        for fill in page:

            try:

                rows.append(
                    {
                        "timestamp": pd.to_datetime(
                            fill["transaction_time"],
                            utc=True,
                        ),
                        "symbol": str(
                            fill["symbol"]
                        ).upper(),
                        "side": str(
                            fill["side"]
                        ).lower(),
                        "qty": float(
                            fill["qty"]
                        ),
                        "price": float(
                            fill["price"]
                        ),
                        "id": fill.get("id"),
                    }
                )

            except Exception:
                continue

        if len(page) < 100:
            break

        page_token = page[-1].get("id")

        if not page_token:
            break

    if not rows:
        return empty_fills_dataframe()

    return (
        pd.DataFrame(rows)
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


# ============================================================
# PORTFOLIO HISTORY
# ============================================================

def get_portfolio_history(
    start,
    end,
    timeframe,
):

    start = normalize_timestamp(start)
    end = normalize_timestamp(end)

    params = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "timeframe": timeframe,
        "pnl_reset": "no_reset",
        "intraday_reporting": "extended_hours",
    }

    response = requests.get(
        f"{TRADING_URL}/account/portfolio/history",
        headers=HEADERS,
        params=params,
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    timestamps = data.get("timestamp", [])
    equity = data.get("equity", [])
    profit_loss = data.get("profit_loss", [])
    profit_loss_pct = data.get(
        "profit_loss_pct",
        [],
    )

    rows = []

    for i, timestamp in enumerate(timestamps):

        if i >= len(equity):
            break

        if equity[i] is None:
            continue

        try:

            row = {
                "timestamp": pd.to_datetime(
                    timestamp,
                    unit="s",
                    utc=True,
                ),
                "equity": float(
                    equity[i]
                ),
            }

            if (
                i < len(profit_loss)
                and profit_loss[i] is not None
            ):
                row["profit_loss"] = float(
                    profit_loss[i]
                )
            else:
                row["profit_loss"] = None

            if (
                i < len(profit_loss_pct)
                and profit_loss_pct[i] is not None
            ):
                row["profit_loss_pct"] = (
                    float(
                        profit_loss_pct[i]
                    )
                    * 100
                )
            else:
                row["profit_loss_pct"] = None

            rows.append(row)

        except Exception:
            continue

    columns = [
        "timestamp",
        "equity",
        "profit_loss",
        "profit_loss_pct",
        "return_pct",
    ]

    if not rows:

        return pd.DataFrame(
            columns=columns
        )

    df = (
        pd.DataFrame(rows)
        .sort_values("timestamp")
        .drop_duplicates(
            subset=["timestamp"]
        )
        .reset_index(drop=True)
    )

    df["return_pct"] = compute_range_return_pct(df)

    # --------------------------------------------------------
    # Remove leading zero-equity observations.
    #
    # Alpaca can return zero-value observations before an account
    # is funded. Those observations should not become the return
    # baseline.
    # --------------------------------------------------------

    positive_equity_mask = (
        pd.to_numeric(
            df["equity"],
            errors="coerce",
        )
        .gt(0)
    )

    if positive_equity_mask.any():

        first_valid_idx = (
            positive_equity_mask
            .idxmax()
        )

        df = (
            df.loc[
                first_valid_idx:
            ]
            .copy()
            .reset_index(drop=True)
        )

    return df


# ============================================================
# HISTORICAL STOCK BARS
# ============================================================

def get_stock_bars(
    symbols,
    start,
    end,
    timeframe,
):

    if not symbols:

        return pd.DataFrame(
            columns=[
                "timestamp",
                "symbol",
                "close",
            ]
        )

    preferred_feeds = []
    env_feed = str(
        os.getenv("ALPACA_DATA_FEED", "")
    ).strip().lower()

    if env_feed:
        preferred_feeds.append(env_feed)

    for fallback_feed in ("iex", "sip"):
        if fallback_feed not in preferred_feeds:
            preferred_feeds.append(fallback_feed)

    all_rows = []

    for symbol in symbols:

        symbol = str(symbol).upper()
        symbol_rows = []

        for feed_name in preferred_feeds:
            page_token = None
            found_any_bars = False

            while True:

                params = {
                    "timeframe": timeframe,
                    "start": normalize_timestamp(
                        start
                    ).isoformat(),
                    "end": normalize_timestamp(
                        end
                    ).isoformat(),
                    "limit": 10000,
                    "sort": "asc",
                    "adjustment": "raw",
                    "feed": feed_name,
                }

                if page_token:
                    params["page_token"] = page_token

                try:
                    response = requests.get(
                        f"{DATA_URL}/stocks/{symbol}/bars",
                        headers=HEADERS,
                        params=params,
                        timeout=60,
                    )
                    response.raise_for_status()
                except Exception:
                    break

                data = response.json() or {}
                bars = data.get("bars") or []

                if not isinstance(bars, list):
                    bars = []

                for bar in bars:
                    try:
                        symbol_rows.append(
                            {
                                "timestamp": pd.to_datetime(
                                    bar["t"],
                                    utc=True,
                                ),
                                "symbol": symbol,
                                "close": float(
                                    bar["c"]
                                ),
                            }
                        )
                        found_any_bars = True
                    except Exception:
                        continue

                page_token = data.get("next_page_token")

                if not page_token:
                    break

            if found_any_bars:
                break

        all_rows.extend(symbol_rows)

    if not all_rows:

        return pd.DataFrame(
            columns=[
                "timestamp",
                "symbol",
                "close",
            ]
        )

    return (
        pd.DataFrame(all_rows)
        .drop_duplicates(
            subset=[
                "timestamp",
                "symbol",
            ]
        )
        .sort_values(
            [
                "symbol",
                "timestamp",
            ]
        )
        .reset_index(drop=True)
    )


# ============================================================
# RECONSTRUCT HISTORICAL SHARE QUANTITY
# ============================================================

def reconstruct_symbol_quantity(
    fills,
    bars,
    symbol,
):

    symbol = str(symbol).upper()

    symbol_bars = (
        bars[
            bars["symbol"] == symbol
        ]
        .copy()
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    if symbol_bars.empty:
        return symbol_bars

    symbol_fills = (
        fills[
            fills["symbol"] == symbol
        ]
        .copy()
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    if symbol_fills.empty:

        symbol_bars["qty"] = 0.0
        symbol_bars["market_value"] = 0.0

        return symbol_bars

    symbol_fills["qty_change"] = (
        symbol_fills["qty"].astype(float)
    )

    symbol_fills.loc[
        symbol_fills["side"] == "sell",
        "qty_change",
    ] *= -1

    quantity_events = (
        symbol_fills[
            [
                "timestamp",
                "qty_change",
            ]
        ]
        .groupby(
            "timestamp",
            as_index=False,
        )
        .sum()
        .sort_values("timestamp")
    )

    quantity_events["qty"] = (
        quantity_events["qty_change"]
        .cumsum()
    )

    result = pd.merge_asof(
        symbol_bars,
        quantity_events[
            [
                "timestamp",
                "qty",
            ]
        ],
        on="timestamp",
        direction="backward",
    )

    result["qty"] = (
        result["qty"]
        .fillna(0.0)
    )

    result["market_value"] = (
        result["qty"]
        * result["close"]
    )

    return result


# ============================================================
# BUILD POSITION HISTORY
# ============================================================

def _concat_per_symbol(symbols, fn) -> pd.DataFrame:
    """Run fn(symbol) -> DataFrame for each symbol, concat the non-empty
    results, and sort by (symbol, timestamp). Shared by build_position_history
    and build_performance_dataframe, which previously repeated this loop
    identically apart from which per-symbol function they called."""
    frames = [result for symbol in symbols if not (result := fn(symbol)).empty]

    if not frames:
        return pd.DataFrame()

    return (
        pd.concat(
            frames,
            ignore_index=True,
        )
        .sort_values(
            [
                "symbol",
                "timestamp",
            ]
        )
        .reset_index(drop=True)
    )


def build_position_history(
    fills,
    bars,
    symbols,
):

    if bars.empty:
        return pd.DataFrame()

    return _concat_per_symbol(symbols, lambda symbol: reconstruct_symbol_quantity(fills, bars, symbol))


# ============================================================
# POSITION RETURN
# ============================================================

def calculate_position_period_return(
    position_df,
    symbol,
):
    """Return price performance for a held position over the selected range.

    Uses the first in-range bar with an open position as the 0% baseline.
    This matches standard brokerage charts and is directly comparable to the
    account-level period return line.
    """

    if position_df is None or position_df.empty:
        return pd.DataFrame()

    df = (
        position_df[
            position_df["symbol"] == symbol
        ]
        .copy()
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    if df.empty:
        return df

    owned_mask = df["qty"].abs() > 1e-10
    owned_rows = df.loc[owned_mask]

    df["return_pct"] = np.nan

    if owned_rows.empty:
        return df

    baseline_close = safe_float(
        owned_rows.iloc[0]["close"],
        0.0,
    )

    if abs(baseline_close) < 1e-10:
        df.loc[owned_mask, "return_pct"] = 0.0
        return df

    df.loc[owned_mask, "return_pct"] = (
        df.loc[owned_mask, "close"] / baseline_close - 1.0
    ) * 100.0

    return df


# ============================================================
# BUILD PERFORMANCE DATAFRAME
# ============================================================

def build_performance_dataframe(
    position_history,
    fills,
    symbols,
):

    return _concat_per_symbol(symbols, lambda symbol: calculate_position_period_return(position_history, symbol))


# ============================================================
# PROJECT TRADE ONTO LINE
# ============================================================

def project_trade_onto_line(
    line_df,
    timestamp,
    value_column,
):

    if line_df is None or line_df.empty:
        return None

    if value_column not in line_df.columns:
        return None

    temp = line_df[
        [
            "timestamp",
            value_column,
        ]
    ].copy()

    temp = temp.dropna(
        subset=[value_column]
    )

    if temp.empty:
        return None

    temp = (
        temp
        .sort_values("timestamp")
        .drop_duplicates(
            subset=["timestamp"]
        )
        .reset_index(drop=True)
    )

    timestamps = [
        normalize_timestamp(t)
        for t in temp["timestamp"]
    ]

    values = (
        temp[value_column]
        .astype(float)
        .to_numpy()
    )

    trade_time = normalize_timestamp(
        timestamp
    )

    if trade_time <= timestamps[0]:
        return float(values[0])

    if trade_time >= timestamps[-1]:
        return float(values[-1])

    timestamp_numbers = np.array(
        [
            t.value
            for t in timestamps
        ],
        dtype=np.int64,
    )

    right_index = int(
        np.searchsorted(
            timestamp_numbers,
            trade_time.value,
            side="right",
        )
    )

    left_index = right_index - 1

    if (
        left_index < 0
        or right_index >= len(timestamps)
    ):
        return None

    left_time = timestamps[left_index]
    right_time = timestamps[right_index]

    left_value = float(
        values[left_index]
    )

    right_value = float(
        values[right_index]
    )

    time_difference = (
        right_time.value
        - left_time.value
    )

    if time_difference == 0:
        return left_value

    fraction = (
        trade_time.value
        - left_time.value
    ) / time_difference

    fraction = float(
        np.clip(
            fraction,
            0.0,
            1.0,
        )
    )

    return float(
        left_value
        + (
            right_value
            - left_value
        )
        * fraction
    )


# ============================================================
# TRADE MARKERS
# ============================================================

def create_trade_markers_data(
    symbol_fills,
    line_df,
    value_column,
    symbol,
    range_start,
    range_end,
):

    markers = []

    if (
        symbol_fills is None
        or symbol_fills.empty
    ):
        return markers

    if (
        line_df is None
        or line_df.empty
    ):
        return markers

    range_start = normalize_timestamp(
        range_start
    )

    range_end = normalize_timestamp(
        range_end
    )

    for _, fill in (
        symbol_fills
        .sort_values("timestamp")
        .iterrows()
    ):

        fill_time = normalize_timestamp(
            fill["timestamp"]
        )

        if fill_time < range_start:
            continue

        if fill_time > range_end:
            continue

        marker_value = project_trade_onto_line(
            line_df=line_df,
            timestamp=fill_time,
            value_column=value_column,
        )

        if marker_value is None:
            continue

        side = (
            "BUY"
            if str(fill["side"]).lower()
            == "buy"
            else "SELL"
        )

        markers.append(
            {
                "timestamp": fill_time.isoformat(),
                "symbol": symbol,
                "side": side,
                "qty": float(fill["qty"]),
                "price": float(fill["price"]),
                "value": float(marker_value),
                "id": fill.get("id"),
            }
        )

    return markers


# ============================================================
# MAIN PORTFOLIO CHART DATA BUILDER
# ============================================================

def get_portfolio_chart(
    selected_range="1D",
    symbols=None,
):
    """
    Build the JSON-serializable data consumed by
    /api/portfolio_chart.

    Returns:

    {
        "range": "1D",
        "start": "...",
        "end": "...",
        "labels": [...],
        "portfolio": [...],
        "return_pct": [...],
        "current_value": 12345.67,
        "current_return_pct": 2.34,
        "series": [...],
        "markers": [...]
    }
    """

    selected_range = str(
        selected_range or "1D"
    ).upper()

    if selected_range not in (
        list(RANGE_DAYS.keys())
        + ["ALL"]
    ):
        selected_range = "1D"

    # --------------------------------------------------------
    # Get fills first.
    # They are useful for both symbols and All-range start.
    # --------------------------------------------------------

    fills = get_all_fills()

    if fills.empty:

        first_trade_time = None

    else:

        first_trade_time = fills[
            "timestamp"
        ].min()

    requested_range_start = get_range_start(
        selected_range,
        first_trade_time,
    )

    range_end = utc_now()

    timeframe = TIMEFRAME_BY_RANGE.get(
        selected_range,
        "5Min",
    )

    # --------------------------------------------------------
    # Account-level portfolio history.
    #
    # This is the primary portfolio-value line and we request
    # the full user-selected range first. Alpaca may return
    # less history if the account is new.
    # --------------------------------------------------------

    portfolio_df = get_portfolio_history(
        requested_range_start,
        range_end,
        timeframe,
    )

    # --------------------------------------------------------
    # Clamp the requested chart start to the first actual
    # portfolio-history point available from Alpaca.
    # --------------------------------------------------------

    range_start = clamp_range_start_to_available_data(
        requested_start=requested_range_start,
        portfolio_df=portfolio_df,
    )

    is_partial_range = (
        range_start > requested_range_start
    )

    # --------------------------------------------------------
    # Determine symbols.
    # --------------------------------------------------------

    if symbols is None:

        symbols = sorted(
            set(
                fills["symbol"].tolist()
                if not fills.empty
                else []
            )
        )

        try:

            current_positions = (
                get_current_positions()
            )

            for position in current_positions:

                symbol = str(
                    position["symbol"]
                ).upper()

                if symbol not in symbols:
                    symbols.append(symbol)

        except Exception:
            pass

    else:

        if isinstance(symbols, str):
            symbols = [
                item.strip().upper()
                for item in symbols.split(",")
                if item.strip()
            ]
        else:
            symbols = [
                str(item).strip().upper()
                for item in symbols
                if str(item).strip()
            ]

    symbols = sorted(
        set(symbols)
    )

    # --------------------------------------------------------

    # --------------------------------------------------------

    labels = []
    portfolio_values = []
    return_values = []

    for _, row in portfolio_df.iterrows():

        timestamp = normalize_timestamp(
            row["timestamp"]
        )

        labels.append(
            timestamp.isoformat()
        )

        portfolio_values.append(
            safe_float(
                row["equity"],
                0.0,
            )
        )

        return_values.append(
            safe_float(
                row["return_pct"],
                0.0,
            )
        )

    # --------------------------------------------------------
    # CURRENT VALUE
    #
    # This is deliberately defined explicitly here so there
    # is never a dangling reference to current_value.
    # --------------------------------------------------------

    if portfolio_values:

        current_value = float(
            portfolio_values[-1]
        )

        current_return_pct = float(
            return_values[-1]
            if return_values
            else 0.0
        )

    else:

        account = get_account()

        current_value = safe_float(
            account.get("equity"),
            0.0,
        )

        current_return_pct = 0.0

    # --------------------------------------------------------
    # Build portfolio series.
    # --------------------------------------------------------

    series = [
        {
            "name": "Portfolio Value",
            "type": "portfolio",
            "symbol": None,
            "data": [
                {
                    "timestamp": label,
                    "value": value,
                    "return_pct": (
                        return_values[index]
                        if index
                        < len(return_values)
                        else 0.0
                    ),
                }
                for index, (
                    label,
                    value,
                ) in enumerate(
                    zip(
                        labels,
                        portfolio_values,
                    )
                )
            ],
        }
    ]

    # --------------------------------------------------------
    # Symbol-level data.
    #
    # Only fetch historical stock bars if symbols exist.
    # --------------------------------------------------------

    markers = []

    if symbols:

        bars = get_stock_bars(
            symbols=symbols,
            start=range_start,
            end=range_end,
            timeframe=timeframe,
        )

        position_history = (
            build_position_history(
                fills=fills,
                bars=bars,
                symbols=symbols,
            )
        )

        performance_df = (
            build_performance_dataframe(
                position_history=position_history,
                fills=fills,
                symbols=symbols,
            )
        )

        for symbol in symbols:

            symbol_df = (
                bars[
                    bars["symbol"] == symbol
                ]
                .copy()
                .sort_values("timestamp")
            )

            if symbol_df.empty:
                continue

            symbol_performance = (
                performance_df[
                    performance_df["symbol"]
                    == symbol
                ]
                .copy()
                .sort_values("timestamp")
                if not performance_df.empty
                else pd.DataFrame()
            )

            # ------------------------------------------------
            # Use close price as symbol line.
            # ------------------------------------------------

            symbol_data = []

            for _, row in symbol_df.iterrows():

                symbol_data.append(
                    {
                        "timestamp":
                            normalize_timestamp(
                                row["timestamp"]
                            ).isoformat(),
                        "value":
                            safe_float(
                                row["close"],
                                0.0,
                            ),
                    }
                )

            series.append(
                {
                    "name": symbol,
                    "type": "symbol",
                    "symbol": symbol,
                    "data": symbol_data,
                    "performance": [
                        {
                            "timestamp":
                                normalize_timestamp(
                                    row["timestamp"]
                                ).isoformat(),
                            "return_pct":
                                safe_float(
                                    row.get(
                                        "return_pct"
                                    ),
                                    0.0,
                                ),
                            "market_value":
                                safe_float(
                                    row.get(
                                        "market_value"
                                    ),
                                    0.0,
                                ),
                        }
                        for _, row
                        in symbol_performance.iterrows()
                    ],
                }
            )

            # ------------------------------------------------
            # BUY / SELL markers.
            # ------------------------------------------------

            symbol_fills = (
                fills[
                    fills["symbol"] == symbol
                ]
                .copy()
                if not fills.empty
                else pd.DataFrame()
            )

            symbol_markers = (
                create_trade_markers_data(
                    symbol_fills=symbol_fills,
                    line_df=symbol_df,
                    value_column="close",
                    symbol=symbol,
                    range_start=range_start,
                    range_end=range_end,
                )
            )

            markers.extend(
                symbol_markers
            )

    # --------------------------------------------------------
    # Return final JSON-safe object.
    # --------------------------------------------------------

        # --------------------------------------------------------
    # RETURN FINAL JSON-SAFE OBJECT
    #
    # Keep the original fields for compatibility, while also
    # exposing the portfolio points in several explicit forms
    # so the frontend can consume the API without ambiguity.
    # --------------------------------------------------------

    portfolio_data = [
        {
            "timestamp": labels[index],
            "value": float(portfolio_values[index]),
            "return_pct": float(
                return_values[index]
                if index < len(return_values)
                else 0.0
            ),
        }
        for index in range(len(labels))
    ]

    return {
        "success": True,

        "range": selected_range,

        # Requested by the user.
        "requested_start": requested_range_start.isoformat(),

        # Actual first point available from Alpaca.
        "start": range_start.isoformat(),

        "end": range_end.isoformat(),

        "timeframe": timeframe,

        "is_partial_range": bool(
            is_partial_range
        ),

        "available_days": max(
            0,
            int(
                (
                    range_end - range_start
                ).total_seconds()
                / 86400
            )
        ),

        "symbols": symbols,

        "labels": labels,
        "portfolio": portfolio_values,
        "return_pct": return_values,

        "portfolio_data": portfolio_data,

        "current_value": float(current_value),

        "current_return_pct": float(
            current_return_pct
        ),

        "series": series,

        "markers": markers,

        "trade_count": len(markers),

        "has_data": bool(
            len(portfolio_data) > 0
        ),

        "portfolio_point_count": len(
            portfolio_data
        ),
    }