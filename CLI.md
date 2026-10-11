# highball_fg2x CLI guide

The CLI provides five commands: `build`, `install`, `download-ngx`, `patch-ngx` and `remove`. Run the examples from the repository directory containing `main.py` using Python 3.9+. No pip packages or RTK installation are required. To use the repository's virtual environment, replace `python3` with `.venv/bin/python`.

This is an experimental GPTK 3.0 patch. See the [README](README.md) for reported game results and compatibility limits.

## Choose a command

| Goal | Command | Main changes |
| --- | --- | --- |
| Patch the engine and one bottle | `install --bottle PATH` | Creates a separate Highball engine; replaces the bottle's NGX DLL when needed |
| Install only the FG2X engine | `install` | Creates a separate Highball engine |
| Build a patched engine for inspection | `build` | Creates output in `dist/` by default |
| Download only the NGX DLL | `download-ngx` | Writes to the cache; leaves engines and bottles unchanged |
| Patch only a bottle's NGX DLL | `patch-ngx --bottle PATH` | Backs up and replaces the DLL when needed |
| Remove the installed FG2X engine | `remove` | Deletes the separate engine after all bottles switch away from it |

To patch both components:

```sh
python3 main.py install --bottle "$HOME/Library/Application Support/Highball/bottles/Games"
```

Replace `Games` with your bottle's directory name. The bottle must already use D3DMetal/GPTK 3.0. Quit the game, Steam, Highball and Wine applications before running the command. After installation, select the FG2X engine in Highball. See [quick setup](README.md#quick-setup).

## Paths and requirements

| Component | Current value |
| --- | --- |
| Supported source engine | `x64-sikarugir10.0_6-r21`, GPTK/D3DMetal 3.0, with the pinned binary SHA256 |
| New engine ID | `x64-sikarugir10.0_6-r21-fg2x-gptk30` |
| Accepted engine ID without the GPTK suffix | `x64-sikarugir10.0_6-r21-fg2x` |
| Highball engines directory | `$HOME/Library/Application Support/Highball/engines/` |
| Highball bottles directory | `$HOME/Library/Application Support/Highball/bottles/` |
| Default NGX cache | `<repo>/work/downloads/gptk30/` |

- Quote paths containing spaces. Use `$HOME` inside double quotes instead of `"~/..."`.
- `--source-engine` takes the engine directory containing `manifest.json`, not its parent `engines/` directory.
- `--bottle` takes the directory containing `bottle.json` and `drive_c/`, not the game directory or `drive_c/` itself.
- Relative paths you supply are resolved from the current working directory. Default output and cache paths are relative to the repository directory.
- Building requires macOS with `cp` and `codesign`. Installation, bottle patching and removal require a Highball environment on macOS. `download-ngx` needs neither Highball nor `codesign`, but Python must support reading XZ archives.
- `install`, `patch-ngx` and `remove` check that Highball, Steam and Wine are closed. The CLI does not terminate processes for you.
- GPTK 4.0 and options to bypass version or hash checks are not implemented.

## Show help

```sh
python3 main.py --help
python3 main.py build --help
python3 main.py install --help
python3 main.py download-ngx --help
python3 main.py patch-ngx --help
python3 main.py remove --help
```

`-h` is equivalent to `--help`. Help commands do not write any files.

## 1. `build`: create a patched engine

### Syntax and options

```text
python3 main.py build [--source-engine PATH] [--output PATH]
```

| Option | Required | Behavior |
| --- | --- | --- |
| `--source-engine PATH` | No | Selects the source directly; otherwise scans installed Highball engines and prompts for a number |
| `--output PATH` | No | Defaults to `<repo>/dist/x64-sikarugir10.0_6-r21-fg2x-gptk30` |

### Examples

Select the source interactively:

```sh
python3 main.py build
```

Select the source explicitly for a noninteractive terminal or CI:

```sh
python3 main.py build \
  --source-engine "$HOME/Library/Application Support/Highball/engines/x64-sikarugir10.0_6-r21"
```

Use a different output when the default already exists:

```sh
python3 main.py build \
  --source-engine "$HOME/Library/Application Support/Highball/engines/x64-sikarugir10.0_6-r21" \
  --output "$PWD/work/build-test/x64-sikarugir10.0_6-r21-fg2x-gptk30"
```

### What happens

1. Validates GPTK 3.0, the source ID, SHA256, architecture and original bytes.
2. Copies the engine into a private staging directory and patches `win32u.so`.
3. Applies an ad-hoc signature, verifies the signature and payload, updates the manifest and adds an installation record named `fgx2.json`.
4. Publishes the completed engine at the output path and prints `Created engine:` and the signed module's SHA256.

