# highball_fg2x — experimental FG 2X patch

An **experimental** Highball patch for DLSS Frame Generation 2X through D3DMetal/MetalFX. FG 2X has been enabled in **Stellar Blade** and **PRAGMATA** during testing. **Compatibility with most games has not been established and is not guaranteed.** Stellar Blade was tested with an earlier per-game shim; PRAGMATA was reported working with the shared engine patch provided here.

## Quick setup

Requires **macOS, Python 3.9+ and the original Highball engine `x64-sikarugir10.0_6-r21` with GPTK/D3DMetal 3.0**. No pip packages or separate build step are needed. GPTK 4.0 is not supported yet.

### 1. Prepare your bottle

In Highball, select your bottle, set its engine to **`x64-sikarugir10.0_6-r21`**, choose **D3DMetal** and enable **DLSS/MetalFX**. Then quit the game, Steam, Highball and all Wine applications.

### 2. Patch the engine and bottle

Open Terminal in the repository directory containing `main.py` and run:

```sh
python3 main.py install --bottle "$HOME/Library/Application Support/Highball/bottles/Games"
```

Replace **`Games`** with your bottle's directory name. Keep the quotes around the path.

Select the original **r21** engine marked **`GPTK 3.0; compatible`** when prompted. Enter `0` to cancel. If the FG2X engine is already installed, it is verified and this prompt is skipped.

The command creates a separate patched engine and installs the verified `nvngx.dll` bridge in the bottle when needed. The first download is about **84.5 MB**. The original engine is preserved, and an existing NGX backup is not overwritten. No files are added to the game directory.

Wait for either `Installed downloaded GPTK 3.0 NGX DLL:` or `Bottle NGX DLL is already correct:` before continuing.

### 3. Select the patched engine

Open Highball → **Settings → Environments → your bottle → Advanced → engine**, then select:

```text
x64-sikarugir10.0_6-r21-fg2x-gptk30
```

Its display name includes **FG2X GPTK 3.0 (experimental)**. Keep **D3DMetal** and **DLSS/MetalFX** enabled. The installer does not switch the bottle's engine automatically.

### 4. Enable FG in the game

Launch a game with DLSS Frame Generation integration and enable **DLSS** and **Frame Generation 2X** in its settings. If Metal HUD is enabled, look for **`Frame Interpolator: Enabled`** to confirm interpolation is running. An unlocked menu alone does not prove it works.

For another bottle, repeat these steps with its directory name. Bottles share the patched engine; each bottle needs its own NGX check.

## If setup stops

- **Applications still running:** quit Highball, Steam and Wine, then retry.
- **No compatible engine:** check that the original r21/GPTK 3.0 engine is installed. Do not bypass the hash checks.
- **NGX fails after engine creation:** fix the reported issue and rerun the same command. The installed engine is verified and reused.

For every command, option, example and recovery procedure, see **[CLI.md](CLI.md)**.

## Switch back

Select the original **`x64-sikarugir10.0_6-r21`** engine for every bottle using FG2X. Quit Highball, Steam and Wine, then optionally remove the patched engine:

```sh
python3 main.py remove
```

Removal does not restore the bottle's NGX DLL. See [manual NGX restoration](CLI.md#restore-ngx-manually) if needed.

## License

Project code is MIT licensed; bundled third-party headers retain their original licenses. Generated engines contain Wine and Apple D3DMetal components under their respective licenses.
