"""
자동 DB 마이그레이션 시스템
- 앱 시작 시 schema_versions 테이블로 현재 버전 확인
- 미적용 마이그레이션을 순차 실행
- 새 마이그레이션 추가: MIGRATIONS 리스트에 (버전, 설명, SQL목록) 튜플 추가
"""
import sqlite3
from app.config import get_settings

settings = get_settings()
DB_PATH = settings.database_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")


# ═══════════════════════════════════════════
# 마이그레이션 정의 — 새 버전은 여기에 추가
# (버전번호, 설명, [SQL문 리스트])
# ═══════════════════════════════════════════

MIGRATIONS = [
    (1, "v0.5.0 — game_config_templates 테이블 + game_requests.config_file_path", [
        # GameConfigTemplate 테이블
        """CREATE TABLE IF NOT EXISTS game_config_templates (
            id VARCHAR PRIMARY KEY,
            game_name VARCHAR(100) NOT NULL UNIQUE,
            filename VARCHAR(255) NOT NULL,
            uploaded_by VARCHAR REFERENCES users(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE INDEX IF NOT EXISTS ix_gct_game_name
           ON game_config_templates(game_name)""",
        # GameRequest.config_file_path 컬럼
        "ALTER TABLE game_requests ADD COLUMN config_file_path VARCHAR(500)",
    ]),

    # ─── 다음 마이그레이션 예시 ───
    # (2, "v0.6.0 — 새 기능 설명", [
    #     "ALTER TABLE users ADD COLUMN some_field VARCHAR(100)",
    #     "CREATE TABLE IF NOT EXISTS new_table (...)",
    # ]),
]


def _ensure_version_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_versions (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)


def _get_current_version(cur) -> int:
    cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_versions")
    return cur.fetchone()[0]


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _table_exists(cur, table: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def run_migrations():
    """앱 시작 시 호출 — 미적용 마이그레이션 순차 실행"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    _ensure_version_table(cur)
    current = _get_current_version(cur)

    pending = [(v, d, sqls) for v, d, sqls in MIGRATIONS if v > current]
    if not pending:
        print(f"[MIGRATE] 스키마 최신 (v{current})")
        conn.close()
        return

    for version, desc, sqls in pending:
        print(f"[MIGRATE] v{version}: {desc}")
        for sql in sqls:
            try:
                # ALTER TABLE ADD COLUMN — 이미 존재하면 무시
                if sql.strip().upper().startswith("ALTER TABLE") and "ADD COLUMN" in sql.upper():
                    parts = sql.upper().split()
                    tbl_idx = parts.index("TABLE") + 1
                    col_idx = parts.index("COLUMN") + 1
                    table = sql.split()[tbl_idx]
                    column = sql.split()[col_idx]
                    if _column_exists(cur, table, column):
                        print(f"  [SKIP] {table}.{column} 이미 존재")
                        continue

                # CREATE TABLE IF NOT EXISTS — 이미 존재하면 무시 (SQLite 자체 처리)
                # CREATE INDEX IF NOT EXISTS — 동일

                cur.execute(sql)
                print(f"  [OK] {sql[:60]}...")
            except sqlite3.OperationalError as e:
                err = str(e).lower()
                if "already exists" in err or "duplicate column" in err:
                    print(f"  [SKIP] 이미 존재: {e}")
                else:
                    print(f"  [ERROR] {e}")
                    conn.rollback()
                    conn.close()
                    raise

        cur.execute(
            "INSERT INTO schema_versions (version, description) VALUES (?, ?)",
            (version, desc)
        )
        conn.commit()
        print(f"  [DONE] v{version} 적용 완료")

    final = _get_current_version(cur)
    print(f"[MIGRATE] 마이그레이션 완료 — 현재 스키마 v{final}")
    conn.close()
