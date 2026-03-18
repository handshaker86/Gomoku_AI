# Gomoku

A Gomoku (Five-in-a-Row) game with AI opponent, built with Python and Tkinter.

## Features

### Game Modes
- **vs AI** — Play against the computer with three difficulty levels (Easy / Medium / Hard) or custom settings
- **PvP** — Local two-player mode

### AI Engine
- Minimax search with alpha-beta pruning
- Zobrist hashing and transposition table to avoid redundant computation
- Incremental evaluation — score boards updated locally per move, not recomputed globally
- Killer move and history heuristics for better move ordering
- Iterative deepening with 2-second time limit
- Easy mode uses a fast greedy evaluator; Medium/Hard use full minimax search

### Difficulty Presets

| Level  | Depth | Defense Rate |
|--------|-------|-------------|
| Easy   | 3     | 1.5         |
| Medium | 5     | 2.0         |
| Hard   | 7     | 2.5         |

Custom mode allows selecting depth (3–8) and defense rate (1.0–4.0) via dropdown.

### GUI
- Wood-textured 15×15 board with star point markers
- Top info bar showing player names, stone colors, and live timers
- Last move highlighted with a red dot
- Win/draw result displayed as an overlay on the board
- Bottom buttons: **Undo**, **Restart** (same settings), **Home** (back to settings)
- AI runs in a background thread — UI stays responsive during computation

## Requirements

- Python 3
- `numpy`
- `tkinter` (included with most Python installations)

## Usage

```
python -m gomoku.main
```
