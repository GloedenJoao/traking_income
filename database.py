import sqlite3
from pathlib import Path
from flask import g


DEFAULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS detail_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL,
    description TEXT NOT NULL,
    entry_type TEXT CHECK(entry_type IN ('provento', 'desconto')) NOT NULL,
    amount REAL NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS monthly_totals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL UNIQUE,
    total_proventos REAL NOT NULL DEFAULT 0,
    total_descontos REAL NOT NULL DEFAULT 0,
    valor_liquido REAL NOT NULL DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db(app):
    # Reutilize a mesma conexão por requisição (Atualizar se necessário).
    if 'db' not in g:
        db_path = Path(app.config['DATABASE'])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


def close_db(_=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    db = get_db(app)
    db.executescript(DEFAULT_SCHEMA)
    db.commit()


def recalculate_month_totals(app, period: str):
    db = get_db(app)
    cur = db.execute(
        """
        SELECT
            SUM(CASE WHEN entry_type = 'provento' THEN amount ELSE 0 END) AS total_proventos,
            SUM(CASE WHEN entry_type = 'desconto' THEN amount ELSE 0 END) AS total_descontos
        FROM detail_entries
        WHERE period = ?
        """,
        (period,),
    )
    row = cur.fetchone()
    total_proventos = row[0] or 0
    total_descontos = row[1] or 0
    valor_liquido = total_proventos - total_descontos

    db.execute(
        """
        INSERT INTO monthly_totals (period, total_proventos, total_descontos, valor_liquido, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(period) DO UPDATE SET
            total_proventos=excluded.total_proventos,
            total_descontos=excluded.total_descontos,
            valor_liquido=excluded.valor_liquido,
            updated_at=CURRENT_TIMESTAMP
        """,
        (period, total_proventos, total_descontos, valor_liquido),
    )
    db.commit()
    return {
        'period': period,
        'total_proventos': total_proventos,
        'total_descontos': total_descontos,
        'valor_liquido': valor_liquido,
    }
