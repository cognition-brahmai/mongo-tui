# Mongrove Product and Technical Plan

## 1. Purpose

Mongrove is a Python terminal user interface for working directly with MongoDB deployments on servers where a graphical MongoDB Compass client is unavailable or unsuitable.

It should provide the core exploratory and operational workflows of MongoDB Compass in a terminal-native form:

- Connect to MongoDB deployments safely.
- Browse servers, databases, collections, and views.
- Query, inspect, edit, insert, clone, and delete documents.
- Build and execute aggregation pipelines.
- Inspect schemas, indexes, validators, query plans, and server activity.
- Import and export data without treating exports as backups.

Mongrove will be a keyboard-first application built with Textual and PyMongo. Mouse input enhances the experience when terminal mouse reporting is available, but no function may depend on a mouse.

## 2. Product Principles

| Principle | Decision |
| --- | --- |
| Keyboard complete | Every action is reachable through focus navigation, shortcuts, action menus, or the command palette. |
| Mouse enhanced | Click, double-click, scroll, tab selection, header sorting, right-click action menus, and splitter dragging are optional accelerators. |
| Information dense | Show query timing, result counts, size information, BSON types, connection state, permissions, and errors where users need them. |
| Context preserving | Opening inspectors, editors, explain plans, and action menus must preserve the current query, page, selection, and scroll position. |
| BSON correct | ObjectId, Date, Decimal128, UUID, Binary, Timestamp, Int64, and other BSON types must not silently lose type information. |
| Safe by default | Destructive actions require explicit confirmation. Empty-filter writes need stronger confirmation. |
| Responsive | The interface works at 80x24 and progressively improves at larger terminal sizes. |
| Honest metadata | Cached counts, sampled schema results, unavailable permissions, and approximate values are always labeled. |
| Direct-server focused | The core product targets standard MongoDB deployments, not Atlas-only, graphical, or AI-only features. |

## 3. Scope and Non-Goals

### In scope

- Standalone, replica set, and sharded MongoDB deployments.
- Standard MongoDB connection strings, TLS, authentication, and read preferences.
- Data exploration, CRUD, aggregation, indexes, validation, schema summaries, explain plans, import/export, and monitoring.
- SSH-friendly terminal operation.
- Keyboard-only operation in terminals without mouse reporting.
- Optional mouse support in capable terminals.

### Explicit non-goals for the direct-server core

- Replacing MongoDB backup and restore tools.
- Graphical map rendering.
- Drag-and-drop as a required aggregation workflow.
- Atlas AI assistant functionality.
- Atlas Search or Vector Search management unless deployment capabilities are detected and a later extension supports them.
- A browser-style accessibility claim. Terminal accessibility must be validated against the actual terminal and assistive technology used by operators.

## 4. Information Architecture

```text
Mongrove
|
+-- Connection Manager
|   +-- Saved connections
|   +-- Favorites
|   +-- New connection
|   +-- Authentication and TLS
|   +-- Connection diagnostics
|
+-- Deployment Workspace
|   +-- Deployment overview
|   +-- Databases
|   +-- Performance
|   +-- Current operations
|   +-- Saved queries
|
+-- Database Workspace
|   +-- Collections
|   +-- Views
|   +-- Database statistics
|   +-- Create collection
|
+-- Collection Workspace
|   +-- Documents
|   +-- Aggregations
|   +-- Schema
|   +-- Indexes
|   +-- Validation
|   +-- Collection details
|
+-- Global Tools
    +-- Command palette
    +-- Query history
    +-- Import and export jobs
    +-- Connection information
    +-- Settings
    +-- Keyboard help
```

The left sidebar provides global namespace navigation. The center area hosts the active workspace. A document inspector or equivalent detail pane appears beside the active workspace on wide terminals and as a temporary full-screen view on narrow terminals.

## 5. Primary Workflows

| Workflow | User outcome |
| --- | --- |
| Connect | Connect to a server from a URI, profile, or environment variable and see actionable diagnostics on failure. |
| Explore | Navigate connection -> database -> collection or view and inspect current database and collection metadata. |
| Query | Enter a filter, projection, sort, collation, skip, limit, and max time; validate it; execute it; page through results. |
| Inspect | Expand a document, view exact EJSON, inspect fields and types, copy data, or add a field/value to a filter. |
| Modify | Insert, patch, replace, clone, or delete documents with distinct semantics and strong confirmations. |
| Aggregate | Build or edit a pipeline, preview stages, execute it, inspect results, save it, and explain it. |
| Analyze | Sample a collection and inspect field presence, BSON types, cardinality, distributions, and candidate validator rules. |
| Optimize | Inspect indexes and query plans, identify scans and inefficient ratios, and create or drop indexes safely. |
| Operate | Inspect deployment activity, current operations, slow operations, and hot collections when privileges permit. |

## 6. Main Screens

### 6.1 Connection Manager

