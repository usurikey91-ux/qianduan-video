import json
import sqlite3
from contextlib import closing


def ensure_tables(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS douyin_own_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL DEFAULT 'manual_import',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS douyin_own_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            source_key TEXT NOT NULL,
            title TEXT NOT NULL,
            video_url TEXT,
            published_at TEXT,
            content_format TEXT,
            visibility_status TEXT,
            transcript TEXT,
            notes TEXT,
            raw_data TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, source_key)
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS douyin_own_video_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL UNIQUE,
            exposure_count INTEGER,
            play_count INTEGER,
            completion_rate REAL,
            five_sec_completion_rate REAL,
            cover_click_rate REAL,
            two_sec_bounce_rate REAL,
            avg_play_duration REAL,
            like_count INTEGER,
            share_count INTEGER,
            comment_count INTEGER,
            collect_count INTEGER,
            profile_visit_count INTEGER,
            follower_delta INTEGER,
            raw_data TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        metric_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(douyin_own_video_metrics)")
        }
        if "exposure_count" not in metric_columns:
            cursor.execute(
                "ALTER TABLE douyin_own_video_metrics ADD COLUMN exposure_count INTEGER"
            )
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS douyin_own_account_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            overview_json TEXT NOT NULL DEFAULT '{}',
            period TEXT NOT NULL DEFAULT '7d',
            captured_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()


def upsert_account(db_path, account_name):
    ensure_tables(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO douyin_own_accounts (name)
        VALUES (?)
        ON CONFLICT(name) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
        """, (account_name,))
        conn.commit()
        row = cursor.execute(
            "SELECT id FROM douyin_own_accounts WHERE name = ?",
            (account_name,),
        ).fetchone()
        return row[0]


def save_import(db_path, rows, account_name, source_key_fn):
    ensure_tables(db_path)
    account_id = upsert_account(db_path, account_name)
    inserted = 0
    updated = 0
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        for item in rows:
            source_key = source_key_fn(item)
            existing = cursor.execute(
                "SELECT id FROM douyin_own_videos WHERE account_id = ? AND source_key = ?",
                (account_id, source_key),
            ).fetchone()
            raw_data = json.dumps(item, ensure_ascii=False)
            cursor.execute("""
            INSERT INTO douyin_own_videos
                (account_id, source_key, title, video_url, published_at, content_format,
                 visibility_status, transcript, notes, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id, source_key) DO UPDATE SET
                title = excluded.title,
                video_url = excluded.video_url,
                published_at = excluded.published_at,
                content_format = excluded.content_format,
                visibility_status = excluded.visibility_status,
                transcript = excluded.transcript,
                notes = excluded.notes,
                raw_data = excluded.raw_data,
                updated_at = CURRENT_TIMESTAMP
            """, (
                account_id, source_key, item.get("title"), item.get("video_url"),
                item.get("published_at"), item.get("content_format"),
                item.get("visibility_status"), item.get("transcript"),
                item.get("notes"), raw_data,
            ))
            video_id = cursor.execute(
                "SELECT id FROM douyin_own_videos WHERE account_id = ? AND source_key = ?",
                (account_id, source_key),
            ).fetchone()[0]
            cursor.execute("""
            INSERT INTO douyin_own_video_metrics
                (video_id, exposure_count, play_count, completion_rate, five_sec_completion_rate, cover_click_rate,
                 two_sec_bounce_rate, avg_play_duration, like_count, share_count, comment_count,
                 collect_count, profile_visit_count, follower_delta, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                exposure_count = excluded.exposure_count,
                play_count = excluded.play_count,
                completion_rate = excluded.completion_rate,
                five_sec_completion_rate = excluded.five_sec_completion_rate,
                cover_click_rate = excluded.cover_click_rate,
                two_sec_bounce_rate = excluded.two_sec_bounce_rate,
                avg_play_duration = excluded.avg_play_duration,
                like_count = excluded.like_count,
                share_count = excluded.share_count,
                comment_count = excluded.comment_count,
                collect_count = excluded.collect_count,
                profile_visit_count = excluded.profile_visit_count,
                follower_delta = excluded.follower_delta,
                raw_data = excluded.raw_data,
                updated_at = CURRENT_TIMESTAMP
            """, (
                video_id, item.get("exposure_count"), item.get("play_count"), item.get("completion_rate"),
                item.get("five_sec_completion_rate"), item.get("cover_click_rate"),
                item.get("two_sec_bounce_rate"), item.get("avg_play_duration"),
                item.get("like_count"), item.get("share_count"), item.get("comment_count"),
                item.get("collect_count"), item.get("profile_visit_count"),
                item.get("follower_delta"), raw_data,
            ))
            if existing:
                updated += 1
            else:
                inserted += 1
        conn.commit()
    return {"account_id": account_id, "inserted": inserted, "updated": updated, "total": len(rows)}


def save_account_snapshot(db_path, account_id, overview):
    ensure_tables(db_path)
    payload = overview if isinstance(overview, dict) else {}
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.execute("""
        INSERT INTO douyin_own_account_snapshots
            (account_id, overview_json, period, captured_at)
        VALUES (?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
        """, (
            account_id,
            json.dumps(payload, ensure_ascii=False),
            payload.get("period") or "7d",
            payload.get("captured_at"),
        ))
        conn.commit()
        return cursor.lastrowid


def get_latest_account_snapshot(db_path):
    ensure_tables(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
        SELECT s.*, a.name AS account_name
        FROM douyin_own_account_snapshots s
        LEFT JOIN douyin_own_accounts a ON a.id = s.account_id
        ORDER BY s.captured_at DESC, s.id DESC
        LIMIT 1
        """).fetchone()
    if not row:
        return None
    result = dict(row)
    try:
        overview = json.loads(result.pop("overview_json") or "{}")
    except (TypeError, ValueError):
        overview = {}
    result.update(overview)
    return result


def list_videos(db_path, limit=100):
    ensure_tables(db_path)
    try:
        limit = max(1, min(int(limit), 500))
    except Exception:
        limit = 100
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
        SELECT
            v.*, a.name AS account_name,
            m.exposure_count, m.play_count, m.completion_rate, m.five_sec_completion_rate,
            m.cover_click_rate, m.two_sec_bounce_rate, m.avg_play_duration,
            m.like_count, m.share_count, m.comment_count, m.collect_count,
            m.profile_visit_count, m.follower_delta
        FROM douyin_own_videos v
        LEFT JOIN douyin_own_accounts a ON a.id = v.account_id
        LEFT JOIN douyin_own_video_metrics m ON m.video_id = v.id
        ORDER BY COALESCE(v.published_at, v.created_at) DESC, v.id DESC
        LIMIT ?
        """, (limit,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            raw = json.loads(item.get("raw_data") or "{}")
        except (TypeError, ValueError):
            raw = {}
        item["official_metric_sections"] = raw.get("official_metric_sections") or []
        item["metric_quality"] = raw.get("metric_quality")
        result.append(item)
    return result
