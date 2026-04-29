# store/job_store.py
import sqlite3
from datetime import date

from models import Job


class JobStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs_seen (
                url TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                source TEXT,
                first_seen DATE,
                score INTEGER,
                emailed BOOLEAN
            )
            """
        )
        self._conn.commit()

    def is_seen(self, url: str) -> bool:
        cursor = self._conn.execute(
            "SELECT 1 FROM jobs_seen WHERE url = ?", (url,)
        )
        return cursor.fetchone() is not None

    def filter_new(self, jobs: list[Job]) -> list[Job]:
        return [job for job in jobs if not self.is_seen(job.url)]

    def mark_seen(self, job: Job, score: int, emailed: bool):
        self._conn.execute(
            """
            INSERT OR IGNORE INTO jobs_seen (url, title, company, source, first_seen, score, emailed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (job.url, job.title, job.company, job.source, date.today().isoformat(), score, emailed),
        )
        self._conn.commit()

    def mark_seen_batch(self, jobs: list[Job], scores: dict[str, int]):
        today = date.today().isoformat()
        rows = [
            (job.url, job.title, job.company, job.source, today, scores.get(job.url, 0), True)
            for job in jobs
        ]
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO jobs_seen (url, title, company, source, first_seen, score, emailed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()

    def close(self):
        self._conn.close()
