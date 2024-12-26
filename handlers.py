import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from db import get_worker_percentage, set_worker_percentage, add_transaction, get_all_workers, get_stats
from utils import calculate_fee, distribute_fee
from config import YOUR_WALLET, OWNER_1_WALLET, OWNER_2_WALLET, ADMIN_USER_ID
from blockchain import check_tokens_received, send_tokens_to_owners

logger = logging.getLogger(__name__)

ENTER_AMOUNT, WAIT_FOR_SCREENSHOT, WAIT_FOR_CONFIRMATION = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Введите сумму, которую вы хотите вывести:")
    return ENTER_AMOUNT

async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        context.user_data['withdraw_amount'] = amount
        await update.message.reply_text("Отправьте скриншот транзакции или подтверждения:")
        return WAIT_FOR_SCREENSHOT
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректное число.")
        return ENTER_AMOUNT

async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Пожалуйста, отправьте скриншот (изображение).")
        return WAIT_FOR_SCREENSHOT

    photo = update.message.photo[-1]
    file_id = photo.file_id
    context.user_data['screenshot_file_id'] = file_id

    worker_id = update.effective_user.id
    conn = context.bot_data['conn']

    withdraw_amount = context.user_data.get('withdraw_amount', 0)
    worker_percentage = get_worker_percentage(conn, worker_id)
    fee_amount = calculate_fee(withdraw_amount, worker_percentage)
    context.user_data['fee_amount'] = fee_amount

    message = (f"Сумма вывода: {withdraw_amount}\n"
               f"Процент для вас: {worker_percentage}%\n"
               f"Ваша комиссия: {fee_amount}\n"
               f"Пожалуйста, отправьте {fee_amount} токенов на адрес {YOUR_WALLET}\n"
               "После перевода напишите /done для проверки.")
    await update.message.reply_text(message)
    return WAIT_FOR_CONFIRMATION

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    worker_id = update.effective_user.id
    conn = context.bot_data['conn']

    fee_amount = context.user_data['fee_amount']
    withdraw_amount = context.user_data['withdraw_amount']
    screenshot_file_id = context.user_data['screenshot_file_id']

    if check_tokens_received(YOUR_WALLET, fee_amount):
        owner_1_amount, owner_2_amount = distribute_fee(fee_amount)
        send_tokens_to_owners(owner_1_amount, OWNER_1_WALLET)
        send_tokens_to_owners(owner_2_amount, OWNER_2_WALLET)
        add_transaction(conn, worker_id, withdraw_amount, fee_amount, owner_1_amount, owner_2_amount, "completed", screenshot_file_id)

        await update.message.reply_text("Токены получены. Транзакция завершена!")
        return ConversationHandler.END
    else:
        await update.message.reply_text("Пока средства не поступили. Попробуйте снова позже или введите /done после перевода.")
        return WAIT_FOR_CONFIRMATION

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END

async def set_percentage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("Доступ запрещен.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Использование: /set_percentage <worker_id> <число>")
        return

    try:
        w_id = int(context.args[0])
        percentage = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректные значения.")
        return

    conn = context.bot_data['conn']
    set_worker_percentage(conn, w_id, percentage)
    await update.message.reply_text(f"Процент для рабочего {w_id} успешно обновлен до {percentage}%")

async def admin_list_workers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("Доступ запрещен.")
        return

    conn = context.bot_data['conn']
    workers = get_all_workers(conn)
    if not workers:
        await update.message.reply_text("Пока нет зарегистрированных работников.")
        return

    text = "Список работников:\n"
    for w_id, perc in workers:
        text += f"Worker ID: {w_id}, Percentage: {perc}%\n"
    await update.message.reply_text(text)

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("Доступ запрещен.")
        return

    conn = context.bot_data['conn']
    stats = get_stats(conn)
    text = (f"Статистика:\n"
            f"Всего транзакций: {stats['total_transactions']}\n"
            f"Общая сумма выводов: {stats['total_withdraw']}\n"
            f"Общая сумма комиссий: {stats['total_fees']}\n")
    await update.message.reply_text(text)
