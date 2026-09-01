# Mongrove

**Mongrove** is a keyboard-first MongoDB workspace for SSH sessions, servers, jump hosts, and every environment where MongoDB Compass cannot go.

It keeps the useful structure of a database GUI inside the terminal: namespaces on the left, query controls above, document results in the middle, and BSON-aware inspection beside them.

**Website:** [mongrove.oss.brahmai.in](https://mongrove.oss.brahmai.in)

## Install

```bash
pip install mongrove
```

Launch the workspace:

```bash
mongrove
```

Connect directly to a deployment:

```bash
mongrove mongodb://localhost:27017
```

For a production exploration session, start in interface read-only mode:

```bash
mongrove --read-only
```

`--read-only` is an interface safeguard. MongoDB server-side roles remain the security boundary. Use a least-privilege `read` user to enforce true production read-only access.

## Target Safeguards

Saved connection names are aliases. Give each alias an explicit `development`, `staging`, or `production` environment label so the active target is always visible in the workspace banner.

Production aliases open in local read-only mode by default. Intentional production changes require `--allow-production-writes`; every mutation still uses its own explicit confirmation flow. This is an operator safeguard, not a substitute for MongoDB roles.

Mongrove resolves startup settings from the command line first, then from environment variables. A command-line URI or `--alias` always wins over a shell's `MONGROVE_URI` or `MONGROVE_PROFILE` value.

```bash
export MONGROVE_PROFILE=staging-eu
export MONGROVE_ENVIRONMENT=staging
export MONGROVE_READ_ONLY=true
mongrove
```

Supported environment settings are `MONGROVE_URI`, `MONGROVE_PROFILE`, `MONGROVE_DATABASE`, `MONGROVE_COLLECTION`, `MONGROVE_CONFIG_DIR`, `MONGROVE_THEME`, `MONGROVE_ENVIRONMENT`, `MONGROVE_READ_ONLY`, `MONGROVE_NO_HISTORY`, and `MONGROVE_ALLOW_PRODUCTION_WRITES`. Boolean values accept `true`/`false`, `yes`/`no`, `on`/`off`, or `1`/`0`; invalid values fail safely at startup.

## What It Does Today

| Area | Available now |
| --- | --- |
| Connections | URI connection testing, named endpoint profiles, diagnostics, and reconnect/disconnect flow. |
| Privacy | Saved profiles remove URI credentials before writing local files. |
| Navigation | Lazy database and collection tree navigation. |
| Documents | Bounded result pages, dynamic table columns, BSON-aware JSON inspection, and a full-document modal. |
| Writes | Confirmed single-document insert, replace, and delete with canonical EJSON editing. |
| Export | Streaming query exports as JSON, canonical EJSON, or BSON-safe CSV. |
| Aggregation | Raw JSON/EJSON pipeline editor with bounded result previews and BSON-aware inspection. |
| Explain | Planner-only find and aggregation explain views with normalized warnings and raw EJSON. |
| Queries | JSON/Extended JSON filter, projection, sort, collation, skip, limit, and `maxTimeMS`. |
| History | Bounded per-target query history with search, names, favorites, filter copy, deletion, and safe full-state restore. |
| Themes | Four Mongrove themes, curated Textual themes, a keyboard picker, and saved preference. |
| Input | Keyboard-first workflows with optional mouse click, wheel, and header-sort support. |

The current release focuses on safe exploration, deliberately confirmed single-document changes, bounded-memory exports, and aggregation previews. Schema analysis, index management, validation, import, and live performance monitoring are planned next.

## First Session

1. Start `mongrove`, then enter a MongoDB URI.
2. Choose **Test and Connect** or press `Ctrl+Enter`.
3. Move through the namespace tree with arrow keys.
4. Press `Space` to expand a database and `Enter` to open a collection.
5. Enter a JSON or Extended JSON filter and press `F5` or `Enter`.
6. Use arrow keys to inspect result rows.
7. Press `Tab` to focus the JSON viewer, then use arrows, `PgUp`, `PgDn`, `Home`, or `End` to scroll long documents.
8. Press `Enter` on a result row to open its full BSON-aware document viewer.

## Query Examples

Mongrove accepts JSON and MongoDB Extended JSON in the filter input.

```json
{ "status": "active" }
```

```json
{ "_id": { "$oid": "65ba0aa00000000000000001" } }
```

Press `O` to set projection, sort, collation, skip, limit, and maximum server execution time. Leave Limit empty, or set it to `0`, to retain bounded result pages across all matching documents.

```json
{ "createdAt": -1, "_id": 1 }
```

Mongrove fetches one page plus one extra document to determine whether a next page exists. It does not automatically materialize a full collection or run an expensive exact count.

## Query History

Press `Ctrl+R` in a collection workspace to search and restore prior successful manual queries. Mongrove stores the complete find form, including filter, projection, sort, collation, pagination, and maximum execution time. Loading a saved entry does not execute it until you press `F5` or **Run**.

History is scoped to a hashed credential-free connection target and namespace. It retains 30 recent non-favorite queries per namespace and at most 1,000 non-favorite entries overall. Favorites are preserved until you remove them. Query filters can contain sensitive values, so use `--no-history` or `MONGROVE_NO_HISTORY=true` whenever local persistence is inappropriate.

## Confirmed Document Writes

For ordinary collections, **Insert**, **Replace**, and **Delete** are available beside the query results and through `Ctrl+P`. Each operation opens a canonical Extended JSON editor or an immutable selector preview, then a separate confirmation screen before Mongrove dispatches the write.

- Insert creates exactly one document.
- Replace uses `replace_one({"_id": original_id}, replacement, upsert=False)` and rejects a missing or changed `_id`.
- Delete uses `delete_one({"_id": original_id})` and requires an explicit target acknowledgement before it can proceed.
- Views, bulk writes, arbitrary write filters, upserts, and unacknowledged `w=0` writes are intentionally unsupported.

`--read-only` prevents every mutation locally. Production targets are also locally read-only unless launched with `--allow-production-writes`; permitted production writes require the exact `WRITE database.collection` acknowledgement in addition to the normal confirmation. MongoDB roles remain the real authorization boundary.

## Export

Use **Export** or `Ctrl+P` from an active collection to stream the full current find query to a local file. Export honors the filter, projection, sort, collation, skip, limit, and `maxTimeMS`; it does not export only the visible 25-row page.

- `json` writes a valid JSON array using relaxed Extended JSON.
- `ejson` writes a valid JSON array using canonical Extended JSON, the lossless option for BSON numeric and binary types.
- `csv` writes explicitly selected top-level columns. Each present cell is compact canonical EJSON, so nested values and BSON types remain unambiguous. Use EJSON when you need every field without choosing CSV columns.

The destination directory must already exist. Mongrove stages output in a same-directory temporary file and atomically replaces the destination only after the query finishes. Existing files require typing `OVERWRITE`; cancellation or an error removes the staged file and keeps the existing destination unchanged. Exports are not backups and do not guarantee a point-in-time snapshot.

## Aggregation Pipelines

Use **Aggregate** or `Ctrl+P` from an active collection to open the raw pipeline editor. Enter a JSON or Extended JSON array of single-operator stage documents, then press `Ctrl+Enter` to run a bounded 100-document preview. Results retain BSON-aware table cells and a full JSON inspector.

```json
[
  { "$match": { "status": "active" } },
  { "$group": { "_id": "$profile.city", "customers": { "$sum": 1 } } },
  { "$sort": { "customers": -1 } }
]
```

The editor detects `$out` and `$merge` and refuses to run them. Those pipeline stages mutate data, so they remain unavailable until a destination-review and explicit confirmation workflow is added.

## Explain Plans

Use **Explain** from the collection toolbar or **Explain Pipeline** in the aggregation editor to inspect planner-only explain output. Mongrove shows the normalized winning-plan stages, indexes, rejected-plan count, and evidence-based observations such as `COLLSCAN`, `SORT`, and `SHARD_MERGE`, while retaining the raw EJSON response for version-specific details.

Explain requests use a 5-second server cap and do not collect execution statistics or all-plans execution data. They are diagnostic planner evidence, not a normal-execution timing benchmark: MongoDB explain does not use the ordinary plan-cache path. Raw explain responses are never added to query history.

## Themes

Press `Ctrl+T` anywhere in Mongrove to open the theme picker. Choose a theme with arrow keys and `Enter`, or click it when mouse reporting is available. Picker selections are saved in local `settings.json` for the next launch.

| Theme | Style |
| --- | --- |
| Grove Night | Default deep-charcoal theme with bright green focus states. |
| Evergreen | Low-glare green palette for long server sessions. |
| Blue Hour | Navy foundation with cyan focus states. |
| Field Notes | Warm high-contrast light mode. |
| Dracula, Nord, Solarized, Gruvbox | Curated familiar Textual themes. |
| ANSI Dark / Light | 16-color fallbacks for limited terminal emulators. |

Choose a theme for one launch with `--theme`:

```bash
mongrove --theme mongrove-ocean
```

Available Mongrove theme IDs:

```text
mongrove-night
mongrove-forest
mongrove-ocean
mongrove-paper
```

## Keyboard and Mouse

| Control | Action |
| --- | --- |
| Arrow keys | Navigate the focused tree, table, option list, or JSON viewer. |
| `Space` | Expand or collapse the focused database tree node. |
| `Enter` | Open a collection, activate a result row, or select a picker item. |
| `Tab` / `Shift+Tab` | Move focus between controls and into the JSON viewer. |
| `F5` | Run the current query or refresh namespaces. |
| `O` | Open query options. |
| `Ctrl+R` | Search and restore local query history for the current collection. |
| `[` / `]` | Previous and next query result page. |
| `Ctrl+T` | Open the theme picker. |
| `Ctrl+D` | Disconnect. |
| `Ctrl+P` | Open Mongrove's contextual command palette for the active workspace or modal. |
| `Ctrl+Q` | Quit Mongrove. |
| `Esc` | Close the current modal or cancel the current action. |

Mouse behavior is an enhancement, never a requirement. Click to focus or activate controls, click table headers to sort, repeat-click a row to open it, and use the wheel over the JSON viewer to scroll. The keyboard path remains complete over SSH, tmux, GNU screen, and terminals with mouse reporting disabled.

## Configuration and Security

Mongrove stores non-secret local state in the platform configuration directory:

```text
connections.json   Saved endpoints with URI credentials removed
settings.json      Theme preference and future non-secret UI settings
```

Use `--config-dir` to keep this state elsewhere:

```bash
mongrove --config-dir /secure/mongrove
```

Security guidance:

- Mongrove does not persist URI passwords in saved profiles.
- Avoid passwords in command-line arguments because they can appear in process listings and shell history.
- Prefer a short-lived prompt, secret injection, or a least-privilege MongoDB user.
- Do not treat future data exports as backups. Use MongoDB backup tooling for backup and restore workflows.

## Development

The repository includes a Conda environment at `.conda_env` for development on this workspace.

```powershell
.\.conda_env\python.exe -m pip install -e ".[dev]"
.\.conda_env\python.exe -m pytest -q -p no:cacheprovider
```

Run the package directly from source:

```powershell
.\.conda_env\python.exe -m mongrove
```

The public landing page source lives in [`site/`](site/). It is dependency-free and deploys to [mongrove.oss.brahmai.in](https://mongrove.oss.brahmai.in).

For the complete product, UX, safety, and delivery specification, read [MONGROVE_PLAN.md](MONGROVE_PLAN.md).
