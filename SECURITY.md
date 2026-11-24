# Security

FxOCRbot is public: anyone can send it files. Treat every upload as hostile.

## Reporting

Use GitHub's private vulnerability reporting (Security tab → "Report a vulnerability").
Please don't open public issues for security problems.

## Threat model

| Threat | Control |
|---|---|
| Non-image payloads (executables, archives, HTML/SVG, PDFs, scripts) disguised as images | File type is decided **only by magic bytes** (`core/imaging.sniff`), never by name or MIME. Allowlist: JPEG, PNG, WEBP. SVG/GIF/TIFF/BMP/HEIF/PDF are refused. |
| Polyglots / trailing payloads | The image is decoded and **re-encoded to a brand-new RGB PNG**; only pixels survive. Metadata (EXIF, GPS, ICC, text chunks) and trailing bytes are dropped. The OCR engine only ever sees this clean PNG. |
| Decompression bombs | Pixel count checked from the header **before** decoding (default 40 MP), Pillow's bomb guard set to the same limit and its warning promoted to an error. Large images are downscaled. |
| Parser exploits in Pillow / OCR engine | Decoding and OCR run in a **separate short-lived worker process** (`python -I`) with rlimits (address space, CPU time, file size, open files, no core dumps), its own session (killed as a group on timeout), a minimal environment **without the bot token**, and a private temp dir. |
| Resource exhaustion / floods | Size checked from Telegram metadata before download and again after (default 10 MB). Per-user rate limit (default 6 images / 60 s, one warning per window). Global concurrency cap (2) and bounded queue (20 → "busy"). Per-job wall-clock timeout. |
| Container escape / lateral movement | Non-root UID, read-only root filesystem, `/tmp` tmpfs with `noexec`, all capabilities dropped, `no-new-privileges`, memory/CPU/PID limits, no host volumes; LAN/host access blocked by `deploy/lan-block.sh` (below). |
| Forged button presses (callback data comes from the client) | Engine-switch callbacks are matched against the engine registry and availability; anything else is ignored. Switches are rate-limited (20/min/user). |
| Preference store tampering / growth | `prefs.json` on a dedicated volume holds only `user id → engine id`; unknown values are dropped on load, writes are atomic, entries capped at 100k. Nothing else is writable in the container. |
| Output injection (Telegram HTML) | All OCR text is HTML-escaped and sent inside `<pre>`; error messages are fixed strings. |
| Token leakage | Token only in `.env` (gitignored). `httpx` request logging (which includes the token in the URL) is silenced. Error logs record exception type/message only, never update contents. |
| Privacy | Images and text are kept in memory / a temp dir for the duration of one job and deleted. Logs hold user ID, file kind, size, timing and character count, never content. |

## Known gaps / deployment notes

- **LAN isolation** is a host firewall job, not something compose can do. `deploy/lan-block.sh`
  (installed as a boot-persistent systemd unit by `sudo bash deploy/install-lan-block.sh`) drops
  everything from the bot's bridge (`br-fxocr`) to private, link-local, CGNAT and multicast
  ranges, and new connections to the host itself; internet access and DNS keep working. The
  installer verifies it from inside the container. Without it, the container can reach your LAN.
- Rate limits are in-memory and reset on restart. Engine choices persist (volume `fxocr-data`).
- Dependencies are pinned at the top level (`pyproject.toml`); rebuild regularly for security fixes.
