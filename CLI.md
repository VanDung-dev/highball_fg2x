# highball_fg2x CLI guide

Use `build`, `install`, `download-ngx`, `patch-ngx` or `remove` to manage the patch. Run the examples with Python 3.9+ from the repository directory containing `main.py`. You do not need pip packages or RTK. To use the repository's virtual environment, replace `python3` with `.venv/bin/python`.

This is an experimental GPTK 3.0 patch. See the [README](README.md) for reported game results and compatibility limits.

## Choose a command

| Goal | Command | Main changes |
| --- | --- | --- |
| Patch the engine and one bottle | `install --bottle PATH` | Creates a separate Highball engine; replaces the bottle's NGX DLL when needed |
| Install only the FG2X engine | `install`, then select bottle option `0` | Creates a separate Highball engine |
| Build a patched engine for inspection | `build` | Creates output in `dist/` by default |
| Download only the NGX DLL | `download-ngx` | Writes to the cache; leaves engines and bottles unchanged |
| Patch only a bottle's NGX DLL | `patch-ngx --bottle PATH` | Backs up and replaces the DLL when needed |
| Remove the installed FG2X engine | `remove` | Deletes the separate engine after all bottles switch away from it |

To patch both components:

```sh
python3 main.py install --bottle Games
```

Replace `Games` with your bottle's directory name, or omit `--bottle` to choose from a list in an interactive terminal. The bottle must already use D3DMetal/GPTK 3.0. Quit the game, Steam, Highball and Wine applications before running the command. Once installation finishes, select the FG2X engine in Highball as described in [quick setup](README.md#quick-setup).

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
- Point `--source-engine` to the engine directory containing `manifest.json`. Passing the parent `engines/` directory will fail.
- For `--bottle`, use a name such as `Games` from Highball's bottles directory, or a path to the directory containing `bottle.json` and `drive_c/`. Use `./NAME` for a relative directory in the current working directory. Passing the game directory or `drive_c/` itself will fail.
- Relative paths you supply are resolved from the current working directory. Default output and cache paths are relative to the repository directory.
- To build an engine, you need macOS with `cp` and `codesign`. To install, patch a bottle or remove an engine, you also need a Highball environment on macOS. You can run `download-ngx` without Highball or `codesign`, provided Python can read XZ archives.
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

1. The script checks GPTK 3.0, the source ID, SHA256, architecture and original bytes.
2. It copies the engine into a private staging directory and patches `win32u.so`.
3. It applies an ad-hoc signature, checks the signature and payload, updates the manifest and adds an installation record named `fgx2.json`.
4. It moves the completed engine to the output path and prints a `Build complete` summary with the engine ID and output path. The record in `fgx2.json` includes the signed module's SHA256.

Enter `0` at source selection to skip the build. No files are written and the command exits successfully.

The build leaves the source engine intact. With the default output, it creates a local copy without installing into Highball, handling NGX or switching bottles. It does not check for running applications as `install` does, so keep the source stable and prevent Highball from updating it during copying.

Choose an output path that does not exist, with the final directory name `x64-sikarugir10.0_6-r21-fg2x-gptk30`. The script rejects a path inside the source engine, an output symlink or a different final name. To build again, choose a new parent directory; there is no `--force` option.

## 2. `install`: install the engine and optionally patch a bottle

### Syntax and options

```text
python3 main.py install [--source-engine PATH] [--bottle NAME_OR_PATH]
```

| Option | Required | Behavior |
| --- | --- | --- |
| `--source-engine PATH` | No | Selects the source directly; otherwise prompts on every run, including when the FG2X engine already exists |
| `--bottle NAME_OR_PATH` | No | Selects a bottle directly; otherwise prompts in an interactive terminal, with `0` for engine only. Noninteractive omission means engine only |

### Examples

Choose an engine first, then a bottle. Select `0` at either prompt to skip that step; skipping the bottle installs only the engine:

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

