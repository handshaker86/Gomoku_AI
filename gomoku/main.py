import tkinter as tk
import threading
import time
from gomoku.player import Player
from gomoku.eval_func_board import Eval_func_board
from gomoku.minimax_board import Minimax_board

# Color scheme
BG_COLOR = "#F5F0E1"
BOARD_COLOR = "#DEB887"
DARK_TEXT = "#3E2723"
ACCENT_GREEN = "#4A7C59"
ACCENT_GREEN_HOVER = "#5A9C6A"
INFO_BG = "#E8E0D0"
BUTTON_FG = "#FFFFFF"

# Difficulty presets: (depth, defense_rate)
DIFFICULTY_PRESETS = {
    "Easy": (3, 1.5),
    "Medium": (5, 2.0),
    "Hard": (7, 2.5),
}


def _create_board_from_config(config, size=15):
    """Create board and players from a settings config dict."""
    mode = config["mode"]
    difficulty = config.get("difficulty", "Medium")
    ai_color = config.get("ai_color", "Black")
    depth_str = config.get("depth", "5")
    defense_rate_str = config.get("defense_rate", "2.0")

    try:
        defense_rate = float(defense_rate_str)
    except ValueError:
        defense_rate = 2.0
    try:
        depth = int(depth_str)
    except ValueError:
        depth = 5

    if mode == "PvP":
        player_1 = Player("P1", 1, is_ai=False)
        player_2 = Player("P2", -1, is_ai=False)
        board = Eval_func_board(size, player_1, player_2, defense_rate=defense_rate)
    else:
        ai_is_p1 = ai_color == "Black"
        player_1 = Player("AI" if ai_is_p1 else "You", 1, is_ai=ai_is_p1)
        player_2 = Player("AI" if not ai_is_p1 else "You", -1, is_ai=not ai_is_p1)

        if difficulty in DIFFICULTY_PRESETS:
            depth, defense_rate = DIFFICULTY_PRESETS[difficulty]

        if difficulty == "Easy":
            board = Eval_func_board(size, player_1, player_2, defense_rate=defense_rate)
        else:
            board = Minimax_board(size, player_1, player_2, depth=depth, defense_rate=defense_rate)

    return board


