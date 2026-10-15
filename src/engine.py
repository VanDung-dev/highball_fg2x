"""Validate, build, install safeguards and remove the dedicated Highball FG2X engine."""
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

from src.gptk import detect_gptk_version
from src.gptk30 import fg2x as profile

SOURCE_ID = profile.SOURCE_ID
# Newer Highball revisions (r22, r24, r26, ...) keep the same Wine 10.0 rev-6
# win32u.so bytes; accept any of them when the hash/patch checks below pass.
SOURCE_RE = re.compile(r"^x64-sikarugir10\.0_6-r\d+$")
ENGINE_RE = re.compile(r"^x64-sikarugir10\.0_6-r\d+-fg2x(?:-gptk30)?$")
LEGACY_SUFFIX = "-fg2x"
ENGINE_SUFFIX = "-fg2x-gptk30"
LEGACY_ENGINE_ID = SOURCE_ID + LEGACY_SUFFIX
ENGINE_ID = SOURCE_ID + ENGINE_SUFFIX
ENGINES = Path.home() / "Library/Application Support/Highball/engines"
MODULE = Path("engine/lib/wine/x86_64-unix/win32u.so")


def is_supported_source(engine_id):
    return isinstance(engine_id, str) and SOURCE_RE.fullmatch(engine_id) is not None


def is_fg2x_engine(engine_id):
    return isinstance(engine_id, str) and ENGINE_RE.fullmatch(engine_id) is not None


def is_legacy_engine(engine_id):
    return is_fg2x_engine(engine_id) and not engine_id.endswith("-gptk30")


def engine_id_for(source_id):
    return source_id + ENGINE_SUFFIX


def legacy_engine_id_for(source_id):
    return source_id + LEGACY_SUFFIX


def source_id_for_engine(engine_id):
    if not is_fg2x_engine(engine_id):
        return None
    if engine_id.endswith(ENGINE_SUFFIX):
        return engine_id[: -len(ENGINE_SUFFIX)]
    return engine_id[: -len(LEGACY_SUFFIX)]


def installed_fg2x_engines():
    """Names of FG2X engine directories currently installed, oldest revision first."""
    if not ENGINES.is_dir():
        return []
    return sorted(root.name for root in ENGINES.iterdir()
                  if root.is_dir() and not root.is_symlink() and is_fg2x_engine(root.name))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require_closed():
    result = subprocess.run(["/bin/ps", "-axo", "comm="], check=True,
                            capture_output=True, text=True)
    names = {Path(line.strip()).name.lower() for line in result.stdout.splitlines()}
    if names & {"highball", "wineserver", "wine", "wine64", "steam.exe"}:
        raise RuntimeError("Close Highball, Steam and Wine apps before install/remove.")


def copy_engine(source, target):
    """APFS copy-on-write where available; never use hard links to the source."""
    result = subprocess.run(["/bin/cp", "-cR", str(source), str(target)],
                            capture_output=True, text=True, timeout=180)
    if result.returncode:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, symlinks=True)


def source_data(source):
    version = detect_gptk_version(source)
    if version != "3.0":
        raise ValueError("GPTK " + version + " detected; only GPTK 3.0 is implemented (gptk40 is a placeholder).")
    manifest = json.loads((source / "manifest.json").read_text())
    manifest_id = manifest.get("id") if isinstance(manifest, dict) else None
    if (not isinstance(manifest, dict) or not is_supported_source(manifest_id)
            or (source / "manifest.json").is_symlink()
            or (source / MODULE).is_symlink()
            or not (source / MODULE).resolve().is_relative_to(source)):
        raise ValueError("Expected an original x64-sikarugir10.0_6-r<N> Highball engine, with a regular win32u.so.")
    original = (source / MODULE).read_bytes()
    return manifest, original, profile.patch(original)


