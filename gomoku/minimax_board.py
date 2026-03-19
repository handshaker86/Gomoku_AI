import time
import numpy as np
from gomoku.board import Base_board
from gomoku.player import Player

# Transposition table flag constants
EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2

# Max entries in transposition table
TT_MAX_SIZE = 1000000


class Minimax_board(Base_board):
    def __init__(
        self, size, player_1: Player, player_2: Player, depth: int, defense_rate: float
    ):
        super().__init__(size, player_1, player_2)
        self.depth = depth
        self.defense_rate = defense_rate
        self.difficulty = 2

        # Incremental candidate set
        self.candidate_set = set()
        self._candidate_stack = []  # stack for undo support

        # Zobrist hashing
        rng = np.random.RandomState(42)
        self.zobrist_table = rng.randint(0, 2**63, size=(size, size, 2), dtype=np.int64)
        self.zobrist_hash = np.int64(0)
        self.transposition_table = {}

        # Killer moves & history heuristic
        self.killer_moves = [[] for _ in range(depth + 2)]
        self.history_table = np.zeros((size, size), dtype=np.int64)

        # Incremental score boards
        self.score_board_p1 = np.zeros((size, size), dtype=float)
        self.score_board_p2 = np.zeros((size, size), dtype=float)
        self._score_stack = []  # stack to save/restore score regions
        self._init_score_boards()

    def _init_score_boards(self):
        """Initialize score boards for the starting (empty) board."""
        for i in range(self.size):
            for j in range(self.size):
                self.score_board_p1[i, j] = self.evaluate_shape(i, j, self.player_1)
                self.score_board_p2[i, j] = self.evaluate_shape(i, j, self.player_2)

    # Overridden set_stone / remove_stone with incremental updates

    def set_stone(self, x, y, player):
        # Update Zobrist hash
        z_idx = 0 if player.stone == 1 else 1
        self.zobrist_hash ^= self.zobrist_table[x, y, z_idx]

        # Save candidate set state for undo
        added = set()
        removed = False
        if (x, y) in self.candidate_set:
            self.candidate_set.discard((x, y))
            removed = True

        # Add neighbors within radius 2
        for di in range(-2, 3):
            for dj in range(-2, 3):
                ni, nj = x + di, y + dj
                if (
                    self.check_valid(ni, nj)
                    and self.board[ni, nj] == 0
                    and (ni, nj) != (x, y)
                    and (ni, nj) not in self.candidate_set
                ):
                    self.candidate_set.add((ni, nj))
                    added.add((ni, nj))
        self._candidate_stack.append((x, y, removed, added))

        # Save score board region before update (use Python lists to avoid numpy copy overhead)
        r = 4
        i_min, i_max = max(0, x - r), min(self.size, x + r + 1)
        j_min, j_max = max(0, y - r), min(self.size, y + r + 1)
        old_p1 = self.score_board_p1[i_min:i_max, j_min:j_max].tolist()
        old_p2 = self.score_board_p2[i_min:i_max, j_min:j_max].tolist()
        self._score_stack.append((i_min, i_max, j_min, j_max, old_p1, old_p2))

        # Place stone
        self.board[x, y] = player.stone

        # Incrementally update score boards in local region
        for i in range(i_min, i_max):
            for j in range(j_min, j_max):
                if self.board[i, j] == 0:
                    self.score_board_p1[i, j] = self.evaluate_shape(i, j, self.player_1)
                    self.score_board_p2[i, j] = self.evaluate_shape(i, j, self.player_2)
                else:
                    self.score_board_p1[i, j] = 0
                    self.score_board_p2[i, j] = 0

    def remove_stone(self, x, y):
        # Restore Zobrist hash
        stone_val = self.board[x, y]
        z_idx = 0 if stone_val == 1 else 1
        self.zobrist_hash ^= self.zobrist_table[x, y, z_idx]

        # Remove stone
        self.board[x, y] = 0

        # Restore score boards (write back from Python lists)
        if self._score_stack:
            i_min, i_max, j_min, j_max, old_p1, old_p2 = self._score_stack.pop()
            for ri, i in enumerate(range(i_min, i_max)):
                for rj, j in enumerate(range(j_min, j_max)):
                    self.score_board_p1[i, j] = old_p1[ri][rj]
                    self.score_board_p2[i, j] = old_p2[ri][rj]

        # Restore candidate set
        if self._candidate_stack:
            cx, cy, was_present, added_set = self._candidate_stack.pop()
            self.candidate_set -= added_set
            if was_present:
                self.candidate_set.add((cx, cy))

    # Fast board evaluation using incremental score boards

    def evaluate_board(self, player):
        if player == self.player_1:
            return float(np.sum(self.score_board_p1))
        else:
            return float(np.sum(self.score_board_p2))

    # Candidate move generation

    def generate_candidate_moves(self):
        """Return current candidate moves (empty cells near existing stones)."""
        if not self.candidate_set:
            # Board is empty or first move
            center = self.size // 2
            if self.board[center, center] == 0:
                return [(center, center)]
            # Fallback: scan for neighbors
            moves = set()
            for i in range(self.size):
                for j in range(self.size):
                    if self.board[i, j] != 0:
                        for di in range(-2, 3):
                            for dj in range(-2, 3):
                                ni, nj = i + di, j + dj
                                if self.check_valid(ni, nj) and self.board[ni, nj] == 0:
                                    moves.add((ni, nj))
            return list(moves) if moves else [(center, center)]
        # Filter out any occupied cells (safety check)
        return [m for m in self.candidate_set if self.board[m[0], m[1]] == 0]

    def _order_moves(self, moves, player, depth, tt_best_move=None):
        """Order moves for better alpha-beta pruning."""
        scored = []
        for move in moves:
            score = 0
            # Highest priority: transposition table best move
            if tt_best_move and move == tt_best_move:
                score = 10000000
            # Killer move bonus
            elif move in self.killer_moves[depth]:
                score = 5000000
            else:
                # Use score boards for fast evaluation
                x, y = move
                p1_score = self.score_board_p1[x, y]
                p2_score = self.score_board_p2[x, y]
                # Combine offensive + defensive value
                if player == self.player_1:
                    score = p1_score + self.defense_rate * p2_score
                else:
                    score = p2_score + self.defense_rate * p1_score
                # History heuristic bonus
                score += self.history_table[x, y] * 0.1
            scored.append((score, move))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored]

    def minimax(
        self, depth, alpha, beta, maximizingPlayer, player, start_time, time_limit
    ):
        opp = self.get_opponent(player)

        # Time check
        if time.time() - start_time > time_limit:
            return (
                self.evaluate_board(player)
                - self.evaluate_board(opp) * self.defense_rate
            )

        # Transposition table lookup
        tt_entry = self.transposition_table.get(self.zobrist_hash)
        tt_best_move = None
        if tt_entry is not None:
            tt_depth, tt_flag, tt_value, tt_move = tt_entry
            if tt_depth >= depth:
                if tt_flag == EXACT:
                    return tt_value
                elif tt_flag == LOWERBOUND:
                    alpha = max(alpha, tt_value)
                elif tt_flag == UPPERBOUND:
                    beta = min(beta, tt_value)
                if alpha >= beta:
                    return tt_value
            tt_best_move = tt_move

        # Leaf node: use incremental score boards
        if depth == 0:
            val = (
                self.evaluate_board(player)
                - self.evaluate_board(opp) * self.defense_rate
            )
            return val

        # Generate and order candidate moves (Top-K limiting)
        raw_moves = self.generate_candidate_moves()
        max_candidates = 15 if depth >= 3 else 12
        ordered_moves = self._order_moves(
            raw_moves, player if maximizingPlayer else opp, depth, tt_best_move
        )
        moves = ordered_moves[:max_candidates]

        best_move_here = moves[0] if moves else None
        orig_alpha = alpha

        if maximizingPlayer:
            max_eval = -np.inf
            for move in moves:
                if self.check_win(move[0], move[1], player):
                    # Store in TT
                    self.transposition_table[self.zobrist_hash] = (
                        depth,
                        EXACT,
                        np.inf,
                        move,
                    )
                    return np.inf
                self.set_stone(move[0], move[1], player)
                eval_value = self.minimax(
                    depth - 1, alpha, beta, False, player, start_time, time_limit
                )
                self.remove_stone(move[0], move[1])
                if eval_value > max_eval:
                    max_eval = eval_value
                    best_move_here = move
                alpha = max(alpha, eval_value)
                if beta <= alpha:
                    # Killer move: record the move that caused cutoff
                    if move not in self.killer_moves[depth]:
                        if len(self.killer_moves[depth]) >= 2:
                            self.killer_moves[depth].pop(0)
                        self.killer_moves[depth].append(move)
                    # History heuristic
                    self.history_table[move[0], move[1]] += depth * depth
                    break

            # Store in transposition table (replace if deeper or same depth)
            if max_eval <= orig_alpha:
                tt_flag = UPPERBOUND
            elif max_eval >= beta:
                tt_flag = LOWERBOUND
            else:
                tt_flag = EXACT
            existing = self.transposition_table.get(self.zobrist_hash)
            if existing is None or depth >= existing[0]:
                self.transposition_table[self.zobrist_hash] = (
                    depth,
                    tt_flag,
                    max_eval,
                    best_move_here,
                )
            return max_eval
        else:
            min_eval = np.inf
            for move in moves:
                if self.check_win(move[0], move[1], opp):
                    self.transposition_table[self.zobrist_hash] = (
                        depth,
                        EXACT,
                        -np.inf,
                        move,
                    )
                    return -np.inf
                self.set_stone(move[0], move[1], opp)
                eval_value = self.minimax(
                    depth - 1, alpha, beta, True, player, start_time, time_limit
                )
                self.remove_stone(move[0], move[1])
                if eval_value < min_eval:
                    min_eval = eval_value
                    best_move_here = move
                beta = min(beta, eval_value)
                if beta <= alpha:
                    if move not in self.killer_moves[depth]:
                        if len(self.killer_moves[depth]) >= 2:
                            self.killer_moves[depth].pop(0)
                        self.killer_moves[depth].append(move)
                    self.history_table[move[0], move[1]] += depth * depth
                    break

            if min_eval >= beta:
                tt_flag = LOWERBOUND
            elif min_eval <= orig_alpha:
                tt_flag = UPPERBOUND
            else:
                tt_flag = EXACT
            existing = self.transposition_table.get(self.zobrist_hash)
            if existing is None or depth >= existing[0]:
                self.transposition_table[self.zobrist_hash] = (
                    depth,
                    tt_flag,
                    min_eval,
                    best_move_here,
                )
            return min_eval

    def quick_evaluate(self, move, player):
        """Fast move evaluation using score boards."""
        x, y = move
        if player == self.player_1:
            return (
                self.score_board_p1[x, y]
                + self.defense_rate * self.score_board_p2[x, y]
            )
        else:
            return (
                self.score_board_p2[x, y]
                + self.defense_rate * self.score_board_p1[x, y]
            )

    def get_best_move(self, player, time_limit=5.0):
        """
        Choose the best move using Iterative Deepening and Minimax with Alpha-Beta pruning.
        """
        best_move = None
        best_score = -np.inf
        start_time = time.time()

        # Clear per-search heuristics (keep TT across moves for reuse)
        if len(self.transposition_table) > TT_MAX_SIZE:
            self.transposition_table.clear()
        self.history_table.fill(0)
        for i in range(len(self.killer_moves)):
            self.killer_moves[i] = []

        # Generate and order candidate moves
        candidate_moves = self.generate_candidate_moves()

        # Check for immediate win
        for move in candidate_moves:
            if self.check_win(move[0], move[1], player):
                return move

        # Initial ordering using score boards
        candidate_moves = sorted(
            candidate_moves,
            key=lambda m: self.quick_evaluate(m, player),
            reverse=True,
        )
        # Limit root candidates
        candidate_moves = candidate_moves[:20]

        # Iterative Deepening
        current_depth = 1
        while current_depth <= self.depth:
            if time.time() - start_time > time_limit:
                break

            depth_best_move = None
            depth_best_score = -np.inf

            for move in candidate_moves:
                if time.time() - start_time > time_limit:
                    break
                self.set_stone(move[0], move[1], player)
                score = self.minimax(
                    current_depth - 1,
                    -np.inf,
                    np.inf,
                    False,
                    player,
                    start_time,
                    time_limit,
                )
                self.remove_stone(move[0], move[1])
                if score > depth_best_score:
                    depth_best_score = score
                    depth_best_move = move

            # Only update best if we completed this depth (or found something)
            if depth_best_move is not None:
                best_score = depth_best_score
                best_move = depth_best_move
                # Principal variation: search best move first at next depth
                if depth_best_move in candidate_moves:
                    candidate_moves.remove(depth_best_move)
                    candidate_moves.insert(0, depth_best_move)

            current_depth += 1

        return best_move
