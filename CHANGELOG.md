# Changelog

## 2026-08-16

### Phase 0 — Baseline health audit
- Implemented the full Phase 0 health-check suite for Alpaca, Finnhub, Gemini, indicator internals, and the pipeline.
- Fixed the feed-selection bug in the Alpaca health script so the report correctly handles an invalid or missing `ALPACA_DATA_FEED` without crashing.
- Corrected aggregate service accounting so a broken service is reflected properly in the overall health summary.
- Marked the Phase 0 milestone as complete in the roadmap.

### Phase 1 — Run IDs and observability foundation
 - Added a unique run identifier to each analysis cycle using the format `RUN-YYYYMMDD-HHMMSS-SYMBOL`.
 - The run ID is now shared across the orchestrator session, agent message bus, and final API payload.
 - Added a regression test to lock in the behavior and prevent reintroducing the missing run-id contract.
 - Project plan marked Phase 1 as complete and ready for review.

### Phase 2 — Event and trace tracking
- Added an observability package with JSONL-backed run tracking, event logging, metrics summaries, and health snapshots.
- Hooked the run tracker into the orchestrator so each analysis produces a traceable event stream tied to the run ID.
- Added a dedicated regression test to ensure the event stream and run summary behave as expected.
- Marked the Phase 2 milestone as complete in the roadmap.

### Phase 3 — Live agent room
- Confirmed the dashboard’s inter-agent group chat is the live agent room centerpiece for each analysis run.
- Renamed the active panel to the explicit LIVE AGENT ROOM label for clarity and presentation.
- Marked the Phase 3 milestone as complete in the roadmap.

### Phase 4 — API call inspector
- Added the missing API endpoint that exposes recorded run-level API events for inspection.
- Hooked the inspector to the run tracker so external provider calls are visible and searchable by run.
- Marked the Phase 4 milestone as complete in the roadmap.

### Notes
- Phase 0 establishes the real baseline for the observability roadmap and gives the project a measurable health snapshot before new features are layered on.
- Added a unique run identifier to each analysis cycle using the format `RUN-YYYYMMDD-HHMMSS-SYMBOL`.
- The run ID is now shared across the orchestrator session, agent message bus, and final API payload.
- Added a regression test to lock in the behavior and prevent reintroducing the missing run-id contract.
- Project plan marked Phase 1 as complete and ready for review.

### Notes
- Phase 0 establishes the real baseline for the observability roadmap and gives the project a measurable health snapshot before new features are layered on.
