"""Database manager for LangTrainer."""
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from config import DB_PATH


class WordRecord:
    """Represents a word record from the database."""
    
    def __init__(self, row: tuple):
        self.id: int = row[0]
        self.word: str = row[1]           # Foreign word
        self.translation: str = row[2]     # Translation
        self.correct_count: int = row[3]   # Correct answers
        self.incorrect_count: int = row[4] # Incorrect answers
        self.total_shown: int = row[5]     # Total times shown
        self.last_shown: Optional[str] = row[6]  # ISO datetime
        self.created_at: str = row[7]
        # SRS fields (may be missing in legacy SELECT * queries)
        self.ease_factor: float = float(row[8]) if len(row) > 8 else 2.5
        self.interval_days: int = int(row[9]) if len(row) > 9 else 0
        self.next_review_date: Optional[str] = row[10] if len(row) > 10 else None
        self.total_reviews: int = int(row[11]) if len(row) > 11 else 0
    
    @property
    def total_attempts(self) -> int:
        return self.correct_count + self.incorrect_count
    
    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.correct_count / self.total_attempts
    
    @property
    def is_mastered(self) -> bool:
        """Word is considered mastered if >= 80% correct with >= 10 attempts."""
        return self.total_attempts >= 10 and self.success_rate >= 0.8
    
    def __repr__(self):
        return f"<Word {self.id}: {self.word} -> {self.translation}>"


