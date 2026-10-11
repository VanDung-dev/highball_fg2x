"""Back up and replace a bottle's NGX bridge with the verified GPTK 3.0 download."""
import json
import os
from pathlib import Path
import stat
import tempfile

from src import engine
from src.gptk import detect_gptk_version
from src.gptk30 import ngx

NGX_CACHE = Path(__file__).resolve().parents[1] / "work/downloads/gptk30"


def patch_ngx(bottle, cache=NGX_CACHE):
    engine.require_closed()
    bottle = bottle.resolve()
    config = json.loads((bottle / "bottle.json").read_text())
    engine_id = config.get("engineID") if isinstance(config, dict) else None
    if not isinstance(engine_id, str) or Path(engine_id).name != engine_id:
        raise ValueError("Bottle has an invalid engine ID.")
    if config.get("renderer") != "d3dmetal" or detect_gptk_version(engine.ENGINES / engine_id) != "3.0":
        raise ValueError("NGX patch requires a bottle using D3DMetal/GPTK 3.0.")
    target = bottle / "drive_c/windows/system32/nvngx.dll"
    backup = target.with_name(target.name + ".before-ngx-test")
    for path in [target, backup]:
        if path.is_symlink() or not path.resolve().is_relative_to(bottle):
            raise ValueError("NGX target/backup must be regular files inside the bottle.")
    original = target.read_bytes()
    if engine.digest(original) == ngx.DLL_SHA:
        print("Bottle NGX DLL is already correct:", target)
        return target
    downloaded = ngx.fetch_ngx(cache).read_bytes()
    if engine.digest(downloaded) != ngx.DLL_SHA:
        raise ValueError("NGX cache changed before installation; stopped.")
    engine.require_closed()
    if target.read_bytes() != original:
        raise RuntimeError("Bottle NGX DLL changed during download; stopped.")
    with tempfile.TemporaryDirectory(prefix=".ngx-patch-", dir=target.parent) as temp:
        replacement = Path(temp) / "nvngx.dll"
        replacement.write_bytes(downloaded)
        replacement.chmod(stat.S_IMODE(target.stat().st_mode))
        snapshot = Path(temp) / "before.dll"
        snapshot.write_bytes(original)
        snapshot.chmod(stat.S_IMODE(target.stat().st_mode))
        try:
            # Publish a complete backup without overwriting a previous one (cp -n semantics).
            os.link(snapshot, backup)
        except FileExistsError:
            if backup.is_symlink() or not backup.is_file():
                raise ValueError("Existing NGX backup is not a regular file; stopped.")
        replacement.replace(target)
    print("Installed downloaded GPTK 3.0 NGX DLL:", target)
    print("Original backup preserved:", backup)
    return target
