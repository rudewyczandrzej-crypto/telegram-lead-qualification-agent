import os
import psycopg
from psycopg.rows import dict_row


def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL не знайдено у Railway Variables")
    return psycopg.connect(database_url, row_factory=dict_row)


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id SERIAL PRIMARY KEY,
                    telegram_chat_id BIGINT NOT NULL,
                    name TEXT,
                    email TEXT,
                    phone TEXT,
                    company TEXT,
                    need TEXT,
                    service_type TEXT,
                    budget TEXT,
                    timeline TEXT,
                    decision_maker TEXT,
                    lead_score INTEGER,
                    quality TEXT,
                    status TEXT DEFAULT 'new',
                    ai_summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lead_messages (
                    id SERIAL PRIMARY KEY,
                    lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
                    telegram_chat_id BIGINT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversation_state (
                    telegram_chat_id BIGINT PRIMARY KEY,
                    lead_id INTEGER,
                    active BOOLEAN DEFAULT FALSE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()


def create_lead(telegram_chat_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO leads (telegram_chat_id, status)
                VALUES (%s, 'collecting')
                RETURNING id;
            """, (telegram_chat_id,))
            row = cur.fetchone()
            conn.commit()
            return row["id"]


def get_lead(lead_id: int, telegram_chat_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM leads WHERE id=%s AND telegram_chat_id=%s;", (lead_id, telegram_chat_id))
            return cur.fetchone()


def list_leads(telegram_chat_id: int, limit: int = 20):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM leads
                WHERE telegram_chat_id=%s
                ORDER BY id DESC
                LIMIT %s;
            """, (telegram_chat_id, limit))
            return cur.fetchall()


def update_lead(lead_id: int, telegram_chat_id: int, data: dict):
    allowed = [
        "name", "email", "phone", "company", "need", "service_type",
        "budget", "timeline", "decision_maker", "lead_score",
        "quality", "status", "ai_summary"
    ]
    fields = []
    values = []
    for key in allowed:
        if key in data:
            fields.append(f"{key}=%s")
            values.append(data[key])

    if not fields:
        return

    values += [lead_id, telegram_chat_id]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                UPDATE leads
                SET {", ".join(fields)},
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=%s AND telegram_chat_id=%s;
            """, values)
            conn.commit()


def add_message(lead_id: int, telegram_chat_id: int, role: str, message: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO lead_messages (lead_id, telegram_chat_id, role, message)
                VALUES (%s, %s, %s, %s);
            """, (lead_id, telegram_chat_id, role, message))
            conn.commit()


def get_messages(lead_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM lead_messages
                WHERE lead_id=%s
                ORDER BY id ASC;
            """, (lead_id,))
            return cur.fetchall()


def set_state(telegram_chat_id: int, lead_id: int | None, active: bool):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO conversation_state (telegram_chat_id, lead_id, active, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (telegram_chat_id)
                DO UPDATE SET lead_id=EXCLUDED.lead_id,
                              active=EXCLUDED.active,
                              updated_at=CURRENT_TIMESTAMP;
            """, (telegram_chat_id, lead_id, active))
            conn.commit()


def get_state(telegram_chat_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM conversation_state WHERE telegram_chat_id=%s;", (telegram_chat_id,))
            return cur.fetchone()


def update_status(lead_id: int, telegram_chat_id: int, status: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE leads SET status=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id=%s AND telegram_chat_id=%s RETURNING id;
            """, (status, lead_id, telegram_chat_id))
            row = cur.fetchone()
            conn.commit()
            return row is not None


def clear_all(telegram_chat_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM conversation_state WHERE telegram_chat_id=%s;", (telegram_chat_id,))
            cur.execute("DELETE FROM leads WHERE telegram_chat_id=%s;", (telegram_chat_id,))
            conn.commit()


def report(telegram_chat_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, COUNT(*) AS count FROM leads
                WHERE telegram_chat_id=%s GROUP BY status ORDER BY status;
            """, (telegram_chat_id,))
            by_status = cur.fetchall()
            cur.execute("""
                SELECT quality, COUNT(*) AS count FROM leads
                WHERE telegram_chat_id=%s GROUP BY quality ORDER BY quality;
            """, (telegram_chat_id,))
            by_quality = cur.fetchall()
            return {"by_status": by_status, "by_quality": by_quality}
