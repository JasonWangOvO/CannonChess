"""LAN TCP helpers for remote CannonChess games."""

from __future__ import annotations

from dataclasses import dataclass
import json
import socket
import threading
from typing import Any, Callable

from .core import GameState, Move

MessageHandler = Callable[[dict[str, Any]], None]
CloseHandler = Callable[[Exception | None], None]


def state_to_dict(state: GameState) -> dict[str, Any]:
    return {
        "width": state.width,
        "height": state.height,
        "grid": [list(row) for row in state.grid],
        "current_player": state.current_player,
        "no_capture_turns": state.no_capture_turns,
        "winner": state.winner,
        "draw": state.draw,
        "move_count": state.move_count,
        "last_captured": [list(coord) for coord in state.last_captured],
    }


def state_from_dict(data: dict[str, Any]) -> GameState:
    return GameState(
        width=int(data["width"]),
        height=int(data["height"]),
        grid=tuple(tuple(int(cell) for cell in row) for row in data["grid"]),
        current_player=int(data["current_player"]),
        no_capture_turns=int(data.get("no_capture_turns", 0)),
        winner=data.get("winner"),
        draw=bool(data.get("draw", False)),
        move_count=int(data.get("move_count", 0)),
        last_captured=tuple(tuple(coord) for coord in data.get("last_captured", [])),
    )


def move_to_dict(move: Move) -> dict[str, list[int]]:
    return {"src": [move.src[0], move.src[1]], "dst": [move.dst[0], move.dst[1]]}


def move_from_dict(data: dict[str, Any]) -> Move:
    return Move(src=tuple(data["src"]), dst=tuple(data["dst"]))


@dataclass
class RemoteConnection:
    sock: socket.socket
    on_message: MessageHandler
    on_close: CloseHandler

    def __post_init__(self) -> None:
        self._send_lock = threading.Lock()
        self._closed = threading.Event()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def send(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        with self._send_lock:
            self.sock.sendall(payload)

    def close(self) -> None:
        self._closed.set()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass

    def _read_loop(self) -> None:
        error: Exception | None = None
        buffer = b""
        try:
            while not self._closed.is_set():
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line:
                        self.on_message(json.loads(line.decode("utf-8")))
        except Exception as exc:
            error = exc
        finally:
            self._closed.set()
            self.on_close(error)


def start_server(
    host: str,
    port: int,
    on_client: Callable[[socket.socket, tuple[str, int]], None],
    on_error: Callable[[Exception], None],
) -> socket.socket:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(1)

    def accept_once() -> None:
        try:
            client, address = server.accept()
            on_client(client, address)
        except OSError:
            pass
        except Exception as exc:
            on_error(exc)
        finally:
            try:
                server.close()
            except OSError:
                pass

    threading.Thread(target=accept_once, daemon=True).start()
    return server


def connect_to_server(host: str, port: int, timeout: float = 8.0) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))
    sock.settimeout(None)
    return sock
