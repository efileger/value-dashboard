import os
from pathlib import Path
import shutil
import subprocess
import time

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
STREAMLIT_CLI = shutil.which("streamlit")


@pytest.mark.skipif(STREAMLIT_CLI is None, reason="Streamlit CLI not available")
def test_headless_bootstrap_startup(tmp_path):
    log_path = tmp_path / "streamlit_bootstrap.log"
    env = os.environ | {
        "SMOKE_TEST": "1",
        "STREAMLIT_SERVER_HEADLESS": "true",
        "STREAMLIT_BROWSER_GATHERUSAGESTATS": "false",
    }

    cmd = [
        STREAMLIT_CLI,
        "run",
        str(REPO_ROOT / "stock_dashboard.py"),
        "--server.headless",
        "true",
        "--server.port",
        "0",
        "--server.address",
        "127.0.0.1",
        "--browser.gatherUsageStats",
        "false",
    ]

    with log_path.open("wb") as log_file:
        proc = subprocess.Popen(
            cmd,
            cwd=REPO_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
        )

        try:
            time.sleep(5)
            assert proc.poll() is None, log_path.read_text()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

    if log_path.exists():
        log_contents = log_path.read_text().strip()
        assert "Traceback" not in log_contents
