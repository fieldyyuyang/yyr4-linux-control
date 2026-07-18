"""M5.4-A2-R4b1b: Installed CLI recovery — no host product imports, exact assertions."""
import unittest, os, tempfile, shutil, subprocess, sys, signal, time, json, http.client, hashlib, stat, textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestInstalledPackageRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.wheel_dir = cls.tmp / "wheel"; cls.wheel_dir.mkdir()
        cls.venv_dir = cls.tmp / "venv"
        cls.home = cls.tmp / "home"
        cls.xdg_config = cls.tmp / "xdg_config"
        cls.xdg_state = cls.tmp / "xdg_state"
        cls.xdg_cache = cls.tmp / "xdg_cache"
        cls.xdg_runtime = cls.tmp / "xdg_runtime"
        for d in [cls.home, cls.xdg_config, cls.xdg_state, cls.xdg_cache, cls.xdg_runtime]:
            d.mkdir(parents=True, exist_ok=True)
        os.chmod(str(cls.xdg_runtime), 0o700)
        build_env = os.environ.copy()
        build_env.pop("PYTHONPATH", None)
        build_env["PYTHONNOUSERSITE"] = "1"; build_env["PIP_NO_INDEX"] = "1"
        build_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        for v in ["PIP_INDEX_URL","PIP_EXTRA_INDEX_URL","PIP_TRUSTED_HOST","PIP_FIND_LINKS"]:
            build_env.pop(v, None)
        r_b = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-index",
             "--no-build-isolation", "--wheel-dir", str(cls.wheel_dir), str(REPO_ROOT)],
            capture_output=True, text=True, timeout=120, cwd=str(cls.tmp), env=build_env)
        assert r_b.returncode == 0, f"Build failed: {r_b.stderr[:300]}"
        cls.wheel_path = list(cls.wheel_dir.glob("*.whl"))[0]
        subprocess.run([sys.executable, "-m", "venv", str(cls.venv_dir)], capture_output=True, timeout=30)
        inst_env = os.environ.copy()
        inst_env.pop("PYTHONPATH", None); inst_env["PYTHONNOUSERSITE"] = "1"
        inst_env["PIP_NO_INDEX"] = "1"; inst_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        r_i = subprocess.run(
            [str(cls.venv_dir / "bin" / "python"), "-m", "pip", "install",
             "--no-deps", "--no-index", str(cls.wheel_path)],
            capture_output=True, text=True, timeout=60, cwd=str(cls.tmp), env=inst_env)
        assert r_i.returncode == 0, f"Install failed: {r_i.stderr[:300]}"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.tmp), ignore_errors=True)

    def _venv_env(self):
        env = os.environ.copy()
        env.pop("PYTHONPATH", None); env["PYTHONNOUSERSITE"] = "1"
        env["HOME"] = str(self.home)
        env["XDG_CONFIG_HOME"] = str(self.xdg_config)
        env["XDG_STATE_HOME"] = str(self.xdg_state)
        env["XDG_CACHE_HOME"] = str(self.xdg_cache)
        env["XDG_RUNTIME_DIR"] = str(self.xdg_runtime)
        return env

    def _yyr4ctl(self, *args, timeout=15):
        return subprocess.run([str(self.venv_dir / "bin" / "yyr4ctl")] + list(args),
                              capture_output=True, text=True, timeout=timeout,
                              cwd=str(self.tmp), env=self._venv_env())

    def test_installed_editor_recovery_survives_sigkill(self):
        cli = str(self.venv_dir / "bin" / "yyr4ctl")
        src = self.tmp / "src.toml"
        tgt = self.tmp / "target.toml"
        example = REPO_ROOT / "examples" / "yyr4-control-from-20260711-backup.toml"
        shutil.copy(str(example), str(src))
        src_bytes = src.read_bytes()
        src_sha = hashlib.sha256(src_bytes).hexdigest()

        # Start editor
        proc = subprocess.Popen(
            [cli, "editor", "--config", str(src), "--target", str(tgt),
             "--port", "0", "--idle-timeout", "300"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            cwd=str(self.tmp), env=self._venv_env())
        url_line = proc.stdout.readline().strip()
        self.assertTrue(url_line)
        if "http://" in url_line:
            url_line = url_line[url_line.index("http://"):]
        self.assertIn("bootstrap", url_line)
        parts = url_line.split("/"); port = int(parts[2].split(":")[1]); btok = parts[-1]

        # Bootstrap
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", f"/bootstrap/{btok}")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 303)
        ck = resp.getheader("Set-Cookie", "").split(";")[0].strip()
        loc = resp.getheader("Location", ""); pub = loc.strip("/").split("/")[-1] if loc else ""
        resp.read(); conn.close()
        conn2 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn2.request("GET", f"/s/{pub}/api/v1/state", headers={"Cookie": ck})
        csrf = json.loads(conn2.getresponse().read())["csrf_token"]; conn2.close()

        # Mutate
        sentinel = {"type":"debug_log","message":"R4B1_INSTALLED_SIGKILL_SENTINEL"}
        d = json.dumps({"profile":"user","layer":"general","control":"A1",
                         "action_spec": sentinel}).encode()
        conn3 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn3.request("POST", f"/s/{pub}/api/v1/control/set-action", body=d,
                      headers={"Content-Type":"application/json","Cookie":ck,
                               "X-YYR4-CSRF-Token": csrf})
        self.assertEqual(conn3.getresponse().status, 200); conn3.close()

        # HTTP state verification
        conn4 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn4.request("GET", f"/s/{pub}/api/v1/state", headers={"Cookie": ck})
        state = json.loads(conn4.getresponse().read()); conn4.close()
        self.assertTrue(state["config"]["dirty"])
        mc = state["config"]["mutation_count"]
        self.assertIsInstance(mc, int); self.assertGreater(mc, 0)
        self.assertIn("R4B1_INSTALLED_SIGKILL_SENTINEL", json.dumps(state))
        conn5 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn5.request("GET", f"/s/{pub}/api/v1/diff", headers={"Cookie": ck})
        diff = json.loads(conn5.getresponse().read()); conn5.close()
        self.assertGreater(diff.get("change_count", 0), 0)

        # ── Recovery ID from installed CLI list output (JSON) ──
        r_list = self._yyr4ctl("editor", "recover", "list")
        self.assertEqual(r_list.returncode, 0)
        dec = json.JSONDecoder(); pos = 0; s = r_list.stdout.strip(); recs = []
        while pos < len(s):
            while pos < len(s) and s[pos] in " \t\n\r": pos += 1
            if pos >= len(s): break
            obj, end = dec.raw_decode(s, pos); recs.append(obj); pos = end
        self.assertGreater(len(recs), 0, "No recoveries in CLI list")
        rid = None
        for rec in recs:
            if Path(rec.get("source","")).resolve() == src.resolve():
                if rid is not None:
                    self.fail(f"Multiple CLI entries match: {rid},{rec['recovery_id']}")
                rid = rec["recovery_id"]
        self.assertIsNotNone(rid, f"No CLI entry matching {src}")

        # Inspect via CLI
        r_insp = self._yyr4ctl("editor","recover","inspect","--recovery-id",rid)
        self.assertEqual(r_insp.returncode, 0)

        # ── Exact manifest assertions ──
        rec_base = self.xdg_state / "yyr4" / "editor-recovery"
        rec_dir = rec_base / rid
        mf = json.loads((rec_dir / "manifest.json").read_text())
        self.assertEqual(mf["recovery_id"], rid)
        self.assertEqual(Path(mf["source"]).resolve(), src.resolve())
        self.assertEqual(Path(mf["target"]).resolve(), tgt.resolve())

        # Draft SHA
        draft_b = (rec_dir / "draft.toml").read_bytes()
        self.assertEqual(hashlib.sha256(draft_b).hexdigest(), mf["draft_sha256"])

        # Sidecar SHA — exact key access (must exist in manifest)
        scp = rec_dir / "draft.toml.yyr4-draft.json"
        self.assertTrue(scp.is_file())
        scb = scp.read_bytes()
        self.assertEqual(hashlib.sha256(scb).hexdigest(), mf["sidecar_sha256"])
        self.assertEqual(json.loads(scb).get("mutation_count",-1), mc)

        # base_sha256 via installed venv Python
        verify_script = textwrap.dedent("""\
            import json, hashlib, sys
            from pathlib import Path
            from yyr4_linux_control.control.config import load_control_config_from_file
            from yyr4_linux_control.configurator.serializer import serialize
            cfg = load_control_config_from_file(Path(sys.argv[1]))
            h = hashlib.sha256(serialize(cfg).encode()).hexdigest()
            print(json.dumps({"sha": h, "mod": __import__("yyr4_linux_control").__file__}))
        """)
        bv = subprocess.run(
            [str(self.venv_dir / "bin" / "python"), "-c", verify_script, str(src)],
            capture_output=True, text=True, timeout=15, cwd=str(self.tmp), env=self._venv_env())
        self.assertEqual(bv.returncode, 0, f"base_sha verify: {bv.stderr[:200]}")
        bi = json.loads(bv.stdout)
        self.assertEqual(bi["sha"], mf["base_sha256"])
        self.assertIn("site-packages", bi["mod"])

        # ── Registry by PID ──
        rb = self.xdg_runtime / "yyr4" / "editor" / "sessions"
        reg = None
        if rb.is_dir():
            for rf in sorted(rb.iterdir()):
                if not rf.is_file(): continue
                try:
                    rg = json.loads(rf.read_text())
                    if rg.get("pid") == proc.pid:
                        if reg is not None: self.fail(f"Multi reg PID {proc.pid}")
                        reg = rg
                except Exception: pass
        self.assertIsNotNone(reg, f"No registry PID {proc.pid}")
        self.assertEqual(reg.get("recovery_id"), rid)
        self.assertEqual(Path(reg["source"]).resolve(), src.resolve())
        self.assertEqual(Path(reg["target"]).resolve(), tgt.resolve())

        # ── AF_UNIX control socket ──
        sp = reg.get("control_socket", "")
        if sp and sp != "None":
            self.assertIn(str(self.xdg_runtime), sp)
            self.assertTrue(stat.S_ISSOCK(os.stat(sp).st_mode), f"Not socket: {sp}")

        self.assertEqual(src.read_bytes(), src_bytes)

        # ── SIGKILL ──
        os.kill(proc.pid, signal.SIGKILL)
        ret = proc.wait(timeout=10)
        self.assertEqual(ret, -signal.SIGKILL)

        # Recovery survives
        self.assertTrue(rec_dir.is_dir())

        # List again via CLI
        r_list2 = self._yyr4ctl("editor", "recover", "list")
        self.assertEqual(r_list2.returncode, 0)
        dec2 = json.JSONDecoder(); pos2 = 0; s2 = r_list2.stdout.strip(); recs2 = []
        while pos2 < len(s2):
            while pos2 < len(s2) and s2[pos2] in " \t\n\r": pos2 += 1
            if pos2 >= len(s2): break
            obj, end = dec2.raw_decode(s2, pos2); recs2.append(obj); pos2 = end
        rid2 = None
        for rec in recs2:
            if Path(rec.get("source","")).resolve() == src.resolve():
                rid2 = rec["recovery_id"]
        self.assertEqual(rid2, rid, "Recovery ID must not change after SIGKILL")

        r_list2 = self._yyr4ctl("editor", "recover", "list")
        self.assertEqual(r_list2.returncode, 0)

        r_insp2 = self._yyr4ctl("editor", "recover", "inspect", "--recovery-id", rid)
        self.assertEqual(r_insp2.returncode, 0)

        r_st = self._yyr4ctl("editor", "status")
        self.assertEqual(r_st.returncode, 0)

        self.assertEqual(src.read_bytes(), src_bytes)
        self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(), src_sha)

        # ── Discard ──
        r_disc = self._yyr4ctl("editor", "recover", "discard", "--recovery-id", rid)
        self.assertEqual(r_disc.returncode, 0, f"Discard: {r_disc.stderr[:200]}")
        self.assertFalse(rec_dir.is_dir())
        self.assertIsNotNone(proc.poll())

    def test_installed_editor_recovery_resumes_with_fresh_auth(self):
        """Installed recover resume: new auth, restored draft, no old creds."""
        import hashlib as hl

        cli = str(self.venv_dir / "bin" / "yyr4ctl")
        src = self.tmp / "src2.toml"
        tgt = self.tmp / "target2.toml"
        example = REPO_ROOT / "examples" / "yyr4-control-from-20260711-backup.toml"
        shutil.copy(str(example), str(src))
        src_bytes = src.read_bytes()
        src_sha = hl.sha256(src_bytes).hexdigest()

        # Start editor
        proc = subprocess.Popen(
            [cli, "editor", "--config", str(src), "--target", str(tgt),
             "--port", "0", "--idle-timeout", "300"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            cwd=str(self.tmp), env=self._venv_env())
        url_line = proc.stdout.readline().strip()
        if "http://" in url_line:
            url_line = url_line[url_line.index("http://"):]
        parts = url_line.split("/"); old_port = int(parts[2].split(":")[1]); btok = parts[-1]

        # Bootstrap original
        conn = http.client.HTTPConnection("127.0.0.1", old_port, timeout=5)
        conn.request("GET", f"/bootstrap/{btok}")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 303)
        old_ck = resp.getheader("Set-Cookie", "").split(";")[0].strip()
        loc = resp.getheader("Location", ""); old_pub = loc.strip("/").split("/")[-1] if loc else ""
        resp.read(); conn.close()
        conn2 = http.client.HTTPConnection("127.0.0.1", old_port, timeout=5)
        conn2.request("GET", f"/s/{old_pub}/api/v1/state", headers={"Cookie": old_ck})
        old_csrf = json.loads(conn2.getresponse().read())["csrf_token"]; conn2.close()
        old_pid = proc.pid

        # Mutate
        sentinel = {"type":"debug_log","message":"R4B2_INSTALLED_RESUME_SENTINEL"}
        d = json.dumps({"profile":"user","layer":"general","control":"A1",
                         "action_spec": sentinel}).encode()
        conn3 = http.client.HTTPConnection("127.0.0.1", old_port, timeout=5)
        conn3.request("POST", f"/s/{old_pub}/api/v1/control/set-action", body=d,
                      headers={"Content-Type":"application/json","Cookie":old_ck,
                               "X-YYR4-CSRF-Token": old_csrf})
        self.assertEqual(conn3.getresponse().status, 200); conn3.close()

        # Verify state
        conn4 = http.client.HTTPConnection("127.0.0.1", old_port, timeout=5)
        conn4.request("GET", f"/s/{old_pub}/api/v1/state", headers={"Cookie": old_ck})
        state = json.loads(conn4.getresponse().read()); conn4.close()
        self.assertTrue(state["config"]["dirty"])
        mc = state["config"]["mutation_count"]
        self.assertGreater(mc, 0)
        self.assertIn("R4B2_INSTALLED_RESUME_SENTINEL", json.dumps(state))

        # Find recovery by CLI list + source match
        rec_base = self.xdg_state / "yyr4" / "editor-recovery"
        rid = None
        if rec_base.is_dir():
            for d2 in sorted(rec_base.iterdir()):
                if not d2.is_dir(): continue
                mfp = d2 / "manifest.json"
                if mfp.is_file():
                    mf = json.loads(mfp.read_text())
                    if Path(mf.get("source","")).resolve() == src.resolve():
                        rid = mf["recovery_id"]; break
        self.assertIsNotNone(rid)

        # SIGKILL original
        os.kill(proc.pid, signal.SIGKILL)
        self.assertEqual(proc.wait(timeout=10), -signal.SIGKILL)
        rec_dir = rec_base / rid
        self.assertTrue(rec_dir.is_dir())

        # Recover resume via installed CLI
        proc2 = subprocess.Popen(
            [cli, "editor", "recover", "resume", "--recovery-id", rid, "--port", "0", "--idle-timeout", "120"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            cwd=str(self.tmp), env=self._venv_env())
        new_url = proc2.stdout.readline().strip()
        self.assertTrue(new_url)
        if "http://" in new_url:
            new_url = new_url[new_url.index("http://"):]
        parts2 = new_url.split("/"); new_port = int(parts2[2].split(":")[1]); new_btok = parts2[-1]

        # New bootstrap
        conn5 = http.client.HTTPConnection("127.0.0.1", new_port, timeout=5)
        conn5.request("GET", f"/bootstrap/{new_btok}")
        resp5 = conn5.getresponse()
        self.assertEqual(resp5.status, 303)
        new_ck = resp5.getheader("Set-Cookie", "").split(";")[0].strip()
        loc5 = resp5.getheader("Location", ""); new_pub = loc5.strip("/").split("/")[-1] if loc5 else ""
        resp5.read(); conn5.close()
        conn6 = http.client.HTTPConnection("127.0.0.1", new_port, timeout=5)
        conn6.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        r6 = conn6.getresponse(); new_csrf = json.loads(r6.read())["csrf_token"]; conn6.close()
        self.assertEqual(r6.status, 200)
        new_pid = proc2.pid

        # Fresh auth assertions
        self.assertNotEqual(new_pid, old_pid)
        self.assertNotEqual(new_url, url_line)
        self.assertNotEqual(new_ck, old_ck)
        self.assertNotEqual(new_csrf, old_csrf)
        self.assertNotEqual(new_pub, old_pub)

        # Old creds rejected
        conn7 = http.client.HTTPConnection("127.0.0.1", new_port, timeout=5)
        conn7.request("GET", f"/s/{new_pub}/api/v1/state")
        self.assertEqual(conn7.getresponse().status, 401); conn7.close()
        conn8 = http.client.HTTPConnection("127.0.0.1", new_port, timeout=5)
        conn8.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": old_ck})
        self.assertEqual(conn8.getresponse().status, 401); conn8.close()
        d2b = json.dumps({"profile":"user","layer":"general","control":"A2",
                          "action_spec":{"type":"noop"}}).encode()
        conn9 = http.client.HTTPConnection("127.0.0.1", new_port, timeout=5)
        conn9.request("POST", f"/s/{new_pub}/api/v1/control/set-action", body=d2b,
                      headers={"Content-Type":"application/json","Cookie":new_ck,
                               "X-YYR4-CSRF-Token": old_csrf})
        self.assertIn(conn9.getresponse().status, (401, 403)); conn9.close()

        # Restored draft state verified
        conn10 = http.client.HTTPConnection("127.0.0.1", new_port, timeout=5)
        conn10.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        state2 = json.loads(conn10.getresponse().read()); conn10.close()
        self.assertTrue(state2["config"]["dirty"])
        self.assertEqual(state2["config"]["mutation_count"], mc)
        self.assertIn("R4B2_INSTALLED_RESUME_SENTINEL", json.dumps(state2))

        # Source unchanged
        self.assertEqual(src.read_bytes(), src_bytes)
        self.assertEqual(hl.sha256(src.read_bytes()).hexdigest(), src_sha)

        # Registry by new PID
        rb = self.xdg_runtime / "yyr4" / "editor" / "sessions"
        reg = None
        if rb.is_dir():
            for rf in sorted(rb.iterdir()):
                if not rf.is_file(): continue
                try:
                    rg = json.loads(rf.read_text())
                    if rg.get("pid") == proc2.pid:
                        reg = rg; break
                except Exception: pass
        self.assertIsNotNone(reg)
        self.assertEqual(reg.get("recovery_id"), rid)

        # Stop via installed CLI --discard-draft using registry session_id
        resumed_session_id = reg.get("session_id", "")
        self.assertTrue(resumed_session_id, "Registry must have session_id")
        # CLI stop via session_id; then discard recovery
        r_stop = self._yyr4ctl("editor", "stop", "--session-id", resumed_session_id)
        self.assertEqual(r_stop.returncode, 0, f"Stop: {r_stop.stderr[:200]}")
        r_disc = self._yyr4ctl("editor", "recover", "discard", "--recovery-id", rid)
        self.assertEqual(r_disc.returncode, 0)
        proc2.stdout.close()
        proc2.wait(timeout=10)
        self.assertIsNotNone(proc2.returncode)  # Editor exited after stop

        # Recovery deleted
        self.assertFalse(rec_dir.is_dir())


    def test_installed_resumed_editor_review_and_save_original_target(self):
        """Installed resume → Review → Save to original Manifest Target."""
        import hashlib as hl

        cli = str(self.venv_dir / "bin" / "yyr4ctl")
        src = self.tmp / "src3.toml"
        tgt = self.tmp / "target3.toml"
        example = REPO_ROOT / "examples" / "yyr4-control-from-20260711-backup.toml"
        shutil.copy(str(example), str(src))
        src_bytes = src.read_bytes()
        src_sha = hl.sha256(src_bytes).hexdigest()

        # Start editor
        proc = subprocess.Popen(
            [cli, "editor", "--config", str(src), "--target", str(tgt),
             "--port", "0", "--idle-timeout", "300"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            cwd=str(self.tmp), env=self._venv_env())
        url_line = proc.stdout.readline().strip()
        if "http://" in url_line: url_line = url_line[url_line.index("http://"):]
        parts = url_line.split("/"); port = int(parts[2].split(":")[1]); btok = parts[-1]

        # Bootstrap
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", f"/bootstrap/{btok}")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 303)
        ck = resp.getheader("Set-Cookie", "").split(";")[0].strip()
        loc = resp.getheader("Location", ""); pub = loc.strip("/").split("/")[-1] if loc else ""
        resp.read(); conn.close()
        conn2 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn2.request("GET", f"/s/{pub}/api/v1/state", headers={"Cookie": ck})
        csrf = json.loads(conn2.getresponse().read())["csrf_token"]; conn2.close()

        # Mutate
        sentinel = {"type":"debug_log","message":"R4B3_INSTALLED_REVIEW_SAVE_SENTINEL"}
        d = json.dumps({"profile":"user","layer":"general","control":"A1",
                         "action_spec": sentinel}).encode()
        conn3 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn3.request("POST", f"/s/{pub}/api/v1/control/set-action", body=d,
                      headers={"Content-Type":"application/json","Cookie":ck,
                               "X-YYR4-CSRF-Token": csrf})
        self.assertEqual(conn3.getresponse().status, 200); conn3.close()
        conn4 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn4.request("GET", f"/s/{pub}/api/v1/state", headers={"Cookie": ck})
        state = json.loads(conn4.getresponse().read()); conn4.close()
        self.assertTrue(state["config"]["dirty"]); mc = state["config"]["mutation_count"]
        self.assertGreater(mc, 0)
        self.assertIn("R4B3_INSTALLED_REVIEW_SAVE_SENTINEL", json.dumps(state))

        # Find recovery
        rec_base = self.xdg_state / "yyr4" / "editor-recovery"
        rid = None
        for d2 in sorted(rec_base.iterdir()):
            if not d2.is_dir(): continue
            mfp = d2 / "manifest.json"
            if mfp.is_file():
                mf = json.loads(mfp.read_text())
                if Path(mf.get("source","")).resolve() == src.resolve():
                    rid = mf["recovery_id"]; break
        self.assertIsNotNone(rid)
        manifest_target = mf.get("target", "")

        # SIGKILL
        os.kill(proc.pid, signal.SIGKILL)
        self.assertEqual(proc.wait(timeout=10), -signal.SIGKILL)

        # Resume
        proc2 = subprocess.Popen(
            [cli, "editor", "recover", "resume", "--recovery-id", rid, "--port", "0", "--idle-timeout", "120"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            cwd=str(self.tmp), env=self._venv_env())
        new_url = proc2.stdout.readline().strip()
        if "http://" in new_url: new_url = new_url[new_url.index("http://"):]
        parts2 = new_url.split("/"); np = int(parts2[2].split(":")[1]); newb = parts2[-1]
        conn5 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn5.request("GET", f"/bootstrap/{newb}")
        r5 = conn5.getresponse()
        self.assertEqual(r5.status, 303)
        new_ck = r5.getheader("Set-Cookie", "").split(";")[0].strip()
        loc5 = r5.getheader("Location", ""); new_pub = loc5.strip("/").split("/")[-1] if loc5 else ""
        r5.read(); conn5.close()
        conn6 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn6.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        new_csrf = json.loads(conn6.getresponse().read())["csrf_token"]; conn6.close()

        # Review
        conn_r = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_r.request("POST", f"/s/{new_pub}/api/v1/review", body=b"{}",
                       headers={"Content-Type":"application/json","Cookie":new_ck,
                                "X-YYR4-CSRF-Token": new_csrf})
        rr = conn_r.getresponse(); rev_body = json.loads(rr.read()); conn_r.close()
        self.assertEqual(rr.status, 200)
        self.assertTrue(rev_body.get("reviewed"))
        conn_r2 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_r2.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        srv = json.loads(conn_r2.getresponse().read()); conn_r2.close()
        self.assertTrue(srv["config"]["dirty"])
        self.assertEqual(srv["config"]["mutation_count"], mc)

        # Save
        conn_s = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_s.request("POST", f"/s/{new_pub}/api/v1/save", body=b"{}",
                       headers={"Content-Type":"application/json","Cookie":new_ck,
                                "X-YYR4-CSRF-Token": new_csrf})
        rs = conn_s.getresponse(); sb = json.loads(rs.read()); conn_s.close()
        self.assertEqual(rs.status, 200)
        self.assertEqual(sb.get("status"), "ok")

        # Post-save state
        conn_a = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_a.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        spa = json.loads(conn_a.getresponse().read()); conn_a.close()
        self.assertFalse(spa["config"]["dirty"])
        self.assertEqual(spa["config"]["mutation_count"], 0)

        # Post-save diff empty
        conn_d = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_d.request("GET", f"/s/{new_pub}/api/v1/diff", headers={"Cookie": new_ck})
        diff_post = json.loads(conn_d.getresponse().read()); conn_d.close()
        self.assertEqual(diff_post.get("change_count", 1), 0)

        # Target written to manifest target
        tgt_path = Path(manifest_target) if manifest_target else tgt
        self.assertTrue(tgt_path.is_file())

        # Verify via installed venv Python
        vscript = self.tmp / "_verify_target.py"
        vscript.write_text(
            'import json, sys\n'
            'from pathlib import Path\n'
            'from yyr4_linux_control.control.config import load_control_config_from_file\n'
            'cfg = load_control_config_from_file(Path(sys.argv[1]))\n'
            'prof = list(cfg.profiles.values())[0]\n'
            'a1 = prof.layers["general"].controls.get("A1")\n'
            'print(json.dumps({"msg": a1.message, "mod": __import__("yyr4_linux_control").__file__}))\n')
        ver_out = subprocess.run(
            [str(self.venv_dir / "bin" / "python"), str(vscript), str(tgt_path)],
            capture_output=True, text=True, timeout=15, cwd=str(self.tmp), env=self._venv_env())
        self.assertEqual(ver_out.returncode, 0, f"Target verify: {ver_out.stderr[:200]}")
        tv = json.loads(ver_out.stdout)
        self.assertIn("site-packages", tv["mod"])
        self.assertEqual(tv["msg"], "R4B3_INSTALLED_REVIEW_SAVE_SENTINEL")

        # Source unchanged
        self.assertEqual(src.read_bytes(), src_bytes)
        self.assertEqual(hl.sha256(src.read_bytes()).hexdigest(), src_sha)

        # Recovery deleted by save
        rec_base = self.xdg_state / "yyr4" / "editor-recovery"
        self.assertFalse((rec_base / rid).is_dir())

        # Registry recovery_id is null
        rb = self.xdg_runtime / "yyr4" / "editor" / "sessions"
        reg = None
        for rf in sorted(rb.iterdir()):
            if not rf.is_file(): continue
            try:
                rg = json.loads(rf.read_text())
                if rg.get("pid") == proc2.pid: reg = rg; break
            except: pass
        self.assertIsNotNone(reg)
        self.assertIsNone(reg.get("recovery_id"))

        # Session still running
        self.assertIsNone(proc2.poll())

        # Stop via installed CLI (clean session, no --discard-draft needed after save)
        saved_session_id = reg.get("session_id", "")
        self.assertTrue(saved_session_id, "Registry must have session_id")
        r_stop2 = self._yyr4ctl("editor", "stop", "--session-id", saved_session_id)
        self.assertEqual(r_stop2.returncode, 0, f"Stop: {r_stop2.stderr[:200]}")
        proc2.stdout.close()
        proc2.wait(timeout=10)


    def test_installed_saved_session_rebinds_new_recovery_after_second_mutation(self):
        """After Save+2nd mutation: new recovery_id, registry rebound, Target untouched."""
        import hashlib as hl

        cli = str(self.venv_dir / "bin" / "yyr4ctl")
        src = self.tmp / "src4.toml"
        tgt = self.tmp / "target4.toml"
        example = REPO_ROOT / "examples" / "yyr4-control-from-20260711-backup.toml"
        shutil.copy(str(example), str(src))
        src_bytes = src.read_bytes()
        src_sha = hl.sha256(src_bytes).hexdigest()

        # Start editor
        proc = subprocess.Popen(
            [cli, "editor", "--config", str(src), "--target", str(tgt),
             "--port", "0", "--idle-timeout", "300"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            cwd=str(self.tmp), env=self._venv_env())
        url_line = proc.stdout.readline().strip()
        if "http://" in url_line: url_line = url_line[url_line.index("http://"):]
        parts = url_line.split("/"); port = int(parts[2].split(":")[1]); btok = parts[-1]

        # Bootstrap + mutate first sentinel
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", f"/bootstrap/{btok}")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 303)
        ck = resp.getheader("Set-Cookie", "").split(";")[0].strip()
        loc = resp.getheader("Location", ""); pub = loc.strip("/").split("/")[-1] if loc else ""
        resp.read(); conn.close()
        conn2 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn2.request("GET", f"/s/{pub}/api/v1/state", headers={"Cookie": ck})
        csrf = json.loads(conn2.getresponse().read())["csrf_token"]; conn2.close()

        sentinel1 = {"type":"debug_log","message":"R4B4_FIRST_SAVE_SENTINEL"}
        d = json.dumps({"profile":"user","layer":"general","control":"A1",
                         "action_spec": sentinel1}).encode()
        conn3 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn3.request("POST", f"/s/{pub}/api/v1/control/set-action", body=d,
                       headers={"Content-Type":"application/json","Cookie":ck,
                                "X-YYR4-CSRF-Token": csrf})
        self.assertEqual(conn3.getresponse().status, 200); conn3.close()

        # Find old recovery
        rec_base = self.xdg_state / "yyr4" / "editor-recovery"
        old_rid = None
        for d2 in sorted(rec_base.iterdir()):
            if not d2.is_dir(): continue
            mfp = d2 / "manifest.json"
            if mfp.is_file():
                mf = json.loads(mfp.read_text())
                if Path(mf.get("source","")).resolve() == src.resolve():
                    old_rid = mf["recovery_id"]; break
        self.assertIsNotNone(old_rid)

        # SIGKILL + resume + review + save
        os.kill(proc.pid, signal.SIGKILL)
        self.assertEqual(proc.wait(timeout=10), -signal.SIGKILL)
        proc2 = subprocess.Popen(
            [cli, "editor", "recover", "resume", "--recovery-id", old_rid,
             "--port", "0", "--idle-timeout", "120"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            cwd=str(self.tmp), env=self._venv_env())
        new_url = proc2.stdout.readline().strip()
        if "http://" in new_url: new_url = new_url[new_url.index("http://"):]
        parts2 = new_url.split("/"); np = int(parts2[2].split(":")[1]); newb = parts2[-1]
        conn5 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn5.request("GET", f"/bootstrap/{newb}")
        r5 = conn5.getresponse()
        self.assertEqual(r5.status, 303)
        new_ck = r5.getheader("Set-Cookie", "").split(";")[0].strip()
        loc5 = r5.getheader("Location", ""); new_pub = loc5.strip("/").split("/")[-1] if loc5 else ""
        r5.read(); conn5.close()
        conn6 = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn6.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        new_csrf = json.loads(conn6.getresponse().read())["csrf_token"]; conn6.close()

        # Review + Save
        conn_r = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_r.request("POST", f"/s/{new_pub}/api/v1/review", body=b"{}",
                       headers={"Content-Type":"application/json","Cookie":new_ck,
                                "X-YYR4-CSRF-Token": new_csrf})
        self.assertEqual(conn_r.getresponse().status, 200); conn_r.close()
        conn_s = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_s.request("POST", f"/s/{new_pub}/api/v1/save", body=b"{}",
                       headers={"Content-Type":"application/json","Cookie":new_ck,
                                "X-YYR4-CSRF-Token": new_csrf})
        rs = conn_s.getresponse(); sb = json.loads(rs.read()); conn_s.close()
        self.assertEqual(rs.status, 200); self.assertEqual(sb.get("status"), "ok")

        # Verify old recovery gone, registry null
        self.assertFalse((rec_base / old_rid).is_dir())
        rb = self.xdg_runtime / "yyr4" / "editor" / "sessions"
        reg = None
        for rf in sorted(rb.iterdir()):
            if not rf.is_file(): continue
            try:
                rg = json.loads(rf.read_text())
                if rg.get("pid") == proc2.pid: reg = rg; break
            except: pass
        self.assertIsNotNone(reg)
        self.assertIsNone(reg.get("recovery_id"))

        # Second mutation on same session
        sentinel2 = {"type":"debug_log","message":"R4B4_SECOND_RECOVERY_SENTINEL"}
        d2 = json.dumps({"profile":"user","layer":"general","control":"A1",
                          "action_spec": sentinel2}).encode()
        conn_m = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_m.request("POST", f"/s/{new_pub}/api/v1/control/set-action", body=d2,
                       headers={"Content-Type":"application/json","Cookie":new_ck,
                                "X-YYR4-CSRF-Token": new_csrf})
        self.assertEqual(conn_m.getresponse().status, 200); conn_m.close()
        conn_st = http.client.HTTPConnection("127.0.0.1", np, timeout=5)
        conn_st.request("GET", f"/s/{new_pub}/api/v1/state", headers={"Cookie": new_ck})
        st = json.loads(conn_st.getresponse().read()); conn_st.close()
        self.assertTrue(st["config"]["dirty"])
        self.assertEqual(st["config"]["mutation_count"], 1)
        self.assertIn("R4B4_SECOND_RECOVERY_SENTINEL", json.dumps(st))

        # New recovery must exist with different ID
        new_rid = None
        for d3 in sorted(rec_base.iterdir()):
            if not d3.is_dir(): continue
            mfp = d3 / "manifest.json"
            if mfp.is_file():
                mf3 = json.loads(mfp.read_text())
                if Path(mf3.get("source","")).resolve() == src.resolve():
                    new_rid = mf3["recovery_id"]; break
        self.assertIsNotNone(new_rid)
        self.assertNotEqual(new_rid, old_rid)

        # Registry rebound
        reg2 = None
        for rf in sorted(rb.iterdir()):
            if not rf.is_file(): continue
            try:
                rg2 = json.loads(rf.read_text())
                if rg2.get("pid") == proc2.pid: reg2 = rg2; break
            except: pass
        self.assertIsNotNone(reg2)
        self.assertEqual(reg2.get("recovery_id"), new_rid)

        # Target still has first sentinel
        ver_out = subprocess.run(
            [str(self.venv_dir / "bin" / "python"),
             str(self._write_verify_script(src, tgt)), str(tgt)],
            capture_output=True, text=True, timeout=15, cwd=str(self.tmp), env=self._venv_env())
        self.assertEqual(ver_out.returncode, 0)
        tv = json.loads(ver_out.stdout)
        self.assertEqual(tv.get("msg"), "R4B4_FIRST_SAVE_SENTINEL")

        # Source unchanged
        self.assertEqual(src.read_bytes(), src_bytes)

        # Stop + discard
        sid3 = reg2.get("session_id", "")
        self.assertTrue(sid3)
        r_stop = self._yyr4ctl("editor", "stop", "--session-id", sid3)
        self.assertEqual(r_stop.returncode, 0)
        self.assertTrue((rec_base / new_rid).is_dir())
        r_disc = self._yyr4ctl("editor", "recover", "discard", "--recovery-id", new_rid)
        self.assertEqual(r_disc.returncode, 0)
        proc2.stdout.close(); proc2.wait(timeout=10)

    def _write_verify_script(self, src, tgt):
        """Write a verify script to self.tmp for target validation."""
        vscript = self.tmp / "_vt.py"
        vscript.write_text(
            'import json, sys\n'
            'from pathlib import Path\n'
            'from yyr4_linux_control.control.config import load_control_config_from_file\n'
            'cfg = load_control_config_from_file(Path(sys.argv[1]))\n'
            'prof = list(cfg.profiles.values())[0]\n'
            'a1 = prof.layers["general"].controls.get("A1")\n'
            'print(json.dumps({"msg": getattr(a1, "message", None), '
            '"mod": __import__("yyr4_linux_control").__file__}))\n')
        return vscript


if __name__ == "__main__":
    unittest.main()
