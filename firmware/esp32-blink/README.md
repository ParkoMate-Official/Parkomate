# Test firmware: ESP32 Blink (bench test only)

A **test build, not the Parkomate firmware**. It blinks the board's LED (GPIO 2 /
`LED_BUILTIN`) every 0.5 s, so you can see that flashing worked. The real firmware always
comes from the Parkomate server; this folder is only read in a bench test (`--bench-test`,
`flash`).

| File | Flash address | Checked |
|---|---|---|
| `Blink.ino.bootloader.bin` | `0x1000` (`programming.bootloader_offset`) | ESP image, chip ID 0 = classic ESP32 |
| `Blink.ino.partitions.bin` | `0x8000` (`programming.partitions_offset`) | partition table: nvs, otadata, app0 at `0x10000`, app1, spiffs, coredump (4 MB flash) |
| `Blink.ino.bin` | `0x10000` (`programming.app_offset`) | ESP image, chip ID 0 |

The addresses were not guessed. Each file was compared byte for byte with
`Blink.ino.merged.bin` from the same build (`build.zip`), and each sits at exactly the
address shown. They are also the station's default settings. The build targets the
**classic ESP32** (`esp32:esp32:esp32`). esptool refuses to write it to an ESP32-S3 / C3.

## Flash it

```powershell
# no screens: read the chip + MAC, flash, show progress
uv run python -m parkomate flash --firmware-dir firmware\esp32-blink            # one ESP32 port
uv run python -m parkomate flash --port COM5 --firmware-dir firmware\esp32-blink

# the whole station with the real board (server, tests, measuring device, camera simulated)
uv run python -m parkomate --bench-test --firmware-dir firmware\esp32-blink
```

If the LED does not blink, check the board first. Its LED may be on another pin, wired
active-low, or an RGB LED. See the original build README for details.
