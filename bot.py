import os
import logging
import time
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

# Concurrent Email Validation with Streaming to Files
def check_emails_streaming(email_list, max_workers=10000):
    """
    Validate Emails Concurrently And Write Results To Files Immediately.
    """
    # Prepare File Locks For Thread-Safe Writing
    locks = {
        "valid": Lock(),
        "syntax": Lock(),
        "domain": Lock(),
        "server": Lock(),
    }

    # Create Temporary Files For Results
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
            # Write To The Appropriate File
            with locks[result]:
                result_files[result].write(email + "\n")
        except Exception as e:
            logging.error("Error While Processing Email %s: %s", email, str(e))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(lambda args: process_email(*args), enumerate(email_list))

    # Close All Files
    for file in result_files.values():
        file.close()

    return {key: file.name for key, file in result_files.items()}

# Handle Uploaded File
async def handle_file(update: Update, context):
    start_time = time.time()

    try:
        # Download File Sent By User
        file = await update.message.document.get_file()
        temp_file = NamedTemporaryFile(delete=False, suffix=".txt")
        await file.download_to_drive(temp_file.name)
        logging.info("File Successfully Downloaded: %s", temp_file.name)

        # Read File Content
        with open(temp_file.name, "r") as f:
            email_list = f.read().splitlines()

        # Validate Emails With Streaming
        validation_start_time = time.time()
        result_files = check_emails_streaming(email_list, max_workers=500)
        validation_end_time = time.time()
        validation_time = validation_end_time - validation_start_time

        # Send Files Back To User
        file_start_time = time.time()
        for category, filepath in result_files.items():
            if os.path.getsize(filepath) > 0:
                with open(filepath, "rb") as file_to_send:
                    await update.message.reply_document(
                        document=file_to_send,
                        filename=f"{category}_emails.txt"
                    )
            else:
                await update.message.reply_text(f"{category}_emails.txt Is Empty And Was Not Sent.")
        file_end_time = time.time()
        file_handling_time = file_end_time - file_start_time

        # Calculate And Send Processing Time
        elapsed_time = time.time() - start_time
        emails_per_second = len(email_list) / elapsed_time if elapsed_time > 0 else 0

        stats_message = (
            f"Processing Completed In {elapsed_time:.2f} Seconds.\n"
            f"Total Emails: {len(email_list)}\n"
            f"Emails Processed Per Second: {emails_per_second:.2f}\n"
            f"Validation Time: {validation_time:.2f} Seconds\n"
            f"File Handling Time: {file_handling_time:.2f} Seconds"
        )

        # Log file handling and validation times
        logging.info(f"Validation Time: {validation_time:.2f} seconds.")
        logging.info(f"File Handling Time: {file_handling_time:.2f} seconds.")

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
