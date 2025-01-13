# handlers.py

import logging
import datetime
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from db import (
    is_admin,
    get_worker_data,
    set_worker_percentage,
    set_worker_owners_share,
    add_transaction,
    get_all_workers,
    get_owner_pending_sum,
    reset_owner_pending_sum,
    set_worker_quota_logic,
    set_worker_daily_quota
)
from utils import calculate_effective_percentage
from config import (
    YOUR_WALLET,
    OWNER_1_WALLET,
    OWNER_2_WALLET
)
from blockchain import check_tokens_received, send_tokens_to_owners

logger = logging.getLogger(__name__)

(
    MAIN_MENU,                 # 0
    WORKER_ENTER_AMOUNT,       # 1
    WORKER_WAIT_SCREEN,        # 2
    WORKER_CONFIRM,            # 3
    ADMIN_MENU,                # 4

    ADMIN_SET_PERC_CHOOSE_WORKER,      # 5
    ADMIN_SET_PERC_WAIT_VALUE,         # 6

    ADMIN_SET_OWNERS_SHARE_CHOOSE_WORKER, # 7
    ADMIN_SET_OWNERS_SHARE_WAIT_VALUES,   # 8

    ADMIN_QUOTA_CHOOSE_WORKER,    # 9
    ADMIN_QUOTA_MENU,             # 10
    ADMIN_QUOTA_DAILY,            # 11
) = range(12)


