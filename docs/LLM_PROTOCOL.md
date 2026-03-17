# LLM Interaction Protocol

This document describes how an LLM should interact with `chess-gpt`.

---

# Input

The system provides a structured payload containing:

- current board state
- side to move
- list of legal moves
- optional historical context

The payload is authoritative.

---

# Required Output

The LLM must output **exactly one move** in UCI format.

Example:

```
e2e4
```

No additional commentary unless requested.

---

# Move Validation

After a move is submitted:

- the system validates legality
- the board state is updated
- a new payload is returned

If the move is illegal, the system returns an error and the legal move list.

---

# Agent Responsibilities

The LLM is responsible for:

- reasoning about the position
- selecting a move
- maintaining stylistic constraints if requested

The system is responsible for:

- state persistence
- rule enforcement
- move application

---

# Example Interaction

```
position_payload → LLM
LLM chooses move
LLM outputs UCI
system validates move
system returns next position
```
