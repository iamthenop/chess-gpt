# Interfaces

This document defines machine-facing interfaces exposed by `chess-gpt`.

Its purpose is to keep structured inputs and outputs stable enough for:

- tooling
- automated tests
- cross-LLM evaluation
- future interface versioning

The project does not need heavy interface machinery yet, but it does benefit from a documented contract.

---

## Design Goal

Machine-facing interfaces in `chess-gpt` should be:

- deterministic
- low-ambiguity
- easy to validate
- stable across small internal refactors

Human-readable output can evolve more freely.

Machine-readable output should change more carefully.

---

## Versioning

Structured interfaces should include a format version once they are intended for reuse.

Current convention:

- `format_version: 1`

This allows future changes without pretending all JSON outputs are permanently frozen.

---

## Position JSON Interface

`show_position.py --format json` emits a structured position object.

### Example

```json
{
  "format_version": 1,
  "position_id": 1,
  "side_to_move": "w",
  "castling": "1111",
  "ep_file": "-",
  "board_rows": [
    "42356324",
    "11111111",
    "00000000",
    "00000000",
    "00000000",
    "00000000",
    "FFFFFFFF",
    "CEDBADEC"
  ]
}
````

### Fields

#### `format_version`

* type: integer
* required: yes
* current value: `1`

Indicates the version of the JSON interface.

---

#### `position_id`

* type: integer
* required: yes

Database position identifier.

This is the retrieval-oriented identity of the position, not just the board layout.

---

#### `side_to_move`

* type: string
* required: yes
* allowed values:

  * `"w"`
  * `"b"`

Indicates whose turn it is in the stored position.

---

#### `castling`

* type: string
* required: yes
* format: 4-character bitstring
* bit order:

  * bit 0: White long
  * bit 1: White short
  * bit 2: Black long
  * bit 3: Black short

Examples:

* `"1111"` = all castling rights still present
* `"0011"` = White long + White short only
* `"0000"` = no castling rights

This is a project-specific encoding, not FEN castling notation.

---

#### `ep_file`

* type: string
* required: yes
* allowed values:

  * `"-"` when no en passant file is available
  * `"a"` through `"h"` when en passant is available on that file

This is a compressed project-specific representation of en passant state.

---

#### `board_rows`

* type: array of strings
* required: yes
* length: exactly 8
* each item: exactly 8 uppercase hex characters

Represents the board in canonical machine row order:

* `board_rows[0]` = rank 1
* `board_rows[7]` = rank 8
* `a1` is the first internal address

This is not human display orientation.

### `board_rows` piece encoding

* `0` = empty
* `1` = white pawn
* `2` = white knight
* `3` = white bishop
* `4` = white rook
* `5` = white queen
* `6` = white king
* `F` = black pawn
* `E` = black knight
* `D` = black bishop
* `C` = black rook
* `B` = black queen
* `A` = black king

---

## Position LLM Text Interface

`show_position.py --format llm` emits a structured text form intended to be easy for language models to parse.

### Example

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

### Notes

This format is intentionally:

* line-oriented
* stable
* minimal
* low-decorative

It exists for model-facing prompt construction rather than generic JSON tooling.

---

## Suggested Move LLM Text Interface

`suggest_move.py --format llm` emits a structured candidate move list.

### Example

```text
position_id:1
min_frequency:5
candidate_moves:
- move_uci:e2e4 move_san:e4 frequency:1222 white_win_rate:0.394 draw_rate:0.409 black_win_rate:0.196
- move_uci:d2d4 move_san:d4 frequency:670 white_win_rate:0.243 draw_rate:0.479 black_win_rate:0.278
- move_uci:g1f3 move_san:Nf3 frequency:339 white_win_rate:0.227 draw_rate:0.605 black_win_rate:0.168
```

### Notes

This output is intended for:

* maintenance
* model-facing prompt input
* quick structured inspection

It is not yet formal JSON.

If later tooling needs stronger validation, this interface may gain a JSON form as well.

---

## Stability Policy

The project aims to keep machine-facing interfaces stable within a given format version.

That means:

* field names should not drift casually
* field semantics should not change silently
* ordering assumptions should be documented
* breaking changes should increment `format_version`

Human-facing text rendering has a looser stability requirement.

---

## Non-Goals

This document does not define:

* chess engine APIs
* network protocols
* OpenAPI specs
* formal JSON Schema files for every interface
* a complete compatibility guarantee forever

It defines the current structured contracts that matter for testing and reuse.

---

## Why This Matters

The project is intended to support more than one consumer.

That may include:

* shell scripts
* test harnesses
* future adapters
* multiple LLMs receiving the same structured state

If the interface is not stable, it becomes hard to tell whether differences in behavior come from:

* model quality
  or
* prompt/interface drift

This document helps reduce that ambiguity.

---

## Future Extensions

Possible future additions include:

* formal JSON Schema files
* a JSON version of move suggestion output
* apply/decision interfaces from the control layer
* audit event export format

Those can be added when the interfaces become important enough to justify stricter validation.

---

## Summary

`chess-gpt` currently exposes two important machine-facing interfaces:

1. structured position state
2. structured candidate move output

These interfaces are intentionally:

* small
* explicit
* versionable
* deterministic

They should remain stable enough to support repeatable testing, including evaluation across different LLMs.