1. The installer asks you to choose a source engine on every run unless you supply `--source-engine`. Enter `0` to skip this step and continue to bottles. It checks a selected source even when the FG2X engine already exists.
2. With a source selected, it follows the `build` procedure or checks the existing engine's record, hash, renderer and signature before reusing it. Skipping the engine step skips both building and verification.
3. After the engine step, it asks you to choose a bottle and checks it. An invalid name or path stops the bottle step, while any completed engine installation stays in place. If interactive discovery finds no compatible bottles, the installer skips this step.
4. With a bottle selected, it follows the NGX procedure below. Enter `0` to skip the bottle step. The `Install complete` summary shows the engine as `created`, `verified` or `skipped`, the bottle name or `skipped`, NGX readiness and a backup filename when one exists. Skipping both steps changes nothing and exits successfully.
5. After creating or verifying the engine, open Highball and select `x64-sikarugir10.0_6-r21-fg2x-gptk30` for the bottle. Keep D3DMetal and DLSS/MetalFX enabled, then enable FG 2X in the game. If you handled only NGX, you still need an existing FG2X engine.

You select the bottle's engine and enable FG in the game yourself. The installer keeps the original engine and game files intact. `install` has no `--output` or `--cache-dir` option. Use `patch-ngx` separately to choose a different cache location.

If bottle selection or NGX fails after a successful engine step, the installer keeps the engine. Fix the reported issue and rerun the command. Select the source again to verify the engine, or enter `0` to go directly to bottles. If you skipped the engine step, the summary reports it as skipped.

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

1. The script reuses `nvngx-gptk30.dll` if the cached DLL has the expected size and hash.
2. Otherwise, it uses the cached archive or downloads the pinned `Template-1.0.11.tar.xz` package over HTTPS. The download is about 84.5 MB.
3. It checks the archive, GPTK 3.0 metadata and the D3DMetal DLL, then saves `nvngx-gptk30.dll` (90,576 bytes).
4. It prints `Verified NGX DLL:` followed by the DLL path.

You can leave Highball open while downloading; this command only writes to the cache. It uses the pinned Template release, with no fallback to an installed engine's DLL. Once the cache is valid, you can reuse it offline.

The command stops if it finds a size or hash mismatch, or a symlink at the cached DLL or archive path. Remove the specific invalid cache file named in the error, then retry. Keep verification enabled. `--cache-dir` sets where files are stored; it does not change the runtime version.

## 4. `patch-ngx`: patch one bottle's NGX DLL

### Syntax and options

```text
python3 main.py patch-ngx [--bottle NAME_OR_PATH] [--cache-dir PATH]
```

| Option | Required | Behavior |
| --- | --- | --- |
| `--bottle NAME_OR_PATH` | No in an interactive terminal | Selects the bottle directly; otherwise prompts. Required for noninteractive use |
| `--cache-dir PATH` | No | Defaults to `<repo>/work/downloads/gptk30/` |

### Examples

Choose a bottle from the list:

```sh
python3 main.py patch-ngx
```

Select a bottle by name:

```sh
python3 main.py patch-ngx --bottle Games
```

Or use a full path:

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

1. The script checks that applications are closed and the bottle uses renderer `d3dmetal` with a GPTK 3.0 engine.
2. It reads `drive_c/windows/system32/nvngx.dll`, which must already exist. If the hash matches, it skips downloading and writing files.
3. Otherwise, it gets the verified DLL from the cache or download, then checks again that applications are closed and the target DLL has not changed during the download.
4. It creates `drive_c/windows/system32/nvngx.dll.before-ngx-test` if needed, keeping any existing backup.
5. It replaces the DLL atomically through a temporary file on the same filesystem, preserving the DLL's permissions. The summary shows `Bottle patch complete`, the bottle name, `NGX: ready` and the backup filename when one exists. You see the same summary when the DLL was already correct.

This command handles the selected bottle's DLL and leaves `bottle.json`, the registry and game files untouched. It does not create an FG2X engine. Run it once per bottle with a different `--bottle` value; there is no option to patch all bottles automatically.

Enter `0` at bottle selection to skip this command. No DLL is changed and the command exits successfully.

The backup keeps the first preserved copy, which may come from earlier testing. It may differ from the DLL present just before your latest run.

### Restore NGX manually