```text
+ Mongrove ---------------------------------------------------------------+
| CONNECTIONS                                        New Connection       |
+----------------------------+--------------------------------------------+
| [/] Search connections     | Name                                      |
|                            | [ Production EU                         ]  |
| * Production EU   ACTIVE   |                                            |
|   Local Docker             | Connection URI                             |
|   Staging API              | [ mongodb://db.internal:27017           ]  |
|   Analytics                |                                            |
|                            | Credentials are not saved by default.      |
|                            |                                            |
|                            | [General] [Auth] [TLS] [Advanced]          |
|                            |                                            |
|                            | Authentication: Username / Password        |
|                            | Username      [ app_reader              ]  |
|                            | Password      [ ********                ]  |
|                            | Auth source   [ admin                   ]  |
|                            |                                            |
|                            | Connection timeout   [ 10,000 ms        ]  |
|                            | Server selection     [ 30,000 ms        ]  |
|                            |                                            |
|                            | [ Test Connection ]  [ Save ]  [ Connect ] |
+----------------------------+--------------------------------------------+
| STATUS  Connected to db.internal:27017 | MongoDB 8.0 | PRIMARY | 8 ms |
+-------------------------------------------------------------------------+
| Tab Next field | Shift+Tab Previous | Ctrl+T Test | Ctrl+Enter Connect |
+-------------------------------------------------------------------------+
```

#### Connection requirements

- Accept `mongodb://` and `mongodb+srv://` connection strings.
- Support standalone servers, replica sets, and sharded deployments.
- Support username/password authentication in the initial release.
- Support TLS certificates, certificate authorities, and insecure TLS options only with a visible warning.
- Support authentication source, authentication mechanism, direct connection, read preference, application name, and timeouts.
- Test the connection before saving or connecting.
- Show clear server selection, authentication, TLS, DNS, timeout, and permission errors.
- Let users save named profiles and favorites.
- Never persist passwords by default.
- Allow credentials from an interactive prompt, environment variables, an optional system keyring, or an explicitly opted-in encrypted store.
- Redact credentials in logs, errors, copy actions, and status displays.
- Offer a read-only UI mode, while explaining that server-side roles are the real security boundary.

### 6.2 Deployment Overview

```text
+ Mongrove -- Production EU [PRIMARY] ------------------------------------+
| [Connections]  Production EU > Overview                 [Reconnect] [x] |
+----------------------+--------------------------------------------------+
| NAMESPACES           | DEPLOYMENT                                       |
| [/] Search           | MongoDB version     8.0.3                        |
|                      | Topology            Replica set                  |
| v Production EU      | Primary             mongo-1.internal:27017       |
|   > admin            | Members             3                            |
|   > app              | Logical data size   18.4 GB                      |
|   > analytics        | Index size          4.7 GB                       |
|   > logs             | Connections         73 current / 838 available   |
|                      | Uptime              31d 07h                       |
|                      |                                                  |
|                      | DATABASES                                        |
|                      | Name       Collections   Data       Indexes       |
|                      | app        18            8.2 GB     2.1 GB        |
|                      | analytics  12            6.7 GB     1.8 GB        |
|                      | logs       7             3.5 GB     0.8 GB        |
+----------------------+--------------------------------------------------+
| CONNECTED | user: app_reader | role: read | ping: 8 ms | refreshed 3s  |
+-------------------------------------------------------------------------+
| F5 Refresh | Enter Open | A Actions | P Performance | Ctrl+P Commands  |
+-------------------------------------------------------------------------+
```

The deployment overview is the initial screen after connecting. It prevents users from landing in an unexplained raw document list and exposes topology, server version, latency, database summaries, and role limitations.

Unavailable values must render as `N/A` or `Unavailable`, never as zero. Cached or estimated statistics use a `~` marker and concise explanatory help.

### 6.3 Database Workspace

```text
+ Production EU > app ----------------------------------------------------+
| [Overview] [Collections] [Performance]                 [Create Collection]|
+--------------------------------------------------------------------------+
| COLLECTIONS  18                                        Updated 4 sec ago |
| [/] Search collections               Sort: [Data size desc]              |
+----------------------+-------+----------+----------+---------+------------+
| Name                 | Type  | Docs     | Data     | Indexes | Avg doc    |
+----------------------+-------+----------+----------+---------+------------+
| customers            | coll  | 124.2 K~ | 1.8 GB   | 6       | 15.1 KB    |
| orders               | coll  | 9.7 M~   | 4.6 GB   | 8       | 509 B      |
| active_customers     | view  | --       | --       | --      | --         |
| audit_events         | coll  | 33.1 M~  | 2.1 GB   | 3       | 68 B       |
+----------------------+-------+----------+----------+---------+------------+
| "~" indicates a cached or estimated value.                              |
+--------------------------------------------------------------------------+
| Enter Open | N New | A Actions | S Sort | F5 Refresh | ? Help            |
+--------------------------------------------------------------------------+
```

#### Collection actions

- Open a collection or view.
- Open a collection in an additional workspace in a later release.
- Copy a namespace.
- Show collection details and statistics.
- Export documents.
- Create a collection or view.
- Drop a collection with typed-name confirmation.
- Rename only where the target server and selected semantics support it.

The action menu is available via `A`, a command palette action, a visible button, and right-click where supported.

### 6.4 Collection Documents Workspace

