#!/usr/bin/env python3
"""Intent Resolution Protocol (IRP) — mother agent + SSE server.

The mother agent owns the Unix domain socket. Micro agents connect as
clients; the mother sends one query per round and collects replies.
"""
from __future__ import annotations

import json
import os
import select
import socket
import threading
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

BUS_PATH = os.environ.get("CORDIA_IRP_BUS", "/var/run/cordia-irp/bus.sock")
STATE_DIR = Path("/var/lib/cordia/irp")
ROUNDS = STATE_DIR / "rounds.jsonl"
MOTHER_STATE = STATE_DIR / "mother_state.json"
BROADCAST_INTERVAL = 1.0
REPLY_TIMEOUT = 0.4
LANES = ["source", "success", "safety", "steering", "switch", "sharpen"]


def _ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    Path(BUS_PATH).parent.mkdir(parents=True, exist_ok=True)


def _now() -> float:
    return time.time()


def _frame(msg_type: int, lane: str, round_id: int, body: dict) -> bytes:
    payload = json.dumps(body).encode("utf-8")
    header = bytes([
        1,
        msg_type,
        1,
        (round_id >> 24) & 0xFF,
        (round_id >> 16) & 0xFF,
        (round_id >> 8) & 0xFF,
        round_id & 0xFF,
        (len(payload) >> 8) & 0xFF,
        len(payload) & 0xFF,
    ])
    return header + payload


def _unframe(data: bytes) -> tuple[int, int, dict]:
    if len(data) < 9:
        raise ValueError("short frame")
    msg_type = data[1]
    round_id = (data[3] << 24) | (data[4] << 16) | (data[5] << 8) | data[6]
    length = (data[7] << 8) | data[8]
    body = json.loads(data[9 : 9 + length].decode("utf-8"))
    return msg_type, round_id, body


class BusServer:
    def __init__(self, path: str):
        self.path = path
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(path)
        self.server.listen(5)
        self.server.setblocking(False)
        self.connections: dict[str, socket.socket] = {}
        self.bufs: dict[str, bytes] = {}
        self.lock = threading.Lock()

    def accept(self) -> list[str]:
        new = []
        try:
            while True:
                conn, _ = self.server.accept()
                conn.settimeout(1.0)
                lane = self._handshake(conn)
                if lane:
                    with self.lock:
                        self.connections[lane] = conn
                        self.bufs[lane] = b""
                    new.append(lane)
                else:
                    try:
                        conn.close()
                    except Exception:
                        pass
        except BlockingIOError:
            pass
        return new

    def _handshake(self, conn: socket.socket) -> str | None:
        conn.settimeout(2.0)
        lane = None
        try:
            for _ in range(4):
                try:
                    data = conn.recv(65535)
                except socket.timeout:
                    continue
                if not data:
                    break
                try:
                    body = json.loads(data[9:].decode("utf-8"))
                except Exception:
                    break
                lane = str(body.get("lane", "")).strip()
                if lane:
                    return lane
        except Exception:
            pass
        # Close only on failure; success returns above
        try:
            conn.close()
        except Exception:
            pass
        return None

    def send_query(self, lane: str, payload: dict) -> bool:
        with self.lock:
            conn = self.connections.get(lane)
        if not conn:
            return False
        try:
            frame = _frame(1, lane, payload.get("round", 0), payload)
            conn.sendall(frame)
            return True
        except Exception:
            return False

    def drain_replies(self, lanes: list[str]) -> dict[str, dict | None]:
        results = {lane: None for lane in lanes}
        with self.lock:
            items = list(self.connections.items())
        for lane, conn in items:
            try:
                data = conn.recv(65535)
                if not data:
                    continue
                buf = self.bufs.get(lane, b"") + data
                while len(buf) >= 9:
                    length = (buf[7] << 8) | buf[8]
                    if len(buf) < 9 + length:
                        break
                    msg_type, round_id, body = _unframe(buf[: 9 + length])
                    buf = buf[9 + length :]
                    if msg_type == 2:
                        results[lane] = body
                self.bufs[lane] = buf
            except Exception:
                pass
        return results

    def close(self) -> None:
        for conn in self.connections.values():
            try:
                conn.close()
            except Exception:
                pass
        try:
            self.server.close()
        except Exception:
            pass