def build(source, destination):
    source, destination = source.resolve(), destination.absolute()
    if not is_fg2x_engine(destination.name):
        raise ValueError("Destination directory must look like <source>-fg2x-gptk30, e.g. " + ENGINE_ID)
    if destination.exists() or destination.is_symlink():
        raise ValueError("Destination already exists; it will not be overwritten.")
    if destination.resolve().is_relative_to(source):
        raise ValueError("Output cannot be inside the original engine.")
    manifest, original, modified = source_data(source)
    source_id = manifest.get("id")
    if destination.name not in (engine_id_for(source_id), legacy_engine_id_for(source_id)):
        raise ValueError("Destination " + destination.name + " does not match source "
                         + str(source_id) + "; expected " + engine_id_for(source_id))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".fg2x-build-", dir=destination.parent) as temp:
        staged = Path(temp) / destination.name
        copy_engine(source, staged)
        module = staged / MODULE
        if (not module.resolve().is_relative_to(staged.resolve())
                or module.is_symlink() or module.read_bytes() != original):
            raise RuntimeError("Source changed during copying; stopped.")
        module.write_bytes(modified)
        subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", "--timestamp=none",
                        "--identifier", profile.IDENTIFIER, str(module)], check=True, capture_output=True, text=True)
        subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(module)],
                       check=True, capture_output=True, text=True)
        signed = module.read_bytes()
        if signed[profile.OFFSET:profile.OFFSET + len(profile.AFTER)] != profile.AFTER:
            raise RuntimeError("Signed module no longer contains the expected patch.")
        if (source / MODULE).read_bytes() != original:
            raise RuntimeError("Original engine changed during build; stopped.")
        manifest["id"] = destination.name
        manifest["displayName"] = manifest.get("displayName", source_id) + " + FG2X GPTK 3.0 (experimental)"
        manifest.setdefault("notes", []).append(
            "Local FG2X v1: hash-pinned HAGS capability response in Wine win32u; "
            "for D3DMetal/MetalFX FG 2X evaluation. Original engine remains installed."
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        marker = {"format": 1, "engine_id": destination.name, "source_engine": source_id, "gptk_version": "3.0",
                  "source_sha256": profile.SOURCE_SHA, "patched_sha256": digest(signed),
                  "module": MODULE.as_posix(), "offset": profile.OFFSET,
                  "before": profile.BEFORE.hex(), "after": profile.AFTER.hex()}
        (staged / "fgx2.json").write_text(json.dumps(marker, indent=2) + "\n")
        # Publication happens only after the private staging build has passed validation.
        if destination.exists() or destination.is_symlink():
            raise RuntimeError("Destination appeared during build; stopped.")
        staged.rename(destination)
    return destination


def verify_engine(root):
    if (root.is_symlink() or not is_fg2x_engine(root.name)
            or (root / "manifest.json").is_symlink() or (root / "fgx2.json").is_symlink()
            or (root / MODULE).is_symlink()
            or not (root / MODULE).resolve().is_relative_to(root.resolve())):
        raise ValueError("Expected the dedicated FG2X engine directory.")
    if (not (root / "manifest.json").is_file() or not (root / "fgx2.json").is_file()
            or not (root / MODULE).is_file()):
        raise ValueError("FG2X engine " + root.name + " is missing files; nothing was changed.")
    record = json.loads((root / "fgx2.json").read_text())
    manifest = json.loads((root / "manifest.json").read_text())
    data = (root / MODULE).read_bytes()
    source_id = record.get("source_engine") if isinstance(record, dict) else None
    if not is_supported_source(source_id):
        # Test fixtures and very old installs may lack source_engine; derive it
        # from the directory name instead of rejecting a valid engine.
        if source_id is not None:
            raise ValueError("FG2X engine differs from its installation record; stopped.")
        source_id = source_id_for_engine(root.name)
        if not is_supported_source(source_id):
            raise ValueError("FG2X engine differs from its installation record; stopped.")
    legacy_default = "3.0" if root.name == legacy_engine_id_for(source_id) else None
    if (not isinstance(record, dict) or not isinstance(manifest, dict)
            or record.get("format") != 1 or record.get("engine_id") != root.name
            or root.name not in (engine_id_for(source_id), legacy_engine_id_for(source_id))
            or record.get("source_sha256") != profile.SOURCE_SHA or manifest.get("id") != root.name
            or record.get("gptk_version", legacy_default) != "3.0"
            or digest(data) != record.get("patched_sha256")
            or data[profile.OFFSET:profile.OFFSET + len(profile.AFTER)] != profile.AFTER):
        raise ValueError("FG2X engine differs from its installation record; stopped.")
    if detect_gptk_version(root) != "3.0":
        raise ValueError("FG2X engine renderer is no longer GPTK 3.0; stopped.")
    subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(root / MODULE)], check=True)
    return record


def remove(engine_id=ENGINE_ID):
    require_closed()
    if not is_fg2x_engine(engine_id):
        raise ValueError("Unknown FG2X engine ID; expected like " + ENGINE_ID + ".")
    root = ENGINES / engine_id
    if not root.is_dir() or root.is_symlink():
        installed = installed_fg2x_engines()
        hint = (" Installed FG2X engine: " + installed[0] + "."
                if len(installed) == 1 else
                " Installed FG2X engines: " + ", ".join(installed) + "."
                if installed else
                " No FG2X engine is installed.")
        raise ValueError("No FG2X engine " + engine_id + " is installed; nothing was removed." + hint)
    verify_engine(root)
    source_id = source_id_for_engine(engine_id)
    bottles = ENGINES.parent / "bottles"
    for config in bottles.glob("*/bottle.json"):
        if json.loads(config.read_text()).get("engineID") == engine_id:
            raise RuntimeError("Switch bottle " + config.parent.name + " back to " + str(source_id) + " first.")
    shutil.rmtree(root)
    print("Removed only the FG2X engine. Original engine and bottle settings are unchanged.")
