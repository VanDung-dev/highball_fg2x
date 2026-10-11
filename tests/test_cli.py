import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch as mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import bottle, cli, engine


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engines = self.root / "engines"
        self.engines.mkdir()
        for patcher in [mock.object(engine, "ENGINES", self.engines),
                        mock.object(engine, "require_closed"),
                        mock.object(bottle, "detect_gptk_version", return_value="3.0"),
                        mock.object(cli.sys.stdin, "isatty", return_value=True)]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.output = io.StringIO()
        patcher = mock.object(cli.sys, "stdout", self.output)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_bottle(self, name="Games", renderer="d3dmetal"):
        root = self.root / "bottles" / name
        target = root / "drive_c/windows/system32/nvngx.dll"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"original DLL")
        (root / "bottle.json").write_text(json.dumps({"engineID": engine.SOURCE_ID, "renderer": renderer}))
        return root

    def test_bottle_name_and_path_resolve_to_same_validated_target(self):
        root = self.make_bottle()
        self.assertEqual(cli.resolve_bottle("Games"), root.resolve())
        self.assertEqual(cli.resolve_bottle(str(root)), root.resolve())
        (root / "drive_c/windows/system32/nvngx.dll").unlink()
        with self.assertRaisesRegex(ValueError, "NGX DLL is missing"):
            cli.resolve_bottle("Games")

    def test_bottle_selection_checks_renderer_and_skips_symlink_directories(self):
        root = self.make_bottle()
        self.make_bottle("Other", "dxmt")
        (root.parent / "Linked").symlink_to(root, target_is_directory=True)
        with mock("builtins.input", return_value="1"):
            self.assertEqual(cli.select_bottle(), root.resolve())
        self.assertIn("Games [D3DMetal / GPTK 3.0; compatible]", self.output.getvalue())
        self.assertNotIn("Linked", self.output.getvalue())
        for answer in ["abc", "3", "2"]:
            with self.subTest(answer=answer), mock("builtins.input", return_value=answer), self.assertRaises(ValueError):
                cli.select_bottle()
        with mock.object(bottle, "detect_gptk_version", return_value="4.0b2"), \
                mock("builtins.input", return_value="1"), self.assertRaisesRegex(ValueError, "unsupported"):
            cli.select_bottle()

    def test_skip_no_bottles_and_noninteractive_selection(self):
        with mock("builtins.input", return_value="0") as prompt:
            self.assertIsNone(cli.select_bottle(allow_empty=True))
            prompt.assert_not_called()
            self.assertIsNone(cli.select_bottle())
            prompt.assert_called_once()
        self.make_bottle()
        with mock("builtins.input", return_value="0"):
            self.assertIsNone(cli.select_bottle(allow_empty=True))
            self.assertIsNone(cli.select_bottle())
        with mock.object(cli.sys.stdin, "isatty", return_value=False), \
                self.assertRaisesRegex(RuntimeError, "--bottle"):
            cli.select_bottle()

    def test_install_reports_once_after_engine_and_bottle_steps(self):
        root = self.make_bottle()
        with mock.object(cli.sys, "argv", ["main.py", "install", "--source-engine", "source"]), \
                mock("builtins.input", return_value="1"), mock.object(engine, "build") as build, \
                mock.object(bottle, "patch_ngx") as patcher:
            cli.main()
        build.assert_called_once_with(Path("source"), self.engines / engine.ENGINE_ID)
        patcher.assert_called_once_with(root.resolve())
        output = self.output.getvalue()
        self.assertEqual(output.count("Install complete"), 1)
        self.assertIn("(created)", output)
        self.assertIn("Bottle: Games", output)
        self.assertIn("NGX:    ready", output)
        self.assertNotIn("Patched module SHA256", output)
        self.assertNotIn(str(self.engines), output)

    def test_explicit_bottle_reuses_engine_without_prompt_or_rebuild(self):
        root = self.make_bottle()
        (self.engines / engine.ENGINE_ID).mkdir()
        with mock.object(cli.sys, "argv", ["main.py", "install", "--source-engine", "source", "--bottle", "Games"]), \
                mock("builtins.input") as prompt, mock.object(engine, "build") as build, \
                mock.object(engine, "source_data") as validate, \
                mock.object(engine, "verify_engine") as verify, mock.object(bottle, "patch_ngx") as patcher:
            cli.main()
        verify.assert_called_once_with(self.engines / engine.ENGINE_ID)
        validate.assert_called_once_with(Path("source").resolve())
        build.assert_not_called()
        prompt.assert_not_called()
        patcher.assert_called_once_with(root.resolve())
        self.assertIn("(verified)", self.output.getvalue())

    def test_invalid_bottle_keeps_completed_engine_and_does_not_patch_ngx(self):
        self.make_bottle(renderer="dxmt")
        with mock.object(cli.sys, "argv", ["main.py", "install", "--source-engine", "source", "--bottle", "Games"]), \
                mock.object(engine, "build") as build, mock.object(bottle, "patch_ngx") as patcher, \
                self.assertRaisesRegex(ValueError, "D3DMetal/GPTK 3.0"):
            cli.main()
        build.assert_called_once()
        patcher.assert_not_called()
        self.assertIn("Engine ready:", self.output.getvalue())
        self.assertNotIn("Install complete", self.output.getvalue())

    def test_skipped_and_noninteractive_install_are_engine_only(self):
        self.make_bottle()
        for interactive in [True, False]:
            with self.subTest(interactive=interactive), mock.object(cli.sys.stdin, "isatty", return_value=interactive), \
                    mock.object(cli.sys, "argv", ["main.py", "install", "--source-engine", "source"]), \
                    mock("builtins.input", return_value="0") as prompt, mock.object(engine, "build") as build, \
                    mock.object(bottle, "patch_ngx") as patcher:
                cli.main()
                build.assert_called_once()
                patcher.assert_not_called()
                self.assertEqual(prompt.call_count, int(interactive))

    def test_install_completes_engine_before_prompting_for_bottle(self):
        self.make_bottle()
        source = self.engines / engine.SOURCE_ID
        source.mkdir()
        (source / "manifest.json").write_text("{}")
        events = []
        with mock.object(cli.sys, "argv", ["main.py", "install"]), \
                mock.object(engine, "source_data"), mock.object(cli, "detect_gptk_version", return_value="3.0"), \
                mock("builtins.input", side_effect=lambda prompt: events.append(prompt) or "1"), \
                mock.object(engine, "build", side_effect=lambda *args: events.append("build")), \
                mock.object(bottle, "patch_ngx", side_effect=lambda *args: events.append("patch")):
            cli.main()
        self.assertEqual(events, ["Select source engine number (0 to skip): ",
                                  "build", "Select bottle number (0 to skip): ", "patch"])
        output = self.output.getvalue()
        self.assertLess(output.index("Choose a source engine"), output.index("Choose a bottle"))
        self.assertLess(output.index("FG2X engine created"), output.index("Choose a bottle"))

    def test_existing_engine_still_requires_source_selection_before_verifying(self):
        self.make_bottle()
        (self.engines / engine.ENGINE_ID).mkdir()
        events = []
        with mock.object(cli.sys, "argv", ["main.py", "install"]), \
                mock.object(engine, "verify_engine", side_effect=lambda *args: events.append("verify")), \
                mock("builtins.input", side_effect=lambda prompt: events.append("bottle") or "1"), \
                mock.object(cli, "select_engine", side_effect=lambda: events.append("engine") or Path("source")) as select, \
                mock.object(engine, "build") as build, \
                mock.object(bottle, "patch_ngx", side_effect=lambda *args: events.append("patch")):
            cli.main()
        self.assertEqual(events, ["engine", "verify", "bottle", "patch"])
        select.assert_called_once()
        build.assert_not_called()
        output = self.output.getvalue()
        self.assertLess(output.index("Existing FG2X engine verified"), output.index("Choose a bottle"))

    def test_skipped_engine_selection_continues_to_bottle_without_verifying_or_building(self):
        root = self.make_bottle()
        (self.engines / engine.ENGINE_ID).mkdir()
        with mock.object(cli.sys, "argv", ["main.py", "install"]), \
                mock.object(cli, "select_engine", return_value=None), \
                mock.object(cli, "select_bottle", return_value=root) as select, mock.object(engine, "build") as build, \
                mock.object(engine, "verify_engine") as verify, mock.object(bottle, "patch_ngx") as patcher:
            cli.main()
        select.assert_called_once_with(allow_empty=True)
        build.assert_not_called()
        verify.assert_not_called()
        patcher.assert_called_once_with(root)
        self.assertIn("Engine: skipped", self.output.getvalue())
        self.assertNotIn("select the engine above", self.output.getvalue())

    def test_skipping_both_steps_changes_nothing_and_succeeds(self):
        self.make_bottle()
        with mock.object(cli.sys, "argv", ["main.py", "install"]), \
                mock("builtins.input", side_effect=["0", "0"]) as prompt, \
                mock.object(engine, "build") as build, mock.object(engine, "verify_engine") as verify, \
                mock.object(bottle, "patch_ngx") as patcher:
            cli.run()
        self.assertEqual(prompt.call_count, 2)
        build.assert_not_called()
        verify.assert_not_called()
        patcher.assert_not_called()
        self.assertIn("Bottle: skipped", self.output.getvalue())
        self.assertIn("Nothing changed.", self.output.getvalue())

    def test_standalone_build_and_patch_ngx_skip_without_changes(self):
        self.make_bottle()
        for command in ["build", "patch-ngx"]:
            with self.subTest(command=command), mock.object(cli.sys, "argv", ["main.py", command]), \
                    mock("builtins.input", return_value="0"), mock.object(engine, "build") as build, \
                    mock.object(bottle, "patch_ngx") as patcher:
                cli.run()
                build.assert_not_called()
                patcher.assert_not_called()
        self.assertIn("Build skipped", self.output.getvalue())
        self.assertIn("Bottle step skipped", self.output.getvalue())

    def test_bottle_failure_after_skipping_engine_does_not_claim_engine_ready(self):
        root = self.make_bottle()
        with mock.object(cli.sys, "argv", ["main.py", "install", "--bottle", "Games"]), \
                mock.object(cli, "select_engine", return_value=None), \
                mock.object(bottle, "patch_ngx", side_effect=RuntimeError("download failed")), \
                mock.object(engine, "build") as build, self.assertRaisesRegex(RuntimeError, "download failed"):
            cli.main()
        build.assert_not_called()
        self.assertNotIn("Engine ready:", self.output.getvalue())
        self.assertIn("Engine step skipped", self.output.getvalue())

    def test_failed_engine_build_does_not_prompt_for_bottle(self):
        with mock.object(cli.sys, "argv", ["main.py", "install", "--source-engine", "source"]), \
                mock.object(engine, "build", side_effect=RuntimeError("build failed")), \
                mock.object(cli, "select_bottle") as select, self.assertRaisesRegex(RuntimeError, "build failed"):
            cli.main()
        select.assert_not_called()

    def test_existing_engine_rejects_invalid_explicit_source_before_bottle_step(self):
        (self.engines / engine.ENGINE_ID).mkdir()
        with mock.object(cli.sys, "argv", ["main.py", "install", "--source-engine", "source"]), \
                mock.object(engine, "source_data", side_effect=ValueError("source mismatch")), \
                mock.object(engine, "verify_engine") as verify, mock.object(cli, "select_bottle") as select, \
                self.assertRaisesRegex(ValueError, "source mismatch"):
            cli.main()
        verify.assert_not_called()
        select.assert_not_called()

    def test_partial_failure_reports_engine_state_without_success_summary(self):
        self.make_bottle()
        with mock.object(cli.sys, "argv", ["main.py", "install", "--source-engine", "source", "--bottle", "Games"]), \
                mock.object(engine, "build"), mock.object(bottle, "patch_ngx", side_effect=RuntimeError("download failed")), \
                self.assertRaisesRegex(RuntimeError, "download failed"):
            cli.main()
        self.assertIn("Engine ready:", self.output.getvalue())
        self.assertIn("Bottle step failed", self.output.getvalue())
        self.assertNotIn("Install complete", self.output.getvalue())

    def test_patch_ngx_without_arguments_prompts_for_bottle(self):
        root = self.make_bottle()
        with mock.object(cli.sys, "argv", ["main.py", "patch-ngx"]), mock("builtins.input", return_value="1"), \
                mock.object(bottle, "patch_ngx") as patcher:
            cli.main()
        patcher.assert_called_once_with(root.resolve(), bottle.NGX_CACHE)
        self.assertIn("Bottle patch complete", self.output.getvalue())

    def test_signing_failure_keeps_diagnostic_stderr(self):
        error = subprocess.CalledProcessError(1, ["codesign"], stderr="invalid signature\n")
        with mock.object(cli, "main", side_effect=error), self.assertRaisesRegex(SystemExit, "Stopped: invalid signature"):
            cli.run()


if __name__ == "__main__":
    unittest.main()
