"""Private smoke boot shared by Dev and CI; always stop only our child process."""

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
log = Path(os.getenv("SMOKE_LOG_PATH", "/tmp/value-dashboard-streamlit.log"))
with log.open("w") as output:
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(root / "stock_dashboard.py"),
            "--server.headless",
            "true",
            "--server.address",
            "127.0.0.1",
            "--server.port",
            "8501",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=root,
        stdout=output,
        stderr=subprocess.STDOUT,
        env={**os.environ, "SMOKE_TEST": "1"},
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            if process.poll() is not None:
                raise RuntimeError("Streamlit exited before readiness")
            try:
                with urllib.request.urlopen("http://127.0.0.1:8501/_stcore/health", timeout=2) as response:
                    assert response.status == 200 and response.read().strip() == b"ok"
                break
            except (urllib.error.URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)
        with urllib.request.urlopen("http://127.0.0.1:8501/", timeout=2) as response:
            assert response.status == 200 and b"Streamlit" in response.read()
        assert process.poll() is None
        print("Smoke passed: health=200/ok, homepage=200/Streamlit")
    except Exception:
        print(log.read_text())
        raise
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
