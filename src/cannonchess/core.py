"""Pure game rules for CannonChess.

Coordinates use the requirement convention: (0, 0) is the lower-left cell,
x grows to the right, and y grows upward. The board is stored as grid[y][x].
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import random
from typing import Iterable

EMPTY = 0
PLAYER_A = 1
PLAYER_B = 2
OBSTACLE = 3
DRAW_NO_CAPTURE_TURNS = 50

Coord = tuple[int, int]
DIRECTIONS: tuple[Coord, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))
CAPTURE_AXES: tuple[Coord, ...] = ((1, 0), (0, 1))


@dataclass(frozen=True)
class Move:
    """A one-cell orthogonal move."""

    src: Coord
    dst: Coord


@dataclass(frozen=True)
class GameConfig:
    """Configurable board setup values from the requirements."""

    width: int | None = None
    height: int | None = None
    obstacle_ratio: float = 1 / 20
    seed: int | None = None

    def validate(self) -> None:
        if self.width is not None and not 5 <= self.width <= 10:
            raise ValueError("width must be between 5 and 10")
        if self.height is not None and not 5 <= self.height <= 10:
            raise ValueError("height must be between 5 and 10")
        if self.obstacle_ratio < 0:
            raise ValueError("obstacle_ratio cannot be negative")


@dataclass(frozen=True)
class GameState:
    """Immutable game state for local play, replay, and future AI use."""

    width: int
    height: int
    grid: tuple[tuple[int, ...], ...]
    current_player: int
    no_capture_turns: int = 0
    winner: int | None = None
    draw: bool = False
    move_count: int = 0
    last_captured: tuple[Coord, ...] = field(default_factory=tuple)

    def cell(self, coord: Coord) -> int:
        x, y = coord
        return self.grid[y][x]

    def as_matrix_top_first(self) -> list[list[int]]:
        """Return a display-style matrix with the top row first."""

        return [list(row) for row in reversed(self.grid)]


def create_new_game(config: GameConfig | None = None) -> GameState:
    """Create a random legal starting position."""

    config = config or GameConfig()
    config.validate()
    rng = random.Random(config.seed)
    width = config.width if config.width is not None else rng.randint(5, 10)
    height = config.height if config.height is not None else rng.randint(5, 10)
    grid = [[EMPTY for _ in range(width)] for _ in range(height)]

    obstacle_count = round(width * height * config.obstacle_ratio)
    for x, y in _choose_obstacles(width, height, obstacle_count, rng):
        grid[y][x] = OBSTACLE

    piece_count = min(width, height) + 1
    for x, y in _choose_start_cells(grid, piece_count, top=True, rng=rng):
        grid[y][x] = PLAYER_A
    for x, y in _choose_start_cells(grid, piece_count, top=False, rng=rng):
        grid[y][x] = PLAYER_B

    current_player = rng.choice((PLAYER_A, PLAYER_B))
    return GameState(
        width=width,
        height=height,
        grid=_freeze_grid(grid),
        current_player=current_player,
    )


def legal_moves(state: GameState, player: int | None = None) -> tuple[Move, ...]:
    """Return all legal one-cell orthogonal moves for a player."""

    player = player or state.current_player
    moves: list[Move] = []
    for src in piece_positions(state, player):
        for dx, dy in DIRECTIONS:
            dst = (src[0] + dx, src[1] + dy)
            if is_legal_move(state, Move(src, dst), player):
                moves.append(Move(src, dst))
    return tuple(moves)


def is_legal_move(state: GameState, move: Move, player: int | None = None) -> bool:
    """Check movement legality without applying captures or turn changes."""

    player = player or state.current_player
    if state.winner is not None or state.draw:
        return False
    if not in_bounds(state, move.src) or not in_bounds(state, move.dst):
        return False
    if state.cell(move.src) != player:
        return False
    dx = abs(move.dst[0] - move.src[0])
    dy = abs(move.dst[1] - move.src[1])
    if dx + dy != 1:
        return False
    return state.cell(move.dst) == EMPTY


def apply_move(state: GameState, move: Move) -> GameState:
    """Apply a legal move, resolve captures, and advance the turn."""

    if not is_legal_move(state, move):
        raise ValueError("illegal move")

    player = state.current_player
    grid = [list(row) for row in state.grid]
    sx, sy = move.src
    dx, dy = move.dst
    grid[sy][sx] = EMPTY
    grid[dy][dx] = player

    captured = _captured_after_move(grid, player)
    for x, y in captured:
        grid[y][x] = EMPTY

    next_state = replace(
        state,
        grid=_freeze_grid(grid),
        no_capture_turns=0 if captured else state.no_capture_turns + 1,
        move_count=state.move_count + 1,
        last_captured=tuple(sorted(captured)),
    )
    next_state = _with_game_result(next_state)
    if next_state.winner is not None or next_state.draw:
        return next_state
    return _advance_turn(next_state, player)


def piece_positions(state: GameState, player: int) -> tuple[Coord, ...]:
    """Return all piece coordinates for a player."""

    result: list[Coord] = []
    for y, row in enumerate(state.grid):
        for x, cell in enumerate(row):
            if cell == player:
                result.append((x, y))
    return tuple(result)


def opponent(player: int) -> int:
    if player == PLAYER_A:
        return PLAYER_B
    if player == PLAYER_B:
        return PLAYER_A
    raise ValueError("unknown player")


def in_bounds(state: GameState, coord: Coord) -> bool:
    x, y = coord
    return 0 <= x < state.width and 0 <= y < state.height


def player_name(player: int) -> str:
    return "A" if player == PLAYER_A else "B"


def _advance_turn(state: GameState, player_who_moved: int) -> GameState:
    next_player = opponent(player_who_moved)
    if legal_moves(state, next_player):
        return replace(state, current_player=next_player)
    return replace(state, current_player=player_who_moved)


def _with_game_result(state: GameState) -> GameState:
    a_count = len(piece_positions(state, PLAYER_A))
    b_count = len(piece_positions(state, PLAYER_B))
    if a_count < 2:
        return replace(state, winner=PLAYER_B)
    if b_count < 2:
        return replace(state, winner=PLAYER_A)
    if state.no_capture_turns >= DRAW_NO_CAPTURE_TURNS:
        return replace(state, draw=True)
    return state


def _captured_after_move(grid: list[list[int]], player: int) -> set[Coord]:
    enemy = opponent(player)
    height = len(grid)
    width = len(grid[0])
    captured: set[Coord] = set()

    for y in range(height):
        for x in range(width):
            if grid[y][x] != player:
                continue
            for ax, ay in CAPTURE_AXES:
                nx, ny = x + ax, y + ay
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                if grid[ny][nx] != player:
                    continue
                before = (x - ax, y - ay)
                after = (x + 2 * ax, y + 2 * ay)
                for tx, ty in (before, after):
                    if 0 <= tx < width and 0 <= ty < height and grid[ty][tx] == enemy:
                        captured.add((tx, ty))
    return captured


def _choose_obstacles(
    width: int, height: int, count: int, rng: random.Random
) -> tuple[Coord, ...]:
    cells = [(x, y) for y in range(height) for x in range(width)]
    rng.shuffle(cells)
    obstacles: list[Coord] = []
    for cell in cells:
        if len(obstacles) >= count:
            break
        if all(not _touching(cell, existing) for existing in obstacles):
            obstacles.append(cell)
    return tuple(obstacles)


def _choose_start_cells(
    grid: list[list[int]], piece_count: int, *, top: bool, rng: random.Random
) -> tuple[Coord, ...]:
    height = len(grid)
    width = len(grid[0])
    rows = range(height - 1, -1, -1) if top else range(height)
    selected: list[Coord] = []
    for y in rows:
        candidates = [(x, y) for x in range(width) if grid[y][x] == EMPTY]
        rng.shuffle(candidates)
        for cell in candidates:
            selected.append(cell)
            if len(selected) == piece_count:
                return tuple(selected)
    raise ValueError("not enough empty cells for starting pieces")


def _touching(a: Coord, b: Coord) -> bool:
    return abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 1


def _freeze_grid(rows: Iterable[Iterable[int]]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(row) for row in rows)
