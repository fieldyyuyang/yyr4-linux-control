import unittest, tempfile, os
from pathlib import Path
from yyr4_linux_control.configurator.serializer import serialize, _toml_str
from yyr4_linux_control.configurator.draft import ConfigDraft
from yyr4_linux_control.control.config import load_control_config_from_file
from yyr4_linux_control.control.actions import TextAction, DebugLogAction, CommandAction, MacroAction, DelayAction
from yyr4_linux_control.control.models import LayerId, ProfileId

class TestSerializerEscaping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_control_config_from_file(
            Path("examples/yyr4-control-from-20260711-backup.toml"))

    def _roundtrip(self, action):
        """serialize → tomllib → ConfigLoader → compare"""
        draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))
        draft.set_action("user", "general", "A1", action)
        text = serialize(draft.working_config)
        # Verify tomllib can parse
        import tomllib
        tomllib.loads(text)
        # Verify ConfigLoader roundtrip
        fd, name = tempfile.mkstemp(suffix=".toml")
        os.write(fd, text.encode("utf-8"))
        os.close(fd)
        c2 = load_control_config_from_file(Path(name))
        os.unlink(name)
        a2 = c2.profiles[ProfileId("user")].layers["general"].controls.get("A1")
        self.assertEqual(type(action), type(a2))
        return text

    def test_quote(self):
        r = self._roundtrip(TextAction('say "hello"'))
        self.assertIn("hello", r)

    def test_backslash(self):
        r = self._roundtrip(TextAction("C:\\path"))
        self.assertIn("path", r)

    def test_tab(self):
        self._roundtrip(TextAction("col1\tcol2"))

    def test_newline(self):
        self._roundtrip(TextAction("line1\nline2"))

    def test_carriage_return(self):
        self._roundtrip(TextAction("a\rb"))

    def test_chinese(self):
        r = self._roundtrip(TextAction("中文测试"))

    def test_emoji(self):
        self._roundtrip(TextAction("😀🎉"))

    def test_empty_string(self):
        self._roundtrip(TextAction(""))

    def test_leading_trailing_spaces(self):
        r = self._roundtrip(TextAction("  spaced  "))

    def test_windows_path(self):
        self._roundtrip(TextAction("C:\\Windows\\System32"))

    def test_multiline_text(self):
        self._roundtrip(TextAction("line one\nline two\nline three"))

    def test_debug_log_content(self):
        self._roundtrip(DebugLogAction("debug: test"))

    def test_command_argv(self):
        self._roundtrip(CommandAction(("echo", "hello world", "--flag")))


class TestSerializerOrdering(unittest.TestCase):
    def test_layer_order_preserved(self):
        draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))
        draft.add_layer("user", "layer_1")
        draft.add_layer("user", "layer_2")
        from yyr4_linux_control.control.actions import DebugLogAction
        draft.set_action("user", "general", "A1", DebugLogAction("g"))
        draft.set_action("user", "layer_1", "A1", DebugLogAction("1"))
        draft.set_action("user", "layer_2", "A1", DebugLogAction("2"))
        text = serialize(draft.working_config)
        # general, layer_1, layer_2 in order
        idx_g = text.index('layers.general.')
        idx_1 = text.index('layers.layer_1.')
        idx_2 = text.index('layers.layer_2.')
        self.assertLess(idx_g, idx_1)
        self.assertLess(idx_1, idx_2)

    def test_next_previous_roundtrip(self):
        draft = ConfigDraft(Path("examples/yyr4-control-from-20260711-backup.toml"))
        from yyr4_linux_control.configurator.serializer import serialize
        text = serialize(draft.working_config)
        fd, name = tempfile.mkstemp(suffix=".toml")
        os.write(fd, text.encode("utf-8"))
        os.close(fd)
        c2 = load_control_config_from_file(Path(name))
        os.unlink(name)
        # Layer list should be the same
        self.assertIn(LayerId("general"), c2.profiles[ProfileId("user")].layers)

    def test_canonical_stable(self):
        t1 = serialize(self._config())
        t2 = serialize(self._config())
        self.assertEqual(t1, t2)

    def _config(self):
        return load_control_config_from_file(Path("examples/yyr4-control-from-20260711-backup.toml"))


if __name__ == "__main__":
    unittest.main()
