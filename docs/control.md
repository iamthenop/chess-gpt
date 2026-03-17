# Control

This document defines the control layer in `chess-gpt`.

The control layer exists to make move application deterministic, auditable, and safe.

It is the boundary between:

- authoritative stored position state
and
- untrusted candidate moves proposed by a human, script, or language model

---

## Purpose

The retrieval layer can suggest plausible moves.

That is useful, but not sufficient.

A suggested move is still only a suggestion until it is:

1. parsed
2. validated
3. checked for legality
4. applied to the authoritative position
5. logged

The control layer is responsible for those steps.

Its purpose is to ensure that move execution is grounded in authoritative state rather than in model interpretation.

---

## Why This Layer Exists

`chess-gpt` intentionally separates:

- **state**
- **suggestion**
- **control**

This matters because a language model can produce output that is:

- malformed
- ambiguous
- unsuggested
- illegal
- plausible-looking but wrong

Without a control layer, the project would risk treating probabilistic output as authoritative chess state.

That would break the architecture.

The control layer prevents that.

---

## Design Goal

The control layer should be:

- deterministic
- minimal
- explicit
- auditable
- authoritative

It should not try to be “smart.”

Its job is not to choose moves.  
Its job is to decide whether a proposed move is acceptable and then apply it correctly.

---

## Core Module

Current implementation:

- `src/chessgpt/control/apply.py`

This module is the first concrete control boundary in the project.

It validates and applies moves using:

- authoritative position data from the database
- deterministic legality checking via `python-chess`
- optional policy requiring a move to be present in the suggestion set
- audit logging

---

## Core Operation

The main control action is:

> given a stored `position_id` and a candidate UCI move, validate it against authoritative state and apply it if permitted

This means the control layer does not trust:
- hand-written SAN
- natural-language move descriptions
- model guesses about legality
- raw board interpretation outside the codec

It reconstructs the authoritative position from stored data and checks the move there.

---

## Position Authority

The control layer treats the database as the source of truth.

A position is loaded from:

- `positions`
- `boards`

That gives the control layer:

- canonical board blob
- side to move
- castling rights
- en passant file

From there, the control layer reconstructs a legal chess board state for deterministic validation.

This means move validation is always performed against authoritative position state, not against a prompt, screenshot, or model memory.

---

## Candidate Move Format

The control layer currently accepts:

- **UCI move strings**

Examples:

- `e2e4`
- `g1f3`
- `e7e8q`
- `e1g1`

This is deliberate.

UCI is better for control purposes because it is:

- explicit
- coordinate-based
- compact
- easy to validate mechanically

SAN is better for display and notation, but UCI is a better control input.

---

## Validation Stages

The current control flow performs several checks in order.

### 1. Syntax validation

The move string must match valid UCI syntax.

Examples of accepted forms:
- `e2e4`
- `b1c3`
- `e7e8q`

If the string is malformed, it is rejected before any chess logic is applied.

---

### 2. Suggestion-set policy check

If `require_suggested=True`, the move must already appear in the retrieved candidate set for the source position.

This is a policy choice, not a chess rule.

It exists to support a stricter operating mode in which the control layer only accepts moves that were surfaced by the query layer.

This is useful when testing or constraining LLM outputs.

If `require_suggested=False`, any legal move may be accepted even if it was not suggested.

---

### 3. Legal move validation

The move is then checked against the reconstructed authoritative chess board.

If it is not legal in the current position, it is rejected.

This is the hard chess rule boundary.

---

### 4. Deterministic application

If the move passes policy and legality checks, it is applied to the reconstructed authoritative board.

The control layer then emits:

- resulting board blob
- resulting side to move
- resulting castling rights
- resulting en passant file
- SAN rendering of the accepted move
- optional resulting position ID if the resulting state already exists in the database

---

## Output

A successful application returns an `AppliedMove` structure containing:

- source position ID
- accepted move in UCI
- accepted move in SAN
- resulting board blob
- resulting side to move
- resulting castling rights
- resulting en passant file
- resulting position ID if found

This output is deterministic and authoritative.

It can then be rendered in:
- text
- LLM text
- JSON

without reinterpreting the move again.

---

## Audit Logging

Every control decision can be recorded in `decision_audit`.

This creates an explicit history of move-application decisions.

### Current audit fields include

