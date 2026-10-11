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
    print("\nChoose a source engine:")
    print("0. Skip engine step")
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
    if not any(status == "compatible" for _, status in choices):
        print("No compatible source engines found; select 0 to skip.")
    if not sys.stdin.isatty():
        raise RuntimeError("Engine selection requires a terminal; use --source-engine PATH for CI.")
    answer = input("Select source engine number (0 to skip): ").strip()
    if answer == "0":
        return None
    if not answer.isdecimal() or not 1 <= int(answer) <= len(choices):
        raise ValueError("Invalid engine number; nothing was changed.")
    source, status = choices[int(answer) - 1]
    if status != "compatible":
        raise ValueError("Selected engine is unsupported or already patched; nothing was changed.")
    return source


def resolve_bottle(value):
    path = Path(value).expanduser()
    if not path.is_absolute() and "/" not in str(value) and str(value) not in (".", ".."):
        path = engine.ENGINES.parent / "bottles" / path
    bottle.ngx_target(path)
    return path.resolve()


def select_bottle(allow_empty=False):
    if not sys.stdin.isatty():
        raise RuntimeError("Bottle selection requires a terminal; use --bottle NAME or PATH.")
    directory = engine.ENGINES.parent / "bottles"
    choices = []
    print("\nChoose a bottle:")
    print("0. Skip bottle step")
    if directory.is_dir():
        for root in sorted(directory.iterdir()):
            if not root.is_dir() or root.is_symlink() or not (root / "bottle.json").is_file():
                continue
            try:
                bottle.ngx_target(root)
                compatible = True
            except (OSError, ValueError, KeyError, TypeError):
                compatible = False
            choices.append((root, compatible))
            status = "D3DMetal / GPTK 3.0; compatible" if compatible else "unsupported"
            print(f"{len(choices)}. {root.name} [{status}]")
    if not any(compatible for _, compatible in choices):
        if allow_empty:
            print("No compatible bottles found; skipping bottle step.")
            return None
        print("No compatible bottles found; select 0 to skip.")
    answer = input("Select bottle number (0 to skip): ").strip()
    if answer == "0":
        return None
    if not answer.isdecimal() or not 1 <= int(answer) <= len(choices):
        raise ValueError("Invalid bottle number.")
    root, compatible = choices[int(answer) - 1]
    if not compatible:
        raise ValueError("Selected bottle is unsupported.")
    return root.resolve()


def show_result(title, engine_path=None, status=None, bottle_path=None):
    print("\n" + title)
    if engine_path is not None:
        print(f"  Engine: {engine_path.name} ({status})")
        if status == "built":
            print("  Output:", engine_path.absolute())
    elif status == "skipped":
        print("  Engine: skipped")
    if bottle_path is not None:
        print("  Bottle:", bottle_path.name)
        print("  NGX:    ready (GPTK 3.0)")
        backup = bottle_path / "drive_c/windows/system32/nvngx.dll.before-ngx-test"
        if backup.is_file():
            print("  Backup: nvngx.dll.before-ngx-test (preserved)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    builder = commands.add_parser("build", help="Build a copy inside this project; no Highball changes")
    builder.add_argument("--source-engine", type=Path, help="Explicit source engine path; skips interactive selection (CI)")
    builder.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "dist" / engine.ENGINE_ID)
    installer = commands.add_parser("install", help="Create a separate installed engine; choose it in Highball afterward")
    installer.add_argument("--source-engine", type=Path, help="Explicit source engine path; skips interactive selection")
    installer.add_argument("--bottle", help="Bottle name or path; prompts in an interactive terminal if omitted")
    downloader = commands.add_parser("download-ngx", help="Download/verify GPTK 3.0 NGX without requiring an installed engine")
    downloader.add_argument("--cache-dir", type=Path, default=bottle.NGX_CACHE)
    ngx_patcher = commands.add_parser("patch-ngx", help="Back up and replace a bottle's NGX DLL with the downloaded GPTK 3.0 bridge")
    ngx_patcher.add_argument("--bottle", help="Bottle name or path; prompts if omitted")
    ngx_patcher.add_argument("--cache-dir", type=Path, default=bottle.NGX_CACHE)
    remover = commands.add_parser("remove", help="Remove the FG2X engine after all bottles switch back")
    remover.add_argument("--engine-id", choices=[engine.ENGINE_ID, engine.LEGACY_ENGINE_ID], default=engine.ENGINE_ID,
                         help="Engine to remove; use the legacy ID for a patch installed before the GPTK suffix")
    args = parser.parse_args()
    if args.command == "build":
        source = args.source_engine if args.source_engine is not None else select_engine()
        if source is None:
            print("\nBuild skipped. No files changed.")
            return
        print("\nBuilding FG2X engine...", flush=True)
        engine.build(source, args.output)
        show_result("Build complete", args.output, "built")
    elif args.command == "download-ngx":
        print("Verified NGX DLL:", ngx.fetch_ngx(args.cache_dir))
    elif args.command == "patch-ngx":
        selected = resolve_bottle(args.bottle) if args.bottle is not None else select_bottle()
        if selected is None:
            print("\nBottle step skipped. No files changed.")
            return
        print(f"\nPreparing NGX for {selected.name}...", flush=True)
        bottle.patch_ngx(selected, args.cache_dir)
        show_result("Bottle patch complete", bottle_path=selected)
    elif args.command == "install":
        destination = engine.ENGINES / engine.ENGINE_ID
        engine.require_closed()
        source = args.source_engine if args.source_engine is not None else select_engine()
        if source is None:
            print("\nEngine step skipped.")
            status = "skipped"
        elif destination.exists():
            if args.source_engine is not None:
                engine.source_data(source.resolve())
            engine.verify_engine(destination)
            print("\nExisting FG2X engine verified.")
            status = "verified"
        else:
            engine.require_closed()
            print("\nBuilding FG2X engine...", flush=True)
            engine.build(source, destination)
            print("FG2X engine created.")
            status = "created"
        try:
            selected = resolve_bottle(args.bottle) if args.bottle is not None else (
                select_bottle(allow_empty=True) if sys.stdin.isatty() else None)
            if selected is not None:
                print(f"\nPreparing NGX for {selected.name}...", flush=True)
                bottle.patch_ngx(selected)
        except (OSError, ValueError, RuntimeError, EOFError, KeyboardInterrupt,
                tarfile.TarError, subprocess.SubprocessError):
            if source is not None:
                print("\nEngine ready:", destination.name)
            else:
                print("\nEngine step skipped.")
            print("Bottle step failed. Fix the error and retry.")
            raise
        show_result("Install complete", destination if source is not None else None, status, selected)
        if selected is None:
            print("  Bottle: skipped")
        if source is None:
            print("\nNothing changed." if selected is None else "\nOnly the bottle's NGX was handled; the engine step was skipped.")
            return
        name = selected.name if selected is not None else "your D3DMetal bottle"
        print(f"\nNext: In Highball, select the engine above for {name}, then enable FG 2X in the game.")
    else:
        engine.remove(args.engine_id)


def run():
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit("Stopped: " + (error.stderr.strip() if error.stderr else str(error)))
    except (OSError, ValueError, KeyError, RuntimeError, EOFError, KeyboardInterrupt,
            subprocess.SubprocessError, tarfile.TarError) as error:
        raise SystemExit("Stopped: " + str(error))
