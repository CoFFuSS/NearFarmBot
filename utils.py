# utils.py

import datetime
import math
from db import get_last_transaction_timestamp

def calculate_effective_percentage(
    conn,
    worker_id: int,
    base_percentage: float,
    use_quota_logic: int,
    daily_quota: float,
    current_withdraw: float
) -> float:
    """
    Логика:
      - Если use_quota_logic=0 => всегда base_percentage (обычно 30).
      - Если use_quota_logic=1:
         1) Смотрим, есть ли предыдущая транзакция.
         2) Если нет => первый вывод = 20%.
         3) Если есть => считаем, сколько полных дней прошло (min=1),
            если current_withdraw >= daily_quota * days => 20%, иначе 30%.
    """
    # Квота выключена => базовый процент
    if use_quota_logic == 0:
        return base_percentage

    # Квота включена
    last_ts_str = get_last_transaction_timestamp(conn, worker_id)
    if not last_ts_str:
        # Первый вывод => 20%
        return 20.0

    # Есть предыдущая транзакция
    last_dt = datetime.datetime.fromisoformat(last_ts_str)  # "YYYY-MM-DDTHH:MM:SS"
    now_dt = datetime.datetime.now()
    diff = now_dt - last_dt
    diff_days = diff.total_seconds() / (3600*24)
    days_count = max(1, math.floor(diff_days))  # минимум 1 день

    required = daily_quota * days_count
    if current_withdraw >= required:
        return 20.0
    else:
        return 30.0