```text
+ Production EU > app > customers --------------------- READ ONLY --------+
| [Documents] [Aggregations] [Schema] [Indexes] [Validation] [Details]     |
+--------------------------------------------------------------------------+
| FILTER                                                                   |
| { "status": "active", "profile.age": { "$gte": 18 } }          [ RUN ]   |
| Options: Project [set] Sort [set] Collation [-] Skip [0] Limit [25]      |
|          Max Time [60000 ms]                               [Reset] [More] |
+--------------------------------------------------------------------------+
| 124,219 docs~ | 25 shown | query 18 ms | page 1 | LIST  TABLE  JSON      |
+--------------------+-----------------------------------------------------+
| DOCUMENTS          | SELECTED DOCUMENT                                   |
|                    |                                                     |
| > 1  ObjectId(...) | _id          ObjectId("66...")                      |
|      Alice Morgan  | name         "Alice Morgan"                         |
|      active        | status       "active"                               |
|                    | email        "alice@example.com"                    |
|   2  ObjectId(...) | profile      {                                      |
|      Robert Chen   |   age        34                                     |
|      active        |   location   {                                      |
|                    |     city     "London"                               |
|   3  ObjectId(...) |     country  "GB"                                   |
|      Kim Patel     |   }                                                 |
|      active        | }                                                   |
|                    | roles        [ "user", "editor" ]                    |
|                    | createdAt    ISODate("2026-03-12T08:15:03Z")         |
|                    |                                                     |
|                    | [Edit] [Clone] [Copy] [Delete] [Add to Filter]      |
+--------------------+-----------------------------------------------------+
| QUERY OK | app.customers | sort: createdAt -1 | returned 25 | 18 ms      |
+--------------------------------------------------------------------------+
| Tab Focus | Enter Expand/Open | A Actions | E Edit | N Insert | ] Next   |
+--------------------------------------------------------------------------+
```

#### Document views

| View | Use case | Initial release behavior |
| --- | --- | --- |
| List | Heterogeneous MongoDB documents | Compact document cards with selected document inspector. |
| Table | Compare top-level values across documents | Rows are documents; fields are columns; `_id` is pinned by default. |
| JSON | Inspect exact structure and BSON-compatible values | Syntax-highlighted Extended JSON with nesting controls. |

List view is the primary document view because MongoDB collections commonly contain heterogeneous nested documents.

#### Query bar requirements

- Filter.
- Projection.
- Sort.
- Collation.
- Skip.
- Limit.
- Maximum execution time.
- Clear syntax errors with a location and a useful explanation.
- Preserve prior valid results when a user has an invalid in-progress query.
- Display active query settings in the result summary.
- Show query duration, result count state, page, returned document count, and whether more documents are available.
- Support recent queries and named query favorites.
- Support an explicit exact count request instead of automatically counting huge collections.

#### Query options dialog

```text
+ Query Options ----------------------------------------------------------+
| Projection                                                              |
| { "name": 1, "email": 1, "profile.age": 1 }                             |
|                                                                          |
| Sort                                                                     |
| { "createdAt": -1, "_id": 1 }                                           |
|                                                                          |
| Collation                                                                |
| { "locale": "en", "strength": 2 }                                       |
|                                                                          |
| Skip             [ 0          ]                                          |
| Limit            [ 25         ]                                          |
| Max Time MS      [ 60000      ]                                          |
|                                                                          |
| [ Validate ]                         [ Cancel ] [ Apply and Run ]          |
+--------------------------------------------------------------------------+
| Tab Next | Shift+Tab Previous | Ctrl+Enter Apply | Esc Cancel             |
+--------------------------------------------------------------------------+
```

The query options dialog is available through the visible `More` button, `O`, focus navigation, and the command palette.

### 6.5 Document Inspector and Editor

```text
+ Edit Document ----------------------------------------------------------+
| app.customers                                               PATCH MODE   |
| _id: ObjectId("66f7...")                                                |
+--------------------------------------------------------------------------+
|  1 {                                                                    |
|  2   "_id": { "$oid": "66f7..." },                                      |
|  3   "name": "Alice Morgan",                                            |
|  4   "status": "active",                                                |
|  5   "profile": {                                                       |
|  6     "age": 35,                                                       |
|  7     "city": "London"                                                 |
|  8   }                                                                  |
|  9 }                                                                    |
+--------------------------------------------------------------------------+
| VALID EJSON | Changed fields: profile.age                               |
|                                                                          |
| Preview                                                                  |
| - "profile.age": 34                                                     |
| + "profile.age": 35                                                     |
|                                                                          |
| [ Validate ] [ Revert ] [ Cancel ] [ Save Changes ]                      |
+--------------------------------------------------------------------------+
| Ctrl+S Save | Ctrl+Z Undo | Ctrl+F Find | Esc Cancel                     |
+--------------------------------------------------------------------------+
```

Document editing has two explicit, visibly distinct modes:

| Mode | MongoDB behavior |
| --- | --- |
| Patch | Generate `$set` and `$unset` operations for fields changed by the user. |
| Replace | Replace the full document while following immutable `_id` constraints. |

The initial edit format is Extended JSON. Shell-style constructors can be added later through a dedicated parser. Python `eval` must never be used to parse document input.

#### Document operations

