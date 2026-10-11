"""Validate, build, install safeguards and remove the dedicated Highball FG2X engine."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from src.gptk import detect_gptk_version
from src.gptk30 import fg2x as profile

SOURCE_ID = profile.SOURCE_ID
LEGACY_ENGINE_ID = SOURCE_ID + "-fg2x"
ENGINE_ID = LEGACY_ENGINE_ID + "-gptk30"
ENGINES = Path.home() / "Library/Application Support/Highball/engines"
MODULE = Path("engine/lib/wine/x86_64-unix/win32u.so")


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
    if (not isinstance(manifest, dict) or manifest.get("id") != SOURCE_ID
            or (source / "manifest.json").is_symlink()
            or (source / MODULE).is_symlink()
            or not (source / MODULE).resolve().is_relative_to(source)):
        raise ValueError("Expected the original Highball engine, with a regular win32u.so.")
    original = (source / MODULE).read_bytes()
    return manifest, original, profile.patch(original)


def build(source, destination):
    source, destination = source.resolve(), destination.absolute()
    if destination.name != ENGINE_ID:
        raise ValueError("Destination directory must be named " + ENGINE_ID)
    if destination.exists() or destination.is_symlink():
        raise ValueError("Destination already exists; it will not be overwritten.")
    if destination.resolve().is_relative_to(source):
        raise ValueError("Output cannot be inside the original engine.")
    manifest, original, modified = source_data(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".fg2x-build-", dir=destination.parent) as temp:
        staged = Path(temp) / ENGINE_ID
        copy_engine(source, staged)
        module = staged / MODULE
        if (not module.resolve().is_relative_to(staged.resolve())
                or module.is_symlink() or module.read_bytes() != original):
            raise RuntimeError("Source changed during copying; stopped.")
        module.write_bytes(modified)
        subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", "--timestamp=none",
                        "--identifier", profile.IDENTIFIER, str(module)], check=True)
        subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(module)], check=True)
        signed = module.read_bytes()
        if signed[profile.OFFSET:profile.OFFSET + len(profile.AFTER)] != profile.AFTER:
            raise RuntimeError("Signed module no longer contains the expected patch.")
        if (source / MODULE).read_bytes() != original:
            raise RuntimeError("Original engine changed during build; stopped.")
        manifest["id"] = ENGINE_ID
        manifest["displayName"] = manifest.get("displayName", SOURCE_ID) + " + FG2X GPTK 3.0 (experimental)"
        manifest.setdefault("notes", []).append(
            "Local FG2X v1: hash-pinned HAGS capability response in Wine win32u; "
            "for D3DMetal/MetalFX FG 2X evaluation. Original engine remains installed."
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        marker = {"format": 1, "engine_id": ENGINE_ID, "source_engine": SOURCE_ID, "gptk_version": "3.0",
                  "source_sha256": profile.SOURCE_SHA, "patched_sha256": digest(signed),
                  "module": MODULE.as_posix(), "offset": profile.OFFSET,
                  "before": profile.BEFORE.hex(), "after": profile.AFTER.hex()}
        (staged / "fgx2.json").write_text(json.dumps(marker, indent=2) + "\n")
        # Publication happens only after the private staging build has passed validation.
        if destination.exists() or destination.is_symlink():
            raise RuntimeError("Destination appeared during build; stopped.")
        staged.rename(destination)
    print("Created engine:", destination)
    print("Patched module SHA256:", marker["patched_sha256"])
    print("Original engine, bottle configuration and game directories were not edited.")
    return destination


def verify_engine(root):
    if (root.is_symlink() or root.name not in (ENGINE_ID, LEGACY_ENGINE_ID)
            or (root / "manifest.json").is_symlink() or (root / "fgx2.json").is_symlink()
            or (root / MODULE).is_symlink()
            or not (root / MODULE).resolve().is_relative_to(root.resolve())):
        raise ValueError("Expected the dedicated FG2X engine directory.")
    record = json.loads((root / "fgx2.json").read_text())
    manifest = json.loads((root / "manifest.json").read_text())
    data = (root / MODULE).read_bytes()
    if (not isinstance(record, dict) or not isinstance(manifest, dict)
            or record.get("format") != 1 or record.get("engine_id") != root.name
            or record.get("source_sha256") != profile.SOURCE_SHA or manifest.get("id") != root.name
            or record.get("gptk_version", "3.0" if root.name == LEGACY_ENGINE_ID else None) != "3.0"
            or digest(data) != record.get("patched_sha256")
            or data[profile.OFFSET:profile.OFFSET + len(profile.AFTER)] != profile.AFTER):
        raise ValueError("FG2X engine differs from its installation record; stopped.")
    if detect_gptk_version(root) != "3.0":
        raise ValueError("FG2X engine renderer is no longer GPTK 3.0; stopped.")
    subprocess.run(["/usr/bin/codesign", "--verify", "--strict", str(root / MODULE)], check=True)
    return record


def remove(engine_id=ENGINE_ID):
    require_closed()
    if engine_id not in (ENGINE_ID, LEGACY_ENGINE_ID):
        raise ValueError("Unknown FG2X engine ID; stopped.")
    root = ENGINES / engine_id
    verify_engine(root)
    bottles = ENGINES.parent / "bottles"
    for config in bottles.glob("*/bottle.json"):
        if json.loads(config.read_text()).get("engineID") == engine_id:
            raise RuntimeError("Switch bottle " + config.parent.name + " back to " + SOURCE_ID + " first.")
    shutil.rmtree(root)
    print("Removed only the FG2X engine. Original engine and bottle settings are unchanged.")
