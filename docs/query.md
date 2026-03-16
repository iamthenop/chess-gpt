# Query

This document explains how `chess-gpt` is intended to retrieve moves from stored chess data.

The query layer exists to make chess reasoning more efficient through retrieval, not to replace a chess engine.

It answers questions like:

- what moves have been played from this position?
- which moves are common?
- which moves score well?
- which moves are worth considering first?
- what similar positions might inform this one?

---

## Purpose

The query layer is the practical payoff of the project.

The encoding layer gives the system a stable board representation.  
The schema stores positions and transitions.  
The query layer turns that stored structure into usable move suggestions.

Its goal is to improve:

- consistency
- opening stability
- middlegame plausibility
- move ranking
- retrieval efficiency

It does **not** try to solve chess from first principles.

---

## Core Idea

A current position is used as a lookup key into stored chess memory.

The system can then retrieve:

- exact matching positions
- outgoing moves from those positions
- aggregated statistics for those moves

This means the model does not need to invent candidate moves from scratch every time.

Instead, it can start from:

- known continuations
- known frequencies
- known outcomes

That is the foundation of retrieval-first chess reasoning.

---

## Query Layers

The query layer is easiest to understand as three levels.

### 1. Exact Position Lookup

This is the first and most important query mode.

Given:

- board layout
- side to move
- castling rights
- en passant file when relevant

find the matching `positions` row and return outgoing edges.

This gives:
- move list
- frequency
- win/draw/loss counts
- resulting positions

This is the cleanest and cheapest query.

---

### 2. Exact Position Ranking

Once the outgoing moves are retrieved, they can be ranked.

Typical ranking signals include:

- frequency of play
- white win rate
- black win rate
- draw rate
- average Elo
- time control distribution

This is still exact-position querying, but now with scoring.

The system is no longer asking only:

> what moves exist?

It is asking:

> which moves are likely to be useful first?

---

### 3. Similar Position Retrieval

This is a later-stage feature.

When an exact match is missing or sparse, the system can search for similar positions.

That similarity might be based on:

- pawn structure
- material balance
- king placement
- castling state
- open files
- passed pawns
- tags such as `rook_endgame` or `iqp`

This mode is not required for the first version, but it is important for long-term usefulness.

It allows the system to generalize instead of failing whenever an exact board is absent from the database.

---

## Exact Query Workflow

The intended exact query flow is:

1. encode the current board into the canonical board blob
2. resolve the `boards` row
3. resolve the `positions` row using:
   - board
   - side to move
   - castling rights
   - en passant file
4. retrieve outgoing edges from that position
5. rank edges
6. return candidate moves

This is the main query path for the early project.

---

## Why Exact Lookup Matters

Exact lookup is the best way to reduce drift.

Without retrieval, the model must:

- reconstruct state from text
- imagine candidate moves
- infer what is plausible

That is expensive and fragile.

With exact retrieval, the system gets a stable candidate set grounded in prior games.

This improves:
- consistency
- state fidelity
- early move quality
- retrieval speed

---

## What a Query Returns

A query should return more than just a move list.

A good result record includes:

- move in UCI
- move in SAN
- frequency
- white wins
- black wins
- draws
- optional derived rates
- maybe resulting position ID

That gives the query layer enough information to support:

- simple move suggestions
- ranking
- filtering
- later path expansion

---

## Example Exact Query Result

Conceptually, the result of querying a position may look like:

