"""Build/install a separate, hash-pinned Highball GPTK 3.0 engine with HAGS compatibility."""
import argparse
from pathlib import Path
import subprocess
import sys
import tarfile

from src import bottle, engine
from src.gptk import detect_gptk_version
from src.gptk30 import ngx


def select_engine():
    print("Highball engine directory:", engine.ENGINES)
    if not engine.ENGINES.is_dir():
        raise RuntimeError("Highball engine directory is missing; install an engine in Highball first.")
    choices = []
    for root in sorted(engine.ENGINES.iterdir()):
        if not root.is_dir() or root.is_symlink() or not (root / "manifest.json").is_file():
            continue
        version = "unknown"
        try:
            version = detect_gptk_version(root)
            engine.source_data(root.resolve())
            status = "compatible"
        except (OSError, ValueError, KeyError, TypeError):
            status = "unsupported or already patched"
        choices.append((root, status))
        print(f"{len(choices)}. {root.name} [GPTK {version}; {status}]")
    if not choices:
        raise RuntimeError("No installed Highball engines found.")
    if not any(status == "compatible" for _, status in choices):
        raise RuntimeError("No compatible engine found; this patch requires " + engine.SOURCE_ID + " with the pinned SHA256.")
    if not sys.stdin.isatty():
        raise RuntimeError("Engine selection requires a terminal; use --source-engine PATH for CI.")
    answer = input("Select source engine number (0 to cancel): ").strip()
    if answer == "0":
        raise RuntimeError("Engine selection cancelled; nothing was changed.")
    if not answer.isdecimal() or not 1 <= int(answer) <= len(choices):
        raise ValueError("Invalid engine number; nothing was changed.")
    source, status = choices[int(answer) - 1]
    if status != "compatible":
        raise ValueError("Selected engine is unsupported or already patched; nothing was changed.")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    builder = commands.add_parser("build", help="Build a copy inside this project; no Highball changes")
    builder.add_argument("--source-engine", type=Path, help="Explicit source engine path; skips interactive selection (CI)")
    builder.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "dist" / engine.ENGINE_ID)
    installer = commands.add_parser("install", help="Create a separate installed engine; choose it in Highball afterward")
    installer.add_argument("--source-engine", type=Path, help="Explicit source engine path; skips interactive selection")
    installer.add_argument("--bottle", type=Path, help="Also patch this bottle's NGX DLL using the downloaded GPTK 3.0 package")
    downloader = commands.add_parser("download-ngx", help="Download/verify GPTK 3.0 NGX without requiring an installed engine")
    downloader.add_argument("--cache-dir", type=Path, default=bottle.NGX_CACHE)
    ngx_patcher = commands.add_parser("patch-ngx", help="Back up and replace a bottle's NGX DLL with the downloaded GPTK 3.0 bridge")
    ngx_patcher.add_argument("--bottle", type=Path, required=True)
    ngx_patcher.add_argument("--cache-dir", type=Path, default=bottle.NGX_CACHE)
    remover = commands.add_parser("remove", help="Remove the FG2X engine after all bottles switch back")
    remover.add_argument("--engine-id", choices=[engine.ENGINE_ID, engine.LEGACY_ENGINE_ID], default=engine.ENGINE_ID,
                         help="Engine to remove; use the legacy ID for a patch installed before the GPTK suffix")
    args = parser.parse_args()
    if args.command == "build":
        engine.build(args.source_engine if args.source_engine is not None else select_engine(), args.output)
    elif args.command == "download-ngx":
        print("Verified NGX DLL:", ngx.fetch_ngx(args.cache_dir))
    elif args.command == "patch-ngx":
        bottle.patch_ngx(args.bottle, args.cache_dir)
    elif args.command == "install":
        destination = engine.ENGINES / engine.ENGINE_ID
        if destination.exists():
            engine.require_closed()
            engine.verify_engine(destination)
            print("FG2X engine is already installed and verified:", destination)
        else:
            source = args.source_engine if args.source_engine is not None else select_engine()
            engine.require_closed()
            engine.build(source, destination)
        print("Select", engine.ENGINE_ID, "for your D3DMetal bottle in Highball. No bottle was switched automatically.")
        if args.bottle is not None:
            bottle.patch_ngx(args.bottle)
    else:
        engine.remove(args.engine_id)


def run():
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, EOFError, KeyboardInterrupt,
            subprocess.SubprocessError, tarfile.TarError) as error:
        raise SystemExit("Stopped: " + str(error))
