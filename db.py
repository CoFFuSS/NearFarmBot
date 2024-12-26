import sqlite3
from config import DB_PATH, CSV_PATH, XLSX_PATH
import csv
import os
from openpyxl import Workbook, load_workbook

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER,
        withdraw_amount REAL,
        fee_amount REAL,
        owner_1_received REAL,
        owner_2_received REAL,
        status TEXT,
        screenshot_file_id TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workers (
        worker_id INTEGER PRIMARY KEY,
        percentage REAL
    )
    """)
    conn.commit()
    return conn

def get_worker_percentage(conn, worker_id):
    cursor = conn.cursor()
    cursor.execute("SELECT percentage FROM workers WHERE worker_id = ?", (worker_id,))
    row = cursor.fetchone()
    if row is not None:
        return float(row[0])
    else:
        default_percentage = 5.0
        cursor.execute("INSERT INTO workers (worker_id, percentage) VALUES (?, ?)", (worker_id, default_percentage))
        conn.commit()
        return default_percentage

def set_worker_percentage(conn, worker_id, percentage):
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO workers (worker_id, percentage) VALUES (?,?)", (worker_id, percentage))
    conn.commit()

def add_transaction(conn, worker_id, withdraw_amount, fee_amount, owner_1_received, owner_2_received, status, screenshot_file_id):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (worker_id, withdraw_amount, fee_amount, owner_1_received, owner_2_received, status, screenshot_file_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (worker_id, withdraw_amount, fee_amount, owner_1_received, owner_2_received, status, screenshot_file_id))
    conn.commit()

    save_transaction_to_csv(worker_id, withdraw_amount, fee_amount, owner_1_received, owner_2_received, status, screenshot_file_id)
    save_transaction_to_excel(worker_id, withdraw_amount, fee_amount, owner_1_received, owner_2_received, status, screenshot_file_id)

def save_transaction_to_csv(worker_id, withdraw_amount, fee_amount, owner_1_received, owner_2_received, status, screenshot_file_id):
    file_exists = os.path.isfile(CSV_PATH)
    with open(CSV_PATH, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["worker_id", "withdraw_amount", "fee_amount", "owner_1_received", "owner_2_received", "status", "screenshot_file_id"])
        writer.writerow([worker_id, withdraw_amount, fee_amount, owner_1_received, owner_2_received, status, screenshot_file_id])

def save_transaction_to_excel(worker_id, withdraw_amount, fee_amount, owner_1_received, owner_2_received, status, screenshot_file_id):
    if os.path.exists(XLSX_PATH):
        wb = load_workbook(XLSX_PATH)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.append(["worker_id", "withdraw_amount", "fee_amount", "owner_1_received", "owner_2_received", "status", "screenshot_file_id"])

    ws.append([worker_id, withdraw_amount, fee_amount, owner_1_received, owner_2_received, status, screenshot_file_id])

    wb.save(XLSX_PATH)

def get_all_workers(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT worker_id, percentage FROM workers")
    return cursor.fetchall()

def get_stats(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(withdraw_amount), SUM(fee_amount) FROM transactions")
    row = cursor.fetchone()
    total_transactions = row[0]
    total_withdraw = row[1] if row[1] else 0
    total_fees = row[2] if row[2] else 0
    return {
        "total_transactions": total_transactions,
        "total_withdraw": total_withdraw,
        "total_fees": total_fees
    }