- source position ID
- chosen move UCI
- chosen move SAN if accepted
- accepted or rejected
- reason
- actor label
- whether suggestion membership was required
- whether the move was in the suggestion set
- resulting position ID when available
- timestamp

This matters because it preserves the difference between:

- suggested
- attempted
- accepted
- rejected

That difference is important in any system involving an LLM.

---

## Why Audit Matters

Without audit, it is easy to lose track of whether a move was:

- proposed by the model
- present in the suggestion set
- legal
- accepted under strict policy
- accepted only because override mode was enabled

That ambiguity becomes a problem very quickly in evaluation and debugging.

The audit table prevents that.

---

## Policy Modes

The current control layer supports two main operating modes.

### Strict mode

- `require_suggested=True`

The move must:
- be valid UCI
- be present in the suggestion set
- be legal

This is the safer mode for LLM integration.

### Override mode

- `require_suggested=False`

The move must:
- be valid UCI
- be legal

Suggestion membership is recorded but not required.

This is useful for:
- human experimentation
- testing legal alternatives
- comparing suggested vs unsuggested moves

---

## Example

Starting position:

```text id="19870e"
position_id:1
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
````

Applying:

```text id="o2nsmg"
move_uci:e2e4
```

can produce:

```text id="0wlzy7"
source_position_id:1
move_uci:e2e4
move_san:e4
resulting_position_id:2
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

This is the control layer converting a candidate move into authoritative next state.

---

## What the Control Layer Is Not

The control layer is not:

* the board codec
* the render layer
* the query layer
* a search engine
* a tactical evaluator
* a chess engine replacement

It does not decide what move is best.

It decides whether a proposed move is acceptable and then applies it correctly.

---

## Relationship to Other Layers

### Encoding

Defines what a board is.

### Query

Suggests likely moves from stored graph data.

### Control

Validates and applies one candidate move deterministically.

### Render

Shows the resulting state to humans or LLM-facing interfaces.

This separation keeps responsibilities clear.

---

## Current Script

Current user-facing control script:

* `scripts/apply_move.py`

This script allows move application from the command line using:

* `position_id`
* `move_uci`

It supports:

* text output
* llm output
* json output
* strict vs override policy

---

## Machine-Facing Control Output

The control layer already supports JSON output through `scripts/apply_move.py --format json`.

Example:

```json
{
  "format_version": 1,
  "source_position_id": 1,
  "move_uci": "e2e4",
  "move_san": "e4",
  "resulting_position_id": 2,
  "side_to_move": "b",
  "castling": "1111",
  "ep_file": "e",
  "board_rows": [
    "42356324",
    "11110111",
    "00000000",
    "00001000",
    "00000000",
    "00000000",
    "FFFFFFFF",
    "CEDBADEC"
  ]
}
```

This makes the control layer suitable for machine-to-machine testing, including comparisons across different LLMs.

---

## Trust Model

The trust model is simple:

* the database is authoritative
* the codec is authoritative
* the control layer is deterministic
* candidate moves are untrusted until validated

That is the right model for a system that mixes:

* stored structured state
  with
* probabilistic move proposals

---

## Testing

The control layer is important enough to deserve direct tests.

Current tests should verify at least:

* valid suggested move is accepted
* malformed UCI is rejected
* legal but unsuggested move is rejected in strict mode
* legal but unsuggested move is accepted in override mode
* illegal move is rejected
* audit logging records the correct outcome
* audit logging can be skipped when explicitly disabled

This is a trust boundary, so it should remain well tested.

---

## Non-Goals

The current control layer does **not** attempt to provide:

* signed move authorization
* cryptographic tokens
* multiplayer synchronization
* engine analysis
* automatic insertion of newly reached positions into the graph
* policy engines beyond suggested vs unsuggested acceptance

Those may be added later if needed.

The current implementation is intentionally smaller.

---

## Future Extensions

Possible future additions include:

* signed candidate-move tokens
* explicit policy profiles
* automatic persistence of newly applied but previously unseen positions
* richer audit metadata
* JSON Schema for control outputs
* integration with multi-model evaluation harnesses

These are plausible extensions, but they are not required for the current architecture to be sound.

---

## Summary

The control layer is the deterministic boundary that turns a proposed move into an accepted or rejected state transition.

It exists to ensure that:

* state remains authoritative
* move application remains legal
* policy remains explicit
* decisions remain auditable

This is what keeps `chess-gpt` from treating probabilistic move suggestions as if they were already truth.