class GomokuGame:
    def __init__(self, root, board, settings_config):
        self.root = root
        self.root.title("Gomoku")
        self.root.configure(bg=BG_COLOR)
        self.root.resizable(False, False)
        self.board = board
        self.settings_config = settings_config

        self.cell_size = 600 // board.size
        self.current_player = self.board.player_1
        self.move_history = []
        self.ai_thinking = False
        self.game_over = False
        self.last_move_marker = None

        # Timer state
        self.player_time = {self.board.player_1: 0.0, self.board.player_2: 0.0}
        self.turn_start_time = None
        self.timer_after_id = None

        # Player display info
        p1 = self.board.player_1
        p2 = self.board.player_2
        self.player_display = {
            p1: f"Black({p1.name})",
            p2: f"White({p2.name})",
        }
        self.player_symbol = {p1: "\u25CF", p2: "\u25CB"}  # ● ○

        self._build_ui()
        self._start_turn()

        if self.current_player.is_ai:
            self.root.after(300, self.ai_move)

    def _build_ui(self):
        # --- Top info bar ---
        self.top_frame = tk.Frame(self.root, bg=INFO_BG, pady=8)
        self.top_frame.pack(fill=tk.X)

        p1 = self.board.player_1
        p2 = self.board.player_2

        # Left: player 1 (black)
        self.p1_frame = tk.Frame(self.top_frame, bg=INFO_BG)
        self.p1_frame.pack(side=tk.LEFT, expand=True)
        self.p1_label = tk.Label(
            self.p1_frame,
            text=f" {self.player_symbol[p1]}  {self.player_display[p1]}",
            font=("Helvetica", 14, "bold"),
            bg=INFO_BG, fg=DARK_TEXT,
        )
        self.p1_label.pack()
        self.p1_time_label = tk.Label(
            self.p1_frame, text="00:00", font=("Courier", 16, "bold"),
            bg=INFO_BG, fg=ACCENT_GREEN,
        )
        self.p1_time_label.pack()

        # Center separator
        tk.Label(self.top_frame, text="vs", font=("Helvetica", 12),
                 bg=INFO_BG, fg="#999").pack(side=tk.LEFT, padx=10)

        # Right: player 2 (white)
        self.p2_frame = tk.Frame(self.top_frame, bg=INFO_BG)
        self.p2_frame.pack(side=tk.LEFT, expand=True)
        self.p2_label = tk.Label(
            self.p2_frame,
            text=f" {self.player_symbol[p2]}  {self.player_display[p2]}",
            font=("Helvetica", 14, "bold"),
            bg=INFO_BG, fg=DARK_TEXT,
        )
        self.p2_label.pack()
        self.p2_time_label = tk.Label(
            self.p2_frame, text="00:00", font=("Courier", 16, "bold"),
            bg=INFO_BG, fg=ACCENT_GREEN,
        )
        self.p2_time_label.pack()

        # --- Canvas (board) ---
        self.canvas = tk.Canvas(self.root, width=600, height=600, bg=BOARD_COLOR,
                                highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.handle_click)

        self.draw_board()

        # --- Bottom button bar ---
        self.bottom_frame = tk.Frame(self.root, bg=BG_COLOR, pady=10)
        self.bottom_frame.pack(fill=tk.X)

        btn_font = ("Helvetica", 13, "bold")
        self.undo_btn = tk.Button(
            self.bottom_frame, text="Undo", font=btn_font,
            bg=ACCENT_GREEN, fg=BUTTON_FG, activebackground=ACCENT_GREEN_HOVER,
            activeforeground=BUTTON_FG, relief=tk.FLAT, padx=16, pady=6,
            command=self.undo_move,
        )
        self.undo_btn.pack(side=tk.LEFT, expand=True)

        self.restart_btn = tk.Button(
            self.bottom_frame, text="Restart", font=btn_font,
            bg=ACCENT_GREEN, fg=BUTTON_FG, activebackground=ACCENT_GREEN_HOVER,
            activeforeground=BUTTON_FG, relief=tk.FLAT, padx=16, pady=6,
            command=self._restart_same_settings,
        )
        self.restart_btn.pack(side=tk.LEFT, expand=True)

        self.home_btn = tk.Button(
            self.bottom_frame, text="Home", font=btn_font,
            bg=ACCENT_GREEN, fg=BUTTON_FG, activebackground=ACCENT_GREEN_HOVER,
            activeforeground=BUTTON_FG, relief=tk.FLAT, padx=16, pady=6,
            command=self._go_home,
        )
        self.home_btn.pack(side=tk.LEFT, expand=True)

    def draw_board(self):
        cs = self.cell_size
        half = cs // 2
        for i in range(self.board.size):
            self.canvas.create_line(half, half + i * cs, half + (self.board.size - 1) * cs, half + i * cs, fill="#5D4037")
            self.canvas.create_line(half + i * cs, half, half + i * cs, half + (self.board.size - 1) * cs, fill="#5D4037")
        if self.board.size == 15:
            star_points = [(3, 3), (3, 11), (11, 3), (11, 11), (7, 7)]
            r = 4
            for sx, sy in star_points:
                cx, cy = half + sx * cs, half + sy * cs
                self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#5D4037", outline="")

    # --- Timer ---

    def _format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def _start_turn(self):
        self.turn_start_time = time.time()
        self._update_timer()

    def _stop_turn(self):
        if self.turn_start_time is not None:
            elapsed = time.time() - self.turn_start_time
            self.player_time[self.current_player] += elapsed
            self.turn_start_time = None
        if self.timer_after_id is not None:
            self.root.after_cancel(self.timer_after_id)
            self.timer_after_id = None
        self._refresh_time_display()

    def _update_timer(self):
        if self.game_over:
            return
        self._refresh_time_display()
        self.timer_after_id = self.root.after(200, self._update_timer)

    def _refresh_time_display(self):
        p1 = self.board.player_1
        p2 = self.board.player_2
        t1 = self.player_time[p1]
        t2 = self.player_time[p2]
        if self.turn_start_time is not None:
            elapsed = time.time() - self.turn_start_time
            if self.current_player == p1:
                t1 += elapsed
            else:
                t2 += elapsed
        self.p1_time_label.config(text=self._format_time(t1))
        self.p2_time_label.config(text=self._format_time(t2))
        if not self.game_over:
            if self.current_player == p1:
                self.p1_label.config(fg="#D32F2F")
                self.p2_label.config(fg=DARK_TEXT)
            else:
                self.p1_label.config(fg=DARK_TEXT)
                self.p2_label.config(fg="#D32F2F")

    # --- Game actions ---

    def handle_click(self, event):
        if self.ai_thinking or self.game_over:
            return
        if self.current_player.is_ai:
            return
        cs = self.cell_size
        half = cs // 2
        x = round((event.x - half) / cs)
        y = round((event.y - half) / cs)
        if self.board.check_valid(x, y) and self.board.check_available(x, y):
            self._stop_turn()
            self.place_stone(x, y)
            if not self.check_game_over(x, y):
                self.current_player = self.board.get_opponent(self.current_player)
                self._start_turn()
                if self.current_player.is_ai:
                    self.root.after(100, self.ai_move)

    def place_stone(self, x, y):
        self.board.set_stone(x, y, self.current_player)
        cs = self.cell_size
        half = cs // 2
        margin = 3
        cx, cy = half + x * cs, half + y * cs
        r = cs // 2 - margin
        if self.current_player == self.board.player_1:
            fill, outline = "#111111", "#333333"
        else:
            fill, outline = "#FAFAFA", "#888888"
        oval_id = self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill=fill, outline=outline, width=2,
        )
        self.move_history.append((x, y, self.current_player, oval_id))
        self._update_last_move_marker(cx, cy)

    def _update_last_move_marker(self, cx, cy):
        if self.last_move_marker is not None:
            self.canvas.delete(self.last_move_marker)
        r = 4
        self.last_move_marker = self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill="#D32F2F", outline="",
        )

    def undo_move(self):
        if self.ai_thinking or self.game_over:
            return
        if not self.move_history:
            return
        self._stop_turn()
        x, y, player, oval_id = self.move_history.pop()
        self.board.remove_stone(x, y)
        if self.board.difficulty == 1:
            if self.move_history:
                last_x, last_y, last_player, _ = self.move_history[-1]
                self.board.update_score_board(last_x, last_y, last_player)
            else:
                self.board.reset_score_board()
        self.canvas.delete(oval_id)
        self.current_player = player
        if self.last_move_marker is not None:
            self.canvas.delete(self.last_move_marker)
            self.last_move_marker = None
        if self.move_history:
            lx, ly, _, _ = self.move_history[-1]
            cs = self.cell_size
            half = cs // 2
            self._update_last_move_marker(half + lx * cs, half + ly * cs)
        self._start_turn()
        if self.current_player.is_ai:
            self.root.after(300, self.ai_move)

    def ai_move(self):
        if not self.current_player.is_ai or self.game_over:
            return
        self.ai_thinking = True
        self.undo_btn.config(state=tk.DISABLED)
        self.restart_btn.config(state=tk.DISABLED)
        self.home_btn.config(state=tk.DISABLED)

        def compute():
            result = self.board.get_best_move(self.current_player)
            self.root.after(0, lambda: self._apply_ai_move(result))

        if self.board.difficulty == 2:
            threading.Thread(target=compute, daemon=True).start()
        else:
            result = self.board.get_best_move(self.current_player)
            self._apply_ai_move(result)

    def _apply_ai_move(self, move):
        self.ai_thinking = False
        self.undo_btn.config(state=tk.NORMAL)
        self.restart_btn.config(state=tk.NORMAL)
        self.home_btn.config(state=tk.NORMAL)
        if move is None or self.game_over:
            return
        self._stop_turn()
        x, y = move
        self.place_stone(x, y)
        if not self.check_game_over(x, y):
            self.current_player = self.board.get_opponent(self.current_player)
            self._start_turn()
            if self.current_player.is_ai:
                self.root.after(100, self.ai_move)

    def check_game_over(self, x, y):
        if self.board.check_win(x, y, self.current_player):
            self.game_over = True
            self._stop_turn()
            winner = self.player_display[self.current_player]
            self._show_result(f"{winner} Wins!")
            return True
        if self.board.check_full():
            self.game_over = True
            self._stop_turn()
            self._show_result("Draw!")
            return True
        return False

    def _show_result(self, text):
        self.canvas.create_rectangle(0, 0, 600, 600, fill="black", stipple="gray50", outline="")
        self.canvas.create_text(302, 302, text=text, font=("Helvetica", 36, "bold"), fill="#000000")
        self.canvas.create_text(300, 300, text=text, font=("Helvetica", 36, "bold"), fill="#FFD700")
        self.undo_btn.config(state=tk.DISABLED)
        self.p1_label.config(fg=DARK_TEXT)
        self.p2_label.config(fg=DARK_TEXT)

    def _cleanup(self):
        self.game_over = True
        if self.timer_after_id is not None:
            self.root.after_cancel(self.timer_after_id)

    def _go_home(self):
        self._cleanup()
        self.root.destroy()
        new_root = tk.Tk()
        GameSettings(new_root)
        new_root.mainloop()

    def _restart_same_settings(self):
        self._cleanup()
        self.root.destroy()
        board = _create_board_from_config(self.settings_config)
        game_root = tk.Tk()
        GomokuGame(game_root, board, self.settings_config)
        game_root.mainloop()