def get_main_menu_keyboard(is_user_admin: bool) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton("Начать вывод (Рабочий)", callback_data="worker_start")]]
    if is_user_admin:
        buttons.append([InlineKeyboardButton("Админ: открыть меню", callback_data="admin_menu")])
    return InlineKeyboardMarkup(buttons)

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("Список работников", callback_data="admin_list_workers")],
        [InlineKeyboardButton("Изменить % работника", callback_data="admin_set_percentage")],
        [InlineKeyboardButton("Изменить распределение (owner1/owner2)", callback_data="admin_set_owners_share")],
        [InlineKeyboardButton("Настройки квоты", callback_data="admin_quota_settings")],
        [InlineKeyboardButton("Показать pending владельцев", callback_data="admin_owners_pending")],
        [InlineKeyboardButton("Вернуться в главное меню", callback_data="go_main_menu")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_worker_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("Отправить скриншот", callback_data="worker_send_screenshot")],
        [InlineKeyboardButton("Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(buttons)


# ---------------------------
# /start
# ---------------------------

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = context.bot_data['conn']
    admin_flag = is_admin(conn, user_id)

    kb = get_main_menu_keyboard(admin_flag)
    await update.message.reply_text("Добро пожаловать! Выберите нужное действие:", reply_markup=kb)
    return MAIN_MENU

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    conn = context.bot_data['conn']

    if query.data == "worker_start":
        await query.message.reply_text("Введите сумму, которую хотите вывести:")
        return WORKER_ENTER_AMOUNT
    elif query.data == "admin_menu" and is_admin(conn, user_id):
        await query.message.reply_text("Меню администратора:", reply_markup=get_admin_menu_keyboard())
        return ADMIN_MENU
    else:
        await query.message.reply_text("Доступ запрещён или неизвестная команда.")
        return MAIN_MENU


# ---------------------------
# Рабочий
# ---------------------------

async def worker_enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректное число.")
        return WORKER_ENTER_AMOUNT

    context.user_data['withdraw_amount'] = amount
    await update.message.reply_text(
        f"Вы ввели сумму: {amount}\nТеперь отправьте скриншот или отмените:",
        reply_markup=get_worker_menu_keyboard()
    )
    return WORKER_WAIT_SCREEN

async def worker_wait_screenshot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "worker_send_screenshot":
        await query.message.reply_text("Пришлите фотографию (фото) сообщением.")
        return WORKER_WAIT_SCREEN
    elif query.data == "cancel":
        user_id = query.from_user.id
        conn = context.bot_data['conn']
        kb = get_main_menu_keyboard(is_admin(conn, user_id))
        await query.message.reply_text("Операция отменена.", reply_markup=kb)
        return MAIN_MENU

async def worker_receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Это не фото, попробуйте ещё раз.")
        return WORKER_WAIT_SCREEN

    file_id = update.message.photo[-1].file_id
    context.user_data['screenshot_file_id'] = file_id

    worker_id = update.effective_user.id
    conn = context.bot_data['conn']
    withdraw_amount = context.user_data['withdraw_amount']

    # (base_perc, o1_share, o2_share, quota_flag, daily_q)
    row = get_worker_data(conn, worker_id)
    base_perc, o1s, o2s, quota_flag, daily_q = row

    eff_p = calculate_effective_percentage(
        conn=conn,
        worker_id=worker_id,
        base_percentage=base_perc,
        use_quota_logic=quota_flag,
        daily_quota=daily_q,
        current_withdraw=withdraw_amount
    )
    fee_amount = withdraw_amount * (eff_p / 100.0)

    context.user_data['fee_amount'] = fee_amount
    context.user_data['owner_1_share'] = o1s
    context.user_data['owner_2_share'] = o2s

    text = (
        f"Сумма вывода: {withdraw_amount}\n"
        f"Эффективный процент: {eff_p}%\n"
        f"Комиссия: {fee_amount}\n\n"
        f"Отправьте {fee_amount} NEAR на адрес {YOUR_WALLET}, затем нажмите 'Готово' для проверки."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Готово", callback_data="worker_done")],
        [InlineKeyboardButton("Отмена", callback_data="cancel")]
    ])
    await update.message.reply_text(text, reply_markup=kb)
    return WORKER_CONFIRM

async def worker_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    conn = context.bot_data['conn']

    if query.data == "worker_done":
        fee_amount = context.user_data['fee_amount']
        withdraw_amount = context.user_data['withdraw_amount']
        screenshot_file_id = context.user_data['screenshot_file_id']

        o1s = context.user_data['owner_1_share']
        o2s = context.user_data['owner_2_share']

        if check_tokens_received(YOUR_WALLET, fee_amount):
            owner_1_amount = fee_amount * o1s
            owner_2_amount = fee_amount * o2s

            send_tokens_to_owners(owner_1_amount, OWNER_1_WALLET)
            send_tokens_to_owners(owner_2_amount, OWNER_2_WALLET)

            add_transaction(
                conn=conn,
                worker_id=user_id,
                withdraw_amount=withdraw_amount,
                fee_amount=fee_amount,
                owner_1_received=owner_1_amount,
                owner_2_received=owner_2_amount,
                status="completed",
                screenshot_file_id=screenshot_file_id
            )
            await query.message.reply_text("Токены получены. Транзакция завершена!")
        else:
            await query.message.reply_text("Пока средства не поступили. Попробуйте ещё раз позже.")
            return WORKER_CONFIRM

    elif query.data == "cancel":
        await query.message.reply_text("Операция отменена.")

    kb = get_main_menu_keyboard(is_admin(conn, user_id))
    await query.message.reply_text("Главное меню:", reply_markup=kb)
    return MAIN_MENU

# ---------------------------
# Админ
# ---------------------------

async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    conn = context.bot_data['conn']

    if not is_admin(conn, user_id):
        await query.message.reply_text("Доступ запрещён.")
        return MAIN_MENU

    data = query.data

    if data == "go_main_menu":
        kb = get_main_menu_keyboard(is_admin(conn, user_id))
        await query.message.reply_text("Главное меню:", reply_markup=kb)
        return MAIN_MENU

    elif data == "admin_list_workers":
        workers = get_all_workers(conn)
        if not workers:
            await query.message.reply_text("Пока нет работников.")
        else:
            txt = "Список работников:\n"
            for (w_id, perc, o1, o2, qflag, dq) in workers:
                txt += (f"Worker {w_id}: base_p={perc}%, shares=({o1*100:.0f}%/{o2*100:.0f}%), "
                        f"quota_logic={qflag}, daily_q={dq}\n")
            await query.message.reply_text(txt)
        return ADMIN_MENU

    elif data == "admin_set_percentage":
        await query.message.reply_text("Введите ID работника, которому хотите изменить базовый процент:")
        return ADMIN_SET_PERC_CHOOSE_WORKER

    elif data == "admin_set_owners_share":
        await query.message.reply_text("Введите ID работника, кому хотите изменить доли (пример: 0.5 0.5).")
        return ADMIN_SET_OWNERS_SHARE_CHOOSE_WORKER

    elif data == "admin_quota_settings":
        await query.message.reply_text("Введите ID работника для настройки квоты:")
        return ADMIN_QUOTA_CHOOSE_WORKER

    elif data == "admin_owners_pending":
        o1_sum = get_owner_pending_sum(conn, "owner1")
        o2_sum = get_owner_pending_sum(conn, "owner2")
        txt = (f"Owner1 pending: {o1_sum}\nOwner2 pending: {o2_sum}\n\nНажмите, чтобы обнулить:")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Обнулить Owner1", callback_data="admin_reset_owner1")],
            [InlineKeyboardButton("Обнулить Owner2", callback_data="admin_reset_owner2")]
        ])
        await query.message.reply_text(txt, reply_markup=kb)
        return ADMIN_MENU

    elif data == "admin_reset_owner1":
        reset_owner_pending_sum(conn, "owner1")
        o1_sum = get_owner_pending_sum(conn, "owner1")
        o2_sum = get_owner_pending_sum(conn, "owner2")
        txt = f"Owner1 pending: {o1_sum}\nOwner2 pending: {o2_sum}\n"
        await query.message.reply_text(f"Owner1 обнулён.\n{txt}")
        return ADMIN_MENU

    elif data == "admin_reset_owner2":
        reset_owner_pending_sum(conn, "owner2")
        o1_sum = get_owner_pending_sum(conn, "owner1")
        o2_sum = get_owner_pending_sum(conn, "owner2")
        txt = f"Owner1 pending: {o1_sum}\nOwner2 pending: {o2_sum}\n"
        await query.message.reply_text(f"Owner2 обнулён.\n{txt}")
        return ADMIN_MENU

    else:
        await query.message.reply_text("Неизвестная команда.")
        return MAIN_MENU

