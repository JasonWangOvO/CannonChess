"""Tkinter user interface for local two-player CannonChess."""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import messagebox

from .agents import HeuristicAgent
from .core import (
    EMPTY,
    OBSTACLE,
    FRUIT,
    PLAYER_A,
    PLAYER_B,
    DRAW_NO_CAPTURE_TURNS,
    GameConfig,
    GameState,
    Move,
    apply_move,
    create_new_game,
    legal_moves,
    player_name,
)
from .network import (
    RemoteConnection,
    connect_to_server,
    move_from_dict,
    move_to_dict,
    start_server,
    state_from_dict,
    state_to_dict,
)

CELL_SIZE = 64
BOARD_PADDING = 18
MAX_BOARD_SIZE = 10
KLEIN_BLUE = "#002FA7"
BURGUNDY_RED = "#800020"
OBSTACLE_BROWN = "#614124"
FRUIT_PINK = "#A94064"
HINT_YELLOW = "#F7E38A"
BACKGROUND = "#F3F4F6"
GRID_LINE = "#B8BEC9"
RULES_HELP_TEXT = """移动规则：
每回合移动一颗己方棋子一格，只能上下左右移动，不能斜走，也不能移动到棋子或障碍物上。

吃子规则：
只有本次移动的棋子与另一颗己方棋子上下或左右相邻成线时，才会尝试吃掉这条线延长方向一格的敌方棋子。静态成线不会因其他棋子移动而吃子。目标背后一格如果有障碍或目标方友方棋子，则不会被吃掉。

果实规则：
樱桃粉色的 ^_^ 果实可以像棋子一样被炮吃掉。吃掉果实的一方会在己方半区靠边位置生成一颗己方棋子。

胜利规则：
当一方棋子数量少于 2 时，该方失败，对方胜利。连续 200 回合没有吃子则平局。"""


@dataclass
class GameRenderer:
    """UI renderer interface reserved by the requirements."""

    app: "CannonChessApp"

    def render(self, state: GameState) -> None:
        self.app.render_board(state)


