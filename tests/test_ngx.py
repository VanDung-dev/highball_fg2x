import hashlib
import io
import json
from pathlib import Path
import plistlib
import tarfile
import tempfile
import sys
import unittest
from unittest.mock import patch as mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import cli, engine
from src import bottle as fg
ngx = fg.ngx
DLL = b"MZ-test-GPTK3-NGX"


class NGXTests(unittest.TestCase):
    def archive(self, path, version="3.0", dll=DLL, symlink=False):
        with tarfile.open(path, "w:xz") as archive:
            for name, data in [(ngx.INFO_MEMBER, plistlib.dumps({"CFBundleIdentifier": "com.apple.D3DMetal",
                                                               "CFBundleShortVersionString": version})),
                               (ngx.DLL_MEMBER.replace("d3dmetal/", "dxmt/"), b"wrong DXMT bridge"),
                               (ngx.DLL_MEMBER, dll)]:
                info = tarfile.TarInfo(name); info.size = len(data)
                if symlink and name == ngx.DLL_MEMBER:
                    info.type = tarfile.SYMTYPE; info.linkname = "../../outside.dll"; info.size = 0
                archive.addfile(info, io.BytesIO(data))
        return path.read_bytes()

    def pins(self, data):
        return mock.multiple(ngx, ARCHIVE_SHA=hashlib.sha256(data).hexdigest(), ARCHIVE_SIZE=len(data),
                             DLL_SHA=hashlib.sha256(DLL).hexdigest(), DLL_SIZE=len(DLL))

    def test_download_extracts_exact_bridge_and_reuses_verified_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = self.archive(root / "fixture.tar.xz")
            with self.pins(data), mock.object(ngx, "urlopen", return_value=io.BytesIO(data)) as download:
                dll = ngx.fetch_ngx(root / "cache")
                self.assertEqual(dll.read_bytes(), DLL)
                self.assertEqual(ngx.fetch_ngx(root / "cache"), dll)
                self.assertEqual(download.call_count, 1)
            self.assertEqual(sorted(p.name for p in (root / "cache").iterdir()),
                             ["Template-1.0.11.tar.xz", "nvngx-gptk30.dll"])

    def test_bad_truncated_or_oversized_download_never_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = self.archive(root / "fixture.tar.xz")
            for index, downloaded in enumerate([data[:-1], bytes([data[0] ^ 1]) + data[1:], data + b"extra"]):
                cache = root / str(index)
                with self.subTest(index=index), self.pins(data), \
                        mock.object(ngx, "urlopen", return_value=io.BytesIO(downloaded)), self.assertRaises(ValueError):
                    ngx.fetch_ngx(cache)
                self.assertEqual(list(cache.iterdir()), [])

    def test_wrong_version_dll_or_archive_link_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, arguments in enumerate([{"version": "4.0b2"}, {"dll": b"x" * len(DLL)}, {"symlink": True}]):
                path = root / str(index)
                data = self.archive(path, **arguments)
                with self.subTest(arguments=arguments), self.pins(data), self.assertRaises(ValueError):
                    ngx.archive_dll(path)

    def test_corrupt_cache_is_rejected_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ["Template-1.0.11.tar.xz", "nvngx-gptk30.dll"]:
                cache = root / name; cache.mkdir()
                (cache / name).write_bytes(b"corrupt cache")
                with self.subTest(name=name), mock.object(ngx, "urlopen") as download, self.assertRaises(ValueError):
                    ngx.fetch_ngx(cache)
                download.assert_not_called()

    def bottle(self, root, version="3.0"):
        engine = root / "engines/test-engine"
        renderer = engine / "frameworks/renderer/d3dmetal"
        (renderer / "wine").mkdir(parents=True)
        info = renderer / "external/D3DMetal.framework/Versions/A/Resources/Info.plist"
        info.parent.mkdir(parents=True)
        info.write_bytes(plistlib.dumps({"CFBundleIdentifier": "com.apple.D3DMetal",
                                        "CFBundleShortVersionString": version}))
        bottle = root / "bottle"
        target = bottle / "drive_c/windows/system32/nvngx.dll"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"original builtin stub")
        (bottle / "bottle.json").write_text(json.dumps({"engineID": "test-engine", "renderer": "d3dmetal"}))
        source = root / "downloaded.dll"; source.write_bytes(DLL)
        return bottle, target, source

    def test_patch_preserves_first_backup_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bottle, target, source = self.bottle(root)
            config = (bottle / "bottle.json").read_bytes()
            original = target.read_bytes()
            backup = target.with_name(target.name + ".before-ngx-test")
            with mock.object(engine, "ENGINES", root / "engines"), mock.object(engine, "require_closed"), \
                    mock.object(ngx, "DLL_SHA", hashlib.sha256(DLL).hexdigest()), \
                    mock.object(ngx, "fetch_ngx", return_value=source) as fetch:
                fg.patch_ngx(bottle)
                self.assertEqual(target.read_bytes(), DLL)
                self.assertEqual(backup.read_bytes(), original)
                fg.patch_ngx(bottle)
                self.assertEqual(fetch.call_count, 1)
                target.write_bytes(b"another stub")
                fg.patch_ngx(bottle)
                self.assertEqual(backup.read_bytes(), original)
                self.assertEqual(target.read_bytes(), DLL)
            self.assertEqual((bottle / "bottle.json").read_bytes(), config)

    def test_gptk4_bottle_is_rejected_before_downloading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bottle, target, _ = self.bottle(root, "4.0b2")
            original = target.read_bytes()
            with mock.object(engine, "ENGINES", root / "engines"), mock.object(engine, "require_closed"), \
                    mock.object(ngx, "fetch_ngx") as fetch, self.assertRaisesRegex(ValueError, "GPTK 3.0"):
                fg.patch_ngx(bottle)
            fetch.assert_not_called()
            self.assertEqual(target.read_bytes(), original)

    def test_target_or_backup_symlink_cannot_change_external_files(self):
        for link_backup in [False, True]:
            with self.subTest(link_backup=link_backup), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                bottle, target, _ = self.bottle(root)
                outside = root / "outside.dll"; outside.write_bytes(b"preserve external file")
                link = target.with_name(target.name + ".before-ngx-test") if link_backup else target
                if link.exists(): link.unlink()
                link.symlink_to(outside)
                with mock.object(engine, "ENGINES", root / "engines"), mock.object(engine, "require_closed"), \
                        mock.object(ngx, "fetch_ngx") as fetch, self.assertRaises(ValueError):
                    fg.patch_ngx(bottle)
                fetch.assert_not_called()
                self.assertEqual(outside.read_bytes(), b"preserve external file")

    def test_failed_replacement_keeps_original_and_complete_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bottle, target, source = self.bottle(root)
            original = target.read_bytes()
            with mock.object(engine, "ENGINES", root / "engines"), mock.object(engine, "require_closed"), \
                    mock.object(ngx, "DLL_SHA", hashlib.sha256(DLL).hexdigest()), \
                    mock.object(ngx, "fetch_ngx", return_value=source), \
                    mock.object(Path, "replace", side_effect=OSError("replace failed")), self.assertRaises(OSError):
                fg.patch_ngx(bottle)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(target.with_name(target.name + ".before-ngx-test").read_bytes(), original)

    def test_cli_patch_ngx_and_install_bottle_call_shared_mechanism(self):
        bottle = ROOT / "work/test-bottle"
        for command in ["patch-ngx", "install"]:
            with self.subTest(command=command), mock.object(cli.sys, "argv", ["main.py", command, "--bottle", str(bottle)]), \
                    mock.object(fg, "patch_ngx") as patcher, mock.object(engine, "require_closed"), \
                    mock.object(engine, "verify_engine"), mock.object(cli, "select_engine", return_value=Path("source")), \
                    mock.object(cli, "resolve_bottle", return_value=bottle), \
                    mock.object(engine, "build"):
                cli.main()
                self.assertEqual(patcher.call_args.args[0], bottle)


if __name__ == "__main__":
    unittest.main()
