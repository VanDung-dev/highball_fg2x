"""Synchronous stock/FG2X comparison in disposable Wine prefixes, never the real bottle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import engine as fg


def run(engine, bottle, label, plugins, logs):
    with tempfile.TemporaryDirectory(prefix="fg2x-" + label + "-", dir=ROOT / "work") as temp:
        prefix = Path(temp)
        for name in ["user.reg", "system.reg", "userdef.reg", ".update-timestamp"]:
            if (bottle / name).exists():
                shutil.copy2(bottle / name, prefix / name)
        windows = prefix / "drive_c/windows"
        windows.mkdir(parents=True)
        fg.copy_engine(bottle / "drive_c/windows/system32", windows / "system32")
        (prefix / "dosdevices").mkdir()
        (prefix / "dosdevices/c:").symlink_to("../drive_c")
        (prefix / "dosdevices/z:").symlink_to("/")
        for directory in ["drive_c/diag-temp", "drive_c/ProgramData", "drive_c/windows/temp"]:
            (prefix / directory).mkdir(parents=True, exist_ok=True)
        for user in (bottle / "drive_c/users").iterdir():
            if user.is_dir():
                (prefix / "drive_c/users" / user.name / "AppData/Local/Temp").mkdir(parents=True)
        framework = engine / "frameworks"
        metal = framework / "renderer/d3dmetal/wine"
        shim = engine / "renderers/d3dmetal-tsshim/wine"
        overlays = [shim, metal, engine / "renderers/dxmt/wine", framework / "renderer/d9vk/wine"]
        overrides = "nvapi64,nvngx=n,b;mscoree,mshtml,winemenubuilder.exe=d"
        env = {k: v for k, v in os.environ.items() if not k.startswith("PROBE_")}
        env.update(json.loads((bottle / "bottle.json").read_text())["environment"])
        env.update(WINEPREFIX=str(prefix), WINEDEBUG="-all", WINEMSYNC="0", WINEESYNC="0",
                   WINEDLLOVERRIDES=overrides, D3DM_ENABLE_METALFX="1",
                   WINEDLLPATH_PREPEND=":".join(str(p) for p in overlays if p.exists()),
                   DYLD_FALLBACK_FRAMEWORK_PATH=str(framework),
                   DYLD_FALLBACK_LIBRARY_PATH=f"{framework}:{framework}/GStreamer.framework/Versions/1.0/lib",
                   HB_D3D12_REAL="Z:" + str(shim / "x86_64-windows/apd12.dll").replace("/", "\\"),
                   TEMP="C:\\diag-temp", TMP="C:\\diag-temp")
        env.pop("DYLD_INSERT_LIBRARIES", None)
        wine, server = engine / "engine/bin/wine", engine / "engine/bin/wineserver"
        env["WINESERVER"] = str(server)

        def execute(name, arguments, timeout=45):
            result = subprocess.run([str(wine)] + arguments, env=env,
                                    capture_output=True, text=True, timeout=timeout)
            output = f"exit={result.returncode}\n{result.stdout}\n{result.stderr}"
            (logs / (label + "-" + name + ".log")).write_text(output)
            subprocess.run([str(server), "-w"], env=env, capture_output=True, timeout=15, check=True)
            return result

        try:
            boot = execute("setup", ["cmd.exe", "/c", "exit"])
            if boot.returncode:
                raise RuntimeError("Wine setup failed: see " + label + "-setup.log")
            # Setup can regenerate fake builtins; the real bottle's NGX fix is mirrored only here.
            shutil.copy2(metal / "x86_64-windows/nvngx.dll", windows / "system32/nvngx.dll")
            api = execute("hags", [str(ROOT / "work/hags_probe.exe"), label])
            print(label, "API", api.returncode, api.stdout.strip(), flush=True)
            if api.returncode:
                raise RuntimeError("API probe failed: " + label)
            if plugins:
                sdk = execute("streamline", [str(ROOT / "work/streamline_probe.exe"),
                                             "Z:" + str(plugins).replace("/", "\\")])
                summary = [line for line in sdk.stdout.splitlines()
                           if line.startswith(("SL DLL", "SL Init", "SL Feature", "SL Shutdown"))]
                print(label, "SDK", sdk.returncode, "\n".join(summary), flush=True)
                if label == "fg2x":
                    if sdk.returncode or "SL Feature=1000 supported_result=0" not in sdk.stdout:
                        raise RuntimeError("Patched SDK probe failed")
                elif (sdk.returncode != 8 or "SL Init result=0" not in sdk.stdout
                      or "SL Feature=1000 supported_result=31" not in sdk.stdout
                      or "SL Feature=3 supported_result=0" not in sdk.stdout):
                    raise RuntimeError("Stock SDK baseline differs from the known HAGS failure; inspect logs")
        finally:
            # This WINEPREFIX is private; never stop a user's real bottle/server.
            # Wine returns 1 if the diagnostic server has already exited after the blocking wait.
            stop = subprocess.run([str(server), "-k"], env=env, capture_output=True, timeout=10)
            if stop.returncode not in (0, 1):
                raise RuntimeError("Cannot stop the disposable diagnostic server")
            subprocess.run([str(server), "-w"], env=env, capture_output=True, timeout=15, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugins", type=Path, help="SDK plugin directory from any game, read only")
    parser.add_argument("--bottle", type=Path, default=fg.ENGINES.parent / "bottles/Games")
    args = parser.parse_args()
    bottle = args.bottle.resolve()
    plugins = args.plugins.resolve() if args.plugins else None
    if plugins and not (plugins / "sl.interposer.dll").is_file():
        raise ValueError("sl.interposer.dll missing from the specified plugin directory")
    original, modified = fg.ENGINES / fg.SOURCE_ID, ROOT / "dist" / fg.ENGINE_ID
    fg.verify_engine(modified)
    files = [bottle / n for n in ["bottle.json", "user.reg", "system.reg", "userdef.reg"]]
    files += [bottle / "drive_c/windows/system32/nvngx.dll", original / fg.MODULE]
    snapshot = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    logs = ROOT / "dist/validation"
    logs.mkdir(parents=True, exist_ok=True)
    try:
        run(original, bottle, "stock", plugins, logs)
        run(modified, bottle, "fg2x", plugins, logs)
    finally:
        if any(hashlib.sha256(p.read_bytes()).hexdigest() != value for p, value in snapshot.items()):
            raise RuntimeError("Protected source/bottle files changed during diagnostic run")
    print("PASS: stock/FG2X comparison; original engine and real bottle hashes unchanged.", flush=True)


if __name__ == "__main__":
    main()
