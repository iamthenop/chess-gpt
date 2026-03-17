# Architecture

`chess-gpt` is a deterministic chess state machine.

It maintains canonical board state and enforces legal transitions.

The system consists of four conceptual layers.

---

# 1. Position Encoding

Positions are stored using a compact canonical encoding.

This encoding uniquely represents:

- piece placement
- side to move
- castling rights
- en-passant state
- move counters

The encoding ensures that identical positions map to identical identifiers.

---

# 2. Legal Move Generation

Given a position, the system produces the complete set of legal moves.

This is the authoritative action space.

Agents must choose from these moves.

---

# 3. Control Layer

The control layer validates proposed moves.

Responsibilities:

• verify legality  
• update state  
• maintain move history  
• produce next canonical position  

The control layer never chooses moves.

---

# 4. Retrieval Layer (Optional)

Historical games can be queried to provide context such as:

- player corpora
- move frequencies
- historical examples

This information influences agent decisions but does not restrict legality.

---

# System Boundary

The environment guarantees:

- correct chess state
- correct legal move list

The environment does not attempt to determine good moves.

Decision making occurs outside the system.