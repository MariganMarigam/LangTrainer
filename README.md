# LangTrainer

A cross-platform desktop app for learning foreign words. It learns your vocabulary through two
channels at once: **passive popup reminders** that surface a word while you work, and **13
interactive games** that drill recall — all backed by an Anki-style **SM-2 spaced-repetition**
scheduler. Built with PySide6 (Qt 6) and SQLite, with a dark iOS-inspired theme, and it lives in
the system tray so it never interrupts what you are doing.

---

## ⬇️ Download

Grab the build for your platform from the **[Releases page](https://github.com/MariganMarigam/LangTrainer/releases/latest)**.

| Platform | File | Notes |
|---|---|---|
| **Windows** (x64) | `LangTrainer-1.0.1-windows-x64.exe` | Single file, nothing to install. Run it as downloaded — renaming is optional, see below. SmartScreen will warn; it is unsigned. |
| **Linux** (x64) | `LangTrainer-1.0.1-linux-x86_64.tar.gz` | Extract, then `chmod +x LangTrainer-1.0.1-linux-x86_64` before running. |
| **macOS** (Apple Silicon) | `LangTrainer-1.0.1-macos-arm64.tar.gz` | Extract, then right-click `LangTrainer.app` → **Open**. Intel Macs are not supported in v1. |
| Any | `LangTrainer-1.0.1-checksums.txt` | SHA-256 of every file above, for manual verification. |

> **Windows: renaming the download to `LangTrainer.exe` is optional, not required.** The updater
> works under whatever file name you actually run — the downloaded
> `LangTrainer-<version>-windows-x64.exe` updates in place and no second copy is created. Renaming
> once is still worth it as a convenience if you want a **stable file name** for a desktop
> shortcut or a taskbar pin, and a name that does not go stale after every future update.

> **No Linux AppImage in v1.** The app is packaged as a plain executable because the
> application stores its database, dictionaries and logs *next to the executable*, and an
> AppImage is a read-only SquashFS mount — the app cannot create its database inside it.
> A working AppImage needs a writable-data design change, which is tracked as follow-up
> work. The `tar.gz` above is the supported Linux path for now.

---

## ⚠️ Windows: "Windows protected your PC"

The release is **unsigned**. Windows SmartScreen therefore shows a blue warning the first time
you run it. This is expected, it is not a virus, and it takes two clicks:

1. Click **More info** (bottom left of the dialog).
2. Click **Run anyway**.

The warning appears on every update too, because each downloaded binary is a new, unsigned file.

SmartScreen is scanning a file it cannot attribute to a known publisher — a code-signing
certificate is what removes the warning, and signing is deferred to a later release.

---

## 🔄 How updates work

- **Checks at most once every 24 hours.** The timestamp is persisted in `logs/update-check.json`,
  so restarting the app does not re-check.
- **A tray notification, never a pop-up in your face.** The app never steals focus by design, so
  an available update appears as a system-tray balloon. Click the balloon to open the download dialog.
- **You choose.** *Download* starts the transfer, *Later* dismisses it, *Never* opts out permanently.
- **Checksum-verified.** The downloaded file's SHA-256 is compared against the digest published in
  the GitHub release metadata **before** anything is installed. A mismatch aborts the update and
  deletes the bad file.
- **You are asked before anything restarts.** The app never restarts on its own.
- **It will never restart while a game is in progress.** If a game is open, the *Restart Now*
  button is disabled and only *Later* is offered — a restart would lose your in-flight run.
- **Force a check:** right-click the tray icon → **⬆️  Check for Updates**. This bypasses the
  24-hour throttle and the opt-out, and is the way back in after opting out.
- **Opt out permanently:** create an empty file named `NO_AUTOUPDATE` in the same folder as the
  executable, whatever that executable happens to be called.
- **macOS and Linux do not self-install.** On those platforms the updater only notifies you and
  opens the Releases page, because replacing a running macOS `.app` bundle or a Linux binary in
  place is not something this updater does. Download the new file yourself — your `data/` and
  `logs/` folders are untouched.

### What the checksum does and does not protect you from

The SHA-256 check defends against **a corrupt or truncated download** — a flaky connection, a
proxy that mangled the bytes, a partial transfer. It does **not** defend against a compromised
GitHub account — nothing unsigned can. The digest is fetched from the same GitHub release API
response as the download URL, so it protects the transfer, not the publisher. Treat this updater
as **checksum-verified**, not as a guarantee of authenticity.

---

## 🍎 macOS: first launch

macOS Gatekeeper blocks apps that are not notarised. Open it the normal way:

1. Extract `LangTrainer-1.0.1-macos-arm64.tar.gz`.
2. **Right-click** `LangTrainer.app` → **Open**.
3. Confirm with **Open** in the dialog.

Right-click → Open is the intended path and only has to be done once per version. If macOS still
refuses, see [Troubleshooting](#troubleshooting) below.

---

## 📁 Where your data lives

Everything sits **next to the executable**, so an install is one folder you can copy or move:

| Path | What it is |
|---|---|
| `data/lang_trainer.db` | Your words, statistics and best scores (SQLite). Created on first run. |
| `logs/` | Crash log, update-check timestamp, single-instance lock. |
| `dics/` | Ready-made dictionaries, unpacked on first run. |

**To back up:** copy `data/lang_trainer.db` while the app is closed. That single file is your
entire history. To reset completely, delete it — it is recreated empty on the next launch.

> **⚠️ Do not install into a OneDrive (or other sync) folder.** A syncing client can restore an
> old copy of the executable over a newer one, silently downgrading you — and can restore a stale
> `data/lang_trainer.db` over your newer progress. Keep the app in a plain local folder such as
> `C:\Apps\LangTrainer` or `~/Apps/LangTrainer`.

---

## 🧰 Troubleshooting

<details>
<summary><b>macOS: "LangTrainer is damaged and can't be opened"</b></summary>

Right-click → **Open** handles this in the normal case. If you have already quarantined the app
and now it refuses outright, clear the quarantine flag and re-sign it locally:

```bash
xattr -cr /Applications/LangTrainer.app
codesign --force --deep --sign - /Applications/LangTrainer.app
```

</details>

<details>
<summary><b>Linux: "Permission denied" when running the binary</b></summary>

The executable bit is lost when the file is transferred through some browsers, archives or
OneDrive. Restore it:

```bash
chmod +x LangTrainer-1.0.1-linux-x86_64
```

</details>

<details>
<summary><b>Nothing happens when I launch the app</b></summary>

The app runs in the system tray — look for the icon in the tray/notification area, which may be
collapsed behind the ▸ arrow. If it is not there either, the crash log explains why:
**right-click the tray icon → 📂  Open Log Folder**, or read `logs/langtrainer-crash.log`
directly. The app also shows a "could not start" dialog if it cannot create its data folder —
installing into a read-only location such as `C:\Program Files` causes this.

</details>

<details>
<summary><b>I want to check a download myself</b></summary>

`sha256sum -c LangTrainer-1.0.1-checksums.txt` (Linux/macOS) or
`certutil -hashfile LangTrainer-1.0.1-windows-x64.exe SHA256` (Windows).

</details>

---

## 🎮 Games

| Game | Description |
|------|-------------|
| Teach | Browse words and translations at your own pace |
| SRS Flashcard | Anki-style SM-2 review: flip, rate Again/Hard/Good/Easy |
| Meteorites | Speed recall — pick the right translation before time runs out |
| Wordle | Guess the word letter by letter |
| Memory Palace | Match word/translation pairs (3 difficulties) |
| Scrabble | Type the translation (or the word) with hints |
| Chain Reaction | Mixed-direction quiz — word→translation and back |
| Bomb | Answer before the countdown hits zero |
| Domination | Territory control against a CPU teacher |
| Word Sudoku | Fill a Latin square with words |
| Word Snake | Collect letters scattered on the grid |
| Blur | Word unblurs over time — guess the translation |
| Rotating Word | Recall the translation of a rotating word |

## ✨ Features

- **13 games** — from Wordle-style guessing to a word Snake, each targeting a different recall skill
- **Spaced Repetition (SRS)** — Anki-style SM-2 algorithm schedules reviews for long-term retention
- **Passive popup reminders** — the app sits in the system tray and shows word popups on a timer (1–30 min) while you work
- **Smart word selection** — priority + randomness + cooldown: struggling words appear more often, no word dominates
- **System tray** — runs in the background, one click to open
- **Statistics** — per-word success rates, mastery tracking, best scores per game and difficulty
- **In-app updater** — checksum-verified, opt-out, and never interrupts a game (Windows)
- **Full reset** — clear all words and statistics with confirmation

## 🚀 First Steps

1. **Add words** — open the main window and use the **Add Words** dialog to enter word/translation pairs manually, or import them from a file.
2. **Import from file** — the dialog accepts `.txt`/`.csv` files in the format:

   ```
   foreign_word,translation
   ```

   One pair per line, comma-separated. Multiple translations are separated by `/`:

   ```
   for, для / за
   ```

   Files must be UTF-8 encoded. Lines starting with `#` are treated as comments and skipped.
3. **Sample dictionaries** — the `dics/` folder contains ready-made dictionaries (`en-ru.txt`, `esp-en.txt`, `en-esp.txt`) that you can import directly.
4. **Start training** — pick a game from the main menu, or just hide the window and let popup reminders do the work.

## 🖥️ System Tray

- **Hide to tray** — close the main window (X); the app keeps running in the background
- **Show** — click the tray icon
- **📂  Open Log Folder** — opens `logs/` in your file manager
- **⬆️  Check for Updates** — forces an update check
- **Quit** — right-click the tray icon → Quit
- While hidden, the app shows popup reminders on the configured interval (1–30 minutes, default 3)

## 🗑️ Clear Database

The tray menu (and the main window) offer **Clear Database**: a full reset that deletes all words, statistics, and game results in one transaction. It asks for confirmation first. The database schema is preserved — the app is ready for new words immediately.

---

## 🛠️ Build from source

Requires **Python 3.11 or 3.12** (the published builds use 3.12). The only runtime dependency is
`PySide6-Essentials`.

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Windows

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

> Linux and Windows each need their own `.venv` (platform-specific binaries). Do not share one
> across platforms.

### Build a distributable

```bash
pip install -r requirements-build.txt

python build.py            # default: single-file build (--onefile)
python build.py --onedir   # directory distribution: faster startup, bigger folder
python build.py --clean    # wipe the build cache first
```

Output lands in `dist/LangTrainer_onefile/` (or `dist/LangTrainer_onedir/`). On Windows and macOS
`--windowed` is added automatically so no console window appears. UPX compression is deliberately
**not** used — it is the strongest SmartScreen/Defender heuristic and only saves about 10 MB.

### Tests

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -q
```

(On Windows: `set QT_QPA_PLATFORM=offscreen && .venv\Scripts\pytest tests\ -q`)

The `offscreen` platform lets the Qt tests run without a display server.

---

## 📸 Screenshots

*(Screenshots to be added)*

## 📄 License

MIT — see [LICENSE](LICENSE).
