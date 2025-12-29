import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.request

from stock_dashboard import ui


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("", 0))
        return sock.getsockname()[1]


def _wait_for_ready(url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url) as response:  # noqa: S310
                if response.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.5)
            continue

    raise TimeoutError(f"Timed out waiting for {url}")


def test_streamlit_renders_stub_ticker(tmp_path, monkeypatch, streamlit_spy):
    port = _find_free_port()
    env = os.environ | {
        "SMOKE_TEST": "1",
        "STREAMLIT_SERVER_HEADLESS": "true",
    }

    cmd = [
        "streamlit",
        "run",
        "stock_dashboard.py",
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )

    try:
        _wait_for_ready(f"http://127.0.0.1:{port}/")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    assert proc.returncode in (None, 0, -15)
    monkeypatch.setenv("SMOKE_TEST", "1")

    ui.display_stock("AAPL")

    captured = streamlit_spy
    assert "df" in captured
    # Ensure rendered values are not placeholders when using demo data
    assert any(value != "N/A" for value in captured["df"]["Value"].head(3))
