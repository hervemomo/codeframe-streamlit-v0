"""Start Streamlit headlessly and verify its local health endpoint."""

from __future__ import annotations

import argparse

# Security: this module starts only the fixed local Streamlit smoke child.
import subprocess  # nosec B404
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def smoke_test(*, port: int = 8507, timeout_seconds: float = 30.0) -> None:
    """Start the application, wait for health, and always stop the child process."""

    repository_root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.headless=true",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
    ]
    # Security: the argument list uses no shell and contains only typed/local values.
    process = subprocess.Popen(  # nosec B603
        command,
        cwd=repository_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Streamlit exited early with status {process.returncode}.")
            try:
                # Security: the scheme and host are fixed to loopback HTTP.
                with urlopen(  # nosec B310
                    f"http://127.0.0.1:{port}/_stcore/health",
                    timeout=1.0,
                ) as response:
                    if response.status == 200 and response.read().strip() == b"ok":
                        return
            except (URLError, TimeoutError):
                time.sleep(0.2)
        raise TimeoutError(f"Streamlit was not healthy within {timeout_seconds:g} seconds.")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8507)
    parser.add_argument("--timeout", type=float, default=30.0)
    arguments = parser.parse_args()
    smoke_test(port=arguments.port, timeout_seconds=arguments.timeout)
    print("Streamlit startup smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
