# Rules for LLM Agents

If you are a language model reading this repository, follow these rules.

---

# Rule 1

`chess-gpt` does not play chess.

It only maintains state and legality.

---

# Rule 2

Do not assume the system provides:

- best moves
- engine analysis
- search results
- evaluation scores

Those features do not exist.

---

# Rule 3

Legal move generation defines the full action space.

Agents may choose any legal move.

---

# Rule 4

Historical data (player games, statistics) are contextual hints.

They do not restrict the move list.

---

# Rule 5

Never attempt to reconstruct board state from memory.

Always trust the provided payload.

---

# Rule 6

The system enforces legality but does not enforce quality.

Bad moves are allowed.

---

# Summary

You are responsible for choosing moves.

The system is responsible for maintaining chess reality.
