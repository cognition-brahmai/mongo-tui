# MongoTUI

MongoTUI is a keyboard-first terminal workspace for MongoDB. It is built for SSH sessions, Ubuntu servers, jump hosts, and other environments where MongoDB Compass is unavailable or impractical.

The interface is designed around Compass-style exploration without requiring a graphical desktop: connect, browse namespaces, run find queries, inspect BSON documents, and move quickly between results using either keyboard controls or terminal mouse support.

## Current Capabilities

| Area | Available now |
| --- | --- |
| Connections | MongoDB URI connection testing, saved endpoint profiles, connection diagnostics, and disconnect/reconnect workflow. |
| Privacy | Saved profiles remove URI credentials before writing local files. |
| Navigation | Database and collection tree with lazy collection loading. |
| Documents | Bounded result pages, dynamic table columns, BSON-aware JSON inspection, and a full-document modal. |
| Queries | JSON/Extended JSON filter, projection, sort, collation, skip, limit, and `maxTimeMS`. |
| Themes | Four MongoTUI themes plus curated Textual themes, keyboard picker, CLI selection, and saved preference. |
| Input | Keyboard-first operation with optional click, repeated-click, header-sort, wheel-scroll, and pointer support. |

The current application is intentionally read-only. Write operations, aggregation editing, schema analysis, indexes, validation, import/export, and live performance monitoring are planned next. See [MONGOTUI_PLAN.md](MONGOTUI_PLAN.md) for the complete product plan.

## Quick Start

This repository uses the supplied Conda environment at `.conda_env`.

```powershell
.\.conda_env\python.exe -m pip install -e ".[dev]"
.\.conda_env\python.exe -m mongotui
```

Connect directly to a local server:

```powershell
.\.conda_env\python.exe -m mongotui mongodb://localhost:27017
```

Open a specific namespace after connecting:

```powershell
.\.conda_env\python.exe -m mongotui mongodb://localhost:27017 --database app --collection users
```

Use the read-only interface mode for production exploration:

```powershell
.\.conda_env\python.exe -m mongotui --read-only
```

`--read-only` hides write-oriented UI controls as they are introduced. MongoDB roles are still the security boundary; use a server-side `read` role to enforce real production read-only access.

## First Workflow

1. Start MongoTUI and enter a MongoDB URI.
2. Choose **Test and Connect** or press `Ctrl+Enter`.
3. Move through the namespace tree using arrow keys.
4. Press `Space` to expand a database and `Enter` to open a collection.
5. Enter a JSON or Extended JSON filter and press `F5` or `Enter`.
6. Use arrow keys to inspect result rows.
7. Press `Tab` to focus the JSON viewer, then use arrows, `PgUp`, `PgDn`, `Home`, or `End` to scroll long documents.
8. Press `Enter` on a result row to open the full BSON-aware document viewer.

## Themes

Press `Ctrl+T` anywhere in MongoTUI to open the theme picker. Use arrow keys and `Enter`, or click a theme with the mouse. Selections made in the picker are saved in MongoTUI's local `settings.json` and used on the next launch.

| Theme | Style |
| --- | --- |
| Mongo Night | Default deep-charcoal theme with MongoDB green accents. |
| Emerald Forest | Low-glare green palette for long server sessions. |
| Midnight Ocean | Navy background with cyan focus states. |
| Mongo Paper | Warm high-contrast light mode. |
| Dracula | Familiar purple dark palette. |
| Nord | Cool arctic dark palette. |
| Solarized Dark / Light | Low-contrast palettes for dark or bright environments. |
| Gruvbox | Warm retro dark palette. |
| ANSI Dark / Light | 16-color fallbacks for limited terminal emulators. |

Choose a theme for a single launch with `--theme`:

```powershell
.\.conda_env\python.exe -m mongotui --theme mongotui-ocean
```

Available CLI values are:

```text
mongotui-night
mongotui-forest
mongotui-ocean
mongotui-paper
dracula
nord
solarized-dark
solarized-light
gruvbox
ansi-dark
ansi-light
```

## Query Examples

MongoTUI accepts JSON and MongoDB Extended JSON in the filter input.

Find active users:

```json
{ "status": "active" }
```

Find one document by ObjectId:

```json
{ "_id": { "$oid": "65ba0aa00000000000000001" } }
```

Open query options with `O` to set projection, sort, collation, skip, limit, and maximum server execution time. Leave Limit empty, or set it to `0`, to retain normal bounded UI pagination across all matching documents.

Example sort option:

```json
{ "createdAt": -1, "_id": 1 }
```

MongoTUI fetches one page plus one extra document to detect whether a next page exists. It does not automatically materialize an entire collection or run an expensive exact count.

## Keyboard and Mouse Controls

| Key | Action |
| --- | --- |
| Arrow keys | Navigate the focused tree, table, option list, or JSON viewer. |
| `Space` | Expand or collapse the focused database tree node. |
| `Enter` | Open a collection, activate a result row, or select a picker item. |
| `Tab` / `Shift+Tab` | Move focus between controls and into the JSON viewer. |
| `F5` | Run the current query or refresh namespaces. |
| `O` | Open query options. |
| `[` / `]` | Previous and next query result page. |
| `Ctrl+T` | Open the theme picker. |
| `Ctrl+D` | Disconnect. |
| `Ctrl+P` | Open Textual's command palette. |
| `Ctrl+Q` | Quit MongoTUI. |
| `Esc` | Close the current modal or cancel the current operation. |

Terminal mouse interactions are optional enhancements. Click to focus or activate controls, repeat-click a result row to open it, click a column header to sort, and use the mouse wheel over the JSON viewer to scroll. Keyboard controls remain complete when mouse reporting is unavailable over SSH, tmux, screen, or a restricted terminal.

## Configuration and Security

MongoTUI stores local files in the platform configuration directory by default:

```text
connections.json   Saved connection endpoints without URI credentials
settings.json      Theme preference and future non-secret UI settings
```

Use `--config-dir` to keep this state in a different directory:

```powershell
.\.conda_env\python.exe -m mongotui --config-dir C:\secure\mongotui
```

Security guidance:

- MongoTUI does not persist URI passwords in saved profiles.
- Avoid passwords in command-line arguments because they can appear in process listings or shell history.
- Prefer a short-lived URI prompt, environment-specific secret injection, or a least-privilege MongoDB user for server access.
- Saved query history is planned but not currently stored.
- Do not treat document exports, once implemented, as backups. Use MongoDB backup tooling for backup and restore workflows.

## Development

Run the full test suite through the supplied Conda environment:

```powershell
.\.conda_env\python.exe -m pytest -q -p no:cacheprovider
```

The project uses:

- Python 3.10+.
- Textual for the terminal UI, focus management, themes, workers, and tests.
- PyMongo for MongoDB connectivity and BSON support.
- Rich, bundled through Textual, for syntax-aware terminal rendering.

The package layout keeps MongoDB calls behind a synchronous gateway invoked from Textual workers. UI tests use a fake gateway, so core workflows can be tested without a running MongoDB server.