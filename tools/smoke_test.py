"""Start a built executable and check that it stays up and that a second launch reaches it.

    python tools/smoke_test.py path/to/Open-Clipboard-Manager [startup-seconds]

Used by the release workflow on every OS. The second launch (`--show`) must hand over to the running copy
and exit by itself; if the single-instance link is broken it would start a second app and time out.
"""
import os
import signal
import subprocess
import sys
import tempfile
import time


def kill_tree(proc):
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def main():
    exe = sys.argv[1]
    startup = float(sys.argv[2]) if len(sys.argv) > 2 else 15
    home = tempfile.mkdtemp(prefix="ocm-smoke-")  # keep the real data folders out of it
    env = {**os.environ, "APPDATA": home, "XDG_DATA_HOME": home, "HOME": home}
    popen = dict(env=env)
    if os.name != "nt":
        popen["start_new_session"] = True  # so the whole process tree can be killed together
    first = subprocess.Popen([exe], **popen)
    try:
        time.sleep(startup)
        if first.poll() is not None:
            sys.exit(f"FAIL: the app exited during start-up with code {first.returncode}")
        print(f"ok: still running after {startup:.0f}s")
        second = subprocess.Popen([exe, "--show"], **popen)
        try:
            code = second.wait(timeout=60)
        except subprocess.TimeoutExpired:
            kill_tree(second)
            sys.exit("FAIL: a second launch did not hand over to the running app (it started its own copy)")
        if code != 0:
            sys.exit(f"FAIL: the second launch exited with code {code}")
        print("ok: the second launch handed over to the running app and exited")
        if first.poll() is not None:
            sys.exit(f"FAIL: the app exited after the second launch (code {first.returncode})")
        print("ok: the first copy is still running")
    finally:
        kill_tree(first)


if __name__ == "__main__":
    main()
