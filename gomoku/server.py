"""
Gomoku Online Multiplayer Server

Usage:
    python -m gomoku.server [--host HOST] [--port PORT]

Default: ws://0.0.0.0:8765
"""

import asyncio
import json
import random
import string
import time
import argparse

import numpy as np


BOARD_SIZE = 15
DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]


def check_win(board, x, y, stone):
    """Check if placing stone at (x,y) results in 5-in-a-row."""
    for dx, dy in DIRECTIONS:
        count = 1
        for d in [-1, 1]:
            nx, ny = x, y
            for _ in range(4):
                nx, ny = nx + dx * d, ny + dy * d
                if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[nx, ny] == stone:
                    count += 1
                    if count >= 5:
                        return True
                else:
                    break
    return False


class Room:
    def __init__(self, code, creator_ws, creator_name, time_limit=0):
        self.code = code
        self.board = np.zeros((BOARD_SIZE, BOARD_SIZE), dtype=int)
        self.current_turn = "black"  # black goes first
        self.state = "waiting"  # waiting, playing, finished
        self.time_limit = time_limit  # 0 = no limit, >0 = seconds per player
        self.remaining = {"black": float(time_limit), "white": float(time_limit)}
        self.turn_start = None  # time.time() when current turn started
        self.timeout_task = None  # asyncio task for timeout detection

        # players[color] = (websocket, name)
        self.players = {"black": (creator_ws, creator_name), "white": None}

    def get_color(self, ws):
        for color in ("black", "white"):
            if self.players[color] and self.players[color][0] is ws:
                return color
        return None

    def get_opponent_ws(self, ws):
        color = self.get_color(ws)
        if color is None:
            return None
        opp_color = "white" if color == "black" else "black"
        if self.players[opp_color]:
            return self.players[opp_color][0]
        return None


# Global state
rooms = {}          # code -> Room
ws_to_room = {}     # websocket -> Room


def generate_room_code():
    for _ in range(100):
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        if code not in rooms:
            return code
    return None


async def send_json(ws, data):
    try:
        await ws.send(json.dumps(data))
    except Exception:
        pass


async def handle_create_room(ws, msg):
    player_name = msg.get("player_name", "Player")
    time_limit = msg.get("time_limit", 0)
    code = generate_room_code()
    if code is None:
        await send_json(ws, {"type": "error", "message": "Server full, cannot create room"})
        return

    room = Room(code, ws, player_name, time_limit)
    rooms[code] = room
    ws_to_room[ws] = room
    await send_json(ws, {"type": "room_created", "room_code": code})


async def handle_join_room(ws, msg):
    code = msg.get("room_code", "").upper()
    player_name = msg.get("player_name", "Player")

    if code not in rooms:
        await send_json(ws, {"type": "error", "message": "Room not found"})
        return

    room = rooms[code]
    if room.state != "waiting":
        await send_json(ws, {"type": "error", "message": "Room is full or game already started"})
        return

    room.players["white"] = (ws, player_name)
    room.state = "playing"
    ws_to_room[ws] = room

    black_ws, black_name = room.players["black"]
    white_ws, white_name = room.players["white"]

    # Start the clock for black's first turn
    if room.time_limit > 0:
        room.turn_start = time.time()
        room.timeout_task = asyncio.create_task(_timeout_watcher(room))

    # Notify both players
    await send_json(black_ws, {
        "type": "game_start",
        "your_color": "black",
        "opponent_name": white_name,
        "time_limit": room.time_limit,
    })
    await send_json(white_ws, {
        "type": "game_start",
        "your_color": "white",
        "opponent_name": black_name,
        "time_limit": room.time_limit,
    })


