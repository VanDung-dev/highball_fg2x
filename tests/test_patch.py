import json
import os
import plistlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch as mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import cli
from src import engine as fg


class PatchTests(unittest.TestCase):
    def renderer_fixture(self, engine, version="3.0", relative="frameworks/renderer/d3dmetal"):
        renderer = engine / relative
        (renderer / "wine").mkdir(parents=True, exist_ok=True)
        info = renderer / "external/D3DMetal.framework/Versions/A/Resources/Info.plist"
        info.parent.mkdir(parents=True, exist_ok=True)
        info.write_bytes(plistlib.dumps({"CFBundleIdentifier": "com.apple.D3DMetal",
                                        "CFBundleShortVersionString": version}))
        return info

    def test_gptk_detection_prefers_override_to_template(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = Path(directory)
            self.renderer_fixture(engine)
            self.assertEqual(fg.detect_gptk_version(engine), "3.0")
            self.renderer_fixture(engine, "4.0b2", "renderers/d3dmetal")
            self.assertEqual(fg.detect_gptk_version(engine), "4.0b2")

    def test_gptk_detection_does_not_assume_version_for_missing_or_invalid_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = Path(directory)
            self.renderer_fixture(engine)
            info = self.renderer_fixture(engine, "4.0b2", "renderers/d3dmetal")
            for data in [b"not a plist", plistlib.dumps({"CFBundleIdentifier": "com.apple.D3DMetal"}),
                         plistlib.dumps({"CFBundleIdentifier": "unrelated", "CFBundleShortVersionString": "3.0"})]:
                info.write_bytes(data)
                with self.assertRaises(ValueError):
                    fg.detect_gptk_version(engine)
            info.unlink()
            with self.assertRaisesRegex(ValueError, "metadata is missing"):
                fg.detect_gptk_version(engine)

    def test_gptk4_is_rejected_even_when_wine_binary_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source_fixture(Path(directory) / "engines")
            self.renderer_fixture(source, "4.0b2", "renderers/d3dmetal")
            with mock.object(fg.profile, "SOURCE_SHA", fg.digest(self.fixture())), \
                    self.assertRaisesRegex(ValueError, "GPTK 4.0b2"):
                fg.source_data(source)

    def test_assembled_payload_matches_and_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            obj = Path(directory) / "payload.o"
            executable = Path(directory) / "payload-test"
            compiler = ["/usr/bin/xcrun", "clang", "-target", "x86_64-apple-macos10.15"]
            env = dict(os.environ)
            if Path("/Library/Developer/CommandLineTools/usr/bin/clang").exists():
                env["DEVELOPER_DIR"] = "/Library/Developer/CommandLineTools"
            subprocess.run(compiler + ["-c", str(ROOT / "src/gptk30/hags-query.s"), "-o", str(obj)], check=True, env=env)
            output = subprocess.run(["/usr/bin/otool", "-s", "__TEXT", "__text", str(obj)],
                                    capture_output=True, text=True, check=True, env=env).stdout
            hex_bytes = []
            for line in output.splitlines():
                if re.match(r"^[0-9a-f]{16} ", line):
                    hex_bytes.extend(line.split()[1:])
            self.assertEqual(bytes.fromhex("".join(hex_bytes)), fg.profile.PAYLOAD)
            subprocess.run(compiler + [str(ROOT / "tests/payload_test.c"), str(obj), "-o", str(executable)], check=True, env=env)
            subprocess.run([str(executable)], check=True)

    def fixture(self):
        data = bytearray(fg.profile.OFFSET + len(fg.profile.BEFORE) + 100)
        data[:8] = bytes.fromhex("cffaedfe07000001")
        data[fg.profile.OFFSET:fg.profile.OFFSET + len(fg.profile.BEFORE)] = fg.profile.BEFORE
        return bytes(data)

    def test_changes_only_function_and_keeps_length(self):
        data = self.fixture()
        with mock.object(fg.profile, "SOURCE_SHA", fg.digest(data)):
            result = fg.profile.patch(data)
        self.assertEqual(len(result), len(data))
        self.assertEqual(result[:fg.profile.OFFSET], data[:fg.profile.OFFSET])
        end = fg.profile.OFFSET + len(fg.profile.BEFORE)
        self.assertEqual(result[end:], data[end:])
        self.assertEqual(result[fg.profile.OFFSET:end], fg.profile.AFTER)

    def test_rejects_unknown_binary(self):
        with self.assertRaises(ValueError):
            fg.profile.patch(self.fixture())

    def test_checks_preimage_even_with_matching_hash(self):
        data = bytearray(self.fixture()); data[fg.profile.OFFSET] ^= 1; data = bytes(data)
        with mock.object(fg.profile, "SOURCE_SHA", fg.digest(data)), self.assertRaises(ValueError):
            fg.profile.patch(data)

    def test_rejects_wrong_architecture(self):
        data = bytearray(self.fixture()); data[4] = 12; data = bytes(data)
        with mock.object(fg.profile, "SOURCE_SHA", fg.digest(data)), self.assertRaises(ValueError):
            fg.profile.patch(data)

    def source_fixture(self, engines):
        source = engines / fg.SOURCE_ID
        (source / fg.MODULE).parent.mkdir(parents=True)
        (source / "manifest.json").write_text(json.dumps({"id": fg.SOURCE_ID}))
        (source / fg.MODULE).write_bytes(self.fixture())
        self.renderer_fixture(source)
        return source

    def test_selection_checks_missing_and_empty_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            engines = Path(directory) / "engines"
            with mock.object(fg, "ENGINES", engines), mock("builtins.input") as prompt:
                with self.assertRaisesRegex(RuntimeError, "directory is missing"):
                    cli.select_engine()
                engines.mkdir()
                with mock.object(cli.sys.stdin, "isatty", return_value=True), mock("builtins.input", return_value="0"):
                    self.assertIsNone(cli.select_engine())
                prompt.assert_not_called()

    def test_selection_validates_binaries_before_prompting(self):
        with tempfile.TemporaryDirectory() as directory:
            engines = Path(directory) / "engines"
            source = self.source_fixture(engines)
            with mock.object(fg, "ENGINES", engines), mock.object(cli.sys.stdin, "isatty", return_value=True), \
                    mock("builtins.input", return_value="1") as prompt:
                with self.assertRaisesRegex(ValueError, "unsupported"):
                    cli.select_engine()
                prompt.assert_called_once()
            with mock.object(fg, "ENGINES", engines), mock.object(fg.profile, "SOURCE_SHA", fg.digest(self.fixture())), \
                    mock.object(cli.sys.stdin, "isatty", return_value=True), mock("builtins.input", return_value="1"):
                self.assertEqual(cli.select_engine(), source)

    def test_selection_skips_zero_and_rejects_invalid_and_unsupported_choices(self):
        with tempfile.TemporaryDirectory() as directory:
            engines = Path(directory) / "engines"
            source = self.source_fixture(engines)
            unsupported = engines / "zz-other"; unsupported.mkdir()
            (unsupported / "manifest.json").write_text("invalid json")
            before = (source / fg.MODULE).read_bytes()
            with mock.object(fg, "ENGINES", engines), mock.object(fg.profile, "SOURCE_SHA", fg.digest(before)), \
                    mock.object(cli.sys.stdin, "isatty", return_value=True):
                with mock("builtins.input", return_value="0"):
                    self.assertIsNone(cli.select_engine())
                for answer, error in [("abc", ValueError), ("3", ValueError), ("2", ValueError)]:
                    with self.subTest(answer=answer), mock("builtins.input", return_value=answer), self.assertRaises(error):
                        cli.select_engine()
            self.assertEqual((source / fg.MODULE).read_bytes(), before)

    def test_selection_requires_explicit_source_without_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            engines = Path(directory) / "engines"
            self.source_fixture(engines)
            with mock.object(fg, "ENGINES", engines), mock.object(fg.profile, "SOURCE_SHA", fg.digest(self.fixture())), \
                    mock.object(cli.sys.stdin, "isatty", return_value=False), mock("builtins.input") as prompt:
                with self.assertRaisesRegex(RuntimeError, "--source-engine"):
                    cli.select_engine()
                prompt.assert_not_called()

    def test_build_and_install_use_selected_or_explicit_source(self):
        with tempfile.TemporaryDirectory() as directory:
            engines = Path(directory) / "engines"
            selected, explicit = Path(directory) / "selected", Path(directory) / "explicit"
            for command in ["build", "install"]:
                for supplied in [False, True]:
                    arguments = ["main.py", command]
                    if supplied:
                        arguments += ["--source-engine", str(explicit)]
                    with self.subTest(command=command, supplied=supplied), \
                            mock.object(cli.sys, "argv", arguments), mock.object(fg, "ENGINES", engines), \
                            mock.object(cli, "select_engine", return_value=selected) as select, \
                            mock.object(fg, "build") as build, mock.object(fg, "require_closed"):
                        cli.main()
                        self.assertEqual(build.call_args.args[0], explicit if supplied else selected)
                        self.assertEqual(build.call_args.args[1],
                                         (ROOT / "dist" if command == "build" else engines) / fg.ENGINE_ID)
                        self.assertEqual(select.call_count, 0 if supplied else 1)

    def installed_fixture(self, engines, engine_id=None):
        engine_id = engine_id or fg.ENGINE_ID
        root = engines / engine_id
        (root / fg.MODULE).parent.mkdir(parents=True)
        data = bytearray(self.fixture())
        data[fg.profile.OFFSET:fg.profile.OFFSET + len(fg.profile.AFTER)] = fg.profile.AFTER
        (root / fg.MODULE).write_bytes(data)
        (root / "manifest.json").write_text(json.dumps({"id": engine_id}))
        (root / "fgx2.json").write_text(json.dumps({
            "format": 1, "engine_id": engine_id, "source_sha256": fg.profile.SOURCE_SHA, "gptk_version": "3.0",
            "patched_sha256": fg.digest(data)}))
        self.renderer_fixture(root)
        return root

    def test_remove_refuses_an_engine_used_by_a_bottle(self):
        with tempfile.TemporaryDirectory() as directory:
            engines = Path(directory) / "engines"
            root = self.installed_fixture(engines)
            bottle = Path(directory) / "bottles/test"; bottle.mkdir(parents=True)
            (bottle / "bottle.json").write_text(json.dumps({"engineID": fg.ENGINE_ID}))
            with mock.object(fg, "ENGINES", engines), mock.object(fg, "require_closed"), \
                    mock.object(fg.subprocess, "run"), self.assertRaises(RuntimeError):
                fg.remove()
            self.assertTrue((root / fg.MODULE).exists())

    def test_remove_refuses_changed_module(self):
        with tempfile.TemporaryDirectory() as directory:
            engines = Path(directory) / "engines"; root = self.installed_fixture(engines)
            (root / fg.MODULE).write_bytes(b"user modification")
            with mock.object(fg, "ENGINES", engines), mock.object(fg, "require_closed"), \
                    self.assertRaises(ValueError):
                fg.remove()
            self.assertEqual((root / fg.MODULE).read_bytes(), b"user modification")

    def test_remove_keeps_original_engine_and_bottle_config(self):
        with tempfile.TemporaryDirectory() as directory:
            engines = Path(directory) / "engines"; root = self.installed_fixture(engines)
            original = engines / fg.SOURCE_ID; original.mkdir(); (original / "keep").write_bytes(b"original")
            bottle = Path(directory) / "bottles/test"; bottle.mkdir(parents=True)
            data = json.dumps({"engineID": fg.SOURCE_ID, "environment": {"D3DM_ENABLE_METALFX": "1"}})
            (bottle / "bottle.json").write_text(data)
            with mock.object(fg, "ENGINES", engines), mock.object(fg, "require_closed"), \
                    mock.object(fg.subprocess, "run"):
                fg.remove()
            self.assertFalse(root.exists())
            self.assertEqual((original / "keep").read_bytes(), b"original")
            self.assertEqual((bottle / "bottle.json").read_text(), data)

    def test_legacy_engine_remains_verifiable_and_protected_when_in_use(self):
        with tempfile.TemporaryDirectory() as directory:
            engines = Path(directory) / "engines"
            root = self.installed_fixture(engines, fg.LEGACY_ENGINE_ID)
            marker = root / "fgx2.json"
            data = json.loads(marker.read_text()); del data["gptk_version"]
            marker.write_text(json.dumps(data))
            bottle = Path(directory) / "bottles/test"; bottle.mkdir(parents=True)
            (bottle / "bottle.json").write_text(json.dumps({"engineID": fg.LEGACY_ENGINE_ID}))
            with mock.object(fg, "ENGINES", engines), mock.object(fg, "require_closed"), mock.object(fg.subprocess, "run"):
                self.assertEqual(fg.verify_engine(root)["engine_id"], fg.LEGACY_ENGINE_ID)
                with self.assertRaisesRegex(RuntimeError, "Switch bottle"):
                    fg.remove(fg.LEGACY_ENGINE_ID)
            self.assertTrue(root.is_dir())

    def test_new_engine_requires_matching_gptk_marker_and_renderer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.installed_fixture(Path(directory) / "engines")
            marker = root / "fgx2.json"
            data = json.loads(marker.read_text()); del data["gptk_version"]
            marker.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "installation record"):
                fg.verify_engine(root)
            data["gptk_version"] = "3.0"; marker.write_text(json.dumps(data))
            self.renderer_fixture(root, "4.0b2", "renderers/d3dmetal")
            with self.assertRaisesRegex(ValueError, "renderer is no longer GPTK 3.0"):
                fg.verify_engine(root)


if __name__ == "__main__":
    unittest.main()
