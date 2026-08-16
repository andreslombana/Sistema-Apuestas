# utils/db_manager.py
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "quant_history.db"

def init_db():
    """Inicializa la base de datos relacional para el registro de backtesting."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            team_a TEXT,
            team_b TEXT,
            market TEXT,
            model_pick TEXT,
            ev_percentage REAL,
            odds REAL,
            result TEXT DEFAULT 'PENDING'
        )
    ''')
    conn.commit()
    conn.close()

def log_prediction(team_a: str, team_b: str, market: str, pick: str, ev: float, odds: float):
    """Inserta una nueva proyección cuantitativa en el registro histórico."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO predictions (timestamp, team_a, team_b, market, model_pick, ev_percentage, odds)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), team_a, team_b, market, pick, ev, odds))
    conn.commit()
    conn.close()

def get_history_df() -> pd.DataFrame:
    """Extrae el historial completo en un DataFrame para análisis visual."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM predictions ORDER BY timestamp DESC", conn)
    conn.close()
    return df