from app import get_all_fills, get_range_start, get_portfolio_history, TIMEFRAME_BY_RANGE, utc_now, clamp_range_start_to_available_data, get_stock_bars

fills = get_all_fills()
symbols = sorted(fills['symbol'].dropna().unique().tolist())
print('symbols', symbols)
rng = get_range_start('1D', None)
timeframe = TIMEFRAME_BY_RANGE['1D']
hist = get_portfolio_history(rng, utc_now(), timeframe)
range_start = clamp_range_start_to_available_data(rng, hist)
for s in symbols[:10]:
    bars = get_stock_bars([s], range_start, utc_now(), timeframe)
    print(s, 'rows=', len(bars), 'nunique=', bars['symbol'].nunique() if not bars.empty else 0)
    if not bars.empty:
        print(bars.head(3).to_dict('records'))
