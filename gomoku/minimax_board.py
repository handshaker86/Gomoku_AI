import time
import numpy as np
from gomoku.board import Base_board
from gomoku.player import Player


class Minimax_board(Base_board):
    def __init__(
        self, size, player_1: Player, player_2: Player, depth: int, defense_rate: float
    ):
        super().__init__(size, player_1, player_2)
        self.depth = depth
        self.defense_rate = defense_rate
        self.difficulty = 2

    def evaluate_board(self, player):
        """
        Evaluate the board for a given player.
        """
        score = 0
        for i in range(self.size):
            for j in range(self.size):
                if self.get_stone(i, j) == 0 and self.check_valid(i, j):
                    score += self.evaluate_shape(i, j, player)
        return score

    def generate_candidate_moves(self):
        """
        Generate candidate moves:
          Only consider empty positions near existing stones; if the board is empty,
          return the center position.
        """
        moves = set()
        search_range = 1  # search range around existing stones
        for i in range(self.size):
            for j in range(self.size):
                if self.board[i, j] != 0:
                    for di in range(-search_range, search_range + 1):
                        for dj in range(-search_range, search_range + 1):
                            ni, nj = i + di, j + dj
                            if self.check_valid(ni, nj) and self.get_stone(ni, nj) == 0:
                                moves.add((ni, nj))
        if not moves:
            moves.add((self.size // 2, self.size // 2))
        return list(moves)

    def minimax(self, depth, alpha, beta, maximizingPlayer, player):
        """
        Minimax recursive search with Alpha-Beta pruning.
        Parameters:
          - depth: remaining search depth
          - alpha: current maximum lower bound
          - beta: current minimum upper bound
          - maximizingPlayer: True if it's the maximizer's turn
          - player: the root player for whom the search is performed
        """
        opp = self.get_opponent(player)

        if depth == 0:
            return (
                self.evaluate_board(player)
                - self.evaluate_board(opp) * self.defense_rate
            )

        if maximizingPlayer:
            max_eval = -np.inf
            for move in self.generate_candidate_moves():
                if self.check_win(move[0], move[1], player):
                    return np.inf
                self.set_stone(move[0], move[1], player)
                eval_value = self.minimax(depth - 1, alpha, beta, False, player)
                self.remove_stone(move[0], move[1])
                max_eval = max(max_eval, eval_value)
                alpha = max(alpha, eval_value)
                if beta <= alpha:
                    break  # Prune branch
            return max_eval
        else:
            opp = self.get_opponent(player)
            min_eval = np.inf
            for move in self.generate_candidate_moves():
                if self.check_win(move[0], move[1], opp):
                    return -np.inf
                self.set_stone(move[0], move[1], opp)
                eval_value = self.minimax(depth - 1, alpha, beta, True, player)
                self.remove_stone(move[0], move[1])
                min_eval = min(min_eval, eval_value)
                beta = min(beta, eval_value)
                if beta <= alpha:
                    break  # Prune branch
            return min_eval

    def quick_evaluate(self, move, player):
        """
        Quickly evaluate a candidate move by placing the stone,
        then using a shallow evaluation of the board, and finally removing the stone.
        This function is used to order candidate moves heuristically.
        """
        self.set_stone(move[0], move[1], player)

        # Evaluate a local area around the move
        local_range = 2
        local_score = 0
        x, y = move
        i_min, i_max = max(0, x - local_range), min(self.size, x + local_range + 1)
        j_min, j_max = max(0, y - local_range), min(self.size, y + local_range + 1)

        for i in range(i_min, i_max):
            for j in range(j_min, j_max):
                if self.get_stone(i, j) == 0:
                    local_score += self.evaluate_shape(i, j, player)

        # Remove the stone
        self.remove_stone(move[0], move[1])
        return local_score

    def get_best_move(self, player, time_limit=2000.0):
        """
        Choose the best move using Iterative Deepening and Minimax with Alpha-Beta pruning.
        A time limit is applied; if the time is up, the best move from the last completed depth is returned.

        Parameters:
          - player: the current player
          - time_limit: maximum allowed time (in seconds) for search
        """
        best_move = None
        best_score = -np.inf
        start_time = time.time()
        current_depth = 1

        # Generate candidate moves and order them using quick evaluation.
        candidate_moves = self.generate_candidate_moves()

        for move in candidate_moves:
            if self.check_win(move[0], move[1], player):
                return move

        candidate_moves = sorted(
            candidate_moves,
            key=lambda move: self.quick_evaluate(move, player),
            reverse=True,
        )

        # Iterative Deepening: search from depth 1 to self.depth (or until time is up)
        while current_depth <= self.depth:
            # Check if time limit has been exceeded
            if time.time() - start_time > time_limit:
                break

            for move in candidate_moves:
                # Before processing each move, optionally check time as well
                if time.time() - start_time > time_limit:
                    break
                self.set_stone(move[0], move[1], player)
                score = self.minimax(current_depth - 1, -np.inf, np.inf, False, player)
                self.remove_stone(move[0], move[1])
                if score > best_score:
                    best_score = score
                    best_move = move
            current_depth += 1

        return best_move