# ---------------------------
# Изменение процента
# ---------------------------

async def admin_set_perc_choose_worker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        w_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Некорректный ID. Повторите.")
        return ADMIN_SET_PERC_CHOOSE_WORKER

    context.user_data['temp_worker_id'] = w_id
    await update.message.reply_text(f"Введите новый базовый процент для работника {w_id} (обычно 30):")
    return ADMIN_SET_PERC_WAIT_VALUE

async def admin_set_perc_wait_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_p = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Некорректное число. Повторите.")
        return ADMIN_SET_PERC_WAIT_VALUE

    w_id = context.user_data['temp_worker_id']
    set_worker_percentage(context.bot_data['conn'], w_id, new_p)
    await update.message.reply_text(f"Процент у работника {w_id} теперь {new_p}%.")

    await update.message.reply_text("Меню админа:", reply_markup=get_admin_menu_keyboard())
    return ADMIN_MENU

# ---------------------------
# Изменение долей (owner1/owner2)
# ---------------------------

async def admin_set_owners_share_choose_worker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        w_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Некорректный ID. Повторите.")
        return ADMIN_SET_OWNERS_SHARE_CHOOSE_WORKER

    context.user_data['temp_worker_id'] = w_id
    await update.message.reply_text("Введите доли для owner1, owner2 (пример: 0.5 0.5)")
    return ADMIN_SET_OWNERS_SHARE_WAIT_VALUES

async def admin_set_owners_share_wait_values(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.strip().split()
        o1 = float(parts[0])
        o2 = float(parts[1])
    except:
        await update.message.reply_text("Некорректный ввод. Пример: 0.5 0.5")
        return ADMIN_SET_OWNERS_SHARE_WAIT_VALUES

    w_id = context.user_data['temp_worker_id']
    set_worker_owners_share(context.bot_data['conn'], w_id, o1, o2)
    await update.message.reply_text(f"Установлены доли: owner1={o1}, owner2={o2} для {w_id}.")

    await update.message.reply_text("Меню админа:", reply_markup=get_admin_menu_keyboard())
    return ADMIN_MENU

# ---------------------------
# Настройка квоты (0/1) + daily
# ---------------------------

async def admin_quota_choose_worker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    После ввода ID, предложим в ответ:
    /quota_toggle <0/1>
    /quota_daily <число>
    """
    try:
        w_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Некорректный worker_id. Повторите.")
        return ADMIN_QUOTA_CHOOSE_WORKER

    context.user_data['temp_worker_id'] = w_id
    msg = (
        f"Работник {w_id} выбран.\n"
        f"Включить/выключить квоту: /quota_toggle 0 или 1\n"
        f"Изменить daily_quota: /quota_daily <число>\n\n"
        "Или /cancel, чтобы выйти."
    )
    await update.message.reply_text(msg)
    return ADMIN_QUOTA_MENU
