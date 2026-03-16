# Schema

This document defines the database model used by `chess-gpt`.

The schema is designed for a retrieval-first chess memory system.

It is **not** designed to be a full chess engine database, and it is **not** trying to encode every rule of chess directly into storage. Its purpose is to store:

- board layouts
- position metadata
- move-labeled transitions
- game provenance
- aggregated move statistics

---

## Purpose

The schema exists to support four main workflows:

1. store canonical board layouts
2. distinguish live-game positions that share the same board layout
3. represent chess as a graph of positions and moves
4. ingest PGN games into reusable move statistics

This supports the project goal:

> make LLM chess reasoning more efficient through retrieval and stable state representation

---

## Core Model

The schema separates chess data into three conceptual layers:

### 1. Board
A pure square-occupancy layout.

This is just the physical board arrangement:
- what piece is on what square

A board does **not** include:
- side to move
- castling rights
- en passant
- clocks

### 2. Position
A board plus minimal live-game metadata.

This is the actual node identity for move retrieval.

Two positions may share the same board while differing in:
- side to move
- castling rights
- en passant availability

### 3. Edge
A move-labeled transition from one position to another.

Edges also aggregate:
- frequency
- result counts
- optional rating/time-control stats

---

## Why Board and Position Are Separate

This is one of the most important design choices in the project.

Two games can produce the **same board layout** while still representing different legal states.

Examples:
- same board, different side to move
- same board, one side can castle and the other cannot
- same board, en passant available in one case but not the other

If the schema stored only boards, it would collapse legal distinctions that matter for move retrieval.

So the schema deliberately distinguishes:

- **board equality**
from
- **position equality**

A board is a layout.  
A position is a layout interpreted in the current game.

---

## Tables

### `boards`

Stores canonical board layouts only.

#### Purpose
- deduplicate identical board occupancy
- store the packed 32-byte board representation once
- provide a stable foundation for positions

#### Fields
- `id`
- `board_blob`

#### Notes
- `board_blob` is the canonical 32-byte packed nibble board
- this table has no turn or castling information
- identical layouts share one row here

---

### `positions`

Stores live-game positions built on top of boards.

#### Purpose
- represent actual retrievable positions
- preserve metadata that affects future legal moves
- act as graph nodes

#### Fields
- `id`
- `board_id`
- `side_to_move`
- `castling_rights`
- `ep_file`
- `pos_key` (optional future hash slot)

#### Notes
- `side_to_move` is required
- `castling_rights` is stored as a 4-bit mask
- `ep_file` is nullable because en passant is transient
- the uniqueness constraint is on the combination of board + metadata

A position is the real lookup unit for move suggestions.

---

### `games`

Stores imported PGN provenance.

#### Purpose
- preserve where transitions came from
- allow replay and auditing
- connect aggregate move statistics back to real games

#### Fields
- `id`
- `site`
- `event`
- `round`
- `game_date`
- `white_player`
- `black_player`
- `result`
- `time_control`
- `eco`
- `opening`
- `variation`
- `pgn_source`

#### Notes
This table is descriptive, not structural.
It exists so the graph can retain traceability to actual games.

---

### `edges`

Stores move-labeled transitions between positions.

#### Purpose
- represent the graph
- capture move identity
- store aggregate move statistics

#### Fields
- `id`
- `from_position_id`
- `to_position_id`
- `move_uci`
- `move_san`
- `frequency`
- `white_wins`
- `black_wins`
- `draws`
- `avg_elo`
- `blitz_count`
- `rapid_count`
- `classical_count`

#### Notes
This is the most important behavioral table in the schema.

Each row means:

> from this position, this move led to that resulting position

And across many imported games, that edge accumulates:
- how often it happened
- how often White won
- how often Black won
- how often the game was drawn

This is the primary source of retrieval priors.

---

### `game_moves`

Stores a game as an ordered path through the graph.

#### Purpose
- reconstruct game paths
- associate each ply with a specific edge and resulting position
- support replay and provenance inspection

#### Fields
- `id`
- `game_id`
- `ply`
- `edge_id`
- `position_id`

#### Notes
This table gives a game ordered structure.

Without it, the graph would know transitions exist, but not the precise sequence each individual game followed.

So this table turns:
- abstract graph edges
into
- actual game traversals

---

### `position_tags`

Stores optional structural labels for positions.

#### Purpose
- support later similarity search
- label positions with reusable strategic categories
- avoid baking all semantics into the core schema up front