class MotherAgent:
    def __init__(self):
        self.bus = BusServer(BUS_PATH)
        self.current_text = ""
        self.current_learner = ""
        self.round_counter = 0
        self.running = True
        self.subscribers: list[socket.socket] = []
        self.sub_lock = threading.Lock()

    def start(self) -> None:
        _ensure_dirs()
        threading.Thread(target=self._broadcast_loop, daemon=True).start()

    def _broadcast_loop(self) -> None:
        known = set()
        while self.running:
            try:
                new = self.bus.accept()
                known.update(new)
            except Exception:
                pass
            if known:
                self.round_counter += 1
                round_id = self.round_counter
                payload = {
                    "round": round_id,
                    "learner": self.current_learner,
                    "text": self.current_text,
                }
                for lane in known:
                    self.bus.send_query(lane, payload)
                time.sleep(REPLY_TIMEOUT)
                replies = self.bus.drain_replies(list(known))
                record = {
                    "round": round_id,
                    "learner": self.current_learner,
                    "ts": _now(),
                    "lanes": {},
                }
                for lane, reply in replies.items():
                    if reply:
                        record["lanes"][lane] = {
                            "resolution": reply.get("resolution"),
                            "confidence": reply.get("confidence", 0.0),
                            "fallback": reply.get("fallback", False),
                            "evidence": reply.get("evidence", []),
                        }
                    else:
                        record["lanes"][lane] = {
                            "resolution": "timeout",
                            "confidence": 0.0,
                            "fallback": True,
                        }
                self._persist_round(record)
                self._notify_subscribers(record)
            time.sleep(BROADCAST_INTERVAL)

    def _persist_round(self, record: dict) -> None:
        try:
            with ROUNDS.open("a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass
        try:
            MOTHER_STATE.write_text(json.dumps(record, indent=2))
        except Exception:
            pass

    def _notify_subscribers(self, record: dict) -> None:
        msg = f"data: {json.dumps(record)}\n\n".encode("utf-8")
        dead = []
        with self.sub_lock:
            for s in self.subscribers:
                try:
                    s.sendall(msg)
                except Exception:
                    dead.append(s)
            for s in dead:
                try:
                    self.subscribers.remove(s)
                except ValueError:
                    pass

    def submit(self, learner: str, text: str) -> None:
        self.current_learner = learner
        self.current_text = text
        self.round_counter = 0

    def stop(self) -> None:
        self.running = False
        self.bus.close()


class SSEHandler(BaseHTTPRequestHandler):
    mother: MotherAgent | None = None

    def log_message(self, format, *args):  # noqa: A002
        pass

    def do_GET(self):  # noqa: A002
        if self.path != "/irp/stream":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.flush()
        if self.mother is None:
            return
        with self.mother.sub_lock:
            self.mother.subscribers.append(self.request)
        try:
            while True:
                time.sleep(60)
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except Exception:
            pass
        finally:
            with self.mother.sub_lock:
                try:
                    self.mother.subscribers.remove(self.request)
                except ValueError:
                    pass

    def do_POST(self):  # noqa: A002
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        if self.path == "/irp/submit" and self.mother:
            learner = str(body.get("learner", ""))
            text = str(body.get("text", ""))
            self.mother.submit(learner, text)
            self.send_response(202)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')
        else:
            self.send_response(404)
            self.end_headers()


def run_mother(host: str = "127.0.0.1", port: int = 9998) -> None:
    _ensure_dirs()
    mother = MotherAgent()
    SSEHandler.mother = mother
    mother.start()
    server = HTTPServer((host, port), SSEHandler)
    print(f"IRP mother on :{port}, lanes={LANES}, bus={BUS_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        mother.stop()
        server.server_close()


if __name__ == "__main__":
    run_mother()
