"""Local storage for Xiaohongshu creator-work review data.

The MCP adapter is intentionally kept outside this repository.  This module
stores the normalized rows returned by an adapter (or a CSV/XLSX fallback),
so the UI remains usable when a platform connector is unavailable.
"""

import json
import sqlite3
from contextlib import closing


def ensure_tables(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS xiaohongshu_own_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL DEFAULT 'manual_import',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS xiaohongshu_own_videos (
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
        CREATE TABLE IF NOT EXISTS xiaohongshu_own_video_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL UNIQUE,
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
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS xiaohongshu_own_account_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            profile_json TEXT NOT NULL DEFAULT '[]',
            stats_json TEXT NOT NULL DEFAULT '[]',
            period TEXT NOT NULL DEFAULT 'thirty',
            captured_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()


def upsert_account(db_path, account_name):
    ensure_tables(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO xiaohongshu_own_accounts (name)
        VALUES (?)
        ON CONFLICT(name) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
        """, (account_name,))
        conn.commit()
        return cursor.execute(
            "SELECT id FROM xiaohongshu_own_accounts WHERE name = ?", (account_name,)
        ).fetchone()[0]


def save_import(db_path, rows, account_name, source_key_fn):
    ensure_tables(db_path)
    account_id = upsert_account(db_path, account_name)
    inserted = updated = 0
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        for item in rows:
            source_key = source_key_fn(item)
            raw_data = json.dumps(item, ensure_ascii=False)
            existing = cursor.execute(
                "SELECT id FROM xiaohongshu_own_videos WHERE account_id = ? AND source_key = ?",
                (account_id, source_key),
            ).fetchone()
            cursor.execute("""
            INSERT INTO xiaohongshu_own_videos
                (account_id, source_key, title, video_url, published_at, content_format,
                 visibility_status, transcript, notes, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id, source_key) DO UPDATE SET
                title = excluded.title, video_url = excluded.video_url,
                published_at = excluded.published_at, content_format = excluded.content_format,
                visibility_status = excluded.visibility_status, transcript = excluded.transcript,
                notes = excluded.notes, raw_data = excluded.raw_data,
                updated_at = CURRENT_TIMESTAMP
            """, (
                account_id, source_key, item.get("title"), item.get("video_url"),
                item.get("published_at"), item.get("content_format"),
                item.get("visibility_status"), item.get("transcript"),
                item.get("notes"), raw_data,
            ))
            video_id = cursor.execute(
                "SELECT id FROM xiaohongshu_own_videos WHERE account_id = ? AND source_key = ?",
                (account_id, source_key),
            ).fetchone()[0]
            cursor.execute("""
            INSERT INTO xiaohongshu_own_video_metrics
                (video_id, play_count, completion_rate, five_sec_completion_rate,
                 cover_click_rate, two_sec_bounce_rate, avg_play_duration, like_count,
                 share_count, comment_count, collect_count, profile_visit_count,
                 follower_delta, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                play_count = excluded.play_count, completion_rate = excluded.completion_rate,
                five_sec_completion_rate = excluded.five_sec_completion_rate,
                cover_click_rate = excluded.cover_click_rate,
                two_sec_bounce_rate = excluded.two_sec_bounce_rate,
                avg_play_duration = excluded.avg_play_duration,
                like_count = excluded.like_count, share_count = excluded.share_count,
                comment_count = excluded.comment_count, collect_count = excluded.collect_count,
                profile_visit_count = excluded.profile_visit_count,
                follower_delta = excluded.follower_delta, raw_data = excluded.raw_data,
                updated_at = CURRENT_TIMESTAMP
            """, (
                video_id, item.get("play_count"), item.get("completion_rate"),
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


def save_account_snapshot(db_path, account_id, profile, stats, period="thirty"):
    ensure_tables(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.execute("""
        INSERT INTO xiaohongshu_own_account_snapshots
            (account_id, profile_json, stats_json, period)
        VALUES (?, ?, ?, ?)
        """, (
            account_id,
            json.dumps(profile or [], ensure_ascii=False),
            json.dumps(stats or [], ensure_ascii=False),
            period,
        ))
        conn.commit()
        return cursor.lastrowid


def get_latest_account_snapshot(db_path, account_id=None):
    ensure_tables(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
        SELECT s.*, a.name AS account_name
        FROM xiaohongshu_own_account_snapshots s
        LEFT JOIN xiaohongshu_own_accounts a ON a.id = s.account_id
        WHERE (? IS NULL OR s.account_id = ?)
        ORDER BY s.captured_at DESC, s.id DESC
        LIMIT 1
        """, (account_id, account_id)).fetchone()
    if not row:
        return None
    result = dict(row)
    for source_key, target_key in (("profile_json", "profile"), ("stats_json", "stats")):
        try:
            result[target_key] = json.loads(result.pop(source_key) or "[]")
        except (TypeError, ValueError):
            result[target_key] = []
    # 官方资料中的昵称是当前连接账号的真实名称；历史数据里可能曾使用过
    # “我的小红书账号”等 UI 默认名，因此展示时以资料快照为准。
    for item in result.get("profile") or []:
        if item.get("label") == "账号名称" and item.get("value"):
            result["account_name"] = str(item["value"]).strip()
            break
    return result


def list_videos(db_path, limit=100, account_id=None):
    ensure_tables(db_path)
    try:
        limit = max(1, min(int(limit), 500))
    except Exception:
        limit = 100
    current_account_name = None
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        if account_id is None:
            latest = conn.execute(
                "SELECT account_id FROM xiaohongshu_own_account_snapshots "
                "ORDER BY captured_at DESC, id DESC LIMIT 1"
            ).fetchone()
            # 没有“当前账号”快照时不能回退为全量历史账号，避免把多个账号混在一起。
            if not latest:
                return []
            account_id = latest[0]
        if account_id is not None:
            snapshot = conn.execute(
                "SELECT profile_json FROM xiaohongshu_own_account_snapshots "
                "WHERE account_id = ? ORDER BY captured_at DESC, id DESC LIMIT 1",
                (account_id,),
            ).fetchone()
            if snapshot:
                try:
                    profile = json.loads(snapshot[0] or "[]")
                    current_account_name = next(
                        (str(item.get("value")).strip() for item in profile
                         if item.get("label") == "账号名称" and item.get("value")),
                        None,
                    )
                except (TypeError, ValueError):
                    current_account_name = None
        rows = conn.execute("""
        SELECT v.*, a.name AS account_name,
               m.play_count, m.completion_rate, m.five_sec_completion_rate,
               m.cover_click_rate, m.two_sec_bounce_rate, m.avg_play_duration,
               m.like_count, m.share_count, m.comment_count, m.collect_count,
               m.profile_visit_count, m.follower_delta
        FROM xiaohongshu_own_videos v
        LEFT JOIN xiaohongshu_own_accounts a ON a.id = v.account_id
        LEFT JOIN xiaohongshu_own_video_metrics m ON m.video_id = v.id
        WHERE (? IS NULL OR v.account_id = ?)
        ORDER BY COALESCE(v.published_at, v.created_at) DESC, v.id DESC
        LIMIT ?
        """, (account_id, account_id, limit)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        if current_account_name and item.get("account_id") == account_id:
            item["account_name"] = current_account_name
        try:
            raw = json.loads(item.get("raw_data") or "{}")
        except (TypeError, ValueError):
            raw = {}
        item["official_metric_sections"] = raw.get("official_metric_sections") or []
        item["metric_quality"] = raw.get("metric_quality")
        result.append(item)
    return result