#### Fields
- `position_id`
- `tag`
- `value`

#### Example tags
- `pawn_structure = iqp`
- `king_safety = opposite_castled`
- `material = rook_endgame`
- `center = closed`

#### Notes
This table is intentionally optional and open-ended.

It allows the project to grow into:
- structure-aware retrieval
- similarity search
- motif tagging

without overcomplicating the core schema early.

---

## Position Metadata

### Side to Move

This is required for position identity.

The same board with White to move and Black to move is not the same retrieval problem.

### Castling Rights

Castling rights are stored as a 4-bit mask:

- `1` = White long
- `2` = White short
- `4` = Black long
- `8` = Black short

These bits capture historical eligibility.

Actual castling legality still depends on the board state, but rights must be stored because they affect possible future moves.

### En Passant

`ep_file` stores the file of a transient en passant opportunity when relevant.

This is included because two otherwise identical positions may differ in legal moves if en passant is available in one and not the other.

The schema intentionally stores only the file because that is enough for the current project scope.

---

## Why This Is a Graph

Although the database is implemented with SQLite tables, the data model is graph-shaped.

### Nodes
`positions`

### Edges
`edges`

### Paths
`game_moves`

This matters because the conceptual model is:

- a position is a node
- a move is a directed transition
- a game is a traversal through nodes and edges

The relational schema exists to store that graph compactly and portably.

---

## Why SQLite Was Chosen

SQLite was chosen because the project goal is retrieval efficiency, not infrastructure complexity.

It provides:
- simple local storage
- easy inspection
- easy versioning
- no server setup
- enough performance for exact-position lookup and aggregation

It is not graph-native, but it is good enough for an early retrieval-first prototype.

This project is trying to make chess reasoning more stable, not become a database platform.

---

## Normal Flow Through the Schema

The intended ingestion flow is:

1. parse a PGN game
2. replay the game move by move
3. emit a board and metadata snapshot after each move
4. insert or reuse the corresponding `boards` row
5. insert or reuse the corresponding `positions` row
6. insert or update the `edges` row for the transition
7. insert the traversal record into `game_moves`
8. store provenance in `games`

That produces:
- reusable positions
- reusable transitions
- accumulated move statistics
- replayable game paths

---

## What the Schema Optimizes For

The schema is optimized for:

- exact position lookup
- stable board storage
- move frequency retrieval
- result priors
- PGN ingestion
- future extension into structure-aware retrieval

It is not optimized for:

- full legal engine state in every query
- deep tactical search
- tablebase replacement
- real-time multiplayer game state management

---

## What the Schema Deliberately Avoids

The schema does **not** try to do the following in storage alone:

- encode all move legality rules
- reconstruct castling rights from history on demand
- infer en passant from old edges during retrieval
- solve chess
- store every possible derived evaluation metric up front

Those concerns belong to:
- replay logic
- query logic
- later analytical layers

The schema stays lean on purpose.

---

## Views

The schema also defines a few views for convenience.

### `board_hex_view`
Provides board blobs as uppercase hex for inspection and debugging.

### `edge_stats`
Computes win-rate style derived fields from raw counts.

### `position_lookup`
Joins positions to their board hex for easier inspection.

### `move_suggestions`
Provides a ready-made exact-position move lookup surface.

### `game_replay`
Joins game paths back into readable ordered replay output.

These views are convenience layers, not canonical storage.

---

## Key Design Decisions

### Separate board from position
Needed to distinguish identical layouts with different game-state meaning.

### Store move transitions explicitly
Needed for graph traversal and move retrieval.

### Aggregate statistics on edges
Needed for cheap priors without deep traversal.

### Keep game provenance
Needed for replay, auditing, and future annotation.

### Keep tags optional
Needed to avoid premature over-modeling while preserving room for similarity search later.

---

## Non-Goals

This schema is not trying to be:

- a full chess engine schema
- a PGN archival standard
- a graph database replacement
- a perfect legal-state formalization of all edge cases up front

It is a practical schema for a chess retrieval layer.

---

## Summary

The schema treats chess as:

- **boards** for pure layout
- **positions** for retrievable game states
- **edges** for move-labeled transitions
- **games** for provenance
- **game_moves** for ordered traversals
- **tags** for future semantic structure

This gives `chess-gpt` a stable foundation for:

- importing PGNs
- storing position graphs
- retrieving common moves
- attaching statistical priors
- reducing symbolic drift in chess reasoning
