"""Test configuration: isolated database + local Hindsight-compatible server, no LLM key (deterministic engine)."""
from __future__ import annotations

import os
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


FAKE_PORT = _free_port()
_tmp = Path(tempfile.mkdtemp(prefix="medistock-test-"))
os.environ.update({
    "HINDSIGHT_BASE_URL": f"http://127.0.0.1:{FAKE_PORT}",
    "HINDSIGHT_API_KEY": "test-key",
    "HINDSIGHT_BANK_ID": "medistock-test",
    "GROQ_API_KEY": "",
    "DATABASE_PATH": str(_tmp / "test.db"),
})


@pytest.fixture(scope="session", autouse=True)
def fake_hindsight_server():
    import uvicorn

    from tests import fake_hindsight

    server = uvicorn.Server(uvicorn.Config(fake_hindsight.app, host="127.0.0.1", port=FAKE_PORT, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    yield fake_hindsight
    server.should_exit = True
    thread.join(timeout=5)
