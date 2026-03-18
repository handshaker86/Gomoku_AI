import tkinter as tk
import threading
from gomoku.player import Player
from gomoku.eval_func_board import Eval_func_board
from gomoku.minimax_board import Minimax_board


class GomokuGame:
    def __init__(self, root, board):
        self.root = root
        self.board = board
        self.canvas = tk.Canvas(root, width=600, height=600, bg="beige")
        self.canvas.pack()

        # Bind mouse wheel events (cross-platform)
        self.canvas.bind("<Button-1>", self.handle_click)
        self.canvas.bind(
            "<MouseWheel>", self.handle_mousewheel
        )  # For Windows and macOS
        self.canvas.bind("<Button-4>", self.handle_mousewheel)  # For Linux: scroll up
        self.canvas.bind("<Button-5>", self.handle_mousewheel)  # For Linux: scroll down

        self.cell_size = 600 // board.size
        self.current_player = self.board.player_1

        # Tuple format: (x, y, player, oval_id)
        self.move_history = []
        self.ai_thinking = False

        self.draw_board()

        if self.current_player.is_ai:
            self.root.after(500, self.ai_move)

    def draw_board(self):
        """Draw the board grid"""
        for i in range(self.board.size):
            # Horizontal line
            self.canvas.create_line(
                self.cell_size / 2,
                (i + 0.5) * self.cell_size,
                600 - self.cell_size / 2,
                (i + 0.5) * self.cell_size,
            )
            # Vertical line
            self.canvas.create_line(
                (i + 0.5) * self.cell_size,
                self.cell_size / 2,
                (i + 0.5) * self.cell_size,
                600 - self.cell_size / 2,
            )

    def handle_click(self, event):
        """Handle player's click on the board"""
        if self.ai_thinking:
            return
        x, y = int(event.x / self.cell_size), int(event.y / self.cell_size)
        if self.board.check_valid(x, y) and self.board.check_available(x, y):
            self.place_stone(x, y)
            if not self.check_game_over(x, y):
                # Switch turn after placing a stone
                self.current_player = self.board.get_opponent(self.current_player)
                self.root.after(100, self.ai_move)

    def handle_mousewheel(self, event):
        """
        Handle mouse wheel events:
          - Scroll up (positive direction) to undo the last move.
          - Scroll down does nothing (can be extended to implement redo functionality).
        """
        direction = 0
        # For Windows/macOS: event.delta positive indicates scrolling up
        if hasattr(event, "delta") and event.delta:
            direction = event.delta
        # For Linux: Button-4 indicates scrolling up, Button-5 indicates scrolling down
        elif hasattr(event, "num"):
            if event.num == 4:
                direction = 1
            elif event.num == 5:
                direction = -1

        if direction < 0:
            self.undo_move()

    def place_stone(self, x, y):
        """Place a stone on the board and draw it"""
        self.board.set_stone(x, y, self.current_player)
        color = "black" if self.current_player == self.board.player_1 else "white"
        oval_id = self.canvas.create_oval(
            x * self.cell_size + 10,
            y * self.cell_size + 10,
            (x + 1) * self.cell_size - 10,
            (y + 1) * self.cell_size - 10,
            fill=color,
        )
        # Record all details of the move
        self.move_history.append((x, y, self.current_player, oval_id))

    def undo_move(self):
        """
        Undo the most recent move: remove the stone from the board and canvas,
        and revert turn back to the player who made the move.
        """
        if self.ai_thinking:
            return
        if not self.move_history:
            print("No move to undo.")
            return

        x, y, player, oval_id = self.move_history.pop()
        self.board.remove_stone(x, y)
        if self.board.difficulty == 1:
            if self.move_history:
                last_x, last_y, last_player, _ = self.move_history[-1]
                self.board.update_score_board(last_x, last_y, last_player)
            else:
                self.board.reset_score_board()
        self.canvas.delete(oval_id)
        # Revert turn back to the player who made the undone move
        self.current_player = player
        print(f"Undid move by {player.name} at ({x}, {y}).")

        # If it's AI's turn, automatically call the AI to make a move
        if self.current_player.is_ai:
            self.root.after(500, self.ai_move)

    def ai_move(self):
        """Let the AI make its move in a background thread (for Minimax)"""
        if not self.current_player.is_ai:
            return
        self.ai_thinking = True
        self.root.title("Gomoku - AI thinking...")

        def compute():
            result = self.board.get_best_move(self.current_player)
            self.root.after(0, lambda: self._apply_ai_move(result))

        if self.board.difficulty == 2:
            threading.Thread(target=compute, daemon=True).start()
        else:
            # Basic AI is fast enough to run on main thread
            result = self.board.get_best_move(self.current_player)
            self._apply_ai_move(result)

    def _apply_ai_move(self, move):
        """Apply the AI's computed move on the main thread"""
        self.ai_thinking = False
        self.root.title("Gomoku")
        if move is None:
            return
        x, y = move
        self.place_stone(x, y)
        if not self.check_game_over(x, y):
            self.current_player = self.board.get_opponent(self.current_player)
            if self.current_player.is_ai:
                self.root.after(100, self.ai_move)

    def check_game_over(self, x, y):
        """Check if the game is over"""
        if self.board.check_win(x, y, self.current_player):
            print(f"{self.current_player.name} wins!")
            return True
        if self.board.check_full():
            print("Draw!")
            return True
        return False


