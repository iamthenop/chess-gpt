# Ingestion

This document explains how chess game data enters `chess-gpt`.

The ingestion pipeline exists to turn recorded games into reusable chess memory.

Its job is to convert:

- PGN text
into
- board layouts
- positions
- move-labeled transitions
- game provenance
- aggregated move statistics

---

## Purpose

The ingestion layer is what populates the database.

Without ingestion, the schema is just an empty structure.

Its role is to:

1. read chess games from PGN
2. replay those games legally
3. emit successive positions
4. store positions and transitions
5. aggregate move statistics for later retrieval

This is how the project builds a usable move graph from real chess games.

---

## Core Idea

A PGN file is not directly useful to the query layer.

The query layer needs:
- canonical board states
- move edges between those states
- counts and results attached to those edges

So ingestion is the translation step from:

**notation**
to
**state transitions**

That means the ingestion pipeline is fundamentally a replay pipeline.

---

## Pipeline Overview

The intended ingestion flow is:

1. read a PGN file
2. extract headers and moves
3. initialize the starting position
4. replay each move in order
5. emit the resulting board and metadata after each move
6. insert or reuse the corresponding board row
7. insert or reuse the corresponding position row
8. insert or update the corresponding edge row
9. record the game path
10. store game provenance

This is repeated for every game in the input set.

---

## Responsibilities by Module

The ingestion path is split into separate concerns.

### `pgn/parser.py`
Responsible for:
- reading PGN files
- yielding parsed games
- exposing headers and move sequences

This module deals with input format.

It should not own database writes.

---

### `pgn/replay.py`
Responsible for:
- replaying moves legally
- producing successive board states
- exposing move-level snapshots

This module is the bridge between notation and canonical position state.

It should not own persistence.

---

### `pgn/ingest.py`
Responsible for:
- taking replay output
- inserting boards
- inserting positions
- inserting or updating edges
- inserting games and traversal records

This module is the database writer for imported games.

---

### `scripts/import_pgn.py`
Responsible for:
- CLI input
- file selection
- invoking ingest
- printing summary output

This script should stay thin.

---

## Why Replay Is Required

PGN is a move list, not a state list.

A move like:

- `Nf3`
- `Qxd5`
- `O-O`
- `c8=Q+`

does not directly tell the database what the resulting board is.

To get usable state, the system must:

- know the current board
- apply the move legally
- update the board
- update position metadata
- produce the next state

That is why replay is the heart of ingestion.

---

## Starting Position

Replay begins from the standard starting board unless the PGN explicitly specifies a different initial state.

The starting board is encoded using the canonical board codec.

If support for non-standard starting positions is added later, ingestion should also handle:

- FEN headers
- variant-specific initialization

But the initial project scope assumes standard chess PGNs unless stated otherwise.

---

## Legal Replay

For the first version, legal replay should be delegated to `python-chess`.

That is the practical choice.

This project is not trying to implement a full chess engine just to import games.

Using `python-chess` gives the ingestion layer:

- legal move application
- SAN parsing
- UCI conversion
- castling handling
- promotion handling
- en passant handling
- board-state progression

That keeps the project focused on state encoding and retrieval.

---

## What Replay Should Emit

Replay should produce a structured sequence of move snapshots.

A useful replay snapshot includes:

- ply number
- SAN move
- UCI move
- resulting board blob
- side to move in the resulting position
- castling rights
- en passant file
- maybe raw board hex for debugging

This is enough for the ingestion layer to store:

- positions
- edges
- game path
- provenance

---

## Example Replay Snapshot

Conceptually, one emitted replay record may look like:

