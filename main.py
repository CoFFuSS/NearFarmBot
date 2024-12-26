import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, filters
from handlers import start, enter_amount, receive_screenshot, done, cancel, set_percentage_command, admin_list_workers, admin_stats, ENTER_AMOUNT, WAIT_FOR_SCREENSHOT, WAIT_FOR_CONFIRMATION
from db import init_db
from config import BOT_TOKEN

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    conn = init_db()

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.bot_data['conn'] = conn

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ENTER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount)],
            WAIT_FOR_SCREENSHOT: [MessageHandler(filters.PHOTO, receive_screenshot)],
            WAIT_FOR_CONFIRMATION: [
                CommandHandler("done", done),
                MessageHandler(filters.TEXT & ~filters.COMMAND, done)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("set_percentage", set_percentage_command))
    application.add_handler(CommandHandler("admin_list_workers", admin_list_workers))
    application.add_handler(CommandHandler("admin_stats", admin_stats))

    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
