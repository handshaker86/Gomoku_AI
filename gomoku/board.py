import numpy as np
from gomoku.player import Player


class Base_board:
    DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]

    WIN_SCORE = 99999999
    LIVE_FOUR_SCORE = 5000000
    BLOCKED_FOUR_SCORE = 500000
    LIVE_THREE_SCORE = 100000
    BLOCKED_THREE_SCORE = 5000
    LIVE_TWO_SCORE = 500
    BLOCKED_TWO_SCORE = 100
    LIVE_ONE_SCORE = 10
    BLOCKED_ONE_SCORE = 1
    DEAD_SCORE = 0
    DOUBLE_SHAPE_BONUS = 1000000

    def __init__(self, size, player_1: Player, player_2: Player):
        """
        player_1 and player_2 represent the players' stones.
        """
        self.size = size
        self.board = np.zeros((size, size), dtype=int)
        self.player_1 = player_1
        self.player_2 = player_2

    def get_opponent(self, player):
        if player == self.player_1:
            return self.player_2
        elif player == self.player_2:
            return self.player_1
        else:
            raise ValueError("Invalid player passed to get_opponent")

    def set_stone(self, x, y, player):
        self.board[x, y] = player.stone

    def get_stone(self, x, y):
        return self.board[x, y]

    def remove_stone(self, x, y):
        self.board[x, y] = 0

    def check_available(self, x, y):
        """Check if the cell (x,y) is available for a move."""
        return self.board[x, y] == 0

    def check_valid(self, x, y):
        """Check if the cell (x,y) is within board bounds."""
        return 0 <= x < self.size and 0 <= y < self.size

    def check_full(self):
        """Check if the board is full."""
        return np.all(self.board != 0)

    def check_win(self, x, y, player):
        """Check whether placing a stone at (x,y) makes the player win."""
        for dx, dy in self.DIRECTIONS:
            count = 1  # count the current stone
            for d in [-1, 1]:
                nx, ny = x, y
                for _ in range(4):
                    nx, ny = nx + dx * d, ny + dy * d
                    if (
                        self.check_valid(nx, ny)
                        and self.get_stone(nx, ny) == player.stone
                    ):
                        count += 1
                        if count >= 5:
                            return True
                    else:
                        break
        return False

    def print_board(self):
        """Print the current board state."""
        header = "   " + " ".join(f"{i+1:2}" for i in range(self.size))
        print("Current board:")
        print(header)
        for i in range(self.size):
            row = f"{i+1:2} "
            for j in range(self.size):
                cell = self.board[i, j]
                if cell == self.player_1.stone:
                    row += " X "
                elif cell == self.player_2.stone:
                    row += " O "
                else:
                    row += " . "
            print(row)
        print()

    def print_score(self, player):
        """Print the player's local score board."""
        header = "   " + "  ".join(f"{i+1:2}" for i in range(self.size))
        print(f"{player.name}'s score board:")
        print(header)
        for i in range(self.size):
            row = f"{i+1:2} " + "  ".join(
                f"{player.score_board[i, j]:2}" for j in range(self.size)
            )
            print(row)
        print()

    def count_consecutive(self, x, y, dx, dy, player):
        """Count consecutive stones of player starting from (x,y) in direction (dx,dy)."""
        count = 0
        while self.check_valid(x, y) and self.get_stone(x, y) == player.stone:
            count += 1
            x, y = x + dx, y + dy
        return count

    def check_ends(self, pos_end, neg_end):
        pos_valid = self.check_valid(*pos_end) and self.get_stone(*pos_end) == 0
        neg_valid = self.check_valid(*neg_end) and self.get_stone(*neg_end) == 0
        if pos_valid and neg_valid:
            return "Alive"
        elif not pos_valid and not neg_valid:
            return "Dead"
        else:
            return pos_end if pos_valid else neg_end

    def count_neighbors(self, end, dx, dy, player):
        # Check neighboring stones to better evaluate the shape
        neighbor_num = self.count_consecutive(end[0] + dx, end[1] + dy, dx, dy, player)

        if (
            neighbor_num > 0
            and self.check_ends(
                (
                    end[0] + (neighbor_num + 1) * dx,
                    end[1] + (neighbor_num + 1) * dy,
                ),
                end,
            )
            == "Alive"
        ):
            neighbor_num += 1

        return neighbor_num

    def evaluate_shape(self, x, y, player):
        """
        Evaluate the potential score at position (x, y) for the given player,
        considering both offensive and defensive potential in one direction.
        """
        score = 0
        shape_count = 0  # count the number of offensive shapes evaluated

        for dx, dy in self.DIRECTIONS:
            pos_count = self.count_consecutive(x + dx, y + dy, dx, dy, player)
            neg_count = self.count_consecutive(x - dx, y - dy, -dx, -dy, player)
            count = 1 + pos_count + neg_count

            pos_end = (x + (pos_count + 1) * dx, y + (pos_count + 1) * dy)
            neg_end = (x - (neg_count + 1) * dx, y - (neg_count + 1) * dy)
            shape = self.check_ends(pos_end, neg_end)

            pos_neighbor = self.count_neighbors(pos_end, dx, dy, player)
            neg_neighbor = self.count_neighbors(neg_end, -dx, -dy, player)
            total_neighbor = pos_neighbor + neg_neighbor

            # Adjusted scoring based on both offensive and defensive value
            if count >= 5:
                add_score = self.WIN_SCORE
            elif count == 4:
                if shape == "Alive":
                    add_score = self.LIVE_FOUR_SCORE
                elif shape == "Dead":
                    add_score = self.DEAD_SCORE
                else:
                    add_score = self.BLOCKED_FOUR_SCORE
            elif count == 3:
                if shape == "Alive":
                    if pos_neighbor >= 1 and neg_neighbor >= 1:
                        add_score = self.LIVE_FOUR_SCORE
                    else:
                        add_score = self.LIVE_THREE_SCORE
                elif shape == "Dead":
                    add_score = self.DEAD_SCORE
                else:
                    num_neighbor = self.count_neighbors(shape, dx, dy, player)
                    if num_neighbor == 0:
                        add_score = self.DEAD_SCORE
                    else:
                        add_score = self.BLOCKED_FOUR_SCORE
            elif count == 2:
                if shape == "Alive":
                    if total_neighbor == 0:
                        add_score = self.LIVE_TWO_SCORE
                    elif total_neighbor == 1:
                        add_score = self.BLOCKED_THREE_SCORE
                    elif pos_neighbor == 1 and neg_neighbor == 1:
                        add_score = self.BLOCKED_THREE_SCORE
                    elif pos_neighbor >= 2 and neg_neighbor >= 2:
                        add_score = self.LIVE_FOUR_SCORE
                    else:
                        add_score = self.LIVE_THREE_SCORE
                elif shape == "Dead":
                    add_score = self.DEAD_SCORE
                else:
                    num_neighbor = self.count_neighbors(shape, dx, dy, player)
                    if num_neighbor <= 1:
                        add_score = self.DEAD_SCORE
                    else:
                        add_score = self.BLOCKED_FOUR_SCORE
            elif count == 1:
                if shape == "Alive":
                    if total_neighbor == 0:
                        add_score = self.LIVE_ONE_SCORE
                    elif total_neighbor == 1:
                        add_score = self.BLOCKED_TWO_SCORE
                    elif pos_neighbor >= 3 and neg_neighbor >= 3:
                        add_score = self.LIVE_FOUR_SCORE
                    elif pos_neighbor >= 3 or neg_neighbor >= 3:
                        add_score = self.BLOCKED_FOUR_SCORE
                    else:
                        add_score = self.BLOCKED_THREE_SCORE
                elif shape == "Dead":
                    add_score = self.DEAD_SCORE
                else:
                    num_neighbor = self.count_neighbors(shape, dx, dy, player)
                    if num_neighbor <= 2:
                        add_score = self.DEAD_SCORE
                    else:
                        add_score = self.BLOCKED_FOUR_SCORE

            if add_score >= 50000:
                shape_count += 1

            score += add_score

        if shape_count >= 2:
            score += self.DOUBLE_SHAPE_BONUS

        return score
