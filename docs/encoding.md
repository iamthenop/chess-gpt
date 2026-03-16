# Encoding

This document defines the canonical board encoding used by `chess-gpt`.

Its purpose is to provide a stable machine-facing representation of chess board state for storage, retrieval, and LLM parsing.

It is **not** a human display format. Human-oriented rendering belongs to the display layer.

---

## Purpose

The encoding layer exists to answer four questions:

1. How is a board represented in memory?
2. How is a board serialized deterministically?
3. How are squares addressed?
4. How can other parts of the system read or update board state without reimplementing the format?

This encoding is meant to be:

- compact
- canonical
- easy to index
- easy to round-trip
- explicit enough for model consumption

---

## Scope

This encoding covers **board layout only**.

It does **not** define:

- side to move
- castling rights
- en passant availability
- halfmove clock
- fullmove number

Those belong to **position metadata**, not the board itself.

Two different live-game positions may share the same board layout while differing in metadata.

---

## Core Design

Each square is encoded as a **4-bit nibble**.

That gives 16 possible values per square.

A chess board has 64 squares, so the packed board requires:

- 64 squares × 4 bits
- 256 bits total
- 32 bytes total

This 32-byte packed board is the canonical machine representation.

---

## Piece Mapping

The encoding uses one canonical empty value and symmetric piece values for white and black.

### Empty

- `0` = empty

### White Pieces

- `1` = white pawn
- `2` = white knight
- `3` = white bishop
- `4` = white rook
- `5` = white queen
- `6` = white king

### Black Pieces

Black pieces are represented as the 4-bit two's complement counterpart of the white value:

- `F` = black pawn
- `E` = black knight
- `D` = black bishop
- `C` = black rook
- `B` = black queen
- `A` = black king

---

## Why This Mapping

This mapping was chosen for three reasons.

### 1. Compactness

A nibble is the smallest clean unit that can represent:

- empty
- 6 white piece types
- 6 black piece types

### 2. Canonical Empty State

Only `0` is used for empty.

This avoids multiple binary encodings for the same board layout.

### 3. Color Symmetry

Black is the 4-bit two's complement counterpart of white.

For any white piece value `x`, the black counterpart is:

```text
((x ^ 0xF) + 1) & 0xF
```

This provides a consistent mathematical relationship between white and black pieces.

---

## Internal Board Layout

Internal storage is machine-oriented.

### Addressing Rules

- `a1` is address `0`
- row-major order
- rank 1 is stored first
- rank 8 is stored last

So the internal square ordering is:

```
a1 b1 c1 d1 e1 f1 g1 h1
a2 b2 c2 d2 e2 f2 g2 h2
a3 ...
...
a8 b8 c8 d8 e8 f8 g8 h8
```

Square Index Formula

For zero-based file and rank indices:

- file `a..h` = `0..7`
- rank `1..8` = `0..7`

The address is:

```
index = rank * 8 + file
```

Examples:

- `a1` = `0`
- `b1` = `1`
- `h1` = `7`
- `a2` = `8`
- `e4` = `28`
- `h8` = `63`

---

## Packed Board Representation

Two squares are packed into one byte:

- first square = high nibble
- second square = low nibble

This means:

- square 0 and square 1 share byte 0
- square 2 and square 3 share byte 1
- ...
- square 62 and square 63 share byte 31

So the board blob is always exactly:

- 32 bytes

This packed byte sequence is the canonical stored board payload.

---

## Canonical Text Serialization

Although the packed 32-byte blob is the canonical machine representation, it is useful to have a deterministic text form.

The canonical text form is:

- 8 rows
- 8 uppercase hex characters per row
- row 0 = rank 1
- row 7 = rank 8

This text form is intended for:

- debugging
- logging
- fixtures
- LLM parsing
- documentation examples

### Example: Starting Position

```
42356324
11111111
00000000
00000000
00000000
00000000
FFFFFFFF
CEDBADEC
```

This is the standard starting board in internal storage order.

### Meaning

Rank 1:

```
42356324
```

decodes to:

- rook
- knight
- bishop
- queen
- king
- bishop
- knight
- rook

Rank 2:

```
11111111
```

decodes to eight white pawns.

Rank 7:

```
FFFFFFFF
```

decodes to eight black pawns.

Rank 8:

```
CEDBADEC
```

decodes to:

- black rook
- black knight
- black bishop
- black queen
- black king
- black bishop
- black knight
- black rook

---

## Orientation Notes

This format is not meant to match traditional human chessboard display by default.

Humans usually expect:

* rank 8 at the top
* rank 1 at the bottom

This encoding does not do that.

It preserves machine-friendly order:

* rank 1 first
* rank 8 last

Human-facing display can flip rows later if needed.

---

## Relationship to Position Metadata

A board layout alone is not a full chess position.

For example, the same board layout may appear in multiple games with different:

* side to move
* castling rights
* en passant availability

So the system distinguishes:

### Board

Pure square occupancy.

### Position

Board plus game-state metadata.

This document defines only the board layer.

---

## LLM-Facing Format

This project treats the codec as a machine/LLM serialization boundary.

That means the encoding should prioritize:

* consistency
* fixed-width output
* low ambiguity
* stable ordering
* minimal decoration

A typical LLM-facing block may look like this:

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

In that structure:

* the `board:` block is the canonical board encoding
* the other fields are position metadata layered on top

---

## Non-Goals

This encoding layer does **not** attempt to do any of the following:

* human UI rendering
* legal move generation
* SAN parsing
* PGN replay
* tactical evaluation
* game history reconstruction

Those belong elsewhere.

The codec is deliberately narrow.

---

## Module Responsibility

`board_codec.py` is responsible for:

* square addressing
* board packing and unpacking
* canonical serialization
* safe board inspection and update helpers

It should remain the single source of truth for how boards are encoded.

Other modules should not reimplement nibble math or raw square offset logic.

---

## Stability Expectations

The codec may evolve in the future, but only behind a stable interface.

That means the rest of the system should depend on codec functions, not on assumptions about raw byte layout.

If the encoding format ever changes after persisted data already exists, the project will need:

* a migration path, or
* explicit encoding versioning

For that reason, the codec should be treated as foundational.

---

## Summary

The board encoding used by `chess-gpt` is:

* 64 squares
* 4 bits per square
* 32 bytes packed
* `a1` at address 0
* row-major, rank 1 first
* one canonical empty value
* white pieces `1..6`
* black pieces `F..A`
* uppercase hex rows for deterministic text serialization

This encoding is optimized for:

* exact storage
* indexing
* retrieval
* machine parsing
* LLM consumption

It is not optimized for human visual display, and that is by design.
