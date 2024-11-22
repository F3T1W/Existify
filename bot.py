from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from email_service import verify_email_with_zerobounce

async def handle_message(update, context):
    user_message = update.message.text.strip()

    if "@" in user_message and "." in user_message:
        result = verify_email_with_zerobounce(user_message)
        await update.message.reply_text(result)
    else:
        await update.message.reply_text("Пожалуйста, отправь корректный email.")

async def start_command(update: Update, context):
    await update.message.reply_text("Привет! Я проверяю email. Напиши мне адрес почты!")

if __name__ == "__main__":
    TOKEN = "YOUR_TG_BOT_API_TOKEN"

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()
