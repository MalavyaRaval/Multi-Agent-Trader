# Changelog

All notable changes to this project will be documented in this file.

### Added
- Added a dedicated regression test file for the portfolio performance range logic:
  - `tests/test_portfolio_return_calculations.py`
- Documented the portfolio visualization/data layer in the project guide so the chart pipeline is clearer to future contributors.
- Clarified the project structure to include the visualization, static, and test folders that were previously under-documented.

### Fixed
- Fixed the portfolio chart range state synchronization so the selected range, button active state, and chart fetch all use the same normalized value.
- Fixed the portfolio return calculation for longer windows so placeholder zero-equity rows no longer distort return percentages for 2M, 3M, 6M, 1Y, and All ranges.
- Corrected the return baseline logic to use the first valid non-zero equity value and avoid synthetic or misleading performance values at the beginning of the selected window.
- Improved the professional trading-style chart behavior by keeping each range window anchored to a meaningful real trading baseline instead of an artificial placeholder start.

### Changed
- Updated the project documentation to reflect the current dashboard architecture, including the visualization and static front-end layers.
- Standardized the portfolio chart logic to be more analytically useful for comparison across time ranges and for performance review.

## [2026-08-14]

### Fixed
- Resolved the stale and inconsistent portfolio range selection issue where the label and graph could drift out of sync.
- Fixed the longer-range calculation bug that caused portfolio performance to appear incorrect when selecting ranges beyond 1 month.

### Added
- Added portfolio return regression tests validating baseline behavior and placeholder-zero handling.
