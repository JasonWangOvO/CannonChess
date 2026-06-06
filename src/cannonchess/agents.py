"""AI agents for CannonChess."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from .core import (
    PLAYER_A,
    PLAYER_B,
    GameState,
    Move,
    apply_move,
    legal_moves,
    opponent,
    piece_positions,
)

WIN_SCORE = 100_000


class PlayerAgent:
    """Base interface for future AI players."""

    def choose_move(self, game_state: GameState) -> Move:
        raise NotImplementedError


@dataclass
class HeuristicAgent(PlayerAgent):
    """Depth-limited alpha-beta AI with a simple board evaluator."""

    player: int = PLAYER_B
    max_depth: int = 2
    candidate_limit: int = 10
    capture_sample_limit: int = 12
    seed: int | None = None

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def choose_move(self, game_state: GameState) -> Move:
        moves = list(legal_moves(game_state, self.player))
        if not moves:
            raise ValueError("AI has no legal move")

        moves = self._ordered_moves(game_state, moves, self.player)

        best_score = -math.inf
        best_moves: list[Move] = []
        for move in moves:
            next_state = apply_move(game_state, move)
            score = self._search(
                next_state,
                depth=self.max_depth - 1,
                alpha=-math.inf,
                beta=math.inf,
            )
            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)
        return self._rng.choice(best_moves)

    def _search(
        self,
        state: GameState,
        *,
        depth: int,
        alpha: float,
        beta: float,
    ) -> float:
        if depth <= 0 or state.winner is not None or state.draw:
            return self.evaluate(state)

        moves = list(legal_moves(state))
        if not moves:
            return self.evaluate(state)

        maximizing = state.current_player == self.player
        moves = self._ordered_moves(state, moves, state.current_player)

        if maximizing:
            value = -math.inf
            for move in moves:
                value = max(
                    value,
                    self._search(
                        apply_move(state, move),
                        depth=depth - 1,
                        alpha=alpha,
                        beta=beta,
                    ),
                )
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value

        value = math.inf
        for move in moves:
            value = min(
                value,
                self._search(
                    apply_move(state, move),
                    depth=depth - 1,
                    alpha=alpha,
                    beta=beta,
                ),
            )
            beta = min(beta, value)
            if alpha >= beta:
                break
        return value

    def evaluate(self, state: GameState) -> float:
        if state.winner == self.player:
            return WIN_SCORE
        if state.winner == opponent(self.player):
            return -WIN_SCORE
        if state.draw:
            return 0

        enemy = opponent(self.player)
        own_count = len(piece_positions(state, self.player))
        enemy_count = len(piece_positions(state, enemy))
        material = own_count - enemy_count

        own_mobility = len(legal_moves(state, self.player))
        enemy_mobility = len(legal_moves(state, enemy))
        mobility = own_mobility - enemy_mobility

        own_capture = self._total_capture_chances(state, self.player)
        enemy_capture = self._total_capture_chances(state, enemy)
        capture_pressure = own_capture - enemy_capture

        # Prefer avoiding draw when ahead; accept draw pressure when behind.
        draw_pressure = state.no_capture_turns if material < 0 else -state.no_capture_turns

        return (
            120 * material
            + 12 * mobility
            + 35 * capture_pressure
            + 0.5 * draw_pressure
        )

    def _ordered_moves(
        self, state: GameState, moves: list[Move], player: int
    ) -> list[Move]:
        self._rng.shuffle(moves)
        moves.sort(
            key=lambda move: self._quick_move_score(state, move, player),
            reverse=True,
        )
        return moves[: self.candidate_limit]

    def _quick_move_score(self, state: GameState, move: Move, player: int) -> float:
        try:
            next_state = self._apply_as_player(state, move, player)
        except ValueError:
            return -math.inf
        capture_count = len(next_state.last_captured)
        if next_state.winner == player:
            return WIN_SCORE
        if next_state.winner == opponent(player):
            return -WIN_SCORE
        own_count = len(piece_positions(next_state, player))
        enemy_count = len(piece_positions(next_state, opponent(player)))
        return 100 * capture_count + 10 * (own_count - enemy_count)

    def _capture_count(self, state: GameState, move: Move) -> int:
        try:
            next_state = apply_move(state, move)
        except ValueError:
            return 0
        return len(next_state.last_captured)

    def _total_capture_chances(self, state: GameState, player: int) -> int:
        total = 0
        moves = list(legal_moves(state, player))
        moves = self._ordered_moves(state, moves, player)
        for move in moves[: self.capture_sample_limit]:
            total += self._capture_count_for_player(state, move, player)
        return total

    def _capture_count_for_player(self, state: GameState, move: Move, player: int) -> int:
        return len(self._apply_as_player(state, move, player).last_captured)

    def _apply_as_player(self, state: GameState, move: Move, player: int) -> GameState:
        if state.current_player == player:
            return apply_move(state, move)
        assumed_state = GameState(
            width=state.width,
            height=state.height,
            grid=state.grid,
            current_player=player,
            no_capture_turns=state.no_capture_turns,
            winner=state.winner,
            draw=state.draw,
            move_count=state.move_count,
            last_captured=state.last_captured,
        )
        return apply_move(assumed_state, move)