- Insert one document or a list of documents.
- Patch a document.
- Replace a document.
- Clone a document into the insert editor.
- Delete a document.
- Copy a document or a selected field.
- Add a selected field/value to the active filter.
- Export selected documents.
- Search within an expanded document.

### 6.6 Aggregation Workspace

```text
+ app.customers > Aggregations -------------------------------------------+
| Pipeline: Active users by country                     [Save] [Explain]   |
+---------------------------------+----------------------------------------+
| STAGES                          | STAGE PREVIEW                          |
|                                 |                                        |
| > 1  $match          enabled    | 1,284 documents                        |
|      { status: "active" }       |                                        |
|                                 | {                                      |
|   2  $group          enabled    |   "_id": "GB",                         |
|      group by country           |   "users": 412                         |
|                                 | }                                      |
|   3  $sort           enabled    |                                        |
|      users descending           | { "_id": "US", "users": 396 }          |
|                                 | { "_id": "DE", "users": 218 }          |
| [+ Add Stage]                   |                                        |
+---------------------------------+----------------------------------------+
| Result: 24 docs | 72 ms | Max Time 60000 ms | No write stages detected  |
+--------------------------------------------------------------------------+
| Enter Edit | N Add | A Actions | Ctrl+Up/Down Reorder | F5 Run | T Raw   |
+--------------------------------------------------------------------------+
```

#### Aggregation requirements

- Raw pipeline editor is a first-class workflow.
- Add, edit, delete, enable, and disable stages.
- Reorder stages through keyboard and mouse interactions.
- Preview a stage and execute the full pipeline.
- Configure max execution time and collation.
- Save and load named pipelines.
- Explain a pipeline.
- Export results.
- Create a view from a pipeline when privileges allow it.
- Detect `$out` and `$merge` stages before execution.
- Require a stronger confirmation for write stages and show the destination namespace.

On narrow terminals, the raw pipeline editor is primary and previews open in a dedicated pane or screen.

### 6.7 Schema Workspace

```text
+ app.customers > Schema -------------------------------------------------+
| Sample: 1,000 random documents | Filter: status="active" | 1.4 sec       |
+----------------------+----------+----------------------+----------+-------+
| Field                | Present  | BSON Types           | Cardinality | Info|
+----------------------+----------+----------------------+-------------+-----+
| _id                  | 100.0%   | ObjectId 100%        | 1,000       | >   |
| name                 | 99.8%    | string 100%          | 984         | >   |
| status               | 100.0%   | string 100%          | 4           | >   |
| profile.age          | 87.4%    | int32 92%, str 8%    | 73          | >   |
| profile.country      | 75.2%    | string 100%          | 42          | >   |
| roles                | 91.0%    | array 100%           | 18 shapes   | >   |
| createdAt            | 100.0%   | date 100%            | 997         | >   |
+----------------------+----------+----------------------+-------------+-----+
| profile.age: min 18 | max 93 | common values                              |
| 18-29  ########################  41%                                     |
| 30-49  ####################      34%                                     |
| 50-69  ###########               19%                                     |
| 70+    ####                       6%                                     |
+--------------------------------------------------------------------------+
| S Sample | Enter Inspect Field | F Add Field Filter | X Export Schema    |
+--------------------------------------------------------------------------+
```

Schema analysis is explicitly sampled. It must state the sample size, active query filter, timing, and any sampling limitation.

#### Schema functionality

- Configurable random sample size.
- Field presence percentage.
- BSON type distribution, including mixed types.
- Cardinality.
- Minimum and maximum values.
- Common values.
- Numeric and date distributions using text bars.
- Array length statistics.
- Nested field expansion.
- Sample values.
- Generated filters from selected values.
- Export as JSON Schema.
- Export as a MongoDB validator candidate.

### 6.8 Index Workspace

```text
+ app.customers > Indexes -----------------------------------------------+
| 6 indexes | Total size 2.1 GB                         [Create Index]     |
+--------------------+------------------------+---------+--------+----------+
| Name               | Keys                   | Size    | Usage  | Properties|
+--------------------+------------------------+---------+--------+----------+
| _id_               | _id: 1                 | 420 MB  | 8.1 M  | unique   |
| email_1            | email: 1               | 610 MB  | 1.7 M  | unique   |
| status_createdAt   | status: 1, date: -1    | 740 MB  | 902 K  | compound |
| expire_sessions    | expiresAt: 1           | 330 MB  | 18 K   | TTL 0s   |
+--------------------+------------------------+---------+--------+----------+
| Selected: status_createdAt                                               |
| Last used statistics are node-local and reset after server restart.      |
| [Details] [Explain Query] [Hide] [Drop]                                  |
+--------------------------------------------------------------------------+
| N New | Enter Details | A Actions | S Sort | F5 Refresh                   |
+--------------------------------------------------------------------------+
```

#### Index functionality

- List index key patterns, types, sizes, usage, and properties.
- Create ordinary and compound indexes.
- Support unique, TTL, partial, wildcard, text, and geospatial indexes in later phases.
- Hide and unhide indexes where supported.
- Drop indexes with typed-name confirmation.
- Open an explain workflow based on a selected index or the active document query.
- Explain that index usage statistics are node-local and reset when the server restarts.