The source engine is preserved. With the default output, this command does not install into Highball, handle NGX or switch bottles. Unlike `install`, `build` does not check for running applications. Use a stable source and avoid letting Highball update it during copying.

The output must not exist, and its final directory name must be exactly `x64-sikarugir10.0_6-r21-fg2x-gptk30`. An output inside the source engine, an output symlink or a different final name is rejected. There is no `--force`; choose a new parent directory to build again.

## 2. `install`: install the engine and optionally patch a bottle

### Syntax and options

```text
python3 main.py install [--source-engine PATH] [--bottle PATH]
```

| Option | Required | Behavior |
| --- | --- | --- |
| `--source-engine PATH` | No | Selects the source directly when creating the engine; otherwise prompts for a selection |
| `--bottle PATH` | No | Handles this bottle's NGX DLL after the engine is ready |

### Examples

Install only the engine:

```sh
python3 main.py install
```

Install the engine and patch the `Games` bottle:

```sh
python3 main.py install --bottle "$HOME/Library/Application Support/Highball/bottles/Games"
```

Specify both paths to skip interactive source selection:

```sh
python3 main.py install \
  --source-engine "$HOME/Library/Application Support/Highball/engines/x64-sikarugir10.0_6-r21" \
  --bottle "$HOME/Library/Application Support/Highball/bottles/Games"
```

### What happens

1. If the FG2X engine is missing, selects a source and creates the patched engine in Highball's engines directory using the `build` procedure.
2. If it already exists, validates the installation record, hash, renderer and signature, then prints `FG2X engine is already installed and verified:`. In this case, `--source-engine` is not read and no rebuild occurs.
3. If `--bottle` was supplied, runs the NGX procedure described under `patch-ngx`.
4. You then open Highball, select `x64-sikarugir10.0_6-r21-fg2x-gptk30` for the bottle, keep D3DMetal and DLSS/MetalFX enabled, and enable FG 2X in the game.

The installer does not switch the bottle's engine or force FG in the game. The original engine and game files are preserved. `install` has no `--output` or `--cache-dir` option; use `patch-ngx` separately if you need a different cache location.

If engine creation succeeds but NGX fails, the new engine remains installed. Fix the reported issue and rerun the command: the installed engine is verified, then bottle patching is retried. An NGX failure does not roll back engine installation.

## 3. `download-ngx`: download the DLL into the cache

### Syntax and options

```text
python3 main.py download-ngx [--cache-dir PATH]
```

| Option | Required | Default |
| --- | --- | --- |
| `--cache-dir PATH` | No | `<repo>/work/downloads/gptk30/` |

### Examples

```sh
python3 main.py download-ngx
python3 main.py download-ngx --cache-dir "$PWD/work/ngx-cache"
```

### What happens

1. Reuses `nvngx-gptk30.dll` immediately if the cached DLL has the correct size and hash.
2. Otherwise uses the cached archive or downloads the pinned `Template-1.0.11.tar.xz` package over HTTPS, approximately 84.5 MB.
3. Verifies the archive, GPTK 3.0 metadata and the D3DMetal DLL, then saves `nvngx-gptk30.dll` (90,576 bytes).
4. Prints `Verified NGX DLL:` followed by the DLL path.

This command does not modify engines or bottles, and Highball can remain open. It does not fetch the latest Template release or fall back to an installed engine's DLL. A valid cache can be reused without network access, so you can download it ahead of offline use.

Invalid size/hash or a symlink at the cached DLL/archive path causes the command to stop when that file is checked. To retry, remove the specific invalid cache file reported by the error; do not bypass verification. `--cache-dir` changes storage location, not the runtime version.

## 4. `patch-ngx`: patch one bottle's NGX DLL

### Syntax and options

```text
python3 main.py patch-ngx --bottle PATH [--cache-dir PATH]
```

| Option | Required | Behavior |
| --- | --- | --- |
| `--bottle PATH` | Yes | Selects the bottle to patch |
| `--cache-dir PATH` | No | Defaults to `<repo>/work/downloads/gptk30/` |

### Examples

```sh
python3 main.py patch-ngx --bottle "$HOME/Library/Application Support/Highball/bottles/Games"
```

Use a cache in another location:

```sh
python3 main.py patch-ngx \
  --bottle "$HOME/Library/Application Support/Highball/bottles/Games" \
  --cache-dir "$PWD/work/ngx-cache"
```

### What happens

