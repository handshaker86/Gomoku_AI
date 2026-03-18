from gomoku.board import Base_board
from gomoku.player import Player


class Online_board(Base_board):
    """Board for online multiplayer games. No AI logic, just board state and win detection."""

    def __init__(self, size, player_1: Player, player_2: Player):
        super().__init__(size, player_1, player_2)
        self.difficulty = 0  # Indicates online mode
