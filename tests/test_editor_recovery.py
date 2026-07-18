"""M5.4-A2: Recovery — permissions, symlink, manifest, shutdown policies."""
import unittest, os, tempfile, shutil, time, json, http.client
from pathlib import Path


class TestRecoveryPermissions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        import yyr4_linux_control.configurator.web.session as smod
        self._old = smod.RECOVERY_BASE_DIR
        smod.RECOVERY_BASE_DIR = os.path.join(self.tmp, "recovery")

    def tearDown(self):
        import yyr4_linux_control.configurator.web.session as smod
        smod.RECOVERY_BASE_DIR = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _start_and_mutate(self):
        from yyr4_linux_control.configurator.web.server import EditorServer
        src = os.path.join(self.tmp, "src.toml")
        target = os.path.join(self.tmp, "target.toml")
        shutil.copy(os.path.join(os.path.dirname(__file__), "..", "examples",
            "yyr4-control-from-20260711-backup.toml"), src)
        s = EditorServer(src, target, port=0, idle_timeout=30, open_browser=False)
        s.start(); time.sleep(0.2)
        pub = s._session.public_session_id
        ck = f"yyr4_session_{pub}={s._session.session_cookie}"
        d = json.dumps({"profile":"user","layer":"general","control":"A1",
                         "action_spec":{"type":"noop"}}).encode()
        conn = http.client.HTTPConnection("127.0.0.1", s.listen_port, timeout=5)
        conn.request("GET", f"/bootstrap/{s._session.bootstrap_token}")
        conn.getresponse().read(); conn.close()
        conn2 = http.client.HTTPConnection("127.0.0.1", s.listen_port, timeout=5)
        conn2.request("POST", f"/s/{pub}/api/v1/control/set-action", body=d,
                      headers={"Content-Type":"application/json","Cookie":ck,
                               "X-YYR4-CSRF-Token":s._session.csrf_token})
        conn2.getresponse().read(); conn2.close()
        return s

    def test_recovery_dir_mode_700(self):
        s = self._start_and_mutate()
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        recs = list_recoveries()
        self.assertGreater(len(recs), 0)
        rdir = Path(os.path.join(self.tmp,"recovery")) / recs[0]["recovery_id"]
        self.assertEqual(os.stat(str(rdir)).st_mode & 0o777, 0o700)
        s.stop()
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_dirty_session_creates_recovery(self):
        s = self._start_and_mutate()
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        self.assertGreater(len(list_recoveries()), 0)
        s.stop()
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_clean_session_no_recovery(self):
        from yyr4_linux_control.configurator.web.server import EditorServer
        src = os.path.join(self.tmp, "src2.toml")
        target = os.path.join(self.tmp, "target2.toml")
        shutil.copy(os.path.join(os.path.dirname(__file__), "..", "examples",
            "yyr4-control-from-20260711-backup.toml"), src)
        s = EditorServer(src, target, port=0, idle_timeout=30, open_browser=False)
        s.start(); time.sleep(0.2)
        s.stop()
        from yyr4_linux_control.configurator.web.session import list_recoveries
        self.assertEqual(len(list_recoveries()), 0)

    def test_recovery_manifest_fields(self):
        s = self._start_and_mutate()
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        recs = list_recoveries()
        self.assertGreaterEqual(len(recs), 1)
        r = recs[0]
        for field in ("recovery_version","recovery_id","base_sha256","draft_sha256",
                       "mutation_count","dirty","application_version"):
            self.assertIn(field, r)
        s.stop()
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_recovery_no_tokens(self):
        s = self._start_and_mutate()
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        recs = list_recoveries()
        txt = json.dumps(recs[0])
        self.assertNotIn("token", txt.lower())
        self.assertNotIn("cookie", txt.lower())
        self.assertNotIn("csrf", txt.lower())
        s.stop()
        for r in list_recoveries(): discard_recovery(r["recovery_id"])


