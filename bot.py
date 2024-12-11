import os
import logging
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from tempfile import NamedTemporaryFile
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from aiogram.types import InputFile, FSInputFile

from email_service import verify_email

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    filename="bot.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Initialize bot and dispatcher
BOT_TOKEN = "7859648875:AAG_fOtVhuLqgbavv-FXzxLychLXniBy2Do"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Create uploads directory if it doesn't exist
UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Concurrent Email Validation with Streaming to Files
def check_emails_streaming(email_list, max_workers=10000):
    """
    Validate emails concurrently and write results to files immediately.
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
        try:
            # Log the current email being processed
            logging.info("Processing email %d/%d: %s", index + 1, len(email_list), email)

            result = verify_email(email)
            with locks[result]:
                result_files[result].write(email + "\n")
        except Exception as e:
            logging.error("Error processing email %s: %s", email, str(e))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(lambda args: process_email(*args), enumerate(email_list))

    for file in result_files.values():
        file.close()

    return {key: file.name for key, file in result_files.items()}

# Handler for /start command
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Hello! Send me a .txt file containing emails, and I will validate them.")

# Handler for uploaded .txt files
@dp.message(lambda message: message.document and message.document.file_name.endswith(".txt"))
async def handle_file(message: types.Message):
    start_time = time.time()
    try:
        # Download the file
        file = await bot.download(message.document)
        sender_name = message.from_user.username or message.from_user.first_name or "unknown_user"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{sender_name}_{timestamp}.txt"
        file_path = os.path.join(UPLOADS_DIR, file_name)

        # Save file locally
        with open(file_path, "wb") as f:
            f.write(file.read())
        logging.info("File successfully saved: %s", file_path)

        # Read file content
        with open(file_path, "r") as f:
            email_list = f.read().splitlines()

        # Validate emails
        result_files = check_emails_streaming(email_list)

        # Send result files to user
        for category, filepath in result_files.items():
            if os.path.getsize(filepath) > 0:
                # Use FSInputFile to send the file
                file_to_send = FSInputFile(filepath)
                await message.answer_document(file_to_send, caption=f"{category}_emails.txt")
            else:
                await message.answer(f"{category}_emails.txt is empty and was not sent.")

        # Send processing stats
        elapsed_time = time.time() - start_time
        emails_per_second = len(email_list) / elapsed_time if elapsed_time > 0 else 0
        stats_message = (
            f"Processing completed in {elapsed_time:.2f} seconds.\n"
            f"Total emails: {len(email_list)}\n"
            f"Emails processed per second: {emails_per_second:.2f}"
        )
        await message.answer(stats_message)

    except Exception as e:
        logging.error("Error while processing file: %s", str(e))
        await message.answer("An error occurred while processing the file.")


# Error handler
@dp.errors()
async def handle_errors(update: types.Update, exception: Exception):
    logging.error(f"Update {update} caused error {exception}")

# Start polling
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    import sys

    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
