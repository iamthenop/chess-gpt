from __future__ import annotations


class ChessGptError(Exception):
    """
    Base exception for chess-gpt.
    """


class PositionNotFoundError(ChessGptError):
    """
    Raised when a requested position_id does not exist.
    """


class InvalidMoveSyntaxError(ChessGptError):
    """
    Raised when a candidate move is not valid UCI syntax.
    """


class MoveNotSuggestedError(ChessGptError):
    """
    Raised when strict policy requires a move to be in the issued/suggested set
    and it is not.
    """


class IllegalMoveError(ChessGptError):
    """
    Raised when a syntactically valid move is illegal in the authoritative position.
    """


class InterfaceError(ChessGptError):
    """
    Raised when a machine-facing interface contract is violated.
    """