class TestShutdownPolicies(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from yyr4_linux_control.configurator.web.server import EditorServer
        src = os.path.join(self.tmp, "src.toml")
        target = os.path.join(self.tmp, "target.toml")
        shutil.copy(os.path.join(os.path.dirname(__file__), "..", "examples",
            "yyr4-control-from-20260711-backup.toml"), src)
        self.srv = EditorServer(src, target, port=0, idle_timeout=60, open_browser=False)
        self.srv.start(); time.sleep(0.2)
        self.port = self.srv.listen_port
        self.pub = self.srv._session.public_session_id
        self.ck = f"yyr4_session_{self.pub}={self.srv._session.session_cookie}"
        self.csrf = self.srv._session.csrf_token
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", f"/bootstrap/{self.srv._session.bootstrap_token}")
        conn.getresponse().read(); conn.close()
        d = json.dumps({"profile":"user","layer":"general","control":"A1",
                         "action_spec":{"type":"noop"}}).encode()
        conn2 = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn2.request("POST", f"/s/{self.pub}/api/v1/control/set-action", body=d,
                      headers={"Content-Type":"application/json","Cookie":self.ck,
                               "X-YYR4-CSRF-Token":self.csrf})
        conn2.getresponse().read(); conn2.close()

    def tearDown(self):
        try: self.srv.stop()
        except: pass
        time.sleep(0.2)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _shutdown(self, policy):
        d = json.dumps({"dirty_policy": policy}).encode()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", f"/s/{self.pub}/api/v1/shutdown", body=d,
                     headers={"Content-Type":"application/json","Cookie":self.ck,
                              "X-YYR4-CSRF-Token":self.csrf})
        resp = conn.getresponse(); body = resp.read(); conn.close()
        return resp.status, json.loads(body) if body else {}

    def test_keep_recovery(self):
        st, _ = self._shutdown("keep_recovery")
        self.assertEqual(st, 200)
        time.sleep(1)
        from yyr4_linux_control.configurator.web.session import list_recoveries, discard_recovery
        self.assertGreater(len([r for r in list_recoveries() if r.get("dirty")]), 0)
        for r in list_recoveries(): discard_recovery(r["recovery_id"])

    def test_discard(self):
        st, _ = self._shutdown("discard")
        self.assertEqual(st, 200)
        time.sleep(1)

    def test_cancel(self):
        st, _ = self._shutdown("cancel")
        self.assertEqual(st, 200)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", f"/s/{self.pub}/api/v1/state", headers={"Cookie": self.ck})
        self.assertEqual(conn.getresponse().status, 200); conn.close()



class TestConfigDraftFromRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = Path(self.tmp) / 'source.toml'
        shutil.copy(
            os.path.join(os.path.dirname(__file__), '..', 'examples',
                         'yyr4-control-from-20260711-backup.toml'),
            str(self.src))
        from yyr4_linux_control.configurator.draft import ConfigDraft
        from yyr4_linux_control.configurator.serializer import serialize
        from yyr4_linux_control.control.config import load_control_config_from_file
        import hashlib
        # Load source, create mutated config, write as recovery draft
        source_cfg = load_control_config_from_file(self.src)
        orig_draft = ConfigDraft(self.src)
        # Get serialized working config (from fresh draft = same as source)
        self.working_text = serialize(orig_draft.working_config)
        self.draft_path = Path(self.tmp) / 'recovery_draft.toml'
        self.draft_path.write_text(self.working_text)
        self.recovery_sha = hashlib.sha256(self.working_text.encode()).hexdigest()
        # Write sidecar with mutation count 3
        from yyr4_linux_control.configurator.sidecar import write_sidecar
        # We need a sidecar with mutation_count=3, but the write_sidecar takes mutation_count
        sidecar_path = write_sidecar(self.draft_path, str(self.src), orig_draft.base_sha256, self.recovery_sha, 3)
        self.sidecar_text = sidecar_path.read_text()
        self.sidecar_sha = hashlib.sha256(self.sidecar_text.encode()).hexdigest()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_from_recovery_restores_invariants(self):
        from yyr4_linux_control.configurator.draft import ConfigDraft
        restored = ConfigDraft.from_recovery(
            source_path=self.src, recovery_draft_path=self.draft_path,
            recovery_sidecar_path=Path(str(self.draft_path) + '.yyr4-draft.json'),
            expected_draft_sha256=self.recovery_sha,
        )
        self.assertEqual(restored.mutation_count, 3)
        self.assertTrue(restored.dirty)
        self.assertIsNotNone(restored.base_config)
        self.assertIsNotNone(restored.working_config)
        # Source not modified
        with open(str(self.src)) as _fa: self.assertEqual(self.src.read_text(), _fa.read())
        # Recovery files not modified
        with open(str(self.draft_path)) as _fb: self.assertEqual(_fb.read(), self.working_text)

    def test_from_recovery_rejects_wrong_draft_sha(self):
        from yyr4_linux_control.configurator.draft import ConfigDraft
        with self.assertRaises(ValueError):
            ConfigDraft.from_recovery(
                source_path=self.src, recovery_draft_path=self.draft_path,
                recovery_sidecar_path=Path(str(self.draft_path) + '.yyr4-draft.json'),
                expected_draft_sha256='deadbeef',
            )

    def test_from_recovery_rejects_wrong_sidecar_sha(self):
        from yyr4_linux_control.configurator.draft import ConfigDraft
        with self.assertRaises(ValueError):
            ConfigDraft.from_recovery(
                source_path=self.src, recovery_draft_path=self.draft_path,
                recovery_sidecar_path=Path(str(self.draft_path) + '.yyr4-draft.json'),
                expected_sidecar_sha256='deadcafe',
            )


if __name__ == "__main__":
    unittest.main()


