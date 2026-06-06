import unittest

from cannonchess.core import (
    EMPTY,
    OBSTACLE,
    PLAYER_A,
    PLAYER_B,
    DRAW_NO_CAPTURE_TURNS,
    GameState,
    Move,
    apply_move,
    create_new_game,
    GameConfig,
    is_legal_move,
    legal_moves,
    piece_positions,
)


def state_from_top_rows(rows, current=PLAYER_A, no_capture_turns=0):
    bottom_first = tuple(tuple(row) for row in reversed(rows))
    return GameState(
        width=len(rows[0]),
        height=len(rows),
        grid=bottom_first,
        current_player=current,
        no_capture_turns=no_capture_turns,
    )


class CoreRulesTest(unittest.TestCase):
    def test_move_must_be_one_orthogonal_step_to_empty_cell(self):
        state = state_from_top_rows(
            [
                [EMPTY, EMPTY, EMPTY],
                [EMPTY, PLAYER_A, PLAYER_B],
                [EMPTY, OBSTACLE, EMPTY],
            ]
        )

        self.assertTrue(is_legal_move(state, Move((1, 1), (0, 1))))
        self.assertFalse(is_legal_move(state, Move((1, 1), (2, 1))))
        self.assertFalse(is_legal_move(state, Move((1, 1), (1, 0))))
        self.assertFalse(is_legal_move(state, Move((1, 1), (2, 2))))

    def test_vertical_capture_matches_requirement_example(self):
        state = state_from_top_rows(
            [
                [EMPTY, PLAYER_A, EMPTY],
                [PLAYER_B, EMPTY, EMPTY],
                [EMPTY, PLAYER_B, EMPTY],
            ],
            current=PLAYER_B,
        )

        next_state = apply_move(state, Move((0, 1), (1, 1)))

        self.assertEqual(next_state.cell((1, 2)), EMPTY)
        self.assertEqual(len(piece_positions(next_state, PLAYER_A)), 0)
        self.assertEqual(next_state.winner, PLAYER_B)

    def test_capture_distance_is_exactly_one_cell_beyond_pair(self):
        state = state_from_top_rows(
            [
                [EMPTY, PLAYER_A, EMPTY],
                [EMPTY, EMPTY, EMPTY],
                [PLAYER_B, EMPTY, EMPTY],
                [EMPTY, PLAYER_B, EMPTY],
            ],
            current=PLAYER_B,
        )

        next_state = apply_move(state, Move((0, 1), (1, 1)))

        self.assertEqual(next_state.cell((1, 3)), PLAYER_A)
        self.assertEqual(next_state.last_captured, ())

    def test_static_aligned_pair_does_not_capture_after_other_piece_moves(self):
        state = state_from_top_rows(
            [
                [PLAYER_A, EMPTY, EMPTY, EMPTY],
                [EMPTY, PLAYER_A, EMPTY, EMPTY],
                [EMPTY, PLAYER_B, EMPTY, EMPTY],
                [EMPTY, PLAYER_B, EMPTY, PLAYER_B],
                [EMPTY, EMPTY, EMPTY, EMPTY],
            ],
            current=PLAYER_B,
        )

        next_state = apply_move(state, Move((3, 1), (3, 0)))

        self.assertEqual(next_state.cell((1, 3)), PLAYER_A)
        self.assertEqual(next_state.last_captured, ())

    def test_moved_piece_cannot_capture_through_enemy_backed_by_piece(self):
        state = state_from_top_rows(
            [
                [PLAYER_A, EMPTY, EMPTY],
                [EMPTY, PLAYER_A, EMPTY],
                [EMPTY, PLAYER_B, EMPTY],
                [EMPTY, PLAYER_B, EMPTY],
            ],
            current=PLAYER_A,
        )

        next_state = apply_move(state, Move((0, 3), (1, 3)))

        self.assertEqual(next_state.cell((1, 1)), PLAYER_B)
        self.assertEqual(next_state.last_captured, ())

    def test_moved_piece_cannot_capture_through_enemy_backed_by_obstacle(self):
        state = state_from_top_rows(
            [
                [PLAYER_A, EMPTY, EMPTY],
                [EMPTY, PLAYER_A, EMPTY],
                [EMPTY, PLAYER_B, EMPTY],
                [EMPTY, OBSTACLE, EMPTY],
            ],
            current=PLAYER_A,
        )

        next_state = apply_move(state, Move((0, 3), (1, 3)))

        self.assertEqual(next_state.cell((1, 1)), PLAYER_B)
        self.assertEqual(next_state.last_captured, ())

    def test_draw_after_fifty_moves_without_capture(self):
        state = state_from_top_rows(
            [
                [PLAYER_A, EMPTY, PLAYER_A],
                [EMPTY, EMPTY, EMPTY],
                [PLAYER_B, EMPTY, PLAYER_B],
            ],
            current=PLAYER_A,
            no_capture_turns=DRAW_NO_CAPTURE_TURNS - 1,
        )

        next_state = apply_move(state, Move((0, 2), (1, 2)))

        self.assertTrue(next_state.draw)

    def test_no_draw_before_fifty_moves_without_capture(self):
        state = state_from_top_rows(
            [
                [PLAYER_A, EMPTY, PLAYER_A],
                [EMPTY, EMPTY, EMPTY],
                [PLAYER_B, EMPTY, PLAYER_B],
            ],
            current=PLAYER_A,
            no_capture_turns=DRAW_NO_CAPTURE_TURNS - 2,
        )

        next_state = apply_move(state, Move((0, 2), (1, 2)))

        self.assertFalse(next_state.draw)

    def test_player_with_no_legal_moves_is_skipped(self):
        state = state_from_top_rows(
            [
                [PLAYER_A, EMPTY, PLAYER_A],
                [OBSTACLE, OBSTACLE, OBSTACLE],
                [PLAYER_B, OBSTACLE, PLAYER_B],
            ],
            current=PLAYER_A,
        )

        next_state = apply_move(state, Move((0, 2), (1, 2)))

        self.assertEqual(legal_moves(next_state, PLAYER_B), ())
        self.assertEqual(next_state.current_player, PLAYER_A)

    def test_new_game_uses_required_counts_and_obstacle_values(self):
        state = create_new_game(GameConfig(width=5, height=6, seed=1))

        self.assertEqual(len(piece_positions(state, PLAYER_A)), 6)
        self.assertEqual(len(piece_positions(state, PLAYER_B)), 6)
        self.assertIn(state.current_player, (PLAYER_A, PLAYER_B))
        cells = {cell for row in state.grid for cell in row}
        self.assertLessEqual(cells, {EMPTY, PLAYER_A, PLAYER_B, OBSTACLE})

    def test_default_new_game_uses_random_required_board_size(self):
        state = create_new_game(GameConfig(seed=2))

        self.assertGreaterEqual(state.width, 5)
        self.assertLessEqual(state.width, 10)
        self.assertGreaterEqual(state.height, 5)
        self.assertLessEqual(state.height, 10)
        expected_count = min(state.width, state.height) + 1
        self.assertEqual(len(piece_positions(state, PLAYER_A)), expected_count)
        self.assertEqual(len(piece_positions(state, PLAYER_B)), expected_count)

    def test_obstacles_are_balanced_between_upper_and_lower_halves(self):
        state = create_new_game(GameConfig(width=10, height=10, seed=3))
        lower_count = sum(
            1
            for y in range(0, state.height // 2)
            for x in range(state.width)
            if state.cell((x, y)) == OBSTACLE
        )
        upper_count = sum(
            1
            for y in range(state.height // 2, state.height)
            for x in range(state.width)
            if state.cell((x, y)) == OBSTACLE
        )

        self.assertLessEqual(abs(lower_count - upper_count), 1)

    def test_obstacles_do_not_touch_after_balanced_generation(self):
        state = create_new_game(GameConfig(width=10, height=10, seed=5))
        obstacles = [
            (x, y)
            for y in range(state.height)
            for x in range(state.width)
            if state.cell((x, y)) == OBSTACLE
        ]

        for index, first in enumerate(obstacles):
            for second in obstacles[index + 1 :]:
                self.assertFalse(
                    abs(first[0] - second[0]) <= 1 and abs(first[1] - second[1]) <= 1
                )


if __name__ == "__main__":
    unittest.main()