class GameSettings:
    """Used for selecting AI difficulty, player settings, and configuring Minimax parameters"""

    def __init__(self, root):
        self.root = root
        self.root.title("Gomoku Settings")
        # Set window size
        self.root.geometry("550x450")

        self.size = 15
        self.level = tk.IntVar(value=1)
        self.ai_player = tk.IntVar(value=1)

        # Define fonts
        label_font = ("Helvetica", 16)
        option_font = ("Helvetica", 14)
        entry_font = ("Helvetica", 14)
        button_font = ("Helvetica", 16)

        # AI difficulty selection (centered)
        tk.Label(root, text="Select AI Difficulty:", font=label_font).pack(pady=5)
        tk.Radiobutton(
            root, text="Basic AI", variable=self.level, value=1, font=option_font
        ).pack(pady=2)
        tk.Radiobutton(
            root, text="Advanced AI", variable=self.level, value=2, font=option_font
        ).pack(pady=2)

        # Selection of which player the AI will play as (centered)
        tk.Label(
            root, text="Select which player the AI will play as:", font=label_font
        ).pack(pady=5)
        tk.Radiobutton(
            root, text="Black", variable=self.ai_player, value=1, font=option_font
        ).pack(pady=2)
        tk.Radiobutton(
            root, text="White", variable=self.ai_player, value=2, font=option_font
        ).pack(pady=2)

        # New: Input for Minimax depth (only effective for Advanced AI)
        tk.Label(root, text="Minimax Depth (Advanced AI only):", font=label_font).pack(
            pady=5
        )
        self.depth_entry = tk.Entry(root, font=entry_font, justify="center")
        self.depth_entry.insert(0, "5")  # Default value is 5
        self.depth_entry.pack(pady=2)

        # New: Defense Rate input
        tk.Label(root, text="Defense Rate:", font=label_font).pack(pady=5)
        self.defense_rate_entry = tk.Entry(root, font=entry_font, justify="center")
        # Default value is set to Advanced AI's default 0.5 (adjustable for Basic AI as needed)
        self.defense_rate_entry.insert(0, "2.0")
        self.defense_rate_entry.pack(pady=2)

        # Start game button
        tk.Button(
            root, text="Start Game", command=self.start_game, font=button_font
        ).pack(pady=20)

    def start_game(self):
        """Initialize the board and start the game"""
        # Try to parse defense_rate from the input field
        try:
            defense_rate = float(self.defense_rate_entry.get())
        except ValueError:
            defense_rate = 2.0  # Use default value if parsing fails

        # Create Player objects based on the selected AI player
        player_1 = Player("Player 1", 1, is_ai=self.ai_player.get() == 1)
        player_2 = Player("Player 2", -1, is_ai=self.ai_player.get() == 2)

        if self.level.get() == 1:
            # Basic AI uses only the defense_rate parameter (previously default was 5, now provided by user)
            board = Eval_func_board(
                self.size, player_1, player_2, defense_rate=defense_rate
            )
        else:
            # Advanced AI requires both depth and defense_rate parameters
            try:
                depth = int(self.depth_entry.get())
            except ValueError:
                depth = 5  # Use default value if parsing fails
            board = Minimax_board(
                self.size, player_1, player_2, depth=depth, defense_rate=defense_rate
            )

        # Destroy the settings window and launch the main game window
        self.root.destroy()
        game_root = tk.Tk()
        GomokuGame(game_root, board)
        game_root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    GameSettings(root)
    root.mainloop()
