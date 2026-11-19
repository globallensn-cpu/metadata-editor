"""Reaboard Secure Subprocess Execution Utility.

Enforces argument-list execution (shell=False), hard timeouts with process-group kill,
capped stdout/stderr capture, and asynchronous thread dispatching.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from dataclasses import dataclass

DEFAULT_MAX_OUTPUT_BYTES = 10 * 1024 * 1024  # 10 MB cap


@dataclass(frozen=True)
class CmdResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def run_command_secure(
    args: list[str],
    timeout_seconds: int = 120,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> CmdResult:
    """Execute a CLI tool synchronously with strict sandbox isolation."""
    # Ensure all arguments are strings
    cmd_list = [str(a) for a in args]

    # Process group setup
    kwargs: dict = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "shell": False,
    }

    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(cmd_list, **kwargs)
        stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout_seconds)

        stdout_str = stdout_bytes[:max_output_bytes].decode("utf-8", errors="replace")
        stderr_str = stderr_bytes[:max_output_bytes].decode("utf-8", errors="replace")

        return CmdResult(
            returncode=proc.returncode,
            stdout=stdout_str,
            stderr=stderr_str,
            timed_out=False,
        )

    except subprocess.TimeoutExpired:
        # Kill the entire process group
        _kill_process_group(proc.pid)
        try:
            out, err = proc.communicate(timeout=2)
            stdout_str = out[:max_output_bytes].decode("utf-8", errors="replace")
            stderr_str = err[:max_output_bytes].decode("utf-8", errors="replace")
        except Exception:
            stdout_str, stderr_str = "", ""

        return CmdResult(
            returncode=-1,
            stdout=stdout_str,
            stderr=stderr_str,
            timed_out=True,
        )


def _kill_process_group(pid: int) -> None:
    """Terminate the process group on Windows or POSIX."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
        else:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGKILL)
    except Exception:
        pass


async def run_command_async(
    args: list[str],
    timeout_seconds: int = 120,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> CmdResult:
    """Asynchronous wrapper that offloads subprocess execution to a thread pool."""
    return await asyncio.to_thread(
        run_command_secure,
        args=args,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )
