# Gomoku AI Project

This project is a fully functional Gomoku (Five-in-a-Row) game complete with an AI opponent. The following features have been implemented:

---

## Completed Features

### 1. Game Board & Rules
- **15x15 Board:**  
  A 15x15 grid is used to represent the board state, ensuring every move is recorded accurately.
- **Valid Move Logic:**  
  The game checks that every move is valid by ensuring placements occur only on empty cells.
- **Win Detection:**  
  The system automatically detects a win when any player aligns five consecutive stones horizontally, vertically, or diagonally.

---

### 2. Simple Rule-Based AI
- **Evaluation Function:**  
  The AI evaluates board positions to:
  - Immediately block the opponent’s four-in-a-row threats.
  - Prioritize moves that form its own four-in-a-row.
  - Recognize and create advantageous patterns like open threes and double threes.
- **Board Scanning:**  
  The AI scans the board, selects the highest-scoring moves, and reacts accordingly, making it a challenging opponent in human vs. AI gameplay.

---

### 3. Minimax Algorithm with Alpha-Beta Pruning
- **Minimax Implementation:**  
  The AI uses the Minimax algorithm to look several moves ahead, ensuring optimal decision-making by maximizing its advantage and minimizing the opponent's opportunities.
- **Alpha-Beta Pruning:**  
  This optimization cuts off unnecessary branches in the search tree, significantly improving performance while maintaining strong play.
- **Balanced Search Depth:**  
  A search depth of 3-5 layers strikes a balance between strategic foresight and computational efficiency.

---

### 4. Iterative Deepening and Heuristic Search
- **Iterative Deepening:**  
  The AI progressively deepens its search within set time limits, allowing for more refined decision-making as the game progresses.
- **Heuristic Search:**  
  Focus is placed on high-value board areas (e.g., near existing stones) to further refine move selection.
- **Zobrist Hashing:**  
  Implemented for caching board evaluations, this technique avoids redundant calculations and speeds up the overall search process.
- **Dynamic Evaluation Factors:**  
  The evaluation function has been optimized to consider various factors such as board control and opponent threats dynamically.

---

### 5. Graphical User Interface (GUI)
- **Visual Board Rendering:**  
  A complete graphical interface displays the Gomoku board, allowing for an intuitive visual gameplay experience.
- **Mouse Click Input:**  
  Players can make moves by clicking directly on the board.
- **Real-Time Game Status:**  
  The GUI displays live updates including the current turn and win/loss notifications.
- **AI Difficulty Options:**  
  Users can adjust settings such as the AI’s search depth and strategy strength to customize their challenge level.
- **Enhanced UI Interactions:**  
  Features like undo moves, restart buttons, and game history are available to improve the overall user experience.

---

## Installation & Running

### Requirements
- Dependencies:
  - `numpy`
  - `thkinter`

### Running the project
```
python -m gomoku.main
```
