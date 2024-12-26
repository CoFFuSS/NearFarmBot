
from config import OWNER_1_SHARE, OWNER_2_SHARE

def calculate_fee(withdraw_amount: float, worker_percentage: float) -> float:
    fee_amount = withdraw_amount * (worker_percentage / 100.0)
    return fee_amount

def distribute_fee(fee_amount: float):
    owner_1_amount = fee_amount * OWNER_1_SHARE
    owner_2_amount = fee_amount * OWNER_2_SHARE
    return owner_1_amount, owner_2_amount