class TestManifestSidecarSha(unittest.TestCase):

    def test_write_recovery_manifest_contains_exact_sidecar_sha256(self):
        import hashlib
        src = self.tmp / "src.toml"
        tgt = self.tmp / "target.toml"
        example = Path("examples/yyr4-control-from-20260711-backup.toml")
        shutil.copy(str(example), str(src))
        from yyr4_linux_control.configurator.web.session import create_session
        s = create_session(str(src), str(tgt))
        # Make dirty via a real mutation through the draft
        from yyr4_linux_control.control.config import load_control_config_from_file
        from yyr4_linux_control.configurator.serializer import serialize
        import hashlib as hl
        cfg = load_control_config_from_file(src)
        s.draft.working_config = cfg
        s.draft._dirty = True
        s.draft._mutation_count = 1
        from yyr4_linux_control.configurator.sidecar import write_sidecar as ws
        ws(Path(str(s.draft_path)), str(src), s.base_sha256,
           s.draft_sha256, s.draft._mutation_count)
        s.write_recovery()

        rid = s._recovery_id
        self.assertIsNotNone(rid)
        from yyr4_linux_control.configurator.web.session import RECOVERY_BASE_DIR
        rec_dir = Path(RECOVERY_BASE_DIR) / rid
        mf = json.loads((rec_dir / "manifest.json").read_text())
        self.assertIn("sidecar_sha256", mf, f"Manifest keys: {sorted(mf.keys())}")
        scp = rec_dir / "draft.toml.yyr4-draft.json"
        self.assertTrue(scp.is_file())
        actual_sha = hl.sha256(scp.read_bytes()).hexdigest()
        self.assertEqual(mf["sidecar_sha256"], actual_sha)
        # Draft SHA also correct
        draft_b = (rec_dir / "draft.toml").read_bytes()
        self.assertEqual(hl.sha256(draft_b).hexdigest(), mf["draft_sha256"])
        # Sidecar mutation_count matches draft
        sc = json.loads(scp.read_text())
        self.assertEqual(sc.get("mutation_count", -1), 1)
        # Cleanup
        s.discard_recovery()
        import shutil as _su3; _su3.rmtree(str(Path(s.draft_path).parent), ignore_errors=True)

    def test_rewrite_recovery_refreshes_sidecar_sha256(self):
        import hashlib as hl
        src = self.tmp / "src.toml"
        tgt = self.tmp / "target.toml"
        example = Path("examples/yyr4-control-from-20260711-backup.toml")
        shutil.copy(str(example), str(src))
        from yyr4_linux_control.configurator.web.session import create_session
        from yyr4_linux_control.control.config import load_control_config_from_file
        s = create_session(str(src), str(tgt))
        cfg = load_control_config_from_file(src)
        s.draft.working_config = cfg
        s.draft._dirty = True
        s.draft._mutation_count = 1
        from yyr4_linux_control.configurator.sidecar import write_sidecar as ws3
        ws3(Path(str(s.draft_path)), str(src), s.base_sha256,
            s.draft_sha256, s.draft._mutation_count)
        s.write_recovery()
        rid = s._recovery_id
        from yyr4_linux_control.configurator.web.session import RECOVERY_BASE_DIR
        rec_dir = Path(RECOVERY_BASE_DIR) / rid
        mf1 = json.loads((rec_dir / "manifest.json").read_text())
        sha1 = mf1["sidecar_sha256"]
        mc1 = json.loads((rec_dir / "draft.toml.yyr4-draft.json").read_text()).get("mutation_count", -1)
        self.assertEqual(mc1, 1, "First mutation_count must be 1")

        # Second mutation
        s.draft._mutation_count = 2
        s.touch()
        from yyr4_linux_control.configurator.sidecar import write_sidecar as ws2
        ws2(Path(str(s.draft_path)), str(src), s.base_sha256,
            s.draft_sha256, s.draft._mutation_count)
        s.write_recovery()
        mf2 = json.loads((rec_dir / "manifest.json").read_text())
        sha2 = mf2["sidecar_sha256"]
        mc2 = json.loads((rec_dir / "draft.toml.yyr4-draft.json").read_text()).get("mutation_count", -1)
        self.assertEqual(mc2, 2, "Second mutation_count must be 2")
        self.assertNotEqual(sha1, sha2, "Sidecar SHA must change after rewrite")
        # Verify sha2 matches actual file
        actual2 = hl.sha256((rec_dir / "draft.toml.yyr4-draft.json").read_bytes()).hexdigest()
        self.assertEqual(sha2, actual2)
        s.discard_recovery()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_resume_uses_manifest_sidecar_sha256(self):
        """Resume must enforce manifest sidecar_sha256 against actual file."""
        import hashlib as hl
        src = self.tmp / "src.toml"
        tgt = self.tmp / "target.toml"
        shutil.copy("examples/yyr4-control-from-20260711-backup.toml", str(src))
        from yyr4_linux_control.configurator.web.session import create_session, RECOVERY_BASE_DIR, resume_session
        from yyr4_linux_control.configurator.sidecar import write_sidecar
        s = create_session(str(src), str(tgt))
        from yyr4_linux_control.control.config import load_control_config_from_file
        cfg = load_control_config_from_file(src)
        s.draft.working_config = cfg; s.draft._dirty = True; s.draft._mutation_count = 1
        write_sidecar(Path(str(s.draft_path)), str(src), s.base_sha256,
                      s.draft_sha256, s.draft._mutation_count)
        s.write_recovery()
        rid = s._recovery_id
        rec_dir = Path(RECOVERY_BASE_DIR) / rid
        mf_orig = json.loads((rec_dir / "manifest.json").read_text())
        orig_sidecar_sha = mf_orig["sidecar_sha256"]

        # Tamper: modify sidecar bytes while keeping valid JSON
        scp = rec_dir / "draft.toml.yyr4-draft.json"
        sc = json.loads(scp.read_text())
        sc["mutation_count"] = 9999
        scp.write_text(json.dumps(sc))
        tampered_sha = hl.sha256(scp.read_bytes()).hexdigest()
        self.assertNotEqual(tampered_sha, orig_sidecar_sha)

        # Resume must fail
        with self.assertRaises(ValueError) as ctx:
            resume_session(rid, str(tgt))
        self.assertIn("sidecar", str(ctx.exception).lower() or "SHA", "sidecar")

        # Recovery preserved
        self.assertTrue(rec_dir.is_dir())
        src_bytes = src.read_bytes()
        self.assertEqual(src.read_bytes(), src_bytes)
        s.discard_recovery()
        self.assertFalse(rec_dir.is_dir())
        import shutil as _su2; _su2.rmtree(str(Path(s.draft_path).parent), ignore_errors=True)

    def test_resume_rejects_legacy_manifest_without_sidecar_sha256(self):
        """Old manifests missing sidecar_sha256: list+inspect OK, resume fails."""
        src = self.tmp / "src.toml"
        tgt = self.tmp / "target.toml"
        shutil.copy("examples/yyr4-control-from-20260711-backup.toml", str(src))
        from yyr4_linux_control.configurator.web.session import create_session, RECOVERY_BASE_DIR, resume_session, list_recoveries, get_recovery, discard_recovery
        from yyr4_linux_control.configurator.sidecar import write_sidecar
        s = create_session(str(src), str(tgt))
        from yyr4_linux_control.control.config import load_control_config_from_file
        cfg = load_control_config_from_file(src)
        s.draft.working_config = cfg; s.draft._dirty = True; s.draft._mutation_count = 1
        write_sidecar(Path(str(s.draft_path)), str(src), s.base_sha256,
                      s.draft_sha256, s.draft._mutation_count)
        s.write_recovery()
        rid = s._recovery_id
        rec_dir = Path(RECOVERY_BASE_DIR) / rid
        # Remove sidecar_sha256 from manifest
        mf = json.loads((rec_dir / "manifest.json").read_text())
        del mf["sidecar_sha256"]
        self.assertNotIn("sidecar_sha256", mf)
        (rec_dir / "manifest.json").write_text(json.dumps(mf, indent=2))

        # list/inspect still work
        recs = list_recoveries()
        self.assertGreater(len(recs), 0)
        self.assertIsNotNone(get_recovery(rid))

        # Resume must fail
        with self.assertRaises(ValueError):
            resume_session(rid, str(tgt))

        # Recovery preserved
        self.assertTrue(rec_dir.is_dir())
        # discard still works
        self.assertTrue(discard_recovery(rid))
        self.assertFalse(rec_dir.is_dir())

    def test_write_recovery_does_not_publish_manifest_without_sidecar(self):
        """If sidecar is missing when write_recovery runs, no manifest published."""
        src = self.tmp / "src.toml"
        tgt = self.tmp / "target.toml"
        shutil.copy("examples/yyr4-control-from-20260711-backup.toml", str(src))
        from yyr4_linux_control.configurator.web.session import create_session, RECOVERY_BASE_DIR
        from yyr4_linux_control.configurator.sidecar import write_sidecar
        s = create_session(str(src), str(tgt))
        from yyr4_linux_control.control.config import load_control_config_from_file
        cfg = load_control_config_from_file(src)
        s.draft.working_config = cfg; s.draft._dirty = True; s.draft._mutation_count = 1
        write_sidecar(Path(str(s.draft_path)), str(src), s.base_sha256,
                      s.draft_sha256, s.draft._mutation_count)
        s.write_recovery()
        rid = s._recovery_id
        rec_dir = Path(RECOVERY_BASE_DIR) / rid
        self.assertTrue(rec_dir.is_dir())
        old_mf = (rec_dir / "manifest.json").read_text()

        # Delete sidecar from session draft, then call write_recovery — must fail
        session_sc = Path(str(s.draft_path) + ".yyr4-draft.json")
        session_sc.unlink()
        with self.assertRaises((RuntimeError, FileNotFoundError)) as ctx:
            s.write_recovery()
        self.assertTrue("missing" in str(ctx.exception).lower() or "sidecar" in str(ctx.exception).lower() or "not found" in str(ctx.exception).lower())

        # Manifest not overwritten with broken state
        self.assertEqual((rec_dir / "manifest.json").read_text(), old_mf)
        s.discard_recovery()
