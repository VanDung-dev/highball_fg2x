"""Identify the D3DMetal version shipped by an installed Highball engine."""
from pathlib import Path
import plistlib
import re
from xml.parsers.expat import ExpatError


def version_from_plist(data):
    try:
        metadata = plistlib.loads(data)
    except (plistlib.InvalidFileException, ExpatError, ValueError) as error:
        raise ValueError("Invalid D3DMetal version plist.") from error
    if not isinstance(metadata, dict) or metadata.get("CFBundleIdentifier") != "com.apple.D3DMetal":
        raise ValueError("Invalid D3DMetal framework metadata.")
    version = metadata.get("CFBundleShortVersionString") or metadata.get("CFBundleVersion")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+(?:\.\d+)?(?:[a-zA-Z]\d+)?", version):
        raise ValueError("Cannot identify the D3DMetal/GPTK version.")
    return version


def detect_gptk_version(engine):
    engine = Path(engine).resolve()
    # Highball prefers its own renderer over the framework template's fallback.
    for relative in ["renderers/d3dmetal", "frameworks/renderer/d3dmetal"]:
        renderer = engine / relative
        if not (renderer / "wine").is_dir():
            continue
        info = renderer / "external/D3DMetal.framework/Versions/A/Resources/Info.plist"
        if not info.resolve().is_relative_to(engine):
            raise ValueError("D3DMetal version metadata escapes the engine directory.")
        if not info.is_file():
            raise ValueError("D3DMetal version metadata is missing: " + str(info))
        return version_from_plist(info.read_bytes())
    raise ValueError("No D3DMetal renderer found in the engine.")
