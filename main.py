# main.py

import logging
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters
)
from config import BOT_TOKEN
from db import init_db, is_admin
from handlers import (
    # Состояния:
    MAIN_MENU,
    WORKER_ENTER_AMOUNT,
    WORKER_WAIT_SCREEN,
    WORKER_CONFIRM,
    ADMIN_MENU,
    ADMIN_SET_PERC_CHOOSE_WORKER,
    ADMIN_SET_PERC_WAIT_VALUE,
    ADMIN_SET_OWNERS_SHARE_CHOOSE_WORKER,
    ADMIN_SET_OWNERS_SHARE_WAIT_VALUES,
    ADMIN_QUOTA_CHOOSE_WORKER,
    ADMIN_QUOTA_MENU,
    ADMIN_QUOTA_DAILY,

    # Основные хендлеры:
    start_handler,
    main_menu_callback,
    worker_enter_amount,
    worker_wait_screenshot_callback,
    worker_receive_screenshot,
    worker_confirm_callback,
    admin_menu_callback,
    admin_set_perc_choose_worker,
    admin_set_perc_wait_value,
    admin_set_owners_share_choose_worker,
    admin_set_owners_share_wait_values,
    admin_quota_choose_worker,
    

    # Нам нужно подтянуть меню админа, чтобы вернуться в него
    get_admin_menu_keyboard
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    # Инициализация БД
    conn = init_db()

    # Создаём приложение
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.bot_data['conn'] = conn

    # ConversationHandler со всеми состояниями
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_handler)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(main_menu_callback, pattern="^(worker_start|admin_menu)$"),
            ],
            WORKER_ENTER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, worker_enter_amount),
            ],
            WORKER_WAIT_SCREEN: [
                CallbackQueryHandler(worker_wait_screenshot_callback, pattern="^(worker_send_screenshot|cancel)$"),
                MessageHandler(filters.PHOTO, worker_receive_screenshot),
            ],
            WORKER_CONFIRM: [
                CallbackQueryHandler(worker_confirm_callback, pattern="^(worker_done|cancel)$"),
            ],
            ADMIN_MENU: [
                CallbackQueryHandler(
                    admin_menu_callback,
                    pattern="^(go_main_menu|admin_list_workers|admin_set_percentage|admin_set_owners_share|admin_quota_settings|admin_owners_pending|admin_reset_owner1|admin_reset_owner2)$"
                )
            ],
            ADMIN_SET_PERC_CHOOSE_WORKER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_perc_choose_worker)
            ],
            ADMIN_SET_PERC_WAIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_perc_wait_value)
            ],
            ADMIN_SET_OWNERS_SHARE_CHOOSE_WORKER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_owners_share_choose_worker)
            ],
            ADMIN_SET_OWNERS_SHARE_WAIT_VALUES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_owners_share_wait_values)
            ],
            ADMIN_QUOTA_CHOOSE_WORKER: [
                # Вводим ID работника; дальше админ вводит команды /quota_toggle, /quota_daily
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_quota_choose_worker)
            ],
            ADMIN_QUOTA_MENU: [],
            ADMIN_QUOTA_DAILY: [],
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)

    # Команды для управления квотой
    application.add_handler(CommandHandler("quota_toggle", quota_toggle))
    application.add_handler(CommandHandler("quota_daily", quota_daily))

    application.run_polling()

# -----------------------------
# Логика команд /quota_toggle и /quota_daily
# -----------------------------

async def quota_toggle(update, context):
    """
    /quota_toggle <0|1>
    После переключения квоты сразу возвращаемся в админ-меню.
    """
    conn = context.bot_data['conn']
    user_id = update.effective_user.id

    # Проверка, что это админ
    if not is_admin(conn, user_id):
        await update.message.reply_text("Доступ запрещён.")
        return

    # Проверяем аргументы
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /quota_toggle <0|1>")
        return
    val_str = context.args[0]
    if val_str not in ("0","1"):
        await update.message.reply_text("Введите 0 или 1. Пример: /quota_toggle 1")
        return

    # Проверяем, что в контексте есть worker_id
    w_id = context.user_data.get('temp_worker_id')
    if not w_id:
        await update.message.reply_text("Сначала выберите работника (Настройки квоты).")
        return

    from db import set_worker_quota_logic
    set_worker_quota_logic(conn, w_id, bool(int(val_str)))

    await update.message.reply_text(f"Работник {w_id}: use_quota_logic => {val_str}")

    # Сразу возвращаемся в админ-меню
    await update.message.reply_text("Меню администратора:", reply_markup=get_admin_menu_keyboard())
    # Можно не менять состояние, так как /quota_toggle не внутри ConversationHandler.


async def quota_daily(update, context):
    """
    /quota_daily <число>
    После изменения daily_quota сразу возвращаемся в админ-меню.
    """
    conn = context.bot_data['conn']
    user_id = update.effective_user.id

    # Проверка, что это админ
    if not is_admin(conn, user_id):
        await update.message.reply_text("Доступ запрещён.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Использование: /quota_daily <число>")
        return

    try:
        val = float(context.args[0])
    except ValueError:
        await update.message.reply_text("Некорректное число. Пример: /quota_daily 13")
        return

    w_id = context.user_data.get('temp_worker_id')
    if not w_id:
        await update.message.reply_text("Сначала выберите работника (Настройки квоты).")
        return

    from db import set_worker_daily_quota
    set_worker_daily_quota(conn, w_id, val)

    await update.message.reply_text(f"Работник {w_id}: daily_quota => {val}")

    # Возвращаемся в админ-меню
    await update.message.reply_text("Меню администратора:", reply_markup=get_admin_menu_keyboard())


if __name__ == "__main__":
    main()
