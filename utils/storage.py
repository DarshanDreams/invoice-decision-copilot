import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import pandas as pd


DB_PATH = Path("data/run_history.db")


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS invoice_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_timestamp TEXT,
            file_name TEXT,
            invoice_number TEXT,
            vendor_name TEXT,
            po_number TEXT,
            total_amount REAL,
            decision TEXT,
            decision_category TEXT,
            risk_level TEXT,
            parsed_invoice_json TEXT,
            po_match_json TEXT,
            decision_json TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def save_run(
    file_name: str,
    parsed_invoice: Dict[str, Any],
    po_match_result: Dict[str, Any],
    decision_result: Dict[str, Any]
):
    init_db()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO invoice_runs (
            run_timestamp,
            file_name,
            invoice_number,
            vendor_name,
            po_number,
            total_amount,
            decision,
            decision_category,
            risk_level,
            parsed_invoice_json,
            po_match_json,
            decision_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            file_name,
            parsed_invoice.get("invoice_number"),
            parsed_invoice.get("vendor_name"),
            parsed_invoice.get("po_number"),
            parsed_invoice.get("total_amount"),
            decision_result.get("decision"),
            decision_result.get("decision_category"),
            decision_result.get("risk_level"),
            json.dumps(parsed_invoice, default=str),
            json.dumps(po_match_result, default=str),
            json.dumps(decision_result, default=str),
        )
    )

    conn.commit()
    conn.close()


def load_run_history() -> pd.DataFrame:
    init_db()

    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql_query(
        """
        SELECT
            id,
            run_timestamp,
            file_name,
            invoice_number,
            vendor_name,
            po_number,
            total_amount,
            decision,
            decision_category,
            risk_level
        FROM invoice_runs
        ORDER BY id DESC
        """,
        conn
    )

    conn.close()
    return df


def load_full_run(run_id: int) -> Dict[str, Any] | None:
    init_db()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM invoice_runs WHERE id = ?",
        (run_id,)
    )

    row = cursor.fetchone()
    columns = [description[0] for description in cursor.description]

    conn.close()

    if not row:
        return None

    record = dict(zip(columns, row))

    record["parsed_invoice_json"] = json.loads(record["parsed_invoice_json"])
    record["po_match_json"] = json.loads(record["po_match_json"])
    record["decision_json"] = json.loads(record["decision_json"])

    return record


def clear_history():
    init_db()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM invoice_runs")

    conn.commit()
    conn.close()