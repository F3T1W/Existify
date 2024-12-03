import os
import logging
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from email_service import verify_email
from tempfile import NamedTemporaryFile
from concurrent.futures import ThreadPoolExecutor

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    filename="bot.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Concurrent Email Validation
def check_emails_concurrently(email_list, max_workers=50):
    valid_emails = []
    syntax_errors = []
    domain_errors = []
    server_errors = []

    def process_email(index, email):
        print(f"Checking Email {index + 1}/{len(email_list)}: {email}")
        try:
            result = verify_email(email)
            if result == "valid":
                valid_emails.append(email)
            elif result == "syntax":
                syntax_errors.append(email)
            elif result == "domain":
                domain_errors.append(email)
            elif result == "server":
                server_errors.append(email)
        except Exception as e:
            logging.error("Error While Processing Email %s: %s", email, str(e))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(lambda args: process_email(*args), enumerate(email_list))

    return valid_emails, syntax_errors, domain_errors, server_errors

# Handle Uploaded File
async def handle_file(update: Update, context):
    start_time = time.time()

    try:
        file = await update.message.document.get_file()
        temp_file = NamedTemporaryFile(delete=False, suffix=".txt")
        await file.download_to_drive(temp_file.name)
        logging.info("File Successfully Downloaded: %s", temp_file.name)

        with open(temp_file.name, "r") as f:
            email_list = f.read().splitlines()

        valid_emails, syntax_errors, domain_errors, server_errors = check_emails_concurrently(email_list, max_workers=10)

        result_files = {
            "valid_emails.txt": valid_emails,
            "syntax_errors.txt": syntax_errors,
            "domain_errors.txt": domain_errors,
            "server_errors.txt": server_errors,
        }

        for filename, emails in result_files.items():
            temp_file = NamedTemporaryFile(delete=False, suffix=".txt")
            with open(temp_file.name, "w") as f:
                f.write("\n".join(emails))
            temp_file.close()
            result_files[filename] = temp_file.name

        for filename, filepath in result_files.items():
            if os.path.getsize(filepath) > 0:
                with open(filepath, "rb") as file_to_send:
                    await update.message.reply_document(document=file_to_send, filename=filename)
            else:
                await update.message.reply_text(f"{filename} Is Empty And Was Not Sent.")

        elapsed_time = time.time() - start_time
        stats_message = (
            f"Processing Completed In {elapsed_time:.2f} Seconds.\n"
            f"Total Emails: {len(email_list)}\n"
            f"Valid Emails: {len(valid_emails)}\n"
            f"Syntax Errors: {len(syntax_errors)}\n"
            f"Domain Errors: {len(domain_errors)}\n"
            f"Server Errors: {len(server_errors)}"
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
