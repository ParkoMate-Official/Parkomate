# Third-party assets and licences

## Bundled with the station UI

| Asset | Where | Licence |
|---|---|---|
| **Material Symbols Rounded** icons, weight 400 (npm `@material-symbols/svg-400` 0.47.6, © Google) | `src/parkomate/ui/assets/icons/*.svg` | Apache License 2.0 - full text in `src/parkomate/ui/assets/icons/LICENSE` |
| **Noto Sans** Regular / Medium / SemiBold / Bold | `src/parkomate/ui/assets/fonts/` | SIL Open Font License 1.1 - `src/parkomate/ui/assets/fonts/OFL.txt` |
| **Noto Sans Devanagari** Regular / Medium / SemiBold / Bold | `src/parkomate/ui/assets/fonts/` | SIL Open Font License 1.1 |
| **Noto Sans Mono** Regular / SemiBold | `src/parkomate/ui/assets/fonts/` | SIL Open Font License 1.1 |
| **Noto Sans Symbols 2** Regular | `src/parkomate/ui/assets/fonts/` | SIL Open Font License 1.1 |

The icons are used unmodified (they are recoloured at runtime). The fonts are the static
hinted builds from the Noto project (`notofonts.github.io`), unmodified.

## Runtime libraries (installed, not bundled in the repository)

PySide6 / Qt 6 (LGPL v3), pydantic (MIT), argon2-cffi (MIT), keyring (MIT), openpyxl (MIT),
tomli-w (MIT) - see `pyproject.toml` and `uv.lock`. The full build adds pyserial (BSD),
esptool (GPL-2.0-or-later - see DECISIONS.md), httpx (BSD), OpenCV headless (Apache 2.0) and
pyzbar (MIT).