There is no CLI command to restore NGX. Quit Highball, Steam and Wine, check that the backup exists, then copy it back:

```sh
cp "$HOME/Library/Application Support/Highball/bottles/Games/drive_c/windows/system32/nvngx.dll.before-ngx-test" \
   "$HOME/Library/Application Support/Highball/bottles/Games/drive_c/windows/system32/nvngx.dll"
```

Replace the bottle name in both paths before running `cp`. The command overwrites the current DLL with the backup.

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

1. In Highball, switch every bottle using the engine you want to remove to the original `x64-sikarugir10.0_6-r21` engine or another suitable engine.
2. Quit the game, Steam, Highball and Wine.
3. Remove the default engine:

```sh
python3 main.py remove
```

Or remove the engine without the GPTK suffix:

```sh
python3 main.py remove --engine-id x64-sikarugir10.0_6-r21-fg2x
```

Before deleting the separate engine, the script checks its record, hash and signature, then checks bottle configurations. If a bottle still uses the engine, it stops and tells you which bottle to switch. On success, it prints `Removed only the FG2X engine.`

Removal leaves the original engine, saves, bottle settings and `nvngx.dll` intact. To undo NGX replacement, follow the manual restoration steps above. Running `remove` again after deleting the engine reports a missing-file error.

## Interactive engine selection and CI

`build` and `install` list installed engines whenever `--source-engine` is omitted. For `install`, this also happens when the FG2X engine is already installed. Select an entry marked `compatible`; unsupported or already patched engines cannot be used as sources. Entering `0` skips the engine step successfully; in `install`, bottle selection follows. Invalid numbers or unsupported selections still produce an error before engine changes.

A noninteractive terminal requires `--source-engine` for both `build` and `install`, including when reusing an installed engine. Use the explicit-source examples above. CI builds still require macOS and a separately provided original engine matching the pinned profile. `download-ngx` runs independently without Highball or a bottle.

In an interactive terminal, `install` lists source engines first. It creates or verifies the engine, or skips that step, before listing bottles. Bottle discovery checks the renderer, version and NGX paths, marks unsupported bottles and offers `0` to skip. `patch-ngx` also lists bottles when you omit `--bottle`, and `0` skips the command successfully. For either command in a noninteractive terminal, pass `--bottle NAME_OR_PATH` to patch a bottle; the CLI will not choose one for you.

## Exit codes and troubleshooting

| Exit code | Meaning |
| --- | --- |
| `0` | Success, a skipped step/command, or help output |
| `1` | An operation or validation error handled by the CLI, usually prefixed with `Stopped:` |
| `2` | An argparse syntax error: missing command/argument, unknown option or invalid engine ID |

| Message or situation | Action |
| --- | --- |
| `Close Highball, Steam and Wine apps...` | Quit the relevant applications and retry; the CLI does not terminate processes |
| `No compatible source engines found...` | Install the original r21/GPTK 3.0 engine, or select `0` to skip. Do not edit SHA values to bypass checks |
| `Engine selection requires a terminal...` | Supply `--source-engine PATH` when creating an engine |
| `Bottle selection requires a terminal...` | Supply `--bottle NAME_OR_PATH` for `patch-ngx` in a noninteractive terminal |
| `Destination already exists...` | For `build`, choose a new output with the required final directory name |
| `NGX patch requires a bottle using D3DMetal/GPTK 3.0.` | Select the required renderer/engine in Highball, quit applications and retry |
| `Cached NGX DLL differs...` or an archive checksum/size mismatch | Remove the specific invalid cache file, check connectivity and retry |
| `FG2X engine differs from its installation record...` | Investigate the modified installation; do not edit the marker or hash to bypass checks |
| `Switch bottle ... back to ... first.` | Switch the named bottle to another engine before removal |
| `No such file or directory` | Check the source/bottle path, `bottle.json`, target DLL or engine to remove exists |

A successful installation confirms that the files passed the CLI's checks. Each game still needs compatible FG integration. After selecting the patched engine, check Metal HUD for interpolation and test gameplay stability; an available 2X menu option alone does not confirm that FG works.
