"""M5.4-A2: Subprocess test support for real CLI editor tests."""
import os, tempfile, shutil, time, subprocess, signal, http.client, json


def _copy_example(tmp):
    src = os.path.join(tmp, "src.toml")
    target = os.path.join(tmp, "target.toml")
    examples = os.path.join(os.path.dirname(__file__), "..", "examples",
                            "yyr4-control-from-20260711-backup.toml")
    shutil.copy(examples, src)
    return src, target


def start_editor_cli(tmp=None, port=0):
    """Start editor via CLI subprocess. Returns (proc, port, stdout_line)."""
    if tmp is None:
        tmp = tempfile.mkdtemp()
    src, target = _copy_example(tmp)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.path.dirname(__file__), "..", "src")
    cmd = ["python3", "-m", "yyr4_linux_control.management.cli", "editor",
           "--config", src, "--target", target, "--port", str(port),
           "--idle-timeout", "300"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=env, text=True, bufsize=1)
    url_line = proc.stdout.readline().strip()
    # Parse port from URL: http://127.0.0.1:PORT/bootstrap/TOKEN
    try:
        p = int(url_line.split(":")[2].split("/")[0])
    except (IndexError, ValueError):
        p = 0
    time.sleep(0.3)
    return proc, p, url_line


def bootstrap_http(port, btoken):
    """Bootstrap and return (cookie_header, pubid, csrf)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", f"/bootstrap/{btoken}")
    resp = conn.getresponse()
    set_cookie = resp.getheader("Set-Cookie", "")
    loc = resp.getheader("Location", "")
    resp.read(); conn.close()
    assert resp.status == 303, f"Bootstrap failed: {resp.status}"
    # Parse cookie and pubid
    ck = set_cookie.split(";")[0].strip()
    pubid = loc.strip("/").split("/")[-1] if loc else ""
    # Get CSRF from state
    conn2 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn2.request("GET", f"/s/{pubid}/api/v1/state", headers={"Cookie": ck})
    r2 = conn2.getresponse(); body = r2.read(); conn2.close()
    csrf = json.loads(body)["csrf_token"]
    return ck, pubid, csrf


def do_mutation(port, pubid, ck, csrf, control="A1", action=None):
    """Execute a set-action mutation via HTTP."""
    if action is None:
        action = {"type": "debug_log", "message": "subprocess-test"}
    data = json.dumps({"profile":"user","layer":"general","control":control,
                        "action_spec":action}).encode()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", f"/s/{pubid}/api/v1/control/set-action", body=data,
                 headers={"Content-Type":"application/json", "Cookie":ck,
                          "X-YYR4-CSRF-Token":csrf})
    resp = conn.getresponse(); resp.read(); conn.close()
    return resp.status


def wait_port_closed(port, timeout=5):
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        if s.connect_ex(("127.0.0.1", port)) != 0:
            s.close(); return True
        s.close(); time.sleep(0.2)
    return False


def cli_status():
    """Run yyr4ctl editor status, return (returncode, output)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.path.dirname(__file__), "..", "src")
    r = subprocess.run(["python3", "-m", "yyr4_linux_control.management.cli", "editor", "status"],
                       capture_output=True, text=True, env=env, timeout=10)
    return r.returncode, r.stdout + r.stderr


def cli_stop(session_id, discard=False):
    """Run yyr4ctl editor stop."""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.path.dirname(__file__), "..", "src")
    args = ["python3", "-m", "yyr4_linux_control.management.cli", "editor", "stop",
            "--session-id", str(session_id)]
    if discard:
        args.append("--discard-draft")
    r = subprocess.run(args, capture_output=True, text=True, env=env, timeout=15)
    return r.returncode, r.stdout + r.stderr


def count_test_pids():
    """Count processes matching our test pattern."""
    import subprocess
    r = subprocess.run(["pgrep", "-f", "yyr4_linux_control"], capture_output=True, text=True)
    return len([l for l in (r.stdout or "").split("\n") if l.strip()])



def get_session_id_for_pid(pid):
    """Find session_id in registry for a given PID."""
    from yyr4_linux_control.configurator.web.session import list_sessions
    for ses in list_sessions():
        if ses.get("pid") == pid:
            return ses.get("session_id", "")
    return ""