Atlas Search and Vector Search index administration are not part of the direct-server core. They may become capability-gated extensions later.

### 6.9 Validation Workspace

```text
+ app.customers > Validation ---------------------------------------------+
| Level: strict | Action: error | Source: collection validator             |
+--------------------------------------------------------------------------+
| {                                                                        |
|   "$jsonSchema": {                                                       |
|     "bsonType": "object",                                                |
|     "required": ["name", "email"],                                       |
|     "properties": {                                                      |
|       "email": { "bsonType": "string" },                                 |
|       "profile.age": { "bsonType": "int", "minimum": 0 }                 |
|     }                                                                    |
|   }                                                                      |
| }                                                                        |
+--------------------------------------------------------------------------+
| Preview against sample                                                   |
| Pass: 988 / 1000    Fail: 12 / 1000                                     |
|                                                                          |
| [Show Failing Documents] [Edit Rules] [Generate from Schema]             |
+--------------------------------------------------------------------------+
```

#### Validation functionality

- View the active validator, validation level, and validation action.
- Edit and apply rules using `collMod` where permissions permit.
- Preview matching and failing documents against a sampled set.
- Generate a starting validator from schema analysis.
- Make action and level choices aware of MongoDB server version support.
- Clearly show permission failures and unsupported deployment capabilities.

### 6.10 Explain Plan