class DatabaseManager:
    """Manages SQLite database for word storage and statistics."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None
    
    def connect(self):
        """Open database connection and create tables if needed."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()
        self._migrate_srs_columns()
        self._migrate_game_stats()
    
    def _create_tables(self):
        """Create database schema with SRS columns."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL UNIQUE,
                translation TEXT NOT NULL,
                correct_count INTEGER DEFAULT 0,
                incorrect_count INTEGER DEFAULT 0,
                total_shown INTEGER DEFAULT 0,
                last_shown TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                ease_factor REAL DEFAULT 2.5,
                interval_days INTEGER DEFAULT 0,
                next_review_date TEXT,
                total_reviews INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    

    def _migrate_srs_columns(self):
        """Add SRS columns to existing database if they don't exist."""
        import sqlite3
        for col, col_type in [
            ("ease_factor", "REAL DEFAULT 2.5"),
            ("interval_days", "INTEGER DEFAULT 0"),
            ("next_review_date", "TEXT"),
            ("total_reviews", "INTEGER DEFAULT 0"),
        ]:
            try:
                self.cursor.execute(f"ALTER TABLE words ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists
        self.conn.commit()

    def _migrate_game_stats(self):
        """Create the game_best_results table if it doesn't exist."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_best_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                best_score INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(game, difficulty)
            )
        """)
        self.conn.commit()

    def add_word(self, word: str, translation: str) -> bool:
        """Add a new word. Returns False if duplicate."""
        try:
            self.cursor.execute(
                "INSERT INTO words (word, translation) VALUES (?, ?)",
                (word.strip(), translation.strip())
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def add_words_batch(self, words: list) -> dict:
        """Add multiple words. Returns stats about added/skipped."""
        stats = {"added": 0, "duplicates": 0, "duplicate_words": []}
        for word, translation in words:
            if self.add_word(word, translation):
                stats["added"] += 1
            else:
                stats["duplicates"] += 1
                stats["duplicate_words"].append(word)
        return stats
    
    def word_exists(self, word: str) -> bool:
        """Check if a word already exists in database."""
        self.cursor.execute(
            "SELECT COUNT(*) FROM words WHERE word = ?", (word.strip(),)
        )
        return self.cursor.fetchone()[0] > 0
    
    def get_all_words(self):
        """Get all words ordered by creation date."""
        self.cursor.execute("SELECT * FROM words ORDER BY created_at DESC")
        return [WordRecord(row) for row in self.cursor.fetchall()]
    
    def get_word_count(self) -> int:
        """Get total number of words."""
        self.cursor.execute("SELECT COUNT(*) FROM words")
        return self.cursor.fetchone()[0]
    
    def get_word_by_id(self, word_id: int) -> Optional[WordRecord]:
        """Get a specific word by ID."""
        self.cursor.execute("SELECT * FROM words WHERE id = ?", (word_id,))
        row = self.cursor.fetchone()
        return WordRecord(row) if row else None
    
    def get_random_word(self):
        """Get a random word."""
        self.cursor.execute("SELECT * FROM words ORDER BY RANDOM() LIMIT 1")
        row = self.cursor.fetchone()
        return WordRecord(row) if row else None
    
    def get_random_words(self, count: int):
        """Get N random words."""
        self.cursor.execute("SELECT * FROM words ORDER BY RANDOM() LIMIT ?", (count,))
        return [WordRecord(row) for row in self.cursor.fetchall()]
    
    def record_attempt(self, word_id: int, was_correct: bool):
        """Record a training attempt for a word."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if was_correct:
            self.cursor.execute("""
                UPDATE words SET correct_count = correct_count + 1, 
                    total_shown = total_shown + 1, last_shown = ?
                WHERE id = ?
            """, (now, word_id))
        else:
            self.cursor.execute("""
                UPDATE words SET incorrect_count = incorrect_count + 1, 
                    total_shown = total_shown + 1, last_shown = ?
                WHERE id = ?
""", (now, word_id))
        self.conn.commit()

    def record_game_result(self, game: str, difficulty: str, score: int) -> None:
        """Record a game result, keeping the best score per game+difficulty combo.

        Args:
            game: Game identifier, e.g. 'bomb'.
            difficulty: Difficulty level, e.g. 'easy', 'normal', 'hard'.
            score: Score achieved in this run.

        Behavior:
            - No row for (game, difficulty) -> insert a new row.
            - score > existing best_score -> update best_score and updated_at.
            - score <= existing best_score -> do nothing.
        """
        self.cursor.execute(
            "SELECT best_score FROM game_best_results WHERE game = ? AND difficulty = ?",
            (game, difficulty),
        )
        row = self.cursor.fetchone()
        if row is None:
            self.cursor.execute(
                "INSERT INTO game_best_results (game, difficulty, best_score) VALUES (?, ?, ?)",
                (game, difficulty, score),
            )
        elif score > row[0]:
            self.cursor.execute(
                "UPDATE game_best_results SET best_score = ?, updated_at = datetime('now') "
                "WHERE game = ? AND difficulty = ?",
                (score, game, difficulty),
            )
        self.conn.commit()

    def get_game_best(self, game: str, difficulty: str) -> int:
        """Get the best score for a game+difficulty combo.

        Args:
            game: Game identifier, e.g. 'bomb'.
            difficulty: Difficulty level, e.g. 'easy', 'normal', 'hard'.

        Returns:
            Best recorded score, or 0 if no result has been recorded yet.
        """
        self.cursor.execute(
            "SELECT best_score FROM game_best_results WHERE game = ? AND difficulty = ?",
            (game, difficulty),
        )
        row = self.cursor.fetchone()
        return row[0] if row else 0
    
    def record_dismissed(self, word_id: int):
        """Record that a word was shown but dismissed without answer."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute("""
            UPDATE words SET total_shown = total_shown + 1, last_shown = ?
            WHERE id = ?
        """, (now, word_id))
        self.conn.commit()

    def get_priority_words(self, limit: int = 5):
        """
        Get words sorted by display priority.
        
        Priority formula:
        raw_priority = need_factor + recency_factor
        
        - need_factor (0–1.0):
          Never answered: MAX(0.2, 1.0 - total_shown / 15.0)
            → fresh word = 1.0, dismissed 15+ times = 0.2 (floor)
          Answered: (1 - success_rate) * 0.6
            → 100% correct = 0, 0% correct = 0.6, 50% = 0.3
        
        - recency_factor (0–0.4):
          Never shown: 0.4
          Shown: (days_since / 3.0, capped at 1.0) * 0.4
            → after 1 day = 0.13, after 3 days = 0.4 (full)
        
        - mastery_penalty: 0.5 if mastered (>=10 attempts, >=80%), else 1.0
        """
        self.cursor.execute("""
            SELECT *, 
                -- Need factor: success rate + penalty for over-shown words
                CASE 
                    WHEN (correct_count + incorrect_count) = 0 THEN
                        MAX(0.2, 1.0 - CAST(COALESCE(total_shown, 0) AS REAL) / 15.0)
                    ELSE
                        (1.0 - CAST(correct_count AS REAL) / NULLIF(correct_count + incorrect_count, 0)) * 0.6
                END
                +
                -- Recency factor: time since last shown (3-day decay)
                CASE 
                    WHEN last_shown IS NULL THEN 0.4
                    ELSE MIN(CAST(julianday('now', 'localtime') - julianday(last_shown) AS REAL) / 3.0, 1.0) * 0.4
                END
                AS raw_priority,
                -- Mastery penalty: halve priority for well-known words
                CASE 
                    WHEN (correct_count + incorrect_count) >= 10 
                         AND CAST(correct_count AS REAL) / NULLIF(correct_count + incorrect_count, 0) >= 0.8 
                    THEN 0.5 ELSE 1.0 
                END as mastery_penalty
            FROM words
            ORDER BY raw_priority * mastery_penalty DESC, RANDOM()
            LIMIT ?
        """, (limit,))
        return [WordRecord(row) for row in self.cursor.fetchall()]
    
    def get_popup_word(self, recent_ids: list[int] = None):
        """Get a word for passive popup training.
        
        Strategy: priority + randomness + cooldown.
        
        1. Get top 10 priority words (struggling/recent words rise to top)
        2. Exclude recent_ids (cooldown — don't repeat same word within N popups)
        3. Pick RANDOMLY from remaining candidates (all have equal chance)
        
        This ensures:
        - All words eventually appear (random spread from top pool)
        - Struggling words appear more (they're in the top pool more often)
        - No word dominates (random selection, not deterministic #1)
        - No immediate repeats (cooldown via recent_ids)
        """
        import random
        
        recent_ids = set(recent_ids or [])
        
        # Get top 10 by priority score
        self.cursor.execute("""
            SELECT *, 
                CASE 
                    WHEN (correct_count + incorrect_count) = 0 THEN
                        MAX(0.2, 1.0 - CAST(COALESCE(total_shown, 0) AS REAL) / 15.0)
                    ELSE
                        (1.0 - CAST(correct_count AS REAL) / NULLIF(correct_count + incorrect_count, 0)) * 0.6
                END
                +
                CASE 
                    WHEN last_shown IS NULL THEN 0.4
                    ELSE MIN(CAST(julianday('now', 'localtime') - julianday(last_shown) AS REAL) / 3.0, 1.0) * 0.4
                END
                AS raw_priority,
                CASE 
                    WHEN (correct_count + incorrect_count) >= 10 
                         AND CAST(correct_count AS REAL) / NULLIF(correct_count + incorrect_count, 0) >= 0.8 
                    THEN 0.5 ELSE 1.0 
                END as mastery_penalty
            FROM words
            ORDER BY raw_priority * mastery_penalty DESC, RANDOM()
            LIMIT 10
        """)
        
        rows = self.cursor.fetchall()
        if not rows:
            return None
        
        # Filter out recently shown words (cooldown)
        candidates = [row for row in rows if row["id"] not in recent_ids]
        
        # If cooldown exhausted all candidates, fall back to full top 10
        if not candidates:
            candidates = rows
        
        # Random pick from available pool
        chosen = random.choice(candidates)
        return WordRecord(chosen)
    
    def get_words_for_test(self, count: int):
        """Get words for focused test: 60% priority + 40% random."""
        total = self.get_word_count()
        if total == 0:
            return []
        
        priority_count = max(1, min(int(count * 0.6), total))
        random_count = count - priority_count
        
        priority_words = self.get_priority_words(priority_count)
        
        selected_ids = [w.id for w in priority_words]
        random_words = []
        if selected_ids and random_count > 0:
            placeholders = ",".join("?" * len(selected_ids))
            self.cursor.execute(
                f"SELECT * FROM words WHERE id NOT IN ({placeholders}) ORDER BY RANDOM() LIMIT ?",
                selected_ids + [random_count]
            )
            random_words = [WordRecord(row) for row in self.cursor.fetchall()]
        elif random_count > 0:
            self.cursor.execute("SELECT * FROM words ORDER BY RANDOM() LIMIT ?", (random_count,))
            random_words = [WordRecord(row) for row in self.cursor.fetchall()]
        
        result = priority_words + random_words
        import random
        random.shuffle(result)
        return result[:count]
    
    def delete_all_words(self):
        """Delete all words from database."""
        self.cursor.execute("DELETE FROM words")
        self.conn.commit()
    
    def reset_statistics(self, word_id: int = None):
        """Reset statistics for a word or all words.

        Resets answer counters, the last-shown timestamp, and the SRS
        fields (ease_factor, interval_days, next_review_date,
        total_reviews) back to their schema defaults.

        Args:
            word_id: ID of the word to reset, or None to reset all words.
        """
        if word_id:
            self.cursor.execute("""
                UPDATE words SET correct_count=0, incorrect_count=0, total_shown=0,
                    last_shown=NULL, ease_factor=2.5, interval_days=0,
                    next_review_date=NULL, total_reviews=0
                WHERE id = ?
            """, (word_id,))
        else:
            self.cursor.execute("""
                UPDATE words SET correct_count=0, incorrect_count=0, total_shown=0,
                    last_shown=NULL, ease_factor=2.5, interval_days=0,
                    next_review_date=NULL, total_reviews=0
            """)
        self.conn.commit()

    def clear_all_data(self) -> None:
        """Permanently delete all words, statistics, and game results.

        Performs a TRUE full reset in a single transaction:
        - Deletes every row from ``words`` (removing all per-word
          statistics and SRS fields along with the rows)
        - Deletes every row from ``game_best_results``

        The schema itself is preserved — the tables remain usable for
        new words and game results afterwards.

        Raises:
            sqlite3.Error: If the transaction fails; the connection is
                rolled back and the error is re-raised with context.
        """
        try:
            self.cursor.execute("DELETE FROM words")
            self.cursor.execute("DELETE FROM game_best_results")
            self.conn.commit()
        except sqlite3.Error as exc:
            self.conn.rollback()
            raise sqlite3.Error(f"Failed to clear database: {exc}") from exc

    def get_words_for_review(self, limit: int = 10):
        """Get words due for SRS review.
        
        Returns words where:
        - next_review_date is NULL (never reviewed) OR
        - next_review_date <= today
        
        Ordered by next_review_date ASC (most overdue first).
        """
        today = date.today().strftime("%Y-%m-%d")
        self.cursor.execute("""
            SELECT * FROM words
            WHERE next_review_date IS NULL OR next_review_date <= ?
            ORDER BY 
                CASE WHEN next_review_date IS NULL THEN 0 ELSE 1 END,
                next_review_date ASC,
                total_reviews ASC
            LIMIT ?
        """, (today, limit))
        return [WordRecord(row) for row in self.cursor.fetchall()]

    def record_srs_review(self, word_id: int, quality: int):
        """Record an SRS review using the SM-2 algorithm.
        
        Args:
            word_id: ID of the word being reviewed
            quality: 0-5 rating (1=Again, 2=Hard, 3=Good, 5=Easy)
        """
        quality = max(0, min(5, quality))
        
        self.cursor.execute(
            "SELECT ease_factor, interval_days, total_reviews FROM words WHERE id = ?",
            (word_id,)
        )
        row = self.cursor.fetchone()
        if not row:
            return
        
        ease_factor = row[0]
        interval_days = row[1]
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        from datetime import timedelta
        today = date.today()
        
        if quality >= 3:
            # Correct response
            if interval_days == 0:
                interval_days = 1
            elif interval_days == 1:
                interval_days = 6
            else:
                interval_days = round(interval_days * ease_factor)
            
            # Update ease factor
            ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        else:
            # Incorrect response - reset interval
            interval_days = 0
            ease_factor = max(1.3, ease_factor - 0.2)
        
        # Clamp ease factor
        ease_factor = max(1.3, min(3.0, ease_factor))
        
        # Calculate next review date
        next_review = today + timedelta(days=interval_days) if interval_days > 0 else today
        
        # Update database
        self.cursor.execute("""
            UPDATE words SET
                ease_factor = ?,
                interval_days = ?,
                next_review_date = ?,
                total_reviews = total_reviews + 1,
                last_shown = ?,
                correct_count = correct_count + ?,
                incorrect_count = incorrect_count + ?,
                total_shown = total_shown + 1
            WHERE id = ?
        """, (
            ease_factor,
            interval_days,
            next_review.strftime("%Y-%m-%d"),
            now,
            1 if quality >= 3 else 0,
            1 if quality < 3 else 0,
            word_id
        ))
        self.conn.commit()

    def get_word_srs_stats(self, word_id: int) -> dict:
        """Get SRS statistics for a word."""
        self.cursor.execute(
            "SELECT ease_factor, interval_days, next_review_date, total_reviews FROM words WHERE id = ?",
            (word_id,)
        )
        row = self.cursor.fetchone()
        if not row:
            return {}
        return {
            "ease_factor": row[0],
            "interval_days": row[1],
            "next_review_date": row[2],
            "total_reviews": row[3],
        }
