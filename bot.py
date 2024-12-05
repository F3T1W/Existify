import os
import logging
import time
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from email_service import verify_email
from tempfile import NamedTemporaryFile
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    filename="bot.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Create uploads directory if it doesn't exist
UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Concurrent Email Validation with Streaming to Files
def check_emails_streaming(email_list, max_workers=10000):
    """
    Validate Emails Concurrently And Write Results To Files Immediately.
    """
    locks = {
        "valid": Lock(),
        "syntax": Lock(),
        "domain": Lock(),
        "server": Lock(),
    }

    result_files = {
        "valid": NamedTemporaryFile(delete=False, suffix=".txt", mode="w"),
        "syntax": NamedTemporaryFile(delete=False, suffix=".txt", mode="w"),
        "domain": NamedTemporaryFile(delete=False, suffix=".txt", mode="w"),
        "server": NamedTemporaryFile(delete=False, suffix=".txt", mode="w"),
    }

    def process_email(index, email):
        print(f"Processing Email {index + 1}/{len(email_list)}: {email}")
        try:
            result = verify_email(email)
            with locks[result]:
                result_files[result].write(email + "\n")
        except Exception as e:
            logging.error("Error While Processing Email %s: %s", email, str(e))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(lambda args: process_email(*args), enumerate(email_list))

    for file in result_files.values():
        file.close()

    return {key: file.name for key, file in result_files.items()}

# Handle Uploaded File
async def handle_file(update: Update, context):
    start_time = time.time()

    try:
        # Download File Sent By User
        file = await update.message.document.get_file()

        # Generate unique file name
        sender_name = update.message.from_user.username or update.message.from_user.first_name or "unknown_user"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{sender_name}_{timestamp}.txt"
        file_path = os.path.join(UPLOADS_DIR, file_name)

        # Save file to uploads directory
        await file.download_to_drive(file_path)
        logging.info("File Successfully Saved: %s", file_path)

        # Read File Content
        with open(file_path, "r") as f:
            email_list = f.read().splitlines()

        # Validate Emails With Streaming
        result_files = check_emails_streaming(email_list, max_workers=500)

        # Send Files Back To User
        for category, filepath in result_files.items():
            if os.path.getsize(filepath) > 0:
                with open(filepath, "rb") as file_to_send:
                    await update.message.reply_document(
                        document=file_to_send,
                        filename=f"{category}_emails.txt"
                    )
            else:
                await update.message.reply_text(f"{category}_emails.txt Is Empty And Was Not Sent.")

        # Calculate And Send Processing Time
        elapsed_time = time.time() - start_time
        emails_per_second = len(email_list) / elapsed_time if elapsed_time > 0 else 0

        stats_message = (
            f"Processing Completed In {elapsed_time:.2f} Seconds.\n"
            f"Total Emails: {len(email_list)}\n"
            f"Emails Processed Per Second: {emails_per_second:.2f}"
        )
        await update.message.reply_text(stats_message)

    except Exception as e:
        logging.error("Error While Processing File: %s", str(e))
        await update.message.reply_text("An Error Occurred While Processing The File.")

# Start Command
async def start_command(update: Update, context):
    await update.message.reply_text(
        "Hello! Send Me A .txt File Containing Emails, And I Will Validate Them."
    )

# Main Application
if __name__ == "__main__":
    TOKEN = "7859648875:AAG_fOtVhuLqgbavv-FXzxLychLXniBy2Do"

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), handle_file))

    logging.info("Bot Started...")
    app.run_polling()