```text
move_uci  move_san  frequency  white_win_rate  draw_rate  black_win_rate
e2e4      e4        12543      0.39            0.31       0.30
d2d4      d4         9821      0.41            0.29       0.30
g1f3      Nf3        4210      0.38            0.34       0.28
````

This is not declaring which move is objectively best.

It is showing what the database knows about practical continuations.

---

## Ranking Signals

The query layer should treat stored statistics as priors, not as truth.

Useful ranking signals include:

### Frequency

How often the move was played.

This is useful because common moves often reflect stable theory or repeated practical experience.

But frequency alone is not enough because common moves can still be bad.

### Win Rate

How often the move led to wins for the relevant side.

This is useful because it adds consequence, not just popularity.

But win rate also has limits:

* depends on player pool
* depends on time control
* may reward traps
* may reward practical difficulty more than objective strength

### Draw Rate

Useful for identifying stable, low-volatility lines.

### Average Elo

Useful for weighting moves by the strength of the players who used them.

### Time Control Distribution

Useful for distinguishing:

* strong classical ideas
* blitz habits
* trap-heavy fast-game lines

---

## How Statistics Should Be Used

The query layer should not blindly trust any one signal.

A good mental model is:

* frequency = expectation
* win rate = consequence
* query result = ranked prior

This means retrieval should help answer:

> what moves deserve consideration first?

It does **not** automatically answer:

> what move is objectively correct?

That distinction matters.

---

## Query Output Is Not Final Move Selection

The query layer is not the whole decision system.

It is one layer in a broader flow:

1. retrieve candidate moves
2. eliminate illegal moves
3. rank by priors
4. optionally inspect top candidates more closely
5. choose a move

That means the query layer is fundamentally a **candidate provider**.

Its job is to reduce waste and improve ranking, not to guarantee perfect play.

---

## Similar Position Retrieval

This is the long-term extension of the system.

Exact lookup will often work in:

* openings
* common middlegames
* repeated structures

But there will always be positions with:

* no exact match
* very sparse data
* too little confidence

At that point, the system should search for structurally similar positions.

---

## What Similarity Should Mean

Similarity should not be based only on visual resemblance.

It should eventually prioritize:

* pawn structure
* material class
* king safety
* side to move
* piece activity
* passed pawns
* open or semi-open files

In other words, similarity should be strategic, not merely geometric.

Two positions can differ in exact coordinates and still want the same plan.

That is what similarity search should capture.

---

## Role of Tags

The `position_tags` table exists largely to support this future query layer.

Tags may help answer questions like:

* is this a rook endgame?
* is this an isolated queen pawn structure?
* are kings castled on opposite sides?
* is this a closed center?
* is there a passed pawn?

These tags can improve both:

* similarity search
* move suggestion ranking

without forcing those semantics into the core board encoding.

---

## LLM Query Consumption

The query layer is designed to support LLM use.

That means query output should be:

* stable
* structured
* compact
* easy to parse
* grounded in stored state

A good LLM-facing query result may look like:

```text
position_id:12345
candidate_moves:
- move_uci:e2e4 move_san:e4 frequency:12543 white_win_rate:0.39 draw_rate:0.31 black_win_rate:0.30
- move_uci:d2d4 move_san:d4 frequency:9821 white_win_rate:0.41 draw_rate:0.29 black_win_rate:0.30
- move_uci:g1f3 move_san:Nf3 frequency:4210 white_win_rate:0.38 draw_rate:0.34 black_win_rate:0.28
```

The exact serialization format may change later, but the principle should remain:

* query results should be machine-readable first
* human readability is secondary

---

## Exact Match Failure

Sometimes an exact position will not be found.

That is expected.

When exact lookup fails, the system can respond in stages:

1. confirm there is no exact match
2. optionally relax into similarity search
3. return the best available approximations
4. make it clear the result is approximate

That is better than pretending exact knowledge exists where it does not.

---

## Query Modes

A practical query layer will likely end up supporting modes such as:

### `exact`

Only exact position matches.

### `exact_top`

Exact matches with ranked top moves.

### `similar`

Nearest similar positions when exact match is absent or weak.

### `stats`

Return raw move statistics without ranking logic.

### `path`

Expand one or more plies outward through the move graph.

Not all of these are needed immediately, but they form a useful roadmap.

---

## What Query Is Not

The query layer is not:

* move legality enforcement
* board encoding
* PGN replay
* tactical calculation
* engine evaluation
* endgame tablebase logic

Those belong elsewhere.

The query layer is intentionally narrower:

> retrieve relevant move information from stored chess memory

That is enough.

---

## Why This Helps LLM Chess

This layer matters because language models are good at:

* ranking patterns
* interpreting structured context
* choosing among plausible options

They are worse at:

* generating exact candidate moves from scratch
* maintaining perfect board state in long sequences
* discovering tactical lines without strong priors

So the query layer gives the model something it naturally benefits from:

* a grounded candidate set
* empirical move history
* compact structured priors

This does not make the model an engine.

It does make it less wasteful.

---

## Early Non-Goals

The first version of query logic does **not** need:

* full similarity search
* deep graph traversal
* forced mate detection
* outcome-distance estimation
* engine integration

Those can come later.

The first useful version only needs:

* exact position lookup
* ranked outgoing moves
* stable result format

That is enough to make the system meaningfully better.

---

## Summary

The query layer exists to turn stored chess data into usable move suggestions.

It works by:

* locating a position
* retrieving outgoing move edges
* ranking them using practical statistics
* returning structured candidate moves

The first version should focus on:

* exact lookup
* move frequency
* result-based ranking
* stable LLM-facing output

Later versions can expand into:

* similarity search
* tag-aware retrieval
* multi-hop graph queries
* stronger structural reasoning

The query layer is the bridge between stored chess memory and practical move selection.

