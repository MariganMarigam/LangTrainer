"""Application configuration."""
from pathlib import Path

APP_NAME = "LangTrainer"
APP_VERSION = "1.0.0"

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "lang_trainer.db"
ASSETS_DIR = BASE_DIR / "assets"

TIMER_MIN = 1
TIMER_MAX = 30
TIMER_DEFAULT = 3

WORDS_PER_POPUP = 1
TRANSLATION_OPTIONS = 3
DEFAULT_WORDS_PER_GAME = 10
