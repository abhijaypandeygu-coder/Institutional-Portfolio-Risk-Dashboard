# Performance chart enhancements — 19 November 2026

The Overview chart now reads portfolio NAV from the historical valuation endpoint, portfolio events from the scoped historical event endpoint, and completed cash-flow-adjusted returns from existing archived performance reports. Viewing the chart does not generate reports or write financial records. The latest 20 archived runs are inspected for a matching methodology, currency and applicable period. Observation-level methodology takes precedence over legacy report version labels. Only complete reports are used.

## Added UI
- Six metrics: portfolio return, benchmark return, excess return, annualized return, annualized volatility and maximum drawdown. NAV mode uses explicit unadjusted-NAV labels.
- Dated crosshair and detail pane with NAV, indexed benchmark, observed/daily return, cumulative return and excess return. Native range input provides keyboard and touch exploration.
- SPY, S&P 500 price index, NIFTY 50 price index and custom ticker selection. Currency mismatches block relative comparison without FX conversion.
- Portfolio/benchmark visibility, cumulative return, NAV/indexed benchmark, excess and drawdown views.
- Daily/weekly/monthly observations, mouse drag-to-select zoom, zoom buttons, reset and CSV export.
- Recorded event/cash-flow markers and native event-detail dialog. Contributions/withdrawals from archived observations are explicitly marked at observation end, not at an invented intraday transaction time. Calculated period moves of at least 5% are identified separately.
- Expandable drawdown/recovery analysis, rolling 30/60/90-observation volatility, monthly returns heatmap, rolling 63-observation Sharpe, Sortino, beta and information ratio. Analytical observations are available as text tables.

## Data and calculation policy
The new `/api/v1/dashboard/liquidity/benchmark-history` endpoint returns actual dated adjusted closes. Index symbols are disclosed as price-index returns; ETF adjusted closes are a provider-adjusted proxy, not a claim of certified total-return equivalence. There is no generated fallback curve. The previous fabricated fallback in the legacy benchmark endpoint was also removed.

Series normalize from their first observation. Relative performance needs at least two common observed UTC calendar dates in the same currency. No dates or missing portfolio values are interpolated or forward-filled. Without aligned dates, standalone series retain their own windows and excess return is unavailable. In NAV view recorded NAV uses the left currency axis and the benchmark uses an independent right axis indexed to 100. This view does not require matching return-report dates and does not imply comparable investment returns. The selected portfolio's current NAV is shown separately from the benchmark index.

Risk calculations use sample standard deviation, 252/52/12 daily/weekly/monthly periods, and at least 20 regular period returns. Rolling windows count observations. Annualized returns require at least 365 elapsed days; intraday observations are not annualized. Sharpe/Sortino use the explicitly entered annual risk-free assumption (default 0%). Zero-denominator and insufficient-history metrics remain unavailable. Zero and negative NAV records are not silently discarded. Legacy naive backend timestamps are interpreted as UTC; provider offsets are retained. Initial partial monthly returns and gaps between month ends are not presented as full monthly returns.

TWR and MWR come from archived performance records rather than being invented from NAV alone. MWR is a period summary and does not create a fictional daily IRR path. Unadjusted NAV mode explicitly includes external-flow effects. Summary metrics use the full selected period; zoom affects the plotted/exported window.

## Validation
- 10 frontend mathematical tests passed: drawdown, full loss, negative NAV, normalization, date alignment, UTC handling, annualization guards, cadence, aggregation and missing data.
- 4 backend tests passed: exact dated observations, unavailable-provider behavior, index disclosure and rejected invalid requests.
- TypeScript passed; Vite production build passed.
- Browser: live SPY endpoint rendered 251 observations; weekly aggregation produced 53; zoom/reset, methodology selection and drawdown controls exercised. CSV downloaded with 252 rows (251 benchmark observations plus the independent NAV timestamp); absent portfolio returns remained blank. Mobile viewport 390px fit without page-wide overflow. No console errors in final checks.

## Present data limits
The selected Multi-Strategy Risk Fund has one recorded NAV observation, no performance report and no scoped historical events. Portfolio-only return/risk metrics therefore show unavailable. Both return lines, relative metrics and real event-detail interaction cannot be validated against this portfolio until matching records exist. Benchmark analytics are explicitly labeled as benchmark data. No synthetic report, flow, trade or event was inserted to populate the display. Real-device touch gestures, mouse drag zoom and keyboard observation exploration were not exercised; button zoom and reset were exercised.

References: [GIPS handbook: time-weighted returns and external flows](https://www.gipsstandards.org/standards/gips-standards-for-firms/gips-standards-handbook-for-firms/), [yfinance history](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html). These are calculation references, not a claim of GIPS compliance.

## NAV-view correction
Previously SPY was hidden in NAV view unless at least two return-report dates aligned. With one NAV snapshot, this produced only one dot and disabled zoom. NAV now displays the available benchmark on its own labeled index axis; the actual NAV snapshot is centered on its currency axis. The snapshot warning explains why no portfolio trend exists. Constant-series axis ticks and point coordinates now share consistent bounds. Two regression tests cover constant and independent axes.
