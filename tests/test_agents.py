import unittest

from cannonchess.agents import HeuristicAgent
from cannonchess.core import (
    EMPTY,
    PLAYER_A,
    PLAYER_B,
    GameConfig,
    GameState,
    Move,
    create_new_game,
    legal_moves,
)


def state_from_top_rows(rows, current=PLAYER_B):
    bottom_first = tuple(tuple(row) for row in reversed(rows))
    return GameState(
        width=len(rows[0]),
        height=len(rows),
        grid=bottom_first,
        current_player=current,
    )


class HeuristicAgentTest(unittest.TestCase):
    def test_agent_returns_legal_move(self):
        state = state_from_top_rows(
            [
                [PLAYER_A, EMPTY, PLAYER_A],
                [EMPTY, EMPTY, EMPTY],
                [PLAYER_B, EMPTY, PLAYER_B],
            ]
        )
        agent = HeuristicAgent(player=PLAYER_B, max_depth=2, seed=1)

        move = agent.choose_move(state)

        self.assertIn(move, legal_moves(state, PLAYER_B))

    def test_agent_prefers_immediate_capture(self):
        state = state_from_top_rows(
            [
                [EMPTY, PLAYER_A, EMPTY, PLAYER_A],
                [PLAYER_B, EMPTY, EMPTY, EMPTY],
                [EMPTY, PLAYER_B, EMPTY, PLAYER_A],
            ],
            current=PLAYER_B,
        )
        agent = HeuristicAgent(player=PLAYER_B, max_depth=2, seed=1)

        move = agent.choose_move(state)

        self.assertEqual(move, Move((0, 1), (1, 1)))

    def test_agent_handles_large_board_with_candidate_limit(self):
        state = create_new_game(GameConfig(width=10, height=10, seed=4))
        if state.current_player != PLAYER_B:
            state = GameState(
                width=state.width,
                height=state.height,
                grid=state.grid,
                current_player=PLAYER_B,
                no_capture_turns=state.no_capture_turns,
                winner=state.winner,
                draw=state.draw,
                move_count=state.move_count,
                last_captured=state.last_captured,
            )
        agent = HeuristicAgent(player=PLAYER_B, max_depth=2, candidate_limit=6, seed=2)

        move = agent.choose_move(state)

        self.assertIn(move, legal_moves(state, PLAYER_B))


if __name__ == "__main__":
    unittest.main()
