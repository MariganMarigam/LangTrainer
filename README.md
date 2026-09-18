# LangTrainer

A cross-platform desktop language-learning app for Windows and Linux: learn foreign words through passive popup reminders and 13 interactive games, powered by a spaced-repetition system (SRS).

Built with PySide6 (Qt 6) and SQLite. Dark iOS-inspired theme, lives in the system tray.

## Features

- **13 games** — from Wordle-style guessing to a word Snake, each targeting a different recall skill
- **Spaced Repetition (SRS)** — Anki-style SM-2 algorithm schedules reviews for long-term retention
- **Passive popup reminders** — the app sits in the system tray and shows word popups on a timer (1–30 min) while you work
- **Smart word selection** — priority + randomness + cooldown: struggling words appear more often, no word dominates
- **System tray** — runs in the background, one click to open
- **Statistics** — per-word success rates, mastery tracking, best scores per game and difficulty
- **Full reset** — clear all words and statistics with confirmation

## Screenshots

*(Add screenshots here)*

## Requirements

- Python 3.10+
- PySide6-Essentials >= 6.5.0 (the only dependency)

## Installation

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows

```powershell
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

> Note: Linux and Windows each need their own `.venv` (platform-specific binaries). Do not share a venv across platforms.

## Running

```bash
python main.py
```

The app starts in the system tray. Click the tray icon to open the main window.

## First Steps

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

## Games

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

## System Tray

- **Hide to tray** — close the main window (X); the app keeps running in the background
- **Show** — click the tray icon
- **Quit** — right-click the tray icon → Quit
- While hidden, the app shows popup reminders on the configured interval (1–30 minutes, default 3)

## Clear Database

The tray menu (and the main window) offer **Clear Database**: a full reset that deletes all words, statistics, and game results in one transaction. It asks for confirmation first. The database schema is preserved — the app is ready for new words immediately.

## Data Storage

- The database lives at `data/lang_trainer.db` (SQLite), created automatically on first run.
- To back up your data, copy `data/lang_trainer.db` while the app is closed.
- To reset completely, delete the file — it will be recreated empty on next launch.

## Testing

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -v
```

(On Windows: `set QT_QPA_PLATFORM=offscreen && .venv\Scripts\pytest tests\ -v`)

The `offscreen` platform lets the Qt tests run without a display server.

## Packaging

Build a standalone executable with PyInstaller:

```bash
pip install pyinstaller
python build.py            # onedir build → dist/LangTrainer/
python build.py --onefile  # single executable
python build.py --upx /path/to/upx  # smaller builds
```

## License

MIT — see [LICENSE](LICENSE).