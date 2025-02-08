import numpy as np
import math
from gomoku.board import Base_board
from gomoku.player import Player


class Eval_func_board(Base_board):
    def __init__(self, size, player_1: Player, player_2: Player, defense_rate: float):
        """
        player_1 and player_2 represent the players' stones.
        """
        super().__init__(size, player_1, player_2)

        # initialize score boards
        self.reset_score_board()
        self.defense_rate = defense_rate
        self.difficulty = 1

    def set_stone(self, x, y, player):
        self.board[x, y] = player.stone
        self.update_score_board(x, y, player)

    def reset_score_board(self):
        self.player_1.score_board = np.zeros((self.size, self.size), dtype=float)
        self.player_1.overall_score_board = np.zeros(
            (self.size, self.size), dtype=float
        )
        self.player_2.score_board = np.zeros((self.size, self.size), dtype=float)
        self.player_2.overall_score_board = np.zeros(
            (self.size, self.size), dtype=float
        )

    def update_score_board(self, x, y, player):
        """
        Update the local and overall score boards for both players
        around the recent move (x, y).
        """
        opponent = self.get_opponent(player)
        i_min, i_max = max(0, x - 4), min(self.size, x + 5)
        j_min, j_max = max(0, y - 4), min(self.size, y + 5)
        for i in range(i_min, i_max):
            for j in range(j_min, j_max):
                player_score = self.evaluate_shape(i, j, player)
                opponent_score = self.evaluate_shape(i, j, opponent)
                if self.get_stone(i, j) == 0:
                    player.score_board[i, j] = player_score
                    opponent.score_board[i, j] = opponent_score
                else:
                    player.score_board[i, j] = 0
                    opponent.score_board[i, j] = 0

        player.overall_score_board = (
            player.score_board + self.defense_rate * opponent.score_board
        )
        opponent.overall_score_board = (
            opponent.score_board + self.defense_rate * player.score_board
        )

    def get_best_move(self, player):
        """
        Get the best move for the player based on the overall score board.
        """

        def distance_to_center(x, y):
            # Calculate the Euclidean distance to the center of the board
            center = (math.floor(self.size / 2), math.floor(self.size / 2))
            return math.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2)

        available = np.argwhere(self.board == 0)
        if available.size == 0:
            return None

        best_move = []
        best_score = -np.inf
        for i, j in available:
            score = player.overall_score_board[i, j]
            if score > best_score:
                best_score = score
                best_move = [(i, j)]
            elif score == best_score:
                best_move.append((i, j))

        # choose the best move
        if len(best_move) == 1:
            best_move = best_move[0]
        else:
            best_move = sorted(
                best_move, key=lambda move: distance_to_center(move[0], move[1])
            )
            best_move = best_move[0]

        return best_move
