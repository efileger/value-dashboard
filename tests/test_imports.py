import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest


STREAMLIT_CLI = shutil.which("streamlit")


def test_module_exports_core_attributes():
    import stock_dashboard as module

    for attribute in ("main", "data_access", "metrics", "ui"):
        assert hasattr(module, attribute), f"Missing expected attribute: {attribute}"


def _can_bind_port() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("", 0))
        return True
    except OSError:
        return False


@pytest.mark.skipif(STREAMLIT_CLI is None, reason="Streamlit CLI not available")
@pytest.mark.skipif(not _can_bind_port(), reason="Cannot bind to ephemeral port for Streamlit")
def test_streamlit_startup_smoke():
    env = os.environ | {"SMOKE_TEST": "1", "STREAMLIT_SERVER_HEADLESS": "true"}
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "stock_dashboard.py",
        "--server.headless",
        "true",
        "--server.port",
        "0",
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    try:
        stdout, stderr = proc.communicate(timeout=8)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=5)

    output = (stdout or b"") + (stderr or b"")

    if proc.returncode not in (0, -15, None):
        if b"Address already in use" in output:
            pytest.skip("Streamlit could not bind to a free port")
        pytest.fail(output.decode("utf-8", errors="ignore"))

    assert proc.returncode in (0, -15, None)
