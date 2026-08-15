import traceback
from app import app
from app import get_all_fills, get_range_start, get_portfolio_history, TIMEFRAME_BY_RANGE, utc_now, clamp_range_start_to_available_data

try:
    selected_range = '1D'
    selected_symbols = []
    fills = get_all_fills()
    print('fills empty?', fills.empty)
    range_end = utc_now()
    requested_range_start = get_range_start(selected_range, None)
    timeframe = TIMEFRAME_BY_RANGE[selected_range]
    portfolio_history = get_portfolio_history(requested_range_start, range_end, timeframe)
    print('portfolio_history empty?', portfolio_history.empty)
    print('portfolio_history head:\n', portfolio_history.head())
    range_start = clamp_range_start_to_available_data(requested_start=requested_range_start, portfolio_df=portfolio_history)
    print('range_start', range_start)
    if not selected_symbols and not fills.empty:
        selected_symbols = sorted(fills['symbol'].dropna().unique().tolist())
    print('selected_symbols', selected_symbols)
    if not selected_symbols:
        print('NO SELECTED SYMBOLS PATH')
    else:
        from app import get_stock_bars
        bars = get_stock_bars(selected_symbols, range_start, range_end, timeframe)
        print('bars empty?', bars.empty)
        print('bars head', bars.head())
        from app import build_position_history
        position_history = build_position_history(fills, bars, selected_symbols)
        print('position_history empty?', position_history.empty)
        from app import build_performance_dataframe
        performance_history = build_performance_dataframe(position_history, fills, selected_symbols)
        print('performance_history empty?', performance_history.empty)
        positions = []
        trades = []
        for symbol in selected_symbols:
            print('processing symbol', symbol)
            symbol_fills = fills[fills['symbol'] == symbol].copy() if not fills.empty else []
            if True:
                df = position_history[position_history['symbol'] == symbol].copy()
                print('df rows', len(df))
                if df.empty:
                    continue
                df.loc[df['qty'].abs() < 1e-10, 'market_value'] = float('nan')
                value_column = 'market_value'
            line = []
            for _, row in df.iterrows():
                value = row[value_column]
                line.append({
                    'timestamp': row['timestamp'].isoformat(),
                    'value': None if pd.isna(value) else float(value),
                })
            positions.append({'symbol': symbol, 'data': line})
            if symbol_fills.empty:
                continue
            markers = []
            for _, fill in symbol_fills.sort_values('timestamp').iterrows():
                markers.append({'symbol': symbol, 'side': fill['side']})
            trades.extend(markers)
        print('done processing', len(positions), len(trades))
except Exception:
    traceback.print_exc()
