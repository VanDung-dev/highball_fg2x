# highball_fg2x: experimental FG 2X patch

This experimental patch enables DLSS Frame Generation 2X in Highball through D3DMetal/MetalFX. FG 2X worked in Stellar Blade with an earlier per-game shim, and a user reported success in PRAGMATA with the shared engine patch in this repository. Compatibility with most games is still untested and cannot be guaranteed.

This is an experimental patch. It does not replace the original Highball engine, Highball or CrossOver. I recommend [purchasing CrossOver](https://www.codeweavers.com/crossover) to [support Wine development](https://www.codeweavers.com/open-source).

## Quick setup

You need macOS, Python 3.9+ and the original Highball engine `x64-sikarugir10.0_6-r21` with GPTK/D3DMetal 3.0. You can run the installer without pip packages or a separate build step. GPTK 4.0 is not supported yet.

### 1. Prepare your bottle

In Highball, select your bottle, set its engine to `x64-sikarugir10.0_6-r21`, choose D3DMetal and enable DLSS/MetalFX. Then quit the game, Steam, Highball and all Wine applications.

### 2. Patch the engine and bottle

Open Terminal in the repository directory containing `main.py` and run:

```sh
python3 main.py install
```

First, choose the original r21 engine marked `GPTK 3.0; compatible`. The installer creates the patched engine, or checks and reuses it if it already exists. It asks you to choose a source on every interactive run.

Enter `0` to skip the engine step and continue to bottle selection. This skips both building and verification.

Once the engine step finishes or is skipped, choose your bottle. It must use D3DMetal/GPTK 3.0 and already have an NGX DLL. Enter `0` to skip the bottle step. If you skip both steps, the command exits successfully without changing anything.

To select a bottle directly, use its name or full path:

```sh
python3 main.py install --bottle Games
```

For the steps you select, the installer creates a separate patched engine and installs the verified `nvngx.dll` bridge when the bottle needs it. The first download is about 84.5 MB. It keeps the original engine and any existing NGX backup, and leaves the game directory untouched.

Wait for the final summary before continuing:

```text
Install complete
  Engine: x64-sikarugir10.0_6-r21-fg2x-gptk30 (created)
  Bottle: Games
  NGX:    ready (GPTK 3.0)
  Backup: nvngx.dll.before-ngx-test (preserved)
```

The summary shows a checked, existing engine as `verified` and includes the backup line only when a backup exists. The installer still checks NGX when the DLL is already correct.

### 3. Select the patched engine

If you skipped the engine step, the installer only handled NGX. Select an existing FG2X engine or rerun the installer and choose a source to create one.

In Highball, go to Settings → Environments → your bottle → Advanced → engine and select:

```text
x64-sikarugir10.0_6-r21-fg2x-gptk30
```

Look for FG2X GPTK 3.0 (experimental) in the display name. Keep D3DMetal and DLSS/MetalFX enabled. You need to select the engine yourself; the installer does not switch it for you.

### 4. Enable FG in the game

Launch a game that supports DLSS Frame Generation, then enable DLSS and Frame Generation 2X in its settings. If you use Metal HUD, check for `Frame Interpolator: Enabled`. An unlocked menu option alone does not confirm that interpolation is running.

Repeat these steps with each bottle's directory name. Bottles can share the patched engine, but each needs its own NGX check.

## If setup stops

- **Applications still running:** quit Highball, Steam and Wine, then retry.
- **No compatible engine:** install the original r21/GPTK 3.0 engine to patch it, or choose `0` to handle only a compatible bottle's NGX. Do not bypass the hash checks.
- **Bottle selection or NGX fails:** the installer keeps any engine it has already created or verified. Fix the reported issue and retry. Choose the source again to verify the engine, or enter `0` to skip that step.

See [CLI.md](CLI.md) for command options, examples and recovery steps.

## Switch back

Switch every bottle using FG2X back to the original `x64-sikarugir10.0_6-r21` engine. Quit Highball, Steam and Wine. You can then remove the patched engine:

```sh
python3 main.py remove
```

Removal does not restore the bottle's NGX DLL. See [manual NGX restoration](CLI.md#restore-ngx-manually) if needed.

## Upstream projects

- [Wine](https://source.winehq.org/): official source code resources.
- [Apple D3DMetal / Game Porting Toolkit](https://developer.apple.com/games/game-porting-toolkit/): official information and downloads.
- [Highball](https://github.com/gauthierpiarrette/highball): original app.

## License

Project code is MIT licensed; bundled third-party headers retain their original licenses. Generated engines contain Wine and Apple D3DMetal components under their respective licenses.
