# chess-gpt

A lightweight chess position graph and move-memory project.

The goal is not to build a full chess engine.

The goal is to make a language model more efficient at chess by giving it:

- stable board-state encoding
- exact position lookup
- move-labeled transitions
- frequency and result priors from real games
- a clean path from PGN to retrievable chess memory

## Why This Exists

Language models are good at pattern recognition, strategic language, and statistical priors.

They are not naturally good at:

- exact board-state persistence
- move legality bookkeeping
- endgame precision through raw language alone

This project is an attempt to bridge that gap with a compact retrieval layer.

Instead of reasoning from scratch every move, the system can:

1. encode a board into a canonical binary form
2. look up an exact position
3. retrieve common and successful continuations
4. rank plausible moves more efficiently
5. render state in both machine-facing and human-facing forms

## Design Principles

- Keep the board representation compact.
- Keep the database simple.
- Separate machine representation from human rendering.
- Store chess as a graph of positions and transitions.
- Prefer retrieval and statistical guidance over engine complexity.
- Do not overbuild.

## Board Encoding

Each square is represented by a 4-bit nibble.

Two squares pack into one byte.  
A full board is 64 squares = 256 bits = 32 bytes.

### Piece Encoding

- `0` = empty
- `1` = white pawn
- `2` = white knight
- `3` = white bishop
- `4` = white rook
- `5` = white queen
- `6` = white king

Black pieces are represented as the 4-bit two's complement counterpart of the white value:

- `F` = black pawn
- `E` = black knight
- `D` = black bishop
- `C` = black rook
- `B` = black queen
- `A` = black king

### Internal Layout

Internal board storage is machine-oriented:

- `a1` is address 0
- row-major order
- rank 1 first, rank 8 last

This is optimized for indexing and deterministic storage, not display.

Human rendering can flip the rows for standard chessboard display.

## Position Metadata

The board layout is not the full chess position.

A retrievable position may also include minimal game-state metadata such as:

- side to move
- castling rights
- en passant file when relevant

This project keeps board layout and game-state context conceptually separate.

## Data Model

The project treats chess as a graph.

### Nodes
A node represents a position:
- board layout
- side to move
- minimal metadata needed for future move retrieval

### Edges
An edge represents a move from one position to another:
- UCI move
- SAN move
- frequency
- win/draw/loss counts
- optional rating and time-control statistics

### Games
A game is represented as a path through the graph.

That makes it possible to:
- replay games
- aggregate move frequencies
- identify common continuations
- preserve provenance

## Current Stack

- Python
- SQLite
- PGN ingestion via `python-chess`
- compact custom board encoding

SQLite is used here because it is easy to inspect, easy to version, and good enough for a retrieval-first prototype.

## Repository Layout

```text
chess-gpt/
├─ data/
│  ├─ pgn/
│  ├─ db/
│  └─ samples/
├─ docs/
├─ schema/
├─ scripts/
├─ src/chessgpt/
│  ├─ db/
│  ├─ encoding/
│  ├─ pgn/
│  ├─ query/
│  └─ utils/
└─ tests/
````

## What Works Right Now

The current repo can already:

* initialize the SQLite schema
* parse and replay PGN main lines
* encode resulting board states into the canonical 32-byte format
* ingest games into boards, positions, edges, and game paths
* render positions in:

  * LLM-facing canonical text form
  * human-readable text board form
* suggest moves from an exact stored position
* filter low-frequency suggestions with `--min-frequency`

## Getting Started

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Initialize the database:

```bash
PYTHONPATH=src python scripts/init_db.py
```

Import a PGN file:

```bash
PYTHONPATH=src python scripts/import_pgn.py data/samples/sample_game.pgn
```

Show a stored position in LLM format:

```bash
PYTHONPATH=src python scripts/show_position.py 1 --format llm
```

Show a stored position in human-readable form:

```bash
PYTHONPATH=src python scripts/show_position.py 1
```

Suggest moves from a stored position:

```bash
PYTHONPATH=src python scripts/suggest_move.py 1
```

Suggest moves while filtering low-frequency noise:

```bash
PYTHONPATH=src python scripts/suggest_move.py 1 --min-frequency 5
```

## Example: Canonical LLM Position Format

```text
side_to_move:w
castling:1111
ep_file:-
board:
42356324
11111111
00000000
00000000
00000000
00000000
FFFFFFFF
CEDBADEC
```

## Example: Human Text Board

```text
  +----+----+----+----+----+----+----+----+
8 | ♜  | ♞  | ♝  | ♛  | ♚  | ♝  | ♞  | ♜  |
  +----+----+----+----+----+----+----+----+
7 | ♟  | ♟  | ♟  | ♟  | ♟  | ♟  | ♟  | ♟  |
  +----+----+----+----+----+----+----+----+
6 |    |░░░░|    |░░░░|    |░░░░|    |░░░░|
  +----+----+----+----+----+----+----+----+
5 |░░░░|    |░░░░|    |░░░░|    |░░░░|    |
  +----+----+----+----+----+----+----+----+
4 |    |░░░░|    |░░░░|    |░░░░|    |░░░░|
  +----+----+----+----+----+----+----+----+
3 |░░░░|    |░░░░|    |░░░░|    |░░░░|    |
  +----+----+----+----+----+----+----+----+
2 | ♙  | ♙  | ♙  | ♙  | ♙  | ♙  | ♙  | ♙  |
  +----+----+----+----+----+----+----+----+
1 | ♖  | ♘  | ♗  | ♕  | ♔  | ♗  | ♘  | ♖  |
  +----+----+----+----+----+----+----+----+
    a   b   c   d   e   f   g   h
```

## Current Scripts

### `scripts/init_db.py`

Creates the SQLite schema.

### `scripts/import_pgn.py`

Imports one PGN file into the database.

### `scripts/show_position.py`

Displays a stored position in either:

* `llm` format
* `text` format

### `scripts/suggest_move.py`

Shows ranked outgoing moves from a stored position.

Supports:

* `--format text|llm`
* `--limit`
* `--min-frequency`

## Current Tests

The repo currently includes tests for:

* board encoding
* replay
* rendering
* ingestion
* exact move suggestion

Run all tests with:

```bash
PYTHONPATH=src python -m pytest
```

## What This Is Not

This is not:

* Stockfish
* a full search engine
* a tablebase system
* a complete chess engine replacement
* a graph-database showcase

This is a practical retrieval layer for chess memory.

## Near-Term Next Steps

* tidy script ergonomics
* add more exact-query helpers
* improve README examples as the repo evolves
* optionally add player-scoped suggestion modes later

## Longer-Term Ideas

* similar-position retrieval
* structure tags
* famous game annotations
* game fingerprinting / deduping
* tactical risk labeling
* lightweight outcome-distance heuristics

## Documentation

Additional design notes live in:

* `docs/encoding.md`
* `docs/schema.md`
* `docs/ingestion.md`
* `docs/query.md`
* `docs/examples.md`

## License

MIT