# Examples

This document shows concrete examples of the main data representations used in `chess-gpt`.

Its purpose is to make the project easier to understand by example rather than by abstraction alone.

---

## 1. Starting Board Encoding

The standard starting board in internal machine order is:

```text
42356324
11111111
00000000
00000000
00000000
00000000
FFFFFFFF
CEDBADEC
````

Interpretation:

* row 1 = rank 1
* row 8 = rank 8
* `a1` is the first address in memory
* rows are stored in row-major order

This is **not** a human display format. It is a canonical machine/LLM-facing serialization.

---

## 2. Piece Mapping Example

The nibble mapping is:

```text
0 = empty

1 = white pawn
2 = white knight
3 = white bishop
4 = white rook
5 = white queen
6 = white king

F = black pawn
E = black knight
D = black bishop
C = black rook
B = black queen
A = black king
```

So the first row of the starting board:

```text
42356324
```

means:

```text
a1 = white rook
b1 = white knight
c1 = white bishop
d1 = white queen
e1 = white king
f1 = white bishop
g1 = white knight
h1 = white rook
```

And the last row:

```text
CEDBADEC
```

means:

```text
a8 = black rook
b8 = black knight
c8 = black bishop
d8 = black queen
e8 = black king
f8 = black bishop
g8 = black knight
h8 = black rook
```

---

## 3. Square Addressing Example

Internal square addressing uses:

```text
index = rank * 8 + file
```

with zero-based indices:

* file `a..h` = `0..7`
* rank `1..8` = `0..7`

Examples:

```text
a1 = 0
b1 = 1
h1 = 7
a2 = 8
e4 = 28
h8 = 63
```

---

## 4. Canonical LLM Position Block

A full position block for model consumption may look like this:

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

This separates:

* **board layout**
  from
* **position metadata**

The board is the physical arrangement.
The metadata is the live-game interpretation of that arrangement.

---

## 5. Example Board After `1. e4`

After White plays `e4`, the board might be represented like this:

```text
42356324
11110111
00000000
00001000
00000000
00000000
FFFFFFFF
CEDBADEC
```

Meaning:

* pawn moved from `e2` to `e4`
* `e2` became `0`
* `e4` became `1`

The position metadata would then be something like:

```text
side_to_move:b
castling:1111
ep_file:e
board:
42356324
11110111
00000000
00001000
00000000
00000000
FFFFFFFF
CEDBADEC
```

---

## 6. Exact Position Query Example

Given a current position, the query layer may return candidate moves like this:

```text
position_id:12345
candidate_moves:
- move_uci:e2e4 move_san:e4 frequency:12543 white_win_rate:0.39 draw_rate:0.31 black_win_rate:0.30
- move_uci:d2d4 move_san:d4 frequency:9821 white_win_rate:0.41 draw_rate:0.29 black_win_rate:0.30
- move_uci:g1f3 move_san:Nf3 frequency:4210 white_win_rate:0.38 draw_rate:0.34 black_win_rate:0.28
```

This is a retrieval result, not a proof of best play.

It tells the system:

* what has been played
* how often
* how it scored historically

---

## 7. Edge Example

An edge represents a move from one position to another.

Conceptually:

```text
from_position_id:100
move_uci:e2e4
move_san:e4
to_position_id:101
frequency:12543
white_wins:4891
black_wins:3762
draws:3890
```

This means:

> from position 100, the move `e2e4` led to position 101, and across imported games this happened 12,543 times.

That edge is part of the graph.

---

## 8. Game Path Example

A game is stored as an ordered traversal through positions and edges.

Conceptually:

```text
game_id:77
ply:1 edge:e2e4 -> position:101
ply:2 edge:e7e5 -> position:102
ply:3 edge:g1f3 -> position:103
ply:4 edge:b8c6 -> position:104
```

This allows the system to preserve:

* aggregate move statistics
* exact game replay order
* provenance back to a specific imported game

---

## 9. Human Text Board Example

For humans, a renderer may show the same starting position like this:

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
    a    b    c    d    e    f    g    h
```

This is a display concern, not the canonical board serialization.

---

## 10. Why Board and Position Are Separate

These two examples may share the same board layout but represent different positions.

### Example A

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

### Example B

```text
side_to_move:b
castling:0011
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

Same board.
Different legal state.

That is why the schema distinguishes:

* `boards`
  from
* `positions`

---

## 11. Example SQL-ish Exact Lookup

An exact query conceptually means:

```text
find position where:
- board_blob = current board
- side_to_move = current side
- castling_rights = current mask
- ep_file = current ep state
```

Then return outgoing edges ordered by usefulness.

Example result:

```text
move_san:e4   frequency:12543
move_san:d4   frequency:9821
move_san:Nf3  frequency:4210
```

---

## 12. Example Import Flow

Given this PGN fragment:

```text
1. e4 e5 2. Nf3 Nc6
```

Ingestion conceptually performs:

### Step 1

Initial position

### Step 2

Apply `e4`

* produce new board
* store edge from initial position to new position

### Step 3

Apply `e5`

* produce new board
* store edge from resulting position to next position

### Step 4

Apply `Nf3`

* repeat

### Step 5

Apply `Nc6`

* repeat

This turns notation into reusable state transitions.

---

## 13. Example of Similar Position Retrieval

Future similarity search might return something like:

```text
no exact match found

similar_positions:
- position_id:7001 similarity:0.92 tags:[open_center, kingside_castled]
- position_id:9183 similarity:0.89 tags:[open_center, minor_piece_development]
- position_id:12055 similarity:0.87 tags:[semi_open_e_file]
```

Then the system may use outgoing edges from those similar positions as fallback priors.

This is not required for the first version, but it is a natural extension.

---

## 14. Example of What the System Is Actually Doing

At query time, the system is not solving chess from scratch.

It is doing something closer to:

1. identify the current position
2. retrieve known continuations
3. rank them by practical prior
4. return structured candidates

That is the point of `chess-gpt`.

---

## Summary

These examples show the core ideas of the project in concrete form:

* how boards are encoded
* how positions differ from boards
* how moves become edges
* how games become paths
* how query results return candidate moves
* how ingestion turns PGN into graph data

The project is built around stable chess state representation first.

Everything else depends on that.