1. Checks that applications are closed and the bottle uses renderer `d3dmetal` with a GPTK 3.0 engine.
2. Reads `drive_c/windows/system32/nvngx.dll`, which must already exist. If its hash is correct, prints `Bottle NGX DLL is already correct:` and exits without downloading or writing files.
3. Gets the verified DLL from the cache/download procedure, then checks again that applications are closed and the target DLL has not changed during the download.
4. Creates `drive_c/windows/system32/nvngx.dll.before-ngx-test` if missing; preserves an existing backup.
5. Replaces the DLL atomically using a temporary file on the same filesystem, preserves its permissions and prints `Installed downloaded GPTK 3.0 NGX DLL:` and the backup path.

Only the selected bottle's DLL is handled. This command does not create the FG2X engine or change `bottle.json`, the registry or game files. Run it separately for each bottle by changing `--bottle`; there is no option to patch all bottles automatically.

The backup is the **first preserved copy** and may already exist from earlier testing. It is not necessarily the DLL from immediately before the latest run.

### Restore NGX manually

There is no CLI command to restore NGX. Quit Highball, Steam and Wine, check that the backup exists, then copy it back:

```sh
cp "$HOME/Library/Application Support/Highball/bottles/Games/drive_c/windows/system32/nvngx.dll.before-ngx-test" \
   "$HOME/Library/Application Support/Highball/bottles/Games/drive_c/windows/system32/nvngx.dll"
```

This `cp` command overwrites the current DLL with the backup. Replace the bottle name in **both paths**.

## 5. `remove`: remove the FG2X engine

### Syntax and options

```text
python3 main.py remove [--engine-id ID]
```

| Option | Required | Default |
| --- | --- | --- |
| `--engine-id ID` | No | `x64-sikarugir10.0_6-r21-fg2x-gptk30` |

Only the two IDs listed under paths and requirements are accepted: the `-fg2x-gptk30` engine and the `-fg2x` engine without the GPTK suffix. Arbitrary paths and the original engine ID are not accepted.

### Steps and examples

1. In Highball, switch **every bottle using the engine you want to remove** to the original `x64-sikarugir10.0_6-r21` engine or another suitable engine.
2. Quit the game, Steam, Highball and Wine.
3. Remove the default engine:

```sh
python3 main.py remove
```

Or remove the engine without the GPTK suffix:

```sh
python3 main.py remove --engine-id x64-sikarugir10.0_6-r21-fg2x
```

The command validates the record, hash and signature and checks bottle configurations before deleting the separate engine. If a bottle still references it, removal stops and names the bottle to switch. Success prints `Removed only the FG2X engine.`

The original engine, saves, bottle settings and `nvngx.dll` are preserved. Removal **does not undo NGX replacement**; use the manual restoration procedure above if needed. Running `remove` after the engine has already been deleted reports a missing-file error rather than succeeding again.

## Interactive engine selection and CI

`build` and an `install` that creates a new engine list installed engines when `--source-engine` is omitted. Select an entry marked `compatible`; unsupported or already patched engines cannot be used as sources. Entering `0`, an invalid number or an unsupported selection stops before engine creation.

A noninteractive terminal requires `--source-engine` when creating an engine. Use the explicit-source examples above. CI builds still require macOS and a separately provided original engine matching the pinned profile. `download-ngx` runs independently without Highball or a bottle.

## Exit codes and troubleshooting

| Exit code | Meaning |
| --- | --- |
| `0` | Success or help output |
| `1` | An operation or validation error handled by the CLI, usually prefixed with `Stopped:`; cancelling engine selection also uses this code |
| `2` | An argparse syntax error: missing command/argument, unknown option or invalid engine ID |

| Message or situation | Action |
| --- | --- |
| `Close Highball, Steam and Wine apps...` | Quit the relevant applications and retry; the CLI does not terminate processes |
| `No compatible engine found...` | Check the original r21 engine and GPTK 3.0; do not edit SHA values to bypass checks |
| `Engine selection requires a terminal...` | Supply `--source-engine PATH` when creating an engine |
| `Destination already exists...` | For `build`, choose a new output with the required final directory name |
| `NGX patch requires a bottle using D3DMetal/GPTK 3.0.` | Select the required renderer/engine in Highball, quit applications and retry |
| `Cached NGX DLL differs...` or an archive checksum/size mismatch | Remove the specific invalid cache file, check connectivity and retry |
| `FG2X engine differs from its installation record...` | Investigate the modified installation; do not edit the marker or hash to bypass checks |
| `Switch bottle ... back to ... first.` | Switch the named bottle to another engine before removal |
| `No such file or directory` | Check the source/bottle path, `bottle.json`, target DLL or engine to remove exists |

The CLI confirms patching and installation, not gameplay. Games still need compatible FG integration; an available 2X menu option does not prove interpolation is running. Check Metal HUD and gameplay stability after selecting the patched engine.
