import tkinter as tk
import threading
import time
from gomoku.player import Player
from gomoku.eval_func_board import Eval_func_board
from gomoku.minimax_board import Minimax_board
from gomoku.online_board import Online_board
from gomoku.network_client import NetworkClient

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
    player_color = config.get("player_color", "Black")
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
        ai_is_p1 = player_color != "Black"  # AI is p1 (black) when player chose white
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
    def __init__(self, root, board, settings_config, online_client=None, my_color=None):
        self.root = root
        self.root.title("Gomoku")
        self.root.configure(bg=BG_COLOR)
        self.root.resizable(False, False)
        self.board = board
        self.settings_config = settings_config
        self.online_client = online_client
        self.my_color = my_color

        self.cell_size = 600 // board.size
        self.current_player = self.board.player_1
        self.move_history = []
        self.ai_thinking = False
        self.game_over = False
        self.last_move_marker = None

        # Online mode: identify local player
        if self.online_client:
            if my_color == "black":
                self.my_player = self.board.player_1
            else:
                self.my_player = self.board.player_2
        else:
            self.my_player = None

        # Timer state
        self.time_limit = settings_config.get("time_limit", 0)  # 0 = no limit, >0 = seconds per player
        if self.time_limit > 0:
            # Countdown mode: remaining time per player
            self.player_time = {self.board.player_1: float(self.time_limit),
                                self.board.player_2: float(self.time_limit)}
        else:
            # Count-up mode: elapsed time per player
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

        if self.online_client:
            self.online_client.on_message = self._on_network_message
            self.online_client.start_polling(self.root)
        elif self.current_player.is_ai:
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
        initial_time = self._format_time(self.player_time[p1])
        self.p1_time_label = tk.Label(
            self.p1_frame, text=initial_time, font=("Courier", 16, "bold"),
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
            self.p2_frame, text=initial_time, font=("Courier", 16, "bold"),
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

        # Online mode: disable undo and restart
        if self.online_client:
            self.undo_btn.config(state=tk.DISABLED)
            self.restart_btn.config(state=tk.DISABLED)

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
        seconds = max(0, seconds)
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def _get_display_time(self, player):
        """Get the current display time for a player."""
        t = self.player_time[player]
        if self.turn_start_time is not None and self.current_player == player:
            elapsed = time.time() - self.turn_start_time
            if self.time_limit > 0:
                t -= elapsed  # countdown
            else:
                t += elapsed  # count-up
        return t

    def _start_turn(self):
        self.turn_start_time = time.time()
        self._update_timer()

    def _stop_turn(self):
        if self.turn_start_time is not None:
            elapsed = time.time() - self.turn_start_time
            if self.time_limit > 0:
                self.player_time[self.current_player] -= elapsed
            else:
                self.player_time[self.current_player] += elapsed
            self.turn_start_time = None
        if self.timer_after_id is not None:
            self.root.after_cancel(self.timer_after_id)
            self.timer_after_id = None
        self._refresh_time_display()

    def _update_timer(self):
        if self.game_over:
            return
        # Check timeout in countdown mode (skip during AI thinking — check after AI finishes)
        if self.time_limit > 0 and self.turn_start_time is not None and not self.ai_thinking:
            remaining = self._get_display_time(self.current_player)
            if remaining <= 0:
                self._handle_timeout()
                return
        self._refresh_time_display()
        self.timer_after_id = self.root.after(200, self._update_timer)

    def _handle_timeout(self):
        """Current player ran out of time."""
        self.player_time[self.current_player] = 0.0
        self.turn_start_time = None
        if self.timer_after_id is not None:
            self.root.after_cancel(self.timer_after_id)
            self.timer_after_id = None
        self.game_over = True
        self._refresh_time_display()
        winner = self.board.get_opponent(self.current_player)
        self._show_result(f"{self.player_display[winner]} Wins!\n(Time Out)")

    def _refresh_time_display(self):
        p1 = self.board.player_1
        p2 = self.board.player_2
        t1 = self._get_display_time(p1)
        t2 = self._get_display_time(p2)
        self.p1_time_label.config(text=self._format_time(t1))
        self.p2_time_label.config(text=self._format_time(t2))
        # Color the time label red when low (<30s) in countdown mode
        if self.time_limit > 0:
            self.p1_time_label.config(fg="#D32F2F" if t1 < 30 else ACCENT_GREEN)
            self.p2_time_label.config(fg="#D32F2F" if t2 < 30 else ACCENT_GREEN)
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
        if self.online_client and self.current_player != self.my_player:
            return  # Not my turn in online mode
        if not self.online_client and self.current_player.is_ai:
            return
        cs = self.cell_size
        half = cs // 2
        x = round((event.x - half) / cs)
        y = round((event.y - half) / cs)
        if self.board.check_valid(x, y) and self.board.check_available(x, y):
            if self.online_client:
                # Send move to server; wait for server echo to place stone
                self.online_client.send({"type": "move", "x": x, "y": y})
            else:
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

        if self.board.difficulty == 2:
            # Determine AI search time budget for minimax
            ai_time = 2.0
            if self.time_limit > 0:
                remaining = self._get_display_time(self.current_player)
                ai_time = min(ai_time, max(0.5, remaining - 0.5))

            def compute():
                result = self.board.get_best_move(self.current_player, time_limit=ai_time)
                self.root.after(0, lambda: self._apply_ai_move(result))

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
        # Countdown mode: check if AI ran out of time during thinking
        if self.time_limit > 0:
            remaining = self._get_display_time(self.current_player)
            if remaining <= 0:
                self._handle_timeout()
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

    # --- Online message handling ---

    def _on_network_message(self, msg):
        msg_type = msg.get("type")
        if msg_type == "move":
            color = msg.get("color")
            x, y = msg["x"], msg["y"]
            if color == "black":
                self.current_player = self.board.player_1
            else:
                self.current_player = self.board.player_2
            self._stop_turn()
            # Sync remaining time from server if provided
            if "black_time" in msg and self.time_limit > 0:
                self.player_time[self.board.player_1] = msg["black_time"]
                self.player_time[self.board.player_2] = msg["white_time"]
            self.place_stone(x, y)
            if not self.check_game_over(x, y):
                self.current_player = self.board.get_opponent(self.current_player)
                self._start_turn()
        elif msg_type == "game_over":
            result = msg.get("result", "")
            if not self.game_over:
                self.game_over = True
                self._stop_turn()
                if "black_time" in msg and self.time_limit > 0:
                    self.player_time[self.board.player_1] = msg["black_time"]
                    self.player_time[self.board.player_2] = msg["white_time"]
                    self._refresh_time_display()
                if "timeout" in result:
                    # e.g. "black_timeout" or "white_timeout"
                    loser_color = result.split("_")[0]
                    winner = self.board.player_2 if loser_color == "black" else self.board.player_1
                    self._show_result(f"{self.player_display[winner]} Wins!\n(Time Out)")
                elif "wins" in result:
                    winner_color = result.split("_")[0]
                    winner = self.board.player_1 if winner_color == "black" else self.board.player_2
                    self._show_result(f"{self.player_display[winner]} Wins!")
                elif result == "draw":
                    self._show_result("Draw!")
        elif msg_type == "opponent_disconnected":
            self.game_over = True
            self._stop_turn()
            self._show_result("Opponent Disconnected")
        elif msg_type == "error":
            pass

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
        if self.online_client:
            self.online_client.send({"type": "leave"})
            self.online_client.disconnect()
            self.online_client = None

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


class OnlineLobby:
    """Online lobby window for creating/joining rooms."""

    def __init__(self, root, server_url, player_name, time_limit=0):
        self.root = root
        self.root.title("Gomoku - Online Lobby")
        self.root.configure(bg=BG_COLOR)
        self.root.resizable(False, False)
        self.server_url = server_url
        self.player_name = player_name
        self.time_limit = time_limit
        self.client = None

        w, h = 420, 400
        self.root.geometry(f"{w}x{h}")
        self.root.update_idletasks()
        sx = (self.root.winfo_screenwidth() - w) // 2
        sy = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"+{sx}+{sy}")

        # Title
        tk.Label(root, text="Online Lobby", font=("Helvetica", 24, "bold"),
                 bg=BG_COLOR, fg=DARK_TEXT).pack(pady=(20, 5))
        tk.Label(root, text=f"Server: {server_url}", font=("Helvetica", 10),
                 bg=BG_COLOR, fg="#999").pack(pady=(0, 10))

        lbl_font = ("Helvetica", 12)
        btn_font = ("Helvetica", 13, "bold")

        # Create Room section
        create_frame = tk.LabelFrame(root, text="  Create Room  ",
                                     font=("Helvetica", 12, "bold"),
                                     bg=BG_COLOR, fg=DARK_TEXT, padx=15, pady=10)
        create_frame.pack(fill=tk.X, padx=30, pady=5)

        self.create_btn = tk.Button(
            create_frame, text="Create Room", font=btn_font,
            bg=ACCENT_GREEN, fg=BUTTON_FG, activebackground=ACCENT_GREEN_HOVER,
            activeforeground=BUTTON_FG, relief=tk.FLAT, padx=20, pady=6,
            command=self._create_room,
        )
        self.create_btn.pack()

        self.room_code_label = tk.Label(create_frame, text="", font=("Courier", 20, "bold"),
                                        bg=BG_COLOR, fg=ACCENT_GREEN)
        self.room_code_label.pack(pady=(5, 0))

        # Join Room section
        join_frame = tk.LabelFrame(root, text="  Join Room  ",
                                   font=("Helvetica", 12, "bold"),
                                   bg=BG_COLOR, fg=DARK_TEXT, padx=15, pady=10)
        join_frame.pack(fill=tk.X, padx=30, pady=5)

        code_row = tk.Frame(join_frame, bg=BG_COLOR)
        code_row.pack(fill=tk.X, pady=3)
        tk.Label(code_row, text="Room Code:", font=lbl_font, bg=BG_COLOR, fg=DARK_TEXT).pack(side=tk.LEFT)
        self.code_entry = tk.Entry(code_row, font=("Courier", 14), width=6,
                                   justify=tk.CENTER)
        self.code_entry.pack(side=tk.RIGHT, padx=5)

        self.join_btn = tk.Button(
            join_frame, text="Join Room", font=btn_font,
            bg=ACCENT_GREEN, fg=BUTTON_FG, activebackground=ACCENT_GREEN_HOVER,
            activeforeground=BUTTON_FG, relief=tk.FLAT, padx=20, pady=6,
            command=self._join_room,
        )
        self.join_btn.pack(pady=(5, 0))

        # Status
        self.status_label = tk.Label(root, text="", font=("Helvetica", 11),
                                     bg=BG_COLOR, fg="#D32F2F", wraplength=350)
        self.status_label.pack(pady=8)

        # Back button
        tk.Button(
            root, text="Back", font=btn_font,
            bg="#999", fg=BUTTON_FG, activebackground="#777",
            activeforeground=BUTTON_FG, relief=tk.FLAT, padx=20, pady=6,
            command=self._go_back,
        ).pack(pady=5)

    def _set_status(self, text, color="#D32F2F"):
        self.status_label.config(text=text, fg=color)

    def _connect_and_send(self, after_connect_msg):
        """Connect to server, then send a message once connected."""
        self._set_status("Connecting...", "#999")
        self._pending_msg = after_connect_msg

        self.client = NetworkClient(self.server_url, self._on_message)
        self.client.connect(
            on_connected=self._on_connected,
            on_error=self._on_connect_error,
        )
        self.client.start_polling(self.root)

    def _on_connected(self):
        self._set_status("Connected. Waiting...", ACCENT_GREEN)
        if self._pending_msg:
            self.client.send(self._pending_msg)
            self._pending_msg = None

    def _on_connect_error(self, err):
        self._set_status(f"Connection failed: {err}")
        self.client = None

    def _create_room(self):
        if self.client:
            return
        self.create_btn.config(state=tk.DISABLED)
        self.join_btn.config(state=tk.DISABLED)
        self._connect_and_send({
            "type": "create_room",
            "player_name": self.player_name,
            "time_limit": self.time_limit,
        })

    def _join_room(self):
        if self.client:
            return
        code = self.code_entry.get().strip().upper()
        if not code:
            self._set_status("Please enter a room code")
            return
        self.create_btn.config(state=tk.DISABLED)
        self.join_btn.config(state=tk.DISABLED)
        self._connect_and_send({
            "type": "join_room",
            "room_code": code,
            "player_name": self.player_name,
        })

    def _on_message(self, msg):
        msg_type = msg.get("type")
        if msg_type == "room_created":
            code = msg["room_code"]
            self.room_code_label.config(text=code)
            self._set_status("Room created! Waiting for opponent...", ACCENT_GREEN)
        elif msg_type == "game_start":
            self._start_game(msg)
        elif msg_type == "error":
            self._set_status(msg.get("message", "Error"))
            self.create_btn.config(state=tk.NORMAL)
            self.join_btn.config(state=tk.NORMAL)
            if self.client:
                self.client.disconnect()
                self.client = None

    def _start_game(self, msg):
        my_color = msg["your_color"]
        opponent_name = msg["opponent_name"]
        time_limit = msg.get("time_limit", self.time_limit)

        if my_color == "black":
            p1 = Player(self.player_name, 1, is_ai=False)
            p2 = Player(opponent_name, -1, is_ai=False)
        else:
            p1 = Player(opponent_name, 1, is_ai=False)
            p2 = Player(self.player_name, -1, is_ai=False)

        board = Online_board(15, p1, p2)
        client = self.client
        # Stop polling on lobby root before destroying
        client.stop_polling()

        self.root.destroy()
        game_root = tk.Tk()
        config = {"mode": "Online", "time_limit": time_limit}
        GomokuGame(game_root, board, config, online_client=client, my_color=my_color)
        game_root.mainloop()

    def _go_back(self):
        if self.client:
            self.client.send({"type": "leave"})
            self.client.disconnect()
            self.client = None
        self.root.destroy()
        new_root = tk.Tk()
        GameSettings(new_root)
        new_root.mainloop()


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
        mode_row.pack(fill=tk.X, pady=3)
        tk.Label(mode_row, text="Mode:", font=lbl_font, bg=BG_COLOR, fg=DARK_TEXT).pack(side=tk.LEFT)
        self.game_mode = tk.StringVar(value="vs AI")
        mode_menu = tk.OptionMenu(mode_row, self.game_mode, "vs AI", "PvP", "Online",
                                  command=self._on_mode_change)
        mode_menu.config(font=opt_font, bg=BG_COLOR, highlightthickness=0, width=10)
        mode_menu["menu"].config(font=opt_font)
        mode_menu.pack(side=tk.RIGHT)

        # Time Limit (always visible, for all modes)
        time_row = tk.Frame(mode_frame, bg=BG_COLOR)
        time_row.pack(fill=tk.X, pady=3)
        tk.Label(time_row, text="Time Limit:", font=lbl_font, bg=BG_COLOR, fg=DARK_TEXT).pack(side=tk.LEFT)
        self.time_limit_var = tk.StringVar(value="No Limit")
        time_menu = tk.OptionMenu(time_row, self.time_limit_var,
                                  "No Limit", "1 min", "3 min", "5 min", "10 min", "15 min", "30 min")
        time_menu.config(font=opt_font, bg=BG_COLOR, highlightthickness=0, width=10)
        time_menu["menu"].config(font=opt_font)
        time_menu.pack(side=tk.RIGHT)

        # Your Color (in mode frame, not AI settings)
        self.color_row = tk.Frame(mode_frame, bg=BG_COLOR)
        self.color_row.pack(fill=tk.X, pady=3)
        tk.Label(self.color_row, text="Your Color:", font=lbl_font, bg=BG_COLOR, fg=DARK_TEXT).pack(side=tk.LEFT)
        self.player_color = tk.StringVar(value="Black")
        color_menu = tk.OptionMenu(self.color_row, self.player_color, "Black", "White")
        color_menu.config(font=opt_font, bg=BG_COLOR, highlightthickness=0, width=10)
        color_menu["menu"].config(font=opt_font)
        color_menu.pack(side=tk.RIGHT)

        # --- AI Settings (hidden when PvP) ---
        self.ai_frame = tk.LabelFrame(root, text="  AI Settings  ",
                                      font=("Helvetica", 12, "bold"),
                                      bg=BG_COLOR, fg=DARK_TEXT, padx=15, pady=8)
        self.ai_frame.pack(fill=tk.X, padx=30, pady=5)

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

        # --- Online Settings (hidden by default) ---
        self.online_frame = tk.LabelFrame(root, text="  Online Settings  ",
                                          font=("Helvetica", 12, "bold"),
                                          bg=BG_COLOR, fg=DARK_TEXT, padx=15, pady=8)
        # Not packed yet — shown only when Online is selected

        server_row = tk.Frame(self.online_frame, bg=BG_COLOR)
        server_row.pack(fill=tk.X, pady=3)
        tk.Label(server_row, text="Server:", font=lbl_font, bg=BG_COLOR, fg=DARK_TEXT).pack(side=tk.LEFT)
        self.server_var = tk.StringVar(value="ws://localhost:8765")
        server_entry = tk.Entry(server_row, textvariable=self.server_var, font=("Courier", 11), width=22)
        server_entry.pack(side=tk.RIGHT)

        name_row = tk.Frame(self.online_frame, bg=BG_COLOR)
        name_row.pack(fill=tk.X, pady=3)
        tk.Label(name_row, text="Your Name:", font=lbl_font, bg=BG_COLOR, fg=DARK_TEXT).pack(side=tk.LEFT)
        self.name_var = tk.StringVar(value="Player")
        name_entry = tk.Entry(name_row, textvariable=self.name_var, font=opt_font, width=15)
        name_entry.pack(side=tk.RIGHT)

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
        # Hide everything first
        self.color_row.pack_forget()
        self.ai_frame.pack_forget()
        self.custom_frame.pack_forget()
        self.online_frame.pack_forget()
        self.start_btn.pack_forget()

        if value == "vs AI":
            self.color_row.pack(fill=tk.X, pady=3)
            self.ai_frame.pack(fill=tk.X, padx=30, pady=5)
            if self.difficulty.get() == "Custom":
                self.custom_frame.pack(fill=tk.X, padx=30, pady=5)
        elif value == "Online":
            self.online_frame.pack(fill=tk.X, padx=30, pady=5)
            self.start_btn.config(text="Enter Lobby")
        else:  # PvP
            pass

        if value != "Online":
            self.start_btn.config(text="Start Game")
        self.start_btn.pack(pady=20)

    def _on_difficulty_change(self, value):
        if value == "Custom":
            self.start_btn.pack_forget()
            self.custom_frame.pack(fill=tk.X, padx=30, pady=5)
            self.start_btn.pack(pady=20)
        else:
            self.custom_frame.pack_forget()

    def _parse_time_limit(self):
        """Parse time limit string to seconds. Returns 0 for no limit."""
        val = self.time_limit_var.get()
        if val == "No Limit":
            return 0
        # e.g. "5 min" -> 300
        try:
            minutes = int(val.split()[0])
            return minutes * 60
        except (ValueError, IndexError):
            return 0

    def start_game(self):
        mode = self.game_mode.get()
        time_limit = self._parse_time_limit()

        if mode == "Online":
            server_url = self.server_var.get().strip()
            player_name = self.name_var.get().strip() or "Player"
            self.root.destroy()
            lobby_root = tk.Tk()
            OnlineLobby(lobby_root, server_url, player_name, time_limit)
            lobby_root.mainloop()
            return

        config = {
            "mode": mode,
            "difficulty": self.difficulty.get(),
            "player_color": self.player_color.get(),
            "depth": self.depth_var.get(),
            "defense_rate": self.defense_rate_var.get(),
            "time_limit": time_limit,
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
