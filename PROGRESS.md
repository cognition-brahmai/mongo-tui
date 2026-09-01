# Development Progress

This log records the feature branches merged into `dev`. Each feature is implemented and verified on its own branch before integration.

| Feature | Branch | Status |
| --- | --- | --- |
| Mongrove rename baseline | `dev` | Complete |
| Connection aliases and environment safeguards | `feature/connection-safety` | Complete |
| Query history | `feature/query-history` | Complete |
| Command palette actions | `feature/command-palette` | Complete |
| Confirmed document writes | `feature/confirmed-writes` | Complete |
| Export | `feature/export` | Complete |
| Aggregation pipeline editor | `feature/aggregation-editor` | Complete |
| Explain plans | `feature/explain-plans` | Planned |
| Index management | `feature/index-management` | Planned |
| Schema sampling | `feature/schema-sampling` | Planned |
| pipx deployment | `feature/pipx-deployment` | Planned |

## Log

- 2026-09-01: Created `dev` and committed the tested Mongrove rename baseline (`e74838c`).
- 2026-09-01: Added aliases, persisted environment labels, CLI/environment startup resolution, production safety indicators, and a central session policy on `feature/connection-safety`.
- 2026-09-01: Added bounded, target-scoped SQLite query history with search, restore, favorites, naming, copy, deletion, and `--no-history` enforcement on `feature/query-history`.
- 2026-09-01: Added contextual `Ctrl+P` command-palette actions for global controls and every current connection, browser, document, query, history, and modal operation on `feature/command-palette`.
- 2026-09-01: Added policy-gated, acknowledged single-document insert, replace, and delete workflows with canonical EJSON editors and explicit confirmation on `feature/confirmed-writes`.
- 2026-09-01: Added atomic, streaming JSON, canonical EJSON, and BSON-safe CSV exports for full active find queries on `feature/export`.
- 2026-09-01: Added a raw JSON/EJSON aggregation editor with bounded BSON-aware previews and write-stage detection on `feature/aggregation-editor`.
