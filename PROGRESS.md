# Development Progress

This log records the feature branches merged into `dev`. Each feature is implemented and verified on its own branch before integration.

| Feature | Branch | Status |
| --- | --- | --- |
| Mongrove rename baseline | `dev` | Complete |
| Connection aliases and environment safeguards | `feature/connection-safety` | Complete |
| Query history | `feature/query-history` | Planned |
| Command palette actions | `feature/command-palette` | Planned |
| Confirmed document writes | `feature/confirmed-writes` | Planned |
| Export | `feature/export` | Planned |
| Aggregation pipeline editor | `feature/aggregation-editor` | Planned |
| Explain plans | `feature/explain-plans` | Planned |
| Index management | `feature/index-management` | Planned |
| Schema sampling | `feature/schema-sampling` | Planned |
| pipx deployment | `feature/pipx-deployment` | Planned |

## Log

- 2026-09-01: Created `dev` and committed the tested Mongrove rename baseline (`e74838c`).
- 2026-09-01: Added aliases, persisted environment labels, CLI/environment startup resolution, production safety indicators, and a central session policy on `feature/connection-safety`.