```text
+ Explain Query ----------------------------------------------------------+
| Execution: 12 ms | Returned: 25 | Examined: 25 docs | Keys: 25          |
| Examined/Returned: 1.0 | Winning plan uses index                         |
+--------------------------------+-----------------------------------------+
| PLAN TREE                      | SELECTED STAGE                          |
|                                |                                         |
| FETCH                          | Stage            IXSCAN                  |
| `- IXSCAN                      | Index            status_createdAt        |
|    status_createdAt            | Direction        forward                 |
|                                | Keys examined    25                      |
| Rejected plans: 1              | Documents read   25                      |
|                                | Bounds                                   |
|                                | status: ["active", "active"]             |
+--------------------------------+-----------------------------------------+
| [Winning Plan] [Rejected Plans] [Raw JSON] [Copy]                        |
+--------------------------------------------------------------------------+
```

Explain-plan warnings highlight:

- `COLLSCAN`.
- In-memory sort.
- Large examined-to-returned ratios.
- Unbounded scans.
- Rejected plans.
- Shard merge stages.

Warnings describe observed behavior and do not claim to provide automatic tuning advice.

### 6.11 Performance Workspace

```text
+ Production EU > Performance ------------------------- LIVE every 2s ----+
| Operations/sec       Read  1,842   Write  327   Command  904             |
| Connections          Current 73    Active 11    Available 838            |
| Memory               Resident 5.8 GB   Virtual 12.1 GB                   |
+--------------------------------------------------------------------------+
| OPS/SEC  2500 |                 *                                        |
|         2000  |       *    *  ** **                                      |
|         1500  |  * * *** ****     ***                                   |
|          500  |** *                *                                     |
|             +------------------------------------------------            |
+----------------------------------+---------------------------------------+
| HOT COLLECTIONS                  | SLOW OPERATIONS                       |
| app.orders       1.4k r/s 82 w/s | 8.4s app.orders COLLSCAN             |
| app.customers    0.7k r/s 41 w/s | 2.1s analytics.events IXSCAN         |
| logs.events      0.2k r/s 97 w/s | 1.4s app.customers UPDATE            |
+----------------------------------+---------------------------------------+
| [Pause] [Current Operations] [Refresh]                                   |
+--------------------------------------------------------------------------+
```

#### Performance functionality

- Operation rates.
- Read and write queues.
- Current connections.
- Network activity.
- Memory statistics.
- Hottest collections.
- Current and slow operations.
- Operation detail inspection.
- Privilege-gated kill operation with confirmation.
- Pause and resume display updates.
- Configurable refresh interval.

Performance functionality requires suitable privileges, such as `clusterMonitor`. The UI must say when data is unavailable due to role limits, deployment topology, or server capability.

## 7. Keyboard and Mouse Interaction Contract

### Core rule

Every pointer interaction has a visible keyboard alternative.

| Function | Keyboard path | Mouse enhancement |
| --- | --- | --- |
| Move focus | `Tab`, `Shift+Tab` | Click a control |
| Navigate lists and trees | Arrow keys, `PgUp`, `PgDn`, `Home`, `End` | Click and wheel scroll |
| Expand tree or document | `Space` or `Enter` | Click disclosure marker |
| Open selected item | `Enter` | Double-click or repeated click |
| Switch workspace tab | Focus tabs and use arrows or tab shortcut | Click tab |
| Run query | `F5` or `Ctrl+Enter` | Click Run |
| Open actions | `A` or menu key | Right-click or Actions button |
| Sort table | `S`, then choose field and direction | Click table header |
| Resize split pane | Focus splitter and use arrows | Drag splitter |
| Show contextual help | `?` or command help | Hover tooltip |
| Next result page | `]` or pager focus | Click Next |
| Previous result page | `[` or pager focus | Click Previous |
| Edit document | `E` or action menu | Click Edit |
| Change view | `V`, then choose a view | Click List, Table, or JSON |
| Close dialog | `Esc` | Click Cancel |
| Open command palette | `Ctrl+P` | Click command indicator |
| Copy data | `C` or action menu | Click Copy |
| Search namespaces | `/` outside an editor | Click search field |

### Focus behavior

- The active focus target has a visible border and title marker.
- Focus must never be conveyed only by color.
- The footer updates with shortcuts relevant to the focused widget.
- `Esc` leaves one context at a time.
- Modal dialogs trap focus until canceled or completed.
- Global printable-key shortcuts do not interrupt text editors.
- A `?` help overlay lists context-sensitive and global shortcuts.
- The command palette exposes infrequent and advanced actions.

### Mouse behavior and terminal limitations

Mouse support may be unavailable or intercepted by SSH clients, tmux, GNU screen, terminal selection behavior, or restricted terminals. Therefore:

- Wheel scrolling always has keyboard equivalents.
- Split-pane dragging always has keyboard resizing.
- Right-click action menus always have `A` and command palette alternatives.
- Hover-only details are also visible through help, status, or inspector content.
- Clipboard commands offer an export or visible-text fallback.
- The full application remains usable with mouse reporting disabled.

## 8. Responsive Layout

### Wide terminals: 120 columns and above

- Namespace sidebar.
- Main document list or table.
- Persistent document inspector.
- Full query option summary.
- Expanded status and metadata.

### Standard terminals: 80 to 119 columns

- Collapsible sidebar.
- Main result pane.
- Inspector overlays or temporarily replaces the result pane.
- Query options open in a modal.
- Compact footer.

### Narrow terminals: below 80 columns

```text
+ app.customers -------------------+
| Docs Agg Schema Index Val        |
+----------------------------------+
| Filter: status="active"    [Run] |
+----------------------------------+
| > Alice Morgan                   |
|   active | London                |
|                                  |
|   Robert Chen                    |
|   active | Paris                 |
|                                  |
|   Kim Patel                      |
|   active | Berlin                |
+----------------------------------+
| 25 shown | 18ms | page 1         |
+----------------------------------+
| Enter Open | A Actions | ] Next  |
+----------------------------------+
```

Narrow mode uses one primary pane at a time:

- The namespace sidebar opens as a drawer.
- The document inspector opens as a full screen.
- Query options open in a modal.
- Collection tabs remain accessible.
- Decorative metadata is removed before operational controls.
- Required content scrolls instead of clipping horizontally.

The target minimum terminal size is 80x24. Smaller sizes remain functional but may display a suggestion to enlarge the terminal.

## 9. Functional Scope

### Connections

- URI connection.
- Saved profiles and favorites.
- TLS.
- Username/password authentication.
- Replica sets, SRV records, and sharded clusters.
- Read preferences.
- Connection diagnostics.
- Connect, disconnect, and reconnect.
- Read-only mode.
- Connection status and latency.
- Capability and privilege detection.
- Multiple active connections in a later release.

### Database operations

- List databases.
- Show database statistics.
- Create a database with its initial collection.
- Drop a database.
- Refresh metadata.
- Copy a database name.
- Search namespaces.

### Collection operations

- List collections and views.
- Show collection statistics.
- Create ordinary collections.
- Create views.
- Drop collections.
- Copy namespaces.
- Refresh metadata.
- Add time-series, clustered collection, and custom-collation creation options in later releases.

### Documents

- List, table, and EJSON views.
- Nested-value expansion.
- Pagination.
- Filter, projection, sort, collation, skip, limit, and max time.
- Query validation.
- Insert one or many documents.
- Patch update.
- Full replacement.
- Clone.
- Delete one document.
- Copy document or field.
- Add selected value to a filter.
- Exact count on demand.
- Explain plan.

### Query library

- Up to 30 recent queries per namespace by default.
- Named favorites.
- Full query state, including all find options.
- Load, copy, rename, and delete saved queries.
- Search query history.
- Disable history globally or per connection.
- Configure retention limits.

### Aggregations

- Raw pipeline editor.
- Stage editor.
- Enable, disable, add, remove, and reorder stages.
- Stage previews.
- Run and page results.
- Explain.
- Save and load pipelines.
- Export results.
- Create views.
- Write-stage warning.

### Schema

- Random sampling.
- Field presence.
- BSON types.
- Cardinality.
- Numeric/date distributions.
- Array statistics.
- Nested fields.
- Generated filters.
- JSON Schema export.
- MongoDB validator export.

### Indexes

- List and inspect.
- Create and drop.
- Compound indexes.
- Unique, TTL, partial, wildcard, text, and geospatial options in staged releases.
- Hide and unhide where supported.
- Usage caveats.
- Explain integration.

### Validation

- View validator.
- Edit rules.
- Preview rules.
- Generate candidate rules from schema samples.
- Apply through `collMod`.
- Support validation action and level.

### Import and export

- Newline-delimited JSON.
- JSON arrays.
- Extended JSON.
- Full collection export.
- Filtered or projected export.
- Aggregation result export.
- Streaming progress.
- Cancellation.
- Partial failure reporting.
- CSV import/export in a later release.

Exports are not database backups and must not be described as such.

### Performance

- Deployment metrics.
- Current operations.
- Slow operations.
- Hottest namespaces.
- Pause and resume visual updates.
- Operation inspector.
- Permission-gated kill operation.

## 10. Safety Model

### Read-only mode

Read-only mode hides or disables application write controls, but MongoDB server authorization remains the security boundary. Production read-only access should use server-side `read` roles.

### Destructive operation confirmations

| Operation | Required confirmation |
| --- | --- |
| Delete one document | Review `_id` and confirm. |
| Drop an index | Type the index name. |
| Drop a collection | Type the complete namespace. |
| Drop a database | Type the database name. |
| Bulk update | Review filter, update, and estimated affected count. |
| Bulk delete | Review filter and preview. |
| Empty-filter bulk write | Type an additional confirmation phrase. |
| `$out` or `$merge` | Review the destination namespace and confirm. |
| Kill operation | Review operation ID, owner, duration, and namespace. |

Pressing `Delete` must never execute an irreversible action immediately.

### Query safety

- Use a default `maxTimeMS`.
- Use a configurable page size.
- Do not materialize an entire collection in the UI.
- Run exact document counts only on request.
- Clean up cursors.
- Enforce connection, socket, and server-selection timeouts.
- Cancel or discard stale UI requests.
- Show visible state for long-running operations.

Canceling a UI worker may not terminate a server operation. MongoDB operation timeouts remain mandatory.

## 11. Technical Architecture

### Technology choices

| Layer | Choice | Reason |
| --- | --- | --- |
| Language | Python 3.10+ | Modern typing and broad Ubuntu Server compatibility. |
| TUI framework | Textual | Keyboard/mouse terminal UI, widgets, CSS, workers, and testing support. |
| MongoDB driver | PyMongo | Official, mature MongoDB driver with BSON support. |
| Formatting | Rich via Textual | Syntax highlighting and terminal rendering. |
| Local paths | platformdirs | Platform-correct configuration, data, and cache locations. |
| Local history | SQLite | Bounded, indexed query and pipeline history. |

### Package layout

```text
mongrove/
+-- pyproject.toml
+-- README.md
+-- src/
|   +-- mongrove/
|       +-- __init__.py
|       +-- __main__.py
|       +-- cli.py
|       +-- app.py
|       |
|       +-- domain/
|       |   +-- connection.py
|       |   +-- namespace.py
|       |   +-- query.py
|       |   +-- documents.py
|       |   +-- capabilities.py
|       |
|       +-- services/
|       |   +-- mongo_gateway.py
|       |   +-- connection_manager.py
|       |   +-- bson_codec.py
|       |   +-- query_history.py
|       |   +-- import_export.py
|       |   +-- schema_analyzer.py
|       |
|       +-- storage/
|       |   +-- profiles.py
|       |   +-- history.py
|       |   +-- settings.py
|       |
|       +-- ui/
|           +-- screens/
|           |   +-- connections.py
|           |   +-- deployment.py
|           |   +-- database.py
|           |   +-- collection.py
|           |   +-- performance.py
|           |
|           +-- widgets/
|           |   +-- namespace_tree.py
|           |   +-- query_bar.py
|           |   +-- document_list.py
|           |   +-- document_table.py
|           |   +-- document_tree.py
|           |   +-- status_bar.py
|           |   +-- split_pane.py
|           |
|           +-- dialogs/
|           |   +-- document_editor.py
|           |   +-- confirmation.py
|           |   +-- query_options.py
|           |   +-- action_menu.py
|           |
|           +-- styles/
|               +-- app.tcss
|
+-- tests/
    +-- unit/
    +-- integration/
    +-- ui/