class GameSettings:
    """Settings window with game mode, difficulty presets, and dropdown menus."""

    def __init__(self, root):
        self.root = root
        self.root.title("Gomoku")
        self.root.configure(bg=BG_COLOR)
        self.root.resizable(False, False)

        w, h = 480, 520
        self.root.geometry(f"{w}x{h}")
        self.root.update_idletasks()
        sx = (self.root.winfo_screenwidth() - w) // 2
        sy = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"+{sx}+{sy}")

        self.size = 15

        # Title
        tk.Label(root, text="Gomoku", font=("Helvetica", 32, "bold"),
                 bg=BG_COLOR, fg=DARK_TEXT).pack(pady=(20, 5))
        tk.Label(root, text="Five in a Row", font=("Helvetica", 12),
                 bg=BG_COLOR, fg="#999").pack(pady=(0, 15))

        lbl_font = ("Helvetica", 12)
        opt_font = ("Helvetica", 12)

        # --- Game Mode ---
        mode_frame = tk.LabelFrame(root, text="  Game Mode  ",
                                   font=("Helvetica", 12, "bold"),
                                   bg=BG_COLOR, fg=DARK_TEXT, padx=15, pady=8)
        mode_frame.pack(fill=tk.X, padx=30, pady=5)

        mode_row = tk.Frame(mode_frame, bg=BG_COLOR)
        mode_row.pack(fill=tk.X)
        tk.Label(mode_row, text="Mode:", font=lbl_font, bg=BG_COLOR, fg=DARK_TEXT).pack(side=tk.LEFT)
        self.game_mode = tk.StringVar(value="vs AI")
        mode_menu = tk.OptionMenu(mode_row, self.game_mode, "vs AI", "PvP",
                                  command=self._on_mode_change)
        mode_menu.config(font=opt_font, bg=BG_COLOR, highlightthickness=0, width=10)
        mode_menu["menu"].config(font=opt_font)
        mode_menu.pack(side=tk.RIGHT)

        # --- AI Settings (hidden when PvP) ---
        self.ai_frame = tk.LabelFrame(root, text="  AI Settings  ",
                                      font=("Helvetica", 12, "bold"),
                                      bg=BG_COLOR, fg=DARK_TEXT, padx=15, pady=8)
        self.ai_frame.pack(fill=tk.X, padx=30, pady=5)

        # AI Color
        color_row = tk.Frame(self.ai_frame, bg=BG_COLOR)
        color_row.pack(fill=tk.X, pady=3)
        tk.Label(color_row, text="AI Color:", font=lbl_font, bg=BG_COLOR, fg=DARK_TEXT).pack(side=tk.LEFT)
        self.ai_color = tk.StringVar(value="Black")
        color_menu = tk.OptionMenu(color_row, self.ai_color, "Black", "White")
        color_menu.config(font=opt_font, bg=BG_COLOR, highlightthickness=0, width=10)
        color_menu["menu"].config(font=opt_font)
        color_menu.pack(side=tk.RIGHT)

        # Difficulty
        diff_row = tk.Frame(self.ai_frame, bg=BG_COLOR)
        diff_row.pack(fill=tk.X, pady=3)
        tk.Label(diff_row, text="Difficulty:", font=lbl_font, bg=BG_COLOR, fg=DARK_TEXT).pack(side=tk.LEFT)
        self.difficulty = tk.StringVar(value="Medium")
        diff_menu = tk.OptionMenu(diff_row, self.difficulty, "Easy", "Medium", "Hard", "Custom",
                                  command=self._on_difficulty_change)
        diff_menu.config(font=opt_font, bg=BG_COLOR, highlightthickness=0, width=10)
        diff_menu["menu"].config(font=opt_font)
        diff_menu.pack(side=tk.RIGHT)

        # --- Custom Parameters (hidden by default) ---
        self.custom_frame = tk.LabelFrame(root, text="  Custom Parameters  ",
                                          font=("Helvetica", 12, "bold"),
                                          bg=BG_COLOR, fg=DARK_TEXT, padx=15, pady=8)
        # Not packed yet — shown only when Custom is selected

        depth_row = tk.Frame(self.custom_frame, bg=BG_COLOR)
        depth_row.pack(fill=tk.X, pady=3)
        tk.Label(depth_row, text="Search Depth:", font=lbl_font, bg=BG_COLOR, fg=DARK_TEXT).pack(side=tk.LEFT)
        self.depth_var = tk.StringVar(value="5")
        depth_menu = tk.OptionMenu(depth_row, self.depth_var, "3", "4", "5", "6", "7", "8")
        depth_menu.config(font=opt_font, bg=BG_COLOR, highlightthickness=0, width=6)
        depth_menu["menu"].config(font=opt_font)
        depth_menu.pack(side=tk.RIGHT)

        dr_row = tk.Frame(self.custom_frame, bg=BG_COLOR)
        dr_row.pack(fill=tk.X, pady=3)
        tk.Label(dr_row, text="Defense Rate:", font=lbl_font, bg=BG_COLOR, fg=DARK_TEXT).pack(side=tk.LEFT)
        self.defense_rate_var = tk.StringVar(value="2.0")
        dr_menu = tk.OptionMenu(dr_row, self.defense_rate_var,
                                "1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0")
        dr_menu.config(font=opt_font, bg=BG_COLOR, highlightthickness=0, width=6)
        dr_menu["menu"].config(font=opt_font)
        dr_menu.pack(side=tk.RIGHT)

        # --- Start button ---
        self.start_btn = tk.Button(
            root, text="Start Game",
            font=("Helvetica", 16, "bold"),
            bg=ACCENT_GREEN, fg=BUTTON_FG,
            activebackground=ACCENT_GREEN_HOVER, activeforeground=BUTTON_FG,
            relief=tk.FLAT, padx=30, pady=10,
            command=self.start_game,
        )
        self.start_btn.pack(pady=20)

    def _on_mode_change(self, value):
        if value == "PvP":
            self.ai_frame.pack_forget()
            self.custom_frame.pack_forget()
        else:
            # Re-pack AI frame after mode frame, before start button
            self.start_btn.pack_forget()
            self.custom_frame.pack_forget()
            self.ai_frame.pack(fill=tk.X, padx=30, pady=5)
            if self.difficulty.get() == "Custom":
                self.custom_frame.pack(fill=tk.X, padx=30, pady=5)
            self.start_btn.pack(pady=20)

    def _on_difficulty_change(self, value):
        if value == "Custom":
            self.start_btn.pack_forget()
            self.custom_frame.pack(fill=tk.X, padx=30, pady=5)
            self.start_btn.pack(pady=20)
        else:
            self.custom_frame.pack_forget()

    def start_game(self):
        config = {
            "mode": self.game_mode.get(),
            "difficulty": self.difficulty.get(),
            "ai_color": self.ai_color.get(),
            "depth": self.depth_var.get(),
            "defense_rate": self.defense_rate_var.get(),
        }

        board = _create_board_from_config(config, self.size)

        self.root.destroy()
        game_root = tk.Tk()
        GomokuGame(game_root, board, config)
        game_root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    GameSettings(root)
    root.mainloop()
