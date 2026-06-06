import unittest

from cannonchess.core import GameConfig, Move, create_new_game
from cannonchess.network import move_from_dict, move_to_dict, state_from_dict, state_to_dict


class NetworkSerializationTest(unittest.TestCase):
    def test_game_state_round_trip(self):
        state = create_new_game(GameConfig(width=6, height=7, seed=12))

        restored = state_from_dict(state_to_dict(state))

        self.assertEqual(restored, state)

    def test_move_round_trip(self):
        move = Move((1, 2), (1, 3))

        restored = move_from_dict(move_to_dict(move))

        self.assertEqual(restored, move)


if __name__ == "__main__":
    unittest.main()