```

This separation prevents Textual widgets from directly owning MongoDB behavior and keeps most logic testable without a running TUI.

### MongoDB gateway strategy

`MongoGateway` is the boundary between the UI and PyMongo.

- All MongoDB work runs in Textual workers so the UI remains responsive.
- Cursor consumption stays inside the worker that owns the cursor.
- Every request receives a unique request identifier.
- A result is ignored when a newer request has superseded it.
- Driver exceptions become domain-level errors that UI screens can render consistently.
- Timeouts are required for connection, server selection, socket, and long-running operations.
- The UI never calls PyMongo directly.
- The boundary keeps open the option of moving to an async PyMongo client later without rewriting UI screens.

### Local storage

```text
~/.config/mongrove/config.json
~/.config/mongrove/connections.json
~/.local/share/mongrove/history.sqlite3
~/.cache/mongrove/
```

- Connection profiles exclude credentials by default.
- Files containing connection metadata use restrictive permissions.
- Query and pipeline history use SQLite for bounded, searchable storage.
- History can be disabled globally or per connection.
- URI passwords are redacted in local logs, error reports, and UI output.

### Dependencies

Core runtime dependencies:

- `textual`
- `pymongo`
- `platformdirs`

Optional runtime dependencies:

- `keyring` for operating-system credential storage.

Development dependencies:

- `pytest`
- `pytest-asyncio`
- Textual snapshot/testing tooling
- Linting, formatting, and type-checking tools selected when scaffolding begins

### Command-line interface

```text
mongrove
mongrove mongodb://localhost:27017
mongrove --profile production
mongrove --database app --collection customers
mongrove --read-only
mongrove --no-history
mongrove --theme monochrome
python -m mongrove
```

Supported environment variables:

```text
MONGROVE_URI
MONGROVE_PROFILE
MONGROVE_READ_ONLY
MONGROVE_NO_HISTORY
```

Avoid passing passwords on the command line because process listings can expose them.

## 12. Delivery Plan

### Phase 1: Read-only Explorer

- Python package scaffolding and CLI.
- Connection manager.
- Database and collection navigation.
- Documents list and EJSON views.
- Query bar with all find options.
- Pagination.
- Document inspector.
- Query history.
- Keyboard-complete operation.
- Basic mouse support.
- Responsive layouts.

This phase establishes the full data-exploration architecture without introducing write risk.

### Phase 2: Document Operations

- Insert.
- Patch editing.
- Full replacement.
- Clone.
- Delete.
- Read-only session mode.
- Confirmation system.
- JSON/EJSON import and export.

### Phase 3: Collection Tools

- Aggregation editor.
- Saved pipelines.
- Explain plans.
- Index listing and management.
- Collection details.
- Database and collection creation.
- Drop operations.

### Phase 4: Analysis

- Schema sampling.
- Field distributions.
- Schema export.
- Validation inspection and editing.
- Generated validators.
- Advanced index options.

### Phase 5: Operations

- Deployment dashboard.
- Live performance.
- Current operations.
- Kill operation.
- Multiple simultaneous connections.
- Collection views.
- CSV import/export.
- Special collection creation.

Atlas-only features, AI assistants, graphical maps, and Search/Vector Search management remain outside the direct-server core unless added as separate, capability-gated extensions.

## 13. Test Strategy

### Unit tests

- BSON and Extended JSON round trips.
- Query validation.
- Patch generation.
- Replacement semantics.
- Credential redaction.
- Pagination state.
- Capability detection.
- Destructive confirmation rules.

### Integration tests

Test against supported MongoDB versions and deployment shapes:

- Standalone deployment.
- Replica set.
- Authenticated server.
- TLS deployment.
- Read-only user.
- Administrative user.
- Permission failures.
- Network interruption.
- Slow query.
- Large and heterogeneous documents.

### Textual UI tests

Use Textual `Pilot` tests for:

- Keyboard-only workflows.
- Focus order.
- Mouse-click parity.
- Double-click behavior.
- Right-click action menu behavior.
- Splitter dragging and keyboard resizing.
- Modal focus trapping.
- Responsive terminal resizing.
- No-color mode.
- Loading, error, disconnected, and permission-denied states.

### Real terminal compatibility matrix

Headless tests cannot validate terminal protocols, font widths, clipboard support, or mouse reporting. Perform manual smoke testing with:

- Direct Linux console.
- SSH.
- tmux.
- GNU screen.
- Windows Terminal over SSH.
- iTerm-compatible terminals.
- 256-color mode.
- `NO_COLOR` mode.
- Mouse reporting disabled.
- OSC 52 clipboard allowed and blocked.

## 14. Release Acceptance Criteria

The first production-capable release must meet all of the following criteria:

- Installable with `pipx install mongrove` and `pip install mongrove`.
- Launchable using `mongrove` and `python -m mongrove`.
- Fully usable without a mouse.
- No blocking MongoDB work on the UI thread.
- No plaintext password persistence by default.
- BSON types preserved during display and editing.
- Query workflows do not accidentally load an entire collection into memory.
- Destructive actions cannot execute from a single keypress.
- Network, permission, server, and query errors appear in the relevant workspace.
- Current query state survives inspectors, dialogs, and navigation where expected.
- Usable at 80x24.
- Tested over SSH with mouse reporting disabled.
- A read-only production workflow is verified end to end.

## 15. Initial Implementation Decisions

| Decision | Selected default |
| --- | --- |
| Python baseline | Python 3.10+ |
| Initial product mode | Read-only explorer before write operations |
| Credential policy | Never persist passwords by default; use prompts, environment variables, and optional keyring integration |
| Primary document view | Compass-style expandable list view with table and EJSON alternatives |
| Query history | Enabled locally by default with a visible `--no-history` option |
| Page size | Configurable, with a conservative default of 25 documents |
| Query maximum time | Configurable, with a default of 60,000 ms |
| First aggregation interface | Raw pipeline editor plus terminal-friendly stage list |
| First schema interface | Textual summary tables and ASCII distributions rather than graphical charts |
| First performance interface | Defer until core exploration and safety workflows are stable |

## 16. Open Design Decisions Before Scaffolding

1. Determine whether the first release supports one active connection or multiple concurrent workspaces.
2. Choose the exact credential-storage policy when `keyring` is unavailable on a server.
3. Decide whether query history is opt-in rather than opt-out for high-security environments.
4. Set the supported MongoDB server-version range.
5. Define which advanced authentication mechanisms are included after username/password and TLS.
6. Define the release point for write operations after the read-only explorer is stable.
7. Decide whether connection-profile import/export is included before or after the first stable release.
