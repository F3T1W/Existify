import os
import logging
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from tempfile import NamedTemporaryFile
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, current_thread
import asyncio

from aiogram.types import FSInputFile
from email_service import verify_email

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    filename="bot.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Add console handler for real-time output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)

# Get the root logger and add the console handler
logging.getLogger().addHandler(console_handler)

# Initialize bot and dispatcher
BOT_TOKEN = "7859648875:AAG_fOtVhuLqgbavv-FXzxLychLXniBy2Do"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Create uploads directory if it doesn't exist
UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Hybrid Email Validation with Multithreading and Async Processing
async def process_email_group(emails):
    """
    Asynchronously process a group of emails within a thread.
    """
    results = []
    for index, email in enumerate(emails):
        logging.info(f"[Thread {current_thread().name}] Processing email {index + 1}/{len(emails)}: {email}")
        # Call verify_email in a thread to maintain non-blocking behavior
        result = await asyncio.to_thread(verify_email, email)
        results.append((email, result))
    return results

def process_emails_in_thread(emails):
    """
    Run an asyncio event loop within a thread to process emails asynchronously.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(process_email_group(emails))
    loop.close()
    return results

def hybrid_email_validation(email_list, max_workers=500):
    """
    Use multithreading with asyncio to validate emails with error handling and debugging.
    """
    chunk_size = len(email_list) // max_workers + 1
    email_chunks = [email_list[i:i + chunk_size] for i in range(0, len(email_list), chunk_size)]

    results = []
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_emails_in_thread, chunk) for chunk in email_chunks]

            for i, future in enumerate(futures):
                try:
                    logging.info(f"Retrieving result from thread {i + 1}/{len(futures)}")
                    results.extend(future.result(timeout=30))  # Тайм-аут 30 секунд
                except TimeoutError:
                    logging.error(f"Thread {i + 1} timed out.")
                except Exception as e:
                    logging.error(f"Error in thread {i + 1}: {e}", exc_info=True)

    except Exception as e:
        logging.critical(f"Critical error in hybrid_email_validation: {e}", exc_info=True)

    logging.info("All threads completed. Returning results.")
    return results


# Save validation results to files
def save_results_to_files(results):
    """
    Save email validation results to categorized files.
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

    for email, result in results:
        with locks[result]:
            result_files[result].write(email + "\n")

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

        # Hybrid validation: Multithreading + Async
        results = hybrid_email_validation(email_list, max_workers=4)

        # Save results to files
        result_files = save_results_to_files(results)

        # Send result files to user
        for category, filepath in result_files.items():
            if os.path.getsize(filepath) > 0:
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
    import sys

    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