async def handle_move(ws, msg):
    room = ws_to_room.get(ws)
    if not room or room.state != "playing":
        await send_json(ws, {"type": "error", "message": "Not in an active game"})
        return

    color = room.get_color(ws)
    if color != room.current_turn:
        await send_json(ws, {"type": "error", "message": "Not your turn"})
        return

    x, y = msg.get("x"), msg.get("y")
    if x is None or y is None:
        await send_json(ws, {"type": "error", "message": "Invalid move format"})
        return

    if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
        await send_json(ws, {"type": "error", "message": "Move out of bounds"})
        return

    if room.board[x, y] != 0:
        await send_json(ws, {"type": "error", "message": "Cell already occupied"})
        return

    stone = 1 if color == "black" else -1
    room.board[x, y] = stone

    # Deduct time for current player
    if room.time_limit > 0 and room.turn_start is not None:
        elapsed = time.time() - room.turn_start
        room.remaining[color] -= elapsed
        if room.remaining[color] <= 0:
            room.remaining[color] = 0.0
            # Time ran out during this move (edge case)
            await _end_game_timeout(room, color)
            return

    # Broadcast move to both players (include remaining times)
    move_msg = {"type": "move", "x": x, "y": y, "color": color}
    if room.time_limit > 0:
        move_msg["black_time"] = round(room.remaining["black"], 2)
        move_msg["white_time"] = round(room.remaining["white"], 2)
    for c in ("black", "white"):
        if room.players[c]:
            await send_json(room.players[c][0], move_msg)

    # Check win
    if check_win(room.board, x, y, stone):
        await _end_game(room, f"{color}_wins")
        return

    # Check draw
    if np.all(room.board != 0):
        await _end_game(room, "draw")
        return

    # Switch turn and restart clock
    room.current_turn = "white" if color == "black" else "black"
    if room.time_limit > 0:
        room.turn_start = time.time()


async def _end_game(room, result):
    """End the game and notify both players."""
    room.state = "finished"
    if room.timeout_task:
        room.timeout_task.cancel()
        room.timeout_task = None
    msg = {"type": "game_over", "result": result}
    if room.time_limit > 0:
        msg["black_time"] = round(room.remaining["black"], 2)
        msg["white_time"] = round(room.remaining["white"], 2)
    for c in ("black", "white"):
        if room.players[c]:
            await send_json(room.players[c][0], msg)


async def _end_game_timeout(room, timed_out_color):
    """Handle a player running out of time."""
    room.remaining[timed_out_color] = 0.0
    await _end_game(room, f"{timed_out_color}_timeout")


async def _timeout_watcher(room):
    """Background task that checks if the current player's time has expired."""
    try:
        while room.state == "playing" and room.time_limit > 0:
            if room.turn_start is not None:
                elapsed = time.time() - room.turn_start
                remaining = room.remaining[room.current_turn] - elapsed
                if remaining <= 0:
                    # Deduct and end game
                    room.remaining[room.current_turn] -= elapsed
                    room.turn_start = None
                    await _end_game_timeout(room, room.current_turn)
                    return
                # Sleep until timeout or check again in 0.5s
                await asyncio.sleep(min(remaining + 0.05, 0.5))
            else:
                await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass


def cleanup_room(room):
    if room.timeout_task:
        room.timeout_task.cancel()
        room.timeout_task = None
    code = room.code
    if code in rooms:
        del rooms[code]
    for c in ("black", "white"):
        if room.players[c]:
            ws = room.players[c][0]
            ws_to_room.pop(ws, None)


async def handle_disconnect(ws):
    room = ws_to_room.pop(ws, None)
    if room is None:
        return

    opponent_ws = room.get_opponent_ws(ws)
    if opponent_ws:
        await send_json(opponent_ws, {"type": "opponent_disconnected"})

    cleanup_room(room)


async def handle_leave(ws):
    await handle_disconnect(ws)


async def handler(ws):
    try:
        async for raw_msg in ws:
            try:
                msg = json.loads(raw_msg)
            except json.JSONDecodeError:
                await send_json(ws, {"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type")
            if msg_type == "create_room":
                await handle_create_room(ws, msg)
            elif msg_type == "join_room":
                await handle_join_room(ws, msg)
            elif msg_type == "move":
                await handle_move(ws, msg)
            elif msg_type == "leave":
                await handle_leave(ws)
            else:
                await send_json(ws, {"type": "error", "message": f"Unknown message type: {msg_type}"})
    except Exception:
        pass
    finally:
        await handle_disconnect(ws)


async def main(host="0.0.0.0", port=8765):
    try:
        import websockets
    except ImportError:
        print("Error: 'websockets' package is required. Install with: pip install websockets")
        return

    async with websockets.serve(handler, host, port, ping_interval=20, ping_timeout=10):
        print(f"Gomoku server running on ws://{host}:{port}")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gomoku Online Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port))
