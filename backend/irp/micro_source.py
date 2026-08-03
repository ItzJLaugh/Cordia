#!/usr/bin/env python3
"""Reference micro agent for IRP — Source dimension.

This is a real player branch on the current VPS. The default classifier
is intentionally lightweight so the mother agent, intent bus, intent
store, and weighting layer have something real to talk to.

When Ollama is available and `CORDIA_IRP_OLLAMA_MODEL` is set, this
module uses that model for inference and falls back to the local
classifier only on failure.
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

LANE = "source"
BUS_PATH = os.environ.get("CORDIA_IRP_BUS", "/var/run/cordia-irp/bus.sock")
STATE_DIR = Path("/var/lib/cordia/irp")
STORE = STATE_DIR / "rounds.jsonl"
PID_FILE = STATE_DIR / "micro-source.pid"
HEARTBEAT_INTERVAL = 5
QUERY_TIMEOUT = 0.4
OLLAMA_URL = os.environ.get("CORDIA_IRP_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("CORDIA_IRP_OLLAMA_MODEL", "")

_SOURCE_INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "resolution": {
            "type": "string",
            "enum": ["concrete-instruction", "partially-concrete", "ambiguous-request"],
        },
        "confidence": {"type": "number"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "fallback": {"type": "boolean"},
    },
    "required": ["resolution", "confidence", "evidence", "fallback"],
}


def _ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    Path(BUS_PATH).parent.mkdir(parents=True, exist_ok=True)


def _local_classify(text: str) -> dict:
    t = (text or "").lower()
    evidence: list[str] = []
    score = 0.3
    if any(k in t for k in ["exactly", "specific", "number", "step", "format"]):
        score += 0.35
        evidence.append("precision marker")
    if any(k in t for k in ["must", "required", "should", "check"]):
        score += 0.2
        evidence.append("obligation marker")
    if any(k in t for k in ["vague", "maybe", "probably", "guess"]):
        score -= 0.3
        evidence.append("vagueness marker")
    confidence = max(0.05, min(0.98, score))
    if confidence >= 0.75:
        resolution = "concrete-instruction"
    elif confidence >= 0.45:
        resolution = "partially-concrete"
    else:
        resolution = "ambiguous-request"
    return {
        "lane": LANE,
        "resolution": resolution,
        "confidence": round(confidence, 3),
        "evidence": evidence,
        "fallback": False,
    }


def _ollama_classify(text: str) -> dict:
    if not OLLAMA_MODEL:
        raise RuntimeError("OLLAMA_MODEL not configured")
    prompt = (
        "Classify learner intent for the source lane. Return JSON only.\n"
        f"Input: {text}\n"
        "Schema: " + json.dumps(_SOURCE_INTENT_SCHEMA)
    )
    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": _SOURCE_INTENT_SCHEMA,
            "options": {"num_predict": 120, "temperature": 0},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    raw = body.get("response", "{}")
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("non-dict model response")
    except Exception:
        parsed = {
            "resolution": "ambiguous-request",
            "confidence": 0.1,
            "evidence": ["model-parse-failure"],
            "fallback": True,
        }
    parsed.setdefault("lane", LANE)
    parsed.setdefault("fallback", False)
    return parsed


def _classify(text: str) -> dict:
    try:
        return _ollama_classify(text)
    except Exception as exc:
        result = _local_classify(text)
        result["evidence"] = result.get("evidence", []) + [f"ollama-fallback:{type(exc).__name__}"]
        result["fallback"] = True
        return result


def _handle_query(payload: dict) -> dict:
    round_id = int(payload.get("round", 0))
    learner = str(payload.get("learner", ""))
    text = str(payload.get("text", ""))
    ts = time.time()
    result = _classify(text)
    record = {
        "lane": LANE,
        "round": round_id,
        "learner": learner,
        "ts": ts,
        **result,
    }
    try:
        with STORE.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass
    return {
        "msg_type": 2,
        "lane": LANE,
        "round": round_id,
        "ts": ts,
        **result,
    }


def _frame(msg_type: int, lane: str, round_id: int, body: dict) -> bytes:
    payload = json.dumps(body).encode("utf-8")
    header = bytes(
        [
            1,
            msg_type,
            1,
            (round_id >> 24) & 0xFF,
            (round_id >> 16) & 0xFF,
            (round_id >> 8) & 0xFF,
            round_id & 0xFF,
            (len(payload) >> 8) & 0xFF,
            len(payload) & 0xFF,
        ]
    )
    return header + payload


def _unframe(data: bytes) -> tuple[int, int, dict]:
    if len(data) < 9:
        raise ValueError("short frame")
    msg_type = data[1]
    round_id = (data[3] << 24) | (data[4] << 16) | (data[5] << 8) | data[6]
    length = (data[7] << 8) | data[8]
    body = json.loads(data[9 : 9 + length].decode("utf-8"))
    return msg_type, round_id, body


class MicroAgent:
    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connected = False
        self.alive = True
        self.pid = os.getpid()

    def run(self) -> None:
        _ensure_dirs()
        PID_FILE.write_text(str(self.pid))
        while self.alive:
            try:
                self.sock.connect(str(BUS_PATH))
                self.connected = True
                hello = _frame(3, LANE, 0, {"lane": LANE})
                try:
                    self.sock.sendall(hello)
                except Exception:
                    self.connected = False
                    time.sleep(0.3)
                    continue
                self._loop()
            except (ConnectionRefusedError, FileNotFoundError):
                time.sleep(0.3)
            except Exception:
                time.sleep(0.3)
            finally:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.connected = False

    def _loop(self) -> None:
        buf = b""
        self.sock.settimeout(HEARTBEAT_INTERVAL + 2)
        while self.alive:
            try:
                chunk = self.sock.recv(65535)
                if not chunk:
                    break
                buf += chunk
                while len(buf) >= 9:
                    length = (buf[7] << 8) | buf[8]
                    if len(buf) < 9 + length:
                        break
                    frame = buf[: 9 + length]
                    buf = buf[9 + length :]
                    self._handle_frame(frame)
            except socket.timeout:
                continue
            except Exception:
                break

    def _handle_frame(self, data: bytes) -> None:
        try:
            msg_type, round_id, body = _unframe(data)
        except Exception:
            return
        if msg_type == 1:
            reply = _handle_query(body)
            out = _frame(2, LANE, round_id, reply)
            try:
                self.sock.sendall(out)
            except Exception:
                pass


def main() -> None:
    agent = MicroAgent()
    try:
        agent.run()
    except KeyboardInterrupt:
        agent.alive = False
    finally:
        try:
            PID_FILE.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
