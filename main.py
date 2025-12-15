from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import os, subprocess

TOKEN = os.getenv("BOT_TOKEN")
BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAIN_KB = ReplyKeyboardMarkup(
    [["Upload & Run", "My Files"],
     ["Manage Running", "Server Stats"],
     ["Help"]],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Use the menu to manage your PHP scripts.",
        reply_markup=MAIN_KB
    )

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "Upload & Run":
        await update.message.reply_text("Send me a .php file as a document.")
    elif txt == "My Files":
        files = os.listdir(UPLOAD_DIR)
        if not files:
            await update.message.reply_text("No files uploaded yet.")
        else:
            await update.message.reply_text("Files:
" + "
".join(files))
    elif txt == "Manage Running":
        await update.message.reply_text("Simple manager: re‑upload to run again. Extend as needed.")
    elif txt == "Server Stats":
        out = subprocess.getoutput("uptime && free -h")
        await update.message.reply_text(f"Server stats:
{out}")
    elif txt == "Help":
        await update.message.reply_text("Use Upload & Run to send a .php file, then I will execute it.")
    else:
        await update.message.reply_text("Use the menu buttons.", reply_markup=MAIN_KB)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.endswith(".php"):
        await update.message.reply_text("Only .php files are allowed.")
        return
    file = await doc.get_file()
    save_path = os.path.join(UPLOAD_DIR, doc.file_name)
    await file.download_to_drive(save_path)

    # run php script
    try:
        result = subprocess.run(
            ["php", save_path],
            capture_output=True,
            text=True,
            timeout=20
        )
        output = result.stdout or result.stderr or "No output."
    except Exception as e:
        output = f"Error running script: {e}"

    await update.message.reply_text(f"Executed {doc.file_name}:
{output[:4000]}")
