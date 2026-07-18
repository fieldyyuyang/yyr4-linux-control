"""M5.4-A2: Real recovery lifecycle — SIGKILL → resume → save."""
import unittest, os, tempfile, shutil, time, signal, json, http.client
from pathlib import Path
from tests.editor_subprocess_test_support import (
    start_editor_cli, bootstrap_http, do_mutation, wait_port_closed,
    cli_status, cli_stop, get_session_id_for_pid, cli_recover_inspect,
)


def _wait_port(port, timeout=5):
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(0.1)
        if s.connect_ex(("127.0.0.1", port)) == 0: s.close(); return True
        s.close(); time.sleep(0.1)
    return False


class TestRecoveryLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _parse(self, ul):
        p = ul.strip().split("/")
        hp = p[2]; lst = p[-1] if p[-1] else p[-2]
        port = int(hp.split(":")[-1]) if ":" in hp else 0
        return port, lst

    def _source_path(self):
        return os.path.join(self.tmp, "src.toml")

    def _find_recovery_for_source(self, src_path):
        from yyr4_linux_control.configurator.web.session import list_recoveries
        recs = list_recoveries()
        self.assertGreater(len(recs), 0)
        for r in recs:
            if r.get("source", "") == src_path:
                return r["recovery_id"]
        self.fail(f"No recovery found for source: {src_path}")

    def test_sigkill_resume_save(self):
        from yyr4_linux_control.configurator.web.session import list_recoveries, get_recovery, discard_recovery
        proc, _, url = start_editor_cli(self.tmp)
        port, btok = self._parse(url)
        ck_old, pub_old, csrf_old = bootstrap_http(port, btok)
        do_mutation(port, pub_old, ck_old, csrf_old, "A1",
                    {"type":"debug_log","message":"lifecycle-test"})
        rid = self._find_recovery_for_source(self._source_path())
        rec = get_recovery(rid); mc_before = rec["mutation_count"]
        os.kill(proc.pid, signal.SIGKILL); self.assertEqual(proc.wait(timeout=10), -signal.SIGKILL)
        self.assertGreaterEqual(len(list_recoveries()), 1)
        rc, out = cli_status(); self.assertIn("stale", out.lower())
        rc_i, _ = cli_recover_inspect(rid); self.assertEqual(rc_i, 0)
        rec2 = get_recovery(rid); self.assertEqual(rec2["mutation_count"], mc_before)
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_source_sha_conflict(self):
        from yyr4_linux_control.configurator.web.session import list_recoveries, get_recovery, discard_recovery
        from yyr4_linux_control.control.config import load_control_config_from_file
        from yyr4_linux_control.configurator.serializer import serialize
        from yyr4_linux_control.control.models import ProfileId
        import hashlib, dataclasses, subprocess as sp

        proc, _, url = start_editor_cli(self.tmp)
        port, btok = self._parse(url)
        ck, pub, csrf = bootstrap_http(port, btok)
        do_mutation(port, pub, ck, csrf, "A1", {"type":"noop"})
        rid = self._find_recovery_for_source(self._source_path())
        rec = get_recovery(rid)

        os.kill(proc.pid, signal.SIGKILL)
        self.assertEqual(proc.wait(timeout=10), -signal.SIGKILL)

        src = rec.get("source", "")
        self.assertTrue(src and os.path.isfile(src))
        cfg = load_control_config_from_file(Path(src))
        orig_sha = hashlib.sha256(serialize(cfg).encode()).hexdigest()
        self.assertEqual(orig_sha, rec.get("base_sha256", ""))
        old_p = list(cfg.profiles.values())[0]
        new_pid = ProfileId("modified_test_profile")
        new_profile = dataclasses.replace(old_p, profile_id=new_pid)
        cfg.profiles[new_pid] = new_profile
        cfg2 = dataclasses.replace(cfg, default_profile=new_pid)
        new_content = serialize(cfg2)
        with open(src, "w") as f: f.write(new_content)
        cfg3 = load_control_config_from_file(Path(src))
        new_sha = hashlib.sha256(serialize(cfg3).encode()).hexdigest()
        self.assertNotEqual(new_sha, rec.get("base_sha256", ""))

        env = os.environ.copy()
        pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
        env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")
        args = ["python3", "-m", "yyr4_linux_control.management.cli", "editor", "recover", "resume",
                "--recovery-id", rid, "--port", "0", "--idle-timeout", "5"]
        proc2 = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT, env=env, text=True)
        try:
            out_full, _ = proc2.communicate(timeout=10)
            retcode = proc2.returncode
        except sp.TimeoutExpired:
            proc2.kill(); proc2.wait()
            self.fail("Recover resume should exit quickly on SHA conflict")
        self.assertNotEqual(retcode, 0)
        self.assertIn("concurrent_modification", out_full or "")
        self.assertNotIn("bootstrap", (out_full or "").lower())
        self.assertGreaterEqual(len(list_recoveries()), 1)
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_recover_resume_starts_new_editor(self):
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery, list_sessions
        import subprocess as sp
        proc, _, url = start_editor_cli(self.tmp)
        port, btok = self._parse(url)
        ck, pub, csrf = bootstrap_http(port, btok)
        do_mutation(port, pub, ck, csrf, "A1", {"type":"noop"})
        rid = self._find_recovery_for_source(self._source_path())
        old_url = url
        os.kill(proc.pid, signal.SIGKILL); proc.wait(timeout=10)
        env = os.environ.copy()
        pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
        env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")
        args = ["python3", "-m", "yyr4_linux_control.management.cli", "editor", "recover", "resume",
                "--recovery-id", rid, "--port", "0", "--idle-timeout", "60"]
        proc2 = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT, env=env, text=True)
        new_url = proc2.stdout.readline().strip(); self.assertTrue(new_url)
        self.assertNotEqual(new_url, old_url); self.assertIn("bootstrap", new_url)
        self.assertIsNone(proc2.poll())
        new_sid = get_session_id_for_pid(proc2.pid)
        self.assertTrue(new_sid, f"No session for PID {proc2.pid}")
        rc_s, _ = cli_stop(new_sid); self.assertEqual(rc_s, 0)
        proc2.communicate(timeout=10)
        self.assertEqual(proc2.returncode, 0)
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_resumed_editor_uses_fresh_authentication(self):
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        import subprocess as sp
        old_proc, _, old_url = start_editor_cli(self.tmp)
        op, ob = self._parse(old_url)
        old_ck, old_pub, old_csrf = bootstrap_http(op, ob)
        old_sid = get_session_id_for_pid(old_proc.pid)
        old_cookie_value = old_ck.split("=", 1)[1] if "=" in old_ck else old_ck
        do_mutation(op, old_pub, old_ck, old_csrf, "A1", {"type":"noop"})
        rid = self._find_recovery_for_source(self._source_path())
        os.kill(old_proc.pid, signal.SIGKILL)
        self.assertEqual(old_proc.wait(timeout=10), -signal.SIGKILL)
        env = os.environ.copy()
        pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
        env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")
        args = ["python3", "-m", "yyr4_linux_control.management.cli", "editor", "recover", "resume",
                "--recovery-id", rid, "--port", "0", "--idle-timeout", "120"]
        new_proc = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT, env=env, text=True)
        new_url = new_proc.stdout.readline().strip()
        self.assertTrue(new_url)
        np, nb = self._parse(new_url)
        conn = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn.request("GET", f"/bootstrap/{nb}")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 303)
        set_cookie = resp.getheader("Set-Cookie", "")
        loc = resp.getheader("Location", ""); resp.read(); conn.close()
        new_pub = loc.strip("/").split("/")[-1] if loc else ""
        new_ck = set_cookie.split(";")[0].strip()
        new_cookie_value = new_ck.split("=", 1)[1] if "=" in new_ck else new_ck
        conn2 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn2.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        r2 = conn2.getresponse(); body2 = r2.read(); conn2.close()
        self.assertEqual(r2.status, 200)
        new_csrf = json.loads(body2)["csrf_token"]
        new_sid = get_session_id_for_pid(new_proc.pid)
        self.assertNotEqual(new_url, old_url)
        self.assertNotEqual(new_pub, old_pub)
        self.assertNotEqual(new_sid, old_sid)
        self.assertNotEqual(new_cookie_value, old_cookie_value)
        self.assertNotEqual(new_csrf, old_csrf)
        conn3 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn3.request("GET", f"/s/{new_pub}/api/v1/state")
        self.assertEqual(conn3.getresponse().status, 401); conn3.close()
        conn4 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn4.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": old_ck})
        self.assertEqual(conn4.getresponse().status, 401); conn4.close()
        d = json.dumps({"profile":"user","layer":"general","control":"A2","action_spec":{"type":"noop"}}).encode()
        conn5 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn5.request("POST", f"/s/{new_pub}/api/v1/control/set-action", body=d,
                      headers={"Content-Type":"application/json","Cookie":old_ck,"X-YYR4-CSRF-Token":old_csrf})
        self.assertEqual(conn5.getresponse().status, 401); conn5.close()
        conn6 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn6.request("POST", f"/s/{new_pub}/api/v1/control/set-action", body=d,
                      headers={"Content-Type":"application/json","Cookie":new_ck,"X-YYR4-CSRF-Token":old_csrf})
        self.assertIn(conn6.getresponse().status, (401, 403)); conn6.close()
        conn7 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn7.request("POST", f"/s/{new_pub}/api/v1/control/set-action", body=d,
                      headers={"Content-Type":"application/json","Cookie":old_ck,"X-YYR4-CSRF-Token":new_csrf})
        self.assertEqual(conn7.getresponse().status, 401); conn7.close()
        self.assertEqual(do_mutation(np, new_pub, new_ck, new_csrf, "A3", {"type":"noop"}), 200)
        rc_s, _ = cli_stop(new_sid); self.assertEqual(rc_s, 0)
        new_proc.wait(timeout=10); self.assertEqual(new_proc.returncode, 0)
        dr = sp.run(["python3", "-m", "yyr4_linux_control.management.cli", "editor", "recover", "discard",
                     "--recovery-id", rid], capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(dr.returncode, 0)

    def test_resumed_editor_restores_draft_state(self):
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        import hashlib, subprocess as sp
        sentinel = {"type":"debug_log","message":"R2B_RECOVERED_DRAFT_SENTINEL"}
        old_proc, _, old_url = start_editor_cli(self.tmp)
        op, ob = self._parse(old_url)
        old_ck, old_pub, old_csrf = bootstrap_http(op, ob)
        spath = self._source_path()
        with open(spath, "rb") as _fx: src_bytes = _fx.read()
        src_sha = hashlib.sha256(src_bytes).hexdigest()
        do_mutation(op, old_pub, old_ck, old_csrf, "A1", sentinel)
        conn = http.client.HTTPConnection("127.0.0.1", op, timeout=5)
        conn.request("GET", f"/s/{old_pub}/api/v1/state", headers={"Cookie": old_ck})
        state_before = json.loads(conn.getresponse().read()); conn.close()
        conn2 = http.client.HTTPConnection("127.0.0.1", op, timeout=5)
        conn2.request("GET", f"/s/{old_pub}/api/v1/diff", headers={"Cookie": old_ck})
        diff_before = json.loads(conn2.getresponse().read()); conn2.close()
        change_count_before = diff_before.get("change_count", 0)
        rid = self._find_recovery_for_source(spath)
        os.kill(old_proc.pid, signal.SIGKILL)
        self.assertEqual(old_proc.wait(timeout=10), -signal.SIGKILL)
        env = os.environ.copy()
        pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
        env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")
        args = ["python3", "-m", "yyr4_linux_control.management.cli", "editor", "recover", "resume",
                "--recovery-id", rid, "--port", "0", "--idle-timeout", "120"]
        new_proc = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT, env=env, text=True)
        new_url = new_proc.stdout.readline().strip(); self.assertTrue(new_url)
        np, nb = self._parse(new_url)
        _wait_port(np)
        new_ck, new_pub, new_csrf = bootstrap_http(np, nb)
        conn3 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn3.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        state_after = json.loads(conn3.getresponse().read()); conn3.close()
        conn4 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn4.request("GET", f"/s/{new_pub}/api/v1/diff", headers={"Cookie": new_ck})
        diff_after = json.loads(conn4.getresponse().read()); conn4.close()
        change_count_after = diff_after.get("change_count", 0)
        self.assertEqual(change_count_after, change_count_before)
        self.assertGreater(change_count_after, 0)
        config = state_after.get("config", {})
        self.assertIn("R2B_RECOVERED_DRAFT_SENTINEL", json.dumps(config))
        with open(spath, "rb") as _fy: self.assertEqual(_fy.read(), src_bytes)
        with open(spath, "rb") as _fz: self.assertEqual(hashlib.sha256(_fz.read()).hexdigest(), src_sha)
        new_sid = get_session_id_for_pid(new_proc.pid)
        rc_s, _ = cli_stop(new_sid); self.assertEqual(rc_s, 0)
        new_proc.wait(timeout=10); self.assertEqual(new_proc.returncode, 0)
        self.assertGreaterEqual(len(list_recoveries()), 1)
        dr = sp.run(["python3", "-m", "yyr4_linux_control.management.cli", "editor", "recover", "discard",
                     "--recovery-id", rid], capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(dr.returncode, 0)

    def test_resumed_editor_exposes_restored_draft_over_http(self):
        from yyr4_linux_control.configurator.web.session import list_recoveries, get_recovery
        import hashlib, subprocess as sp
        sentinel = {"type":"debug_log","message":"R2B2_HTTP_RECOVERY_SENTINEL"}
        old_proc, _, old_url = start_editor_cli(self.tmp)
        op, ob = self._parse(old_url)
        old_ck, old_pub, old_csrf = bootstrap_http(op, ob)
        spath = self._source_path()
        with open(spath, "rb") as _fx: src_bytes = _fx.read()
        src_sha = hashlib.sha256(src_bytes).hexdigest()
        do_mutation(op, old_pub, old_ck, old_csrf, "A1", sentinel)
        conn = http.client.HTTPConnection("127.0.0.1", op, timeout=5)
        conn.request("GET", f"/s/{old_pub}/api/v1/state", headers={"Cookie": old_ck})
        state_before = json.loads(conn.getresponse().read()); conn.close()
        mc_before = state_before["config"]["mutation_count"]
        dirty_before = state_before["config"]["dirty"]
        self.assertIsInstance(mc_before, int)
        self.assertGreater(mc_before, 0)
        self.assertTrue(dirty_before)
        conn2 = http.client.HTTPConnection("127.0.0.1", op, timeout=5)
        conn2.request("GET", f"/s/{old_pub}/api/v1/diff", headers={"Cookie": old_ck})
        diff_before = json.loads(conn2.getresponse().read()); conn2.close()
        rid = self._find_recovery_for_source(spath)
        rec = get_recovery(rid)
        os.kill(old_proc.pid, signal.SIGKILL)
        self.assertEqual(old_proc.wait(timeout=10), -signal.SIGKILL)
        env = os.environ.copy()
        pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
        env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")
        args = ["python3", "-m", "yyr4_linux_control.management.cli", "editor", "recover", "resume",
                "--recovery-id", rid, "--port", "0", "--idle-timeout", "120"]
        new_proc = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT, env=env, text=True)
        new_url = new_proc.stdout.readline().strip(); self.assertTrue(new_url)
        np, nb = self._parse(new_url)
        _wait_port(np)
        new_ck, new_pub, new_csrf = bootstrap_http(np, nb)
        new_sid = get_session_id_for_pid(new_proc.pid); self.assertTrue(new_sid)
        conn3 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn3.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        r3 = conn3.getresponse(); state_after = json.loads(r3.read()); conn3.close()
        self.assertEqual(r3.status, 200)
        conn4 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn4.request("GET", f"/s/{new_pub}/api/v1/diff", headers={"Cookie": new_ck})
        diff_after = json.loads(conn4.getresponse().read()); conn4.close()
        mc_after = state_after["config"]["mutation_count"]
        dirty_after = state_after["config"]["dirty"]
        self.assertEqual(mc_after, mc_before)
        self.assertTrue(dirty_after)
        self.assertGreater(mc_after, 0)
        self.assertIn("R2B2_HTTP_RECOVERY_SENTINEL", json.dumps(state_after))
        changes = diff_after.get("changes", [])
        self.assertGreater(len(changes), 0)
        diff_text = json.dumps(diff_after)
        self.assertIn("A1", diff_text)
        self.assertIn("DebugLog", diff_text)
        with open(spath, "rb") as _fy: self.assertEqual(_fy.read(), src_bytes)
        with open(spath, "rb") as _fz: self.assertEqual(hashlib.sha256(_fz.read()).hexdigest(), src_sha)
        rc_s, _ = cli_stop(new_sid); self.assertEqual(rc_s, 0)
        new_proc.wait(timeout=10); self.assertEqual(new_proc.returncode, 0)
        from yyr4_linux_control.configurator.web.session import list_recoveries as lr2, discard_recovery as drr2
        self.assertGreaterEqual(len(lr2()), 1)
        sp.run(["python3","-m","yyr4_linux_control.management.cli","editor","recover","discard",
                "--recovery-id",rid], capture_output=True, text=True, env=env, timeout=10)

    def test_recovered_session_registry_contains_recovery_id(self):
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery, list_sessions
        import subprocess as sp
        old_proc, _, old_url = start_editor_cli(self.tmp)
        op, ob = self._parse(old_url)
        old_ck, old_pub, old_csrf = bootstrap_http(op, ob)
        do_mutation(op, old_pub, old_ck, old_csrf, "A1", {"type":"noop"})
        rid = self._find_recovery_for_source(self._source_path())
        os.kill(old_proc.pid, signal.SIGKILL); old_proc.wait(timeout=10)
        env = os.environ.copy()
        pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
        env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")
        args = ["python3", "-m", "yyr4_linux_control.management.cli", "editor", "recover", "resume",
                "--recovery-id", rid, "--port", "0", "--idle-timeout", "120"]
        new_proc = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT, env=env, text=True)
        new_url = new_proc.stdout.readline().strip(); self.assertTrue(new_url)
        np, nb = self._parse(new_url)
        _wait_port(np)
        new_ck, new_pub, new_csrf = bootstrap_http(np, nb)
        sessions = list_sessions()
        resumed_reg = next((ses for ses in sessions if ses.get("pid") == new_proc.pid), None)
        self.assertIsNotNone(resumed_reg)
        self.assertEqual(resumed_reg.get("recovery_id"), rid)
        conn = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        conn.getresponse().read(); conn.close()
        sessions2 = list_sessions()
        resumed2 = next((ses for ses in sessions2 if ses.get("pid") == new_proc.pid), None)
        self.assertEqual(resumed2.get("recovery_id"), rid)
        new_sid = get_session_id_for_pid(new_proc.pid)
        new_proc.stdout.close(); cli_stop(new_sid); new_proc.wait(timeout=10)
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_normal_session_registry_has_null_recovery_id(self):
        from yyr4_linux_control.configurator.web.session import list_sessions
        proc, _, url = start_editor_cli(self.tmp)
        port, btok = self._parse(url)
        ck, pub, csrf = bootstrap_http(port, btok)
        sessions = list_sessions()
        reg = next((ses for ses in sessions if ses.get("pid") == proc.pid), None)
        self.assertIsNotNone(reg)
        self.assertIsNone(reg.get("recovery_id"))
        sid = get_session_id_for_pid(proc.pid)
        cli_stop(sid); proc.wait(timeout=15)
        self.assertEqual(proc.returncode, 0)

    def test_review_endpoint_marks_current_mutation_reviewed(self):
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        proc, _, url = start_editor_cli(self.tmp)
        port, btok = self._parse(url)
        ck, pub, csrf = bootstrap_http(port, btok)
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", f"/s/{pub}/api/v1/state", headers={"Cookie": ck})
        state = json.loads(conn.getresponse().read()); conn.close()
        self.assertFalse(state["config"]["dirty"])
        mc0 = state["config"]["mutation_count"]
        do_mutation(port, pub, ck, csrf, "A1", {"type":"debug_log","message":"review-sentinel"})
        conn2 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn2.request("GET", f"/s/{pub}/api/v1/state", headers={"Cookie": ck})
        state2 = json.loads(conn2.getresponse().read()); conn2.close()
        mc_before = state2["config"]["mutation_count"]
        self.assertGreater(mc_before, mc0)
        self.assertTrue(state2["config"]["dirty"])
        conn3 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn3.request("POST", f"/s/{pub}/api/v1/review", body=b"{}",
                      headers={"Content-Type":"application/json","Cookie":ck,"X-YYR4-CSRF-Token":csrf})
        r3 = conn3.getresponse(); rev_body = json.loads(r3.read()); conn3.close()
        self.assertEqual(r3.status, 200)
        self.assertTrue(rev_body.get("reviewed"))
        conn4 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn4.request("GET", f"/s/{pub}/api/v1/state", headers={"Cookie": ck})
        state3 = json.loads(conn4.getresponse().read()); conn4.close()
        self.assertTrue(state3["config"]["dirty"])
        self.assertEqual(state3["config"]["mutation_count"], mc_before)
        conn5 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn5.request("POST", f"/s/{pub}/api/v1/review", body=b"{}", headers={"Content-Type":"application/json"})
        self.assertIn(conn5.getresponse().status, (401, 400)); conn5.close()
        conn6 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn6.request("POST", f"/s/{pub}/api/v1/review", body=b"{}",
                      headers={"Content-Type":"application/json","Cookie":ck})
        self.assertIn(conn6.getresponse().status, (401, 403)); conn6.close()
        conn7 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn7.request("POST", f"/s/{pub}/api/v1/review", body=b"{}",
                      headers={"Content-Type":"application/json","Cookie":ck,"X-YYR4-CSRF-Token":"wrong-csrf"})
        self.assertIn(conn7.getresponse().status, (401, 403)); conn7.close()
        do_mutation(port, pub, ck, csrf, "A2", {"type":"noop"})
        conn8 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn8.request("GET", f"/s/{pub}/api/v1/state", headers={"Cookie": ck})
        state4 = json.loads(conn8.getresponse().read()); conn8.close()
        self.assertGreater(state4["config"]["mutation_count"], mc_before)
        sid = get_session_id_for_pid(proc.pid); cli_stop(sid); proc.wait(timeout=5)
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_resumed_session_can_be_marked_reviewed_over_http(self):
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        import subprocess as sp
        sentinel = {"type":"debug_log","message":"R3_REVIEW_RECOVERY"}
        old_proc, _, old_url = start_editor_cli(self.tmp)
        op, ob = self._parse(old_url)
        old_ck, old_pub, old_csrf = bootstrap_http(op, ob)
        do_mutation(op, old_pub, old_ck, old_csrf, "A1", sentinel)
        rid = self._find_recovery_for_source(self._source_path())
        os.kill(old_proc.pid, signal.SIGKILL); self.assertEqual(old_proc.wait(timeout=10), -signal.SIGKILL)
        env = os.environ.copy()
        pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
        env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")
        args = ["python3", "-m", "yyr4_linux_control.management.cli", "editor", "recover", "resume",
                "--recovery-id", rid, "--port", "0", "--idle-timeout", "120"]
        new_proc = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT, env=env, text=True)
        new_url = new_proc.stdout.readline().strip(); self.assertTrue(new_url)
        np, nb = self._parse(new_url)
        _wait_port(np)
        new_ck, new_pub, new_csrf = bootstrap_http(np, nb)
        conn = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        state_pre = json.loads(conn.getresponse().read()); conn.close()
        mc_pre = state_pre["config"]["mutation_count"]
        self.assertGreater(mc_pre, 0)
        conn2 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn2.request("POST", f"/s/{new_pub}/api/v1/review", body=b"{}",
                      headers={"Content-Type":"application/json","Cookie":new_ck,"X-YYR4-CSRF-Token":new_csrf})
        self.assertEqual(conn2.getresponse().status, 200); conn2.close()
        conn3 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn3.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        state3 = json.loads(conn3.getresponse().read()); conn3.close()
        self.assertTrue(state3["config"]["dirty"])
        self.assertEqual(state3["config"]["mutation_count"], mc_pre)
        new_sid = get_session_id_for_pid(new_proc.pid)
        new_proc.stdout.close(); cli_stop(new_sid); new_proc.wait(timeout=10)
        for r in list_recoveries(): discard_recovery(r["recovery_id"])


    def test_resumed_editor_review_save_closes_recovery(self):
        """Review + Save on resumed Editor: writes Target, closes Recovery, clean session."""
        from yyr4_linux_control.configurator.web.session import list_recoveries, get_recovery, discard_recovery
        from yyr4_linux_control.control.config import load_control_config_from_file
        import hashlib, subprocess as sp

        sentinel = {"type":"debug_log","message":"R3A3_REVIEW_SAVE_SENTINEL"}
        old_proc, _, old_url = start_editor_cli(self.tmp)
        op, ob = self._parse(old_url)
        old_ck, old_pub, old_csrf = bootstrap_http(op, ob)
        spath = self._source_path()
        with open(spath, "rb") as _fx: src_bytes = _fx.read()
        src_sha = hashlib.sha256(src_bytes).hexdigest()
        tpath = os.path.join(self.tmp, "target.toml")
        # Mutation
        do_mutation(op, old_pub, old_ck, old_csrf, "A1", sentinel)
        conn = http.client.HTTPConnection("127.0.0.1", op, timeout=5)
        conn.request("GET", f"/s/{old_pub}/api/v1/state", headers={"Cookie": old_ck})
        sb = json.loads(conn.getresponse().read()); conn.close()
        mc_before = sb["config"]["mutation_count"]
        self.assertTrue(sb["config"]["dirty"])
        rid = self._find_recovery_for_source(spath)
        rec = get_recovery(rid)
        manifest_target = rec.get("target", "")
        os.kill(old_proc.pid, signal.SIGKILL)
        self.assertEqual(old_proc.wait(timeout=10), -signal.SIGKILL)
        # Recover resume — no config/target
        env = os.environ.copy()
        pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
        env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")
        args = ["python3","-m","yyr4_linux_control.management.cli","editor","recover","resume",
                "--recovery-id",rid,"--port","0","--idle-timeout","120"]
        new_proc = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT, env=env, text=True)
        new_url = new_proc.stdout.readline().strip(); self.assertTrue(new_url)
        np, nb = self._parse(new_url)
        _wait_port(np)
        new_ck, new_pub, new_csrf = bootstrap_http(np, nb)
        new_sid = get_session_id_for_pid(new_proc.pid); self.assertTrue(new_sid)
        # Registry recovery_id before save
        from yyr4_linux_control.configurator.web.session import list_sessions as ls_before
        reg_before = next((s for s in ls_before() if s.get("pid") == new_proc.pid), None)
        self.assertIsNotNone(reg_before)
        self.assertEqual(reg_before.get("recovery_id"), rid, "Registry must have recovery_id before save")
        # Pre-review state
        conn2 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn2.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        sp2 = json.loads(conn2.getresponse().read()); conn2.close()
        self.assertTrue(sp2["config"]["dirty"])
        self.assertEqual(sp2["config"]["mutation_count"], mc_before)
        # Review
        conn_r = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_r.request("POST", f"/s/{new_pub}/api/v1/review", body=b"{}",
                       headers={"Content-Type":"application/json","Cookie":new_ck,"X-YYR4-CSRF-Token":new_csrf})
        rr = conn_r.getresponse(); rev = json.loads(rr.read()); conn_r.close()
        self.assertEqual(rr.status, 200)
        self.assertTrue(rev.get("reviewed"))
        conn_r2 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_r2.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        srv = json.loads(conn_r2.getresponse().read()); conn_r2.close()
        self.assertTrue(srv["config"]["dirty"])
        self.assertEqual(srv["config"]["mutation_count"], mc_before)
        # Save
        conn_s = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_s.request("POST", f"/s/{new_pub}/api/v1/save", body=b"{}",
                       headers={"Content-Type":"application/json","Cookie":new_ck,"X-YYR4-CSRF-Token":new_csrf})
        rs = conn_s.getresponse(); save_body = json.loads(rs.read()); conn_s.close()
        self.assertEqual(rs.status, 200)
        self.assertEqual(save_body.get("status"), "ok")
        # Post-save state
        conn_a = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_a.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        spa = json.loads(conn_a.getresponse().read()); conn_a.close()
        self.assertFalse(spa["config"]["dirty"])
        self.assertEqual(spa["config"]["mutation_count"], 0)
        # Post-save Diff empty
        conn_d = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_d.request("GET", f"/s/{new_pub}/api/v1/diff", headers={"Cookie": new_ck})
        diff_post = json.loads(conn_d.getresponse().read()); conn_d.close()
        self.assertEqual(diff_post.get("change_count", 1), 0)
        # Target written to manifest target
        tgt = manifest_target or tpath
        self.assertTrue(os.path.isfile(tgt))
        tgt_cfg = load_control_config_from_file(Path(tgt))
        prof = list(tgt_cfg.profiles.values())[0]
        a1 = prof.layers["general"].controls.get("A1")
        self.assertIsNotNone(a1)
        if hasattr(a1, "message"):
            self.assertEqual(a1.message, "R3A3_REVIEW_SAVE_SENTINEL")
        # Source unchanged
        with open(spath, "rb") as _fy: self.assertEqual(_fy.read(), src_bytes)
        with open(spath, "rb") as _fz: self.assertEqual(hashlib.sha256(_fz.read()).hexdigest(), src_sha)
        # Registry recovery_id cleared after save
        from yyr4_linux_control.configurator.web.session import list_sessions as ls_after
        reg_after = next((s for s in ls_after() if s.get("pid") == new_proc.pid), None)
        self.assertIsNotNone(reg_after, "Registry must still exist after save")
        self.assertIsNone(reg_after.get("recovery_id"), "Registry recovery_id must be null after save")
        # Recovery deleted by save
        self.assertIsNone(get_recovery(rid), "Recovery must be deleted after save (discard_recovery)")
        # Session still running
        self.assertIsNone(new_proc.poll())
        # Stop
        rc_s, _ = cli_stop(new_sid); self.assertEqual(rc_s, 0)
        new_proc.wait(timeout=10); self.assertEqual(new_proc.returncode, 0)


    def test_saved_resumed_session_creates_new_recovery_on_next_mutation(self):
        """After Save deletes Recovery, new Mutation creates a NEW recovery_id."""
        from yyr4_linux_control.configurator.web.session import list_recoveries, get_recovery, discard_recovery, list_sessions
        from yyr4_linux_control.control.config import load_control_config_from_file
        import hashlib, subprocess as sp

        sentinel1 = {"type":"debug_log","message":"R3B2_FIRST_SAVED_SENTINEL"}
        sentinel2 = {"type":"debug_log","message":"R3B2_NEW_RECOVERY_SENTINEL"}

        # 1. Start editor, mutate, get recovery
        old_proc, _, old_url = start_editor_cli(self.tmp)
        op, ob = self._parse(old_url)
        old_ck, old_pub, old_csrf = bootstrap_http(op, ob)
        spath = self._source_path()
        with open(spath, "rb") as _fx: src_bytes = _fx.read()
        src_sha = hashlib.sha256(src_bytes).hexdigest()
        do_mutation(op, old_pub, old_ck, old_csrf, "A1", sentinel1)
        old_rid = self._find_recovery_for_source(spath)
        self.assertTrue(old_rid)
        os.kill(old_proc.pid, signal.SIGKILL)
        self.assertEqual(old_proc.wait(timeout=10), -signal.SIGKILL)

        # 2. Recover resume
        env = os.environ.copy()
        pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
        env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")
        args = ["python3","-m","yyr4_linux_control.management.cli","editor","recover","resume",
                "--recovery-id",old_rid,"--port","0","--idle-timeout","120"]
        new_proc = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT, env=env, text=True)
        new_url = new_proc.stdout.readline().strip(); self.assertTrue(new_url)
        np, nb = self._parse(new_url)
        _wait_port(np)
        new_ck, new_pub, new_csrf = bootstrap_http(np, nb)
        new_sid = get_session_id_for_pid(new_proc.pid); self.assertTrue(new_sid)

        # 3. Review + Save
        conn_r = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_r.request("POST", f"/s/{new_pub}/api/v1/review", body=b"{}",
                       headers={"Content-Type":"application/json","Cookie":new_ck,"X-YYR4-CSRF-Token":new_csrf})
        self.assertEqual(conn_r.getresponse().status, 200); conn_r.close()
        conn_s = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_s.request("POST", f"/s/{new_pub}/api/v1/save", body=b"{}",
                       headers={"Content-Type":"application/json","Cookie":new_ck,"X-YYR4-CSRF-Token":new_csrf})
        rs = conn_s.getresponse(); sv = json.loads(rs.read()); conn_s.close()
        self.assertEqual(rs.status, 200)
        self.assertEqual(sv.get("status"), "ok")
        # Verify old recovery gone, registry null
        self.assertIsNone(get_recovery(old_rid))
        reg = next((s for s in list_sessions() if s.get("pid") == new_proc.pid), None)
        self.assertIsNotNone(reg)
        self.assertIsNone(reg.get("recovery_id"))

        # 4. Second mutation (same session, no stop)
        self.assertEqual(do_mutation(np, new_pub, new_ck, new_csrf, "A1", sentinel2), 200)
        conn_st = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_st.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        sp3 = json.loads(conn_st.getresponse().read()); conn_st.close()
        self.assertTrue(sp3["config"]["dirty"])
        self.assertEqual(sp3["config"]["mutation_count"], 1)
        self.assertIn("R3B2_NEW_RECOVERY_SENTINEL", json.dumps(sp3))

        # 5. Verify NEW recovery created with different ID
        reg2 = next((s for s in list_sessions() if s.get("pid") == new_proc.pid), None)
        new_rid = reg2.get("recovery_id")
        self.assertIsNotNone(new_rid, "Registry must have new recovery_id after new mutation")
        self.assertNotEqual(new_rid, old_rid, "New recovery_id must differ from old")
        # Old still gone
        self.assertIsNone(get_recovery(old_rid))
        # New exists
        new_rec = get_recovery(new_rid)
        self.assertIsNotNone(new_rec, "New recovery must exist")
        self.assertEqual(new_rec.get("recovery_id"), new_rid)
        # Source unchanged
        with open(spath, "rb") as _fy: self.assertEqual(_fy.read(), src_bytes)
        # Target still has first sentinel (not yet re-saved)
        tpath = new_rec.get("target", "")
        if tpath and os.path.isfile(tpath):
            tcfg = load_control_config_from_file(Path(tpath))
            prof = list(tcfg.profiles.values())[0]
            a1t = prof.layers["general"].controls.get("A1")
            if hasattr(a1t, "message"):
                self.assertEqual(a1t.message, "R3B2_FIRST_SAVED_SENTINEL")

        # 6. Stop (dirty, recovery preserved)
        rc_s, _ = cli_stop(new_sid); self.assertEqual(rc_s, 0)
        new_proc.wait(timeout=10); self.assertEqual(new_proc.returncode, 0)
        self.assertIsNotNone(get_recovery(new_rid), "New recovery must persist after dirty stop")

        # 7. Discard
        dr = sp.run(["python3","-m","yyr4_linux_control.management.cli","editor","recover","discard",
                     "--recovery-id", new_rid], capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(dr.returncode, 0)


if __name__ == "__main__":
    unittest.main()