```text
ply:1
move_san:e4
move_uci:e2e4
board:
42356324
11110111
00000000
00001000
00000000
00000000
FFFFFFFF
CEDBADEC
side_to_move:b
castling:1111
ep_file:e
````

The exact serialization used in code may differ, but this shows the idea.

The replay layer should produce state, not just move strings.

---

## Insert-or-Reuse Behavior

Ingestion should avoid duplicating identical structures where possible.

### Boards

If an identical board blob already exists, reuse its `boards.id`.

### Positions

If the combination of:

* board
* side to move
* castling rights
* en passant file

already exists, reuse that `positions.id`.

### Edges

If the same:

* from position
* move
* to position

already exists, update its aggregate counters rather than inserting a duplicate edge.

This makes ingestion cumulative.

---

## Aggregating Statistics

Each imported game updates edge statistics.

When a move transition is seen again, ingestion should increment:

* `frequency`
* `white_wins`
* `black_wins`
* `draws`

based on the game result.

Optional counters may also be updated for:

* blitz
* rapid
* classical
* average Elo

The exact statistical richness can grow later, but the basic aggregation rule should be stable.

---

## Recording Game Provenance

Each PGN game should also create a row in `games`.

That row stores metadata such as:

* players
* result
* date
* event
* opening
* source file

This preserves provenance.

Then each replayed move should produce a `game_moves` row linking:

* the game
* the ply number
* the edge taken
* the resulting position

That gives the project both:

* aggregate graph knowledge
  and
* exact per-game replay paths

---

## Why Provenance Matters

Graph aggregation alone is not enough.

Without provenance, the project can tell you:

* a transition exists
* it happened often
* it scored well

But it cannot easily tell you:

* which games contained it
* how a specific game traversed the graph
* where a famous line came from

That is why ingestion stores both:

* aggregate edges
* ordered game paths

---

## Metadata Handling During Replay

Replay must track minimal live-game metadata alongside the board.

At minimum, this includes:

* side to move
* castling rights
* en passant file

These values are part of position identity.

Even if two positions share a visible board layout, replay must preserve metadata when generating the resulting node.

This is important because the same board can have different legal continuations depending on the metadata.

---

## En Passant in Ingestion

En passant is a short-lived transition artifact.

It is caused by the immediately previous move, but it affects future legality in the resulting position.

So during ingestion:

* replay logic determines whether en passant becomes available
* the resulting position stores the relevant `ep_file`
* if the next move does not use it, it disappears in the next position

This is one reason replay must emit positions, not just moves.

---

## Castling Rights in Ingestion

Castling rights should not be recomputed from long game history during query time.

Instead:

* replay starts with full rights
* legal moves update those rights as needed
* the resulting position stores the new castling mask

This is cheaper, cleaner, and less fragile than trying to rediscover castling history later.

---

## Error Handling

Ingestion should fail clearly when input is malformed or unsupported.

Examples include:

* invalid PGN
* illegal move sequence
* unexpected header structure
* codec serialization mismatch

Good ingestion error handling should:

* identify the source file
* identify the game if possible
* identify the move or ply where replay failed
* stop or skip predictably

Silent corruption is worse than a loud failure.

---

## Idempotence

A useful ingestion system should aim for predictable re-import behavior.

There are two common approaches:

### 1. Append-and-aggregate

Re-importing the same PGN increments counts again.

This is simple, but can double-count if the same source is imported twice unintentionally.

### 2. Source-aware deduplication

Track imported files or game fingerprints and avoid double-counting.

This is cleaner, but adds complexity.

For the first version, append-and-aggregate is acceptable as long as it is documented.

Later, a game fingerprinting strategy can be added if needed.

---

## Game Fingerprinting (Later)

A future ingestion improvement may compute a stable fingerprint per game using some combination of:

* headers
* move list
* normalized PGN
* resulting path hash

This would allow the system to:

* detect duplicate imports
* avoid accidental double-counting
* support provenance integrity checks

This is useful, but not required on day one.

---

## Performance Expectations

The ingestion layer should optimize for correctness and stable structure first.

The first version does not need:

* extreme throughput
* parallel replay
* distributed import
* advanced batching tricks

A simple, correct pipeline is enough.

Performance tuning can come later if the dataset grows enough to matter.

---

## Why Ingestion Is Separated From Query

Ingestion is write-heavy and structural.
Query is read-heavy and retrieval-oriented.

Combining them would blur concerns.

Keeping them separate makes it easier to:

* test replay independently
* validate codec output independently
* debug database writes independently
* evolve query logic without touching import logic

This separation is worth keeping.

---

## Testing Priorities

The ingestion path should be tested in layers.

### Parser tests

* headers parsed correctly
* moves extracted correctly

### Replay tests

* move sequence produces expected positions
* castling rights update correctly
* en passant file updates correctly

### Ingest tests

* boards are inserted or reused
* positions are inserted or reused
* edges aggregate correctly
* game paths are stored correctly

The most important tests are not about pretty output.
They are about state integrity.

---

## What Ingestion Is Not

The ingestion layer is not:

* a chess engine
* a move recommender
* a human display system
* a tactical evaluator
* a graph query engine

Its job is simple:

> convert recorded games into structured, reusable chess state transitions

That is enough.

---

## Early Non-Goals

The first version of ingestion does not need:

* support for every chess variant
* deep duplicate-detection logic
* similarity tagging during import
* engine evaluation during replay
* immediate outcome-distance labeling

Those can be added later if useful.

The first version only needs to build a correct graph from PGN.

---

## Summary

The ingestion pipeline turns PGN games into:

* canonical board layouts
* retrievable positions
* move-labeled transitions
* aggregated statistics
* replayable game paths

It works by:

1. parsing PGN
2. replaying moves legally
3. encoding each resulting board
4. inserting or reusing boards and positions
5. updating edges
6. recording game provenance

This is the pipeline that makes the rest of `chess-gpt` possible.
