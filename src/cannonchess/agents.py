"""AI extension point reserved by the requirements."""

from __future__ import annotations

from .core import GameState, Move


class PlayerAgent:
    """Base interface for future AI players."""

    def choose_move(self, game_state: GameState) -> Move:
        raise NotImplementedError
