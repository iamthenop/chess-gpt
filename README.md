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

Instead of searching chess from scratch every move, the system can:

1. encode a board into a canonical binary form
2. look up exact or similar positions
3. retrieve common and successful moves
4. filter illegal moves
5. rank plausible continuations more efficiently

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

This keeps the encoding compact, canonical, and color-symmetric.

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
- compare famous or instructive lines later

## Current Stack

- Python
- SQLite
- PGN ingestion
- compact custom board encoding

SQLite is used here because it is easy to inspect, easy to version, and good enough for a retrieval-first prototype.

## Repository Layout

```text
chess-gpt/
├─ data/
│  ├─ pgn/
│  ├─ db/
│  └─ samples/
├─ schema/
├─ src/chessgpt/
│  ├─ encoding/
│  ├─ pgn/
│  ├─ db/
│  ├─ query/
│  └─ utils/
├─ scripts/
└─ tests/
```

## Planned Flow

1. Parse PGN
2. Replay moves legally
3. Encode each resulting board into the 32-byte canonical format
4. Store positions and move edges
5. Aggregate move statistics
6. Query candidate continuations for a given board state

## What This Is Not

This is not:

- Stockfish
- a full search engine
- a complete tablebase system
- a perfect legality oracle for every edge case on day one
- This is a practical memory layer for chess retrieval.

## Near-Term Goals

- board encoder / decoder
- human board renderer
- SQLite schema initialization
- PGN import pipeline
- exact-position move suggestions
- test coverage around encoding and replay

## Long-Term Ideas

- similar-position retrieval
- structure tags
- famous game annotations
- tactical risk labeling
- lightweight outcome-distance heuristics

## Getting Started

Initialize the database:
```Bash
PYTHONPATH=src python3 scripts/init_db.py
```
Later steps will include PGN import and move suggestion scripts.

## License

MIT