class CannonChessApp(tk.Tk):
    """Desktop app with mode selection and local two-player play."""

    def __init__(self) -> None:
        super().__init__()
        self.title("CannonChess")
        self.configure(bg=BACKGROUND)
        self.resizable(False, False)
        self.state_obj: GameState | None = None
        self.initial_state: GameState | None = None
        self.history: list[GameState] = []
        self.selected: tuple[int, int] | None = None
        self.ai_agent: HeuristicAgent | None = None
        self.human_player = PLAYER_A
        self.remote_connection: RemoteConnection | None = None
        self.remote_server = None
        self.local_player: int | None = None
        self.remote_mode = False
        self.renderer = GameRenderer(self)
        self._show_mode_select()

    def _show_mode_select(self) -> None:
        self._clear()
        frame = tk.Frame(self, bg=BACKGROUND, padx=28, pady=24)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="CannonChess", bg=BACKGROUND, fg="#111827", font=("Microsoft YaHei UI", 20, "bold")).pack(
            anchor="w", pady=(0, 18)
        )

        tk.Button(frame, text="双人本地对战", width=24, command=self.start_local_game).pack(anchor="w", pady=5)
        tk.Button(frame, text="双人远程游玩", width=24, command=self._show_remote_menu).pack(anchor="w", pady=5)
        tk.Button(frame, text="单人 AI 对战", width=24, command=self.start_ai_game).pack(anchor="w", pady=5)

    def return_to_mode_select(self) -> None:
        self._close_remote()
        self.remote_mode = False
        self.local_player = None
        self.ai_agent = None
        self._show_mode_select()

    def start_local_game(self) -> None:
        self._close_remote()
        self.remote_mode = False
        self.local_player = None
        self.ai_agent = None
        self.initial_state = create_new_game(GameConfig())
        self.state_obj = self.initial_state
        self.history = []
        self.selected = None
        self._show_game()

    def start_ai_game(self) -> None:
        self._close_remote()
        self.remote_mode = False
        self.local_player = None
        self.human_player = PLAYER_A
        self.ai_agent = HeuristicAgent(player=PLAYER_B, max_depth=2, candidate_limit=10)
        self.initial_state = create_new_game(GameConfig())
        self.state_obj = self.initial_state
        self.history = []
        self.selected = None
        self._show_game()
        self._schedule_ai_move()

    def _show_remote_menu(self) -> None:
        self._close_remote()
        self._clear()
        frame = tk.Frame(self, bg=BACKGROUND, padx=28, pady=24)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text="局域网远程对战",
            bg=BACKGROUND,
            fg="#111827",
            font=("Microsoft YaHei UI", 18, "bold"),
        ).pack(anchor="w", pady=(0, 16))

        create_row = tk.Frame(frame, bg=BACKGROUND)
        create_row.pack(anchor="w", pady=5)
        tk.Label(create_row, text="监听端口", bg=BACKGROUND).pack(side="left")
        self.create_port_var = tk.StringVar(value="5000")
        tk.Entry(create_row, textvariable=self.create_port_var, width=8).pack(side="left", padx=8)
        tk.Button(create_row, text="创建房间", command=self.create_remote_room).pack(side="left")

        join_row = tk.Frame(frame, bg=BACKGROUND)
        join_row.pack(anchor="w", pady=5)
        tk.Label(join_row, text="主机 IP", bg=BACKGROUND).pack(side="left")
        self.join_host_var = tk.StringVar(value="127.0.0.1")
        tk.Entry(join_row, textvariable=self.join_host_var, width=16).pack(side="left", padx=8)
        tk.Label(join_row, text="端口", bg=BACKGROUND).pack(side="left")
        self.join_port_var = tk.StringVar(value="5000")
        tk.Entry(join_row, textvariable=self.join_port_var, width=8).pack(side="left", padx=8)
        tk.Button(join_row, text="加入房间", command=self.join_remote_room).pack(side="left")

        self.remote_status = tk.Label(
            frame,
            text="创建房间后，把本机局域网 IP 和端口告诉对方。",
            bg=BACKGROUND,
            fg="#374151",
            width=52,
            anchor="w",
        )
        self.remote_status.pack(anchor="w", pady=(14, 6))
        tk.Button(frame, text="返回模式", command=self.return_to_mode_select).pack(anchor="w", pady=8)

    def create_remote_room(self) -> None:
        try:
            port = int(self.create_port_var.get())
        except ValueError:
            messagebox.showerror("远程对战", "端口必须是数字。")
            return

        self.remote_status.config(text=f"正在监听 0.0.0.0:{port}，等待对方加入...")
        self.remote_mode = True
        self.local_player = PLAYER_A
        self.ai_agent = None
        self.initial_state = create_new_game(GameConfig())
        self.state_obj = self.initial_state
        self.history = []
        self.selected = None

        def on_client(sock, address) -> None:
            self.after(0, lambda: self._accept_remote_client(sock, address))

        def on_error(exc: Exception) -> None:
            self.after(0, lambda: messagebox.showerror("远程对战", str(exc)))

        try:
            self.remote_server = start_server("0.0.0.0", port, on_client, on_error)
        except OSError as exc:
            messagebox.showerror("远程对战", f"创建房间失败：{exc}")

    def _accept_remote_client(self, sock, address) -> None:
        self.remote_connection = RemoteConnection(sock, self._on_remote_message, self._on_remote_close)
        assert self.state_obj is not None
        self.remote_connection.send(
            {
                "type": "start",
                "side": PLAYER_B,
                "state": state_to_dict(self.state_obj),
            }
        )
        self._show_game()
        messagebox.showinfo("远程对战", f"玩家已加入：{address[0]}:{address[1]}")

    def join_remote_room(self) -> None:
        host = self.join_host_var.get().strip()
        try:
            port = int(self.join_port_var.get())
        except ValueError:
            messagebox.showerror("远程对战", "端口必须是数字。")
            return
        self.remote_status.config(text=f"正在连接 {host}:{port} ...")

        def connect() -> None:
            try:
                sock = connect_to_server(host, port)
                self.after(0, lambda: self._finish_join_remote(sock))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("远程对战", f"连接失败：{exc}"))

        import threading

        threading.Thread(target=connect, daemon=True).start()

    def _finish_join_remote(self, sock) -> None:
        self.remote_mode = True
        self.local_player = PLAYER_B
        self.ai_agent = None
        self.remote_connection = RemoteConnection(sock, self._on_remote_message, self._on_remote_close)
        self.remote_status.config(text="连接成功，等待主机发送棋局...")

    def restart_current_game(self) -> None:
        if self.remote_mode:
            self.restart_remote_game()
            return
        if self.initial_state is None:
            self.start_local_game()
            return
        self.state_obj = self.initial_state
        self.history = []
        self.selected = None
        self._show_game()
        self._schedule_ai_move()

    def _show_game(self) -> None:
        self._clear()
        root = tk.Frame(self, bg=BACKGROUND, padx=16, pady=16)
        root.pack()

        top = tk.Frame(root, bg=BACKGROUND)
        top.pack(fill="x", pady=(0, 10))
        self.status = tk.Label(
            top, bg=BACKGROUND, fg="#111827", font=("Microsoft YaHei UI", 12, "bold"), width=42, anchor="w"
        )
        self.status.pack(side="left")
        tk.Button(top, text="悔棋", command=self.undo).pack(side="left", padx=3)
        tk.Button(top, text="投降", command=self.surrender).pack(side="left", padx=3)
        tk.Button(top, text="规则", command=self.show_rules).pack(side="left", padx=3)
        tk.Button(top, text="重新开始", command=self.restart_current_game).pack(side="left", padx=3)
        tk.Button(top, text="新的一局", command=self.start_new_game_same_mode).pack(side="left", padx=3)
        tk.Button(top, text="返回模式", command=self.return_to_mode_select).pack(side="left", padx=3)

        assert self.state_obj is not None
        canvas_width = MAX_BOARD_SIZE * CELL_SIZE + BOARD_PADDING * 2
        canvas_height = MAX_BOARD_SIZE * CELL_SIZE + BOARD_PADDING * 2
        self.canvas = tk.Canvas(root, width=canvas_width, height=canvas_height, bg=BACKGROUND, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)
        self.renderer.render(self.state_obj)

    def start_new_game_same_mode(self) -> None:
        if self.remote_mode:
            self.initial_state = create_new_game(GameConfig())
            self.state_obj = self.initial_state
            self.history = []
            self.selected = None
            self.renderer.render(self.state_obj)
            self._send_remote({"type": "new_game", "state": state_to_dict(self.state_obj)})
            return
        if self.ai_agent is not None:
            self.start_ai_game()
            return
        self.start_local_game()

    def undo(self) -> None:
        if not self.history:
            messagebox.showinfo("悔棋", "当前没有可撤销的走法。")
            return
        if self.remote_mode:
            self.state_obj = self.history.pop()
            self.selected = None
            self.renderer.render(self.state_obj)
            self._send_remote({"type": "undo", "state": state_to_dict(self.state_obj)})
            return
        if self.ai_agent is not None and len(self.history) >= 2:
            self.history.pop()
            self.state_obj = self.history.pop()
        else:
            self.state_obj = self.history.pop()
        self.selected = None
        self.renderer.render(self.state_obj)

    def surrender(self) -> None:
        state = self.state_obj
        if state is None or state.winner is not None or state.draw:
            return
        surrender_player = self.local_player if self.remote_mode else state.current_player
        winner = PLAYER_B if surrender_player == PLAYER_A else PLAYER_A
        self.state_obj = GameState(
            width=state.width,
            height=state.height,
            grid=state.grid,
            current_player=state.current_player,
            no_capture_turns=state.no_capture_turns,
            winner=winner,
            draw=state.draw,
            move_count=state.move_count,
            last_captured=state.last_captured,
        )
        self.selected = None
        self.renderer.render(self.state_obj)
        if self.remote_mode:
            self._send_remote({"type": "state", "state": state_to_dict(self.state_obj)})

    def show_rules(self) -> None:
        messagebox.showinfo("游戏规则", RULES_HELP_TEXT)

    def on_click(self, event: tk.Event[tk.Canvas]) -> None:
        state = self.state_obj
        if state is None or state.winner is not None or state.draw:
            return
        if self.ai_agent is not None and state.current_player != self.human_player:
            return
        if self.remote_mode and state.current_player != self.local_player:
            return
        coord = self._pixel_to_coord(event.x, event.y, state)
        if coord is None:
            return
        if self.selected is None:
            if state.cell(coord) == state.current_player:
                self.selected = coord
                self.renderer.render(state)
            return

        if coord == self.selected:
            self.selected = None
            self.renderer.render(state)
            return
        if state.cell(coord) == state.current_player:
            self.selected = coord
            self.renderer.render(state)
            return

        move = Move(self.selected, coord)
        try:
            next_state = apply_move(state, move)
        except ValueError:
            return
        self.history.append(state)
        self.state_obj = next_state
        self.selected = None
        self.renderer.render(next_state)
        if self.remote_mode:
            self._send_remote({"type": "move", "move": move_to_dict(move)})
        self._schedule_ai_move()

    def restart_remote_game(self) -> None:
        if not self.remote_mode:
            return
        if self.initial_state is None:
            return
        self.state_obj = self.initial_state
        self.history = []
        self.selected = None
        self.renderer.render(self.state_obj)
        self._send_remote({"type": "restart", "state": state_to_dict(self.state_obj)})

    def _on_remote_message(self, message: dict) -> None:
        self.after(0, lambda: self._handle_remote_message(message))

    def _handle_remote_message(self, message: dict) -> None:
        msg_type = message.get("type")
        if msg_type == "start":
            self.local_player = int(message["side"])
            self.remote_mode = True
            self.ai_agent = None
            self.initial_state = state_from_dict(message["state"])
            self.state_obj = self.initial_state
            self.history = []
            self.selected = None
            self._show_game()
            return

        if msg_type == "move" and self.state_obj is not None:
            move = move_from_dict(message["move"])
            try:
                next_state = apply_move(self.state_obj, move)
            except ValueError:
                messagebox.showerror("远程对战", "收到非法走法，双方棋局可能不同步。")
                return
            self.history.append(self.state_obj)
            self.state_obj = next_state
            self.selected = None
            self.renderer.render(self.state_obj)
            return

        if msg_type == "undo":
            if self.history:
                self.history.pop()
            self.state_obj = state_from_dict(message["state"])
            self.selected = None
            self.renderer.render(self.state_obj)
            return

        if msg_type == "restart":
            self.initial_state = state_from_dict(message["state"])
            self.state_obj = self.initial_state
            self.history = []
            self.selected = None
            self.renderer.render(self.state_obj)
            return

        if msg_type == "new_game":
            self.initial_state = state_from_dict(message["state"])
            self.state_obj = self.initial_state
            self.history = []
            self.selected = None
            self.renderer.render(self.state_obj)
            return

        if msg_type == "state":
            self.state_obj = state_from_dict(message["state"])
            self.selected = None
            self.renderer.render(self.state_obj)
            return

    def _send_remote(self, message: dict) -> None:
        if self.remote_connection is None:
            messagebox.showwarning("远程对战", "当前没有远程连接。")
            return
        try:
            self.remote_connection.send(message)
        except OSError as exc:
            messagebox.showerror("远程对战", f"发送失败：{exc}")

    def _on_remote_close(self, error: Exception | None) -> None:
        if not self.remote_mode:
            return
        text = "远程连接已断开。"
        if error is not None:
            text = f"远程连接已断开：{error}"
        self.after(0, lambda: messagebox.showwarning("远程对战", text))

    def _close_remote(self) -> None:
        self.remote_mode = False
        if self.remote_connection is not None:
            self.remote_connection.close()
            self.remote_connection = None
        if self.remote_server is not None:
            try:
                self.remote_server.close()
            except OSError:
                pass
            self.remote_server = None

    def _schedule_ai_move(self) -> None:
        state = self.state_obj
        if (
            self.ai_agent is None
            or state is None
            or state.winner is not None
            or state.draw
            or state.current_player != self.ai_agent.player
        ):
            return
        self.after(250, self._perform_ai_move)

    def _perform_ai_move(self) -> None:
        state = self.state_obj
        if (
            self.ai_agent is None
            or state is None
            or state.winner is not None
            or state.draw
            or state.current_player != self.ai_agent.player
        ):
            return
        moves = legal_moves(state, self.ai_agent.player)
        if not moves:
            return
        move = self.ai_agent.choose_move(state)
        self.history.append(state)
        self.state_obj = apply_move(state, move)
        self.selected = None
        self.renderer.render(self.state_obj)
        self._schedule_ai_move()

    def render_board(self, state: GameState) -> None:
        self.canvas.delete("all")
        hints = {move.dst for move in legal_moves(state) if move.src == self.selected}
        for y in range(state.height):
            for x in range(state.width):
                self._draw_cell(state, x, y, (x, y) in hints)

        if self.selected is not None:
            left, top, right, bottom = self._cell_rect(*self.selected, state)
            self.canvas.create_rectangle(left + 3, top + 3, right - 3, bottom - 3, outline="#F59E0B", width=3)

        self._update_status(state)

    def _draw_cell(self, state: GameState, x: int, y: int, hinted: bool) -> None:
        left, top, right, bottom = self._cell_rect(x, y, state)
        cell = state.cell((x, y))
        fill = "#FFFFFF"
        self.canvas.create_rectangle(left, top, right, bottom, fill=fill, outline=GRID_LINE)
        if hinted:
            self.canvas.create_rectangle(
                left + 4, top + 4, right - 4, bottom - 4, fill=HINT_YELLOW, outline="", stipple="gray50"
            )
        if cell == OBSTACLE:
            self.canvas.create_rectangle(
                left + 10, top + 10, right - 10, bottom - 10, fill=OBSTACLE_BROWN, outline="#111111", width=2
            )
        if cell == FRUIT:
            self.canvas.create_rectangle(
                left + 10, top + 10, right - 10, bottom - 10, fill=FRUIT_PINK, outline=""
            )
            self.canvas.create_text(
                (left + right) / 2,
                (top + bottom) / 2,
                text="^_^",
                fill="#FFFFFF",
                font=("Arial", 13, "bold"),
            )
        if cell in (PLAYER_A, PLAYER_B):
            color = KLEIN_BLUE if cell == PLAYER_A else BURGUNDY_RED
            self.canvas.create_rectangle(
                left + 10, top + 10, right - 10, bottom - 10, fill=color, outline="#111827", width=2
            )
            self.canvas.create_text(
                (left + right) / 2,
                (top + bottom) / 2,
                text=player_name(cell),
                fill="#FFFFFF",
                font=("Arial", 16, "bold"),
            )

    def _update_status(self, state: GameState) -> None:
        a_count = sum(row.count(PLAYER_A) for row in state.grid)
        b_count = sum(row.count(PLAYER_B) for row in state.grid)
        if state.winner is not None:
            text = f"{player_name(state.winner)} 方胜利  A:{a_count} B:{b_count}"
        elif state.draw:
            text = f"平局  A:{a_count} B:{b_count}"
        else:
            if self.remote_mode:
                mode = "远程对战"
            else:
                mode = "AI 对战" if self.ai_agent is not None else "本地双人"
            text = (
                f"{mode}  当前回合：{player_name(state.current_player)} 方  "
                f"A:{a_count} B:{b_count}  "
                f"无吃子回合:{state.no_capture_turns}/{DRAW_NO_CAPTURE_TURNS}"
            )
        self.status.config(text=text)

    def _cell_rect(self, x: int, y: int, state: GameState) -> tuple[int, int, int, int]:
        left = BOARD_PADDING + x * CELL_SIZE
        top = BOARD_PADDING + (state.height - 1 - y) * CELL_SIZE
        return left, top, left + CELL_SIZE, top + CELL_SIZE

    def _pixel_to_coord(self, px: int, py: int, state: GameState) -> tuple[int, int] | None:
        bx = px - BOARD_PADDING
        by = py - BOARD_PADDING
        if bx < 0 or by < 0:
            return None
        x = bx // CELL_SIZE
        visual_y = by // CELL_SIZE
        if x >= state.width or visual_y >= state.height:
            return None
        return int(x), int(state.height - 1 - visual_y)

    def _clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()


def main() -> None:
    app = CannonChessApp()
    app.mainloop()
