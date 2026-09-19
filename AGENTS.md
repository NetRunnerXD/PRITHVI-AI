# Agent notes

1. Read `docs/CODEMAP.md` then `docs/codegraph.json` before editing.
2. Product rules live in `project.md` §2. Do not invent millimetres, AQI, rupees, or risk scores in the LLM.
3. Public imports to keep stable:
   - `app.services.snapshot` (`build_snapshot`, `peek_snapshot`, `gather_observations`, `_warnings`, `pin_key`, `primary_reply`)
   - `@/components/OverviewLive` (`OverviewLive`, `OverviewPlots`, `alertTimePhase`)
   - `app.agents.orchestrator.run_agent`
4. Refresh the graph after structural moves: `python backend/scripts/codebase_graph.py`.
