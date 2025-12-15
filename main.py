import os
import logging
import threading
import subprocess
import html
import json
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# --- CONFIGURATION ---
TOKEN = os.environ.get("TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789")) # Replace with your numeric Chat ID
PORT = int(os.environ.get("PORT", "10000"))
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", f"http://localhost:{PORT}")

# --- STORAGE ---
# Note: On Render Free Tier, this resets every time the app restarts.
# For permanent storage, you need a Database (PostgreSQL) or Render Disk.
ALLOWED_USERS = {ADMIN_ID}
USER_FILES = "user_files"

if not os.path.exists(USER_FILES):
    os.makedirs(USER_FILES)

# --- FLASK APP (The Web Server) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running. Python + PHP Environment."

@app.route('/host/<int:user_id>/<filename>', methods=['GET', 'POST'])
def run_php_script(user_id, filename):
    """
    Executes the PHP file and returns the output.
    Acts as the 'Private Webhook' receiver.
    """
    # Security: Ensure file belongs to user
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(USER_FILES, str(user_id), safe_filename)

    if not os.path.exists(file_path):
        return "404 Not Found", 404

    # Prepare environment variables for the PHP script (mimic CGI)
    env = os.environ.copy()
    if request.method == 'POST':
        # Pass POST data as an environment variable or via stdin
        input_data = request.get_data(as_text=True)
    else:
        input_data = ""

    try:
        # EXECUTE PHP CODE
        # We run the php file using subprocess
        # Security: Timeout added to prevent infinite loops
        result = subprocess.run(
            ['php', file_path], 
            input=input_data, 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        # Return the stdout of the PHP script
        if result.returncode == 0:
            return result.stdout
        else:
            return f"<pre>PHP Error:\n{result.stderr}</pre>", 500
    except subprocess.TimeoutExpired:
        return "Script timed out (Max 10s)", 504
    except Exception as e:
        return f"Server Error: {str(e)}", 500

def run_flask():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

# --- TELEGRAM BOT LOGIC ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def check_auth(update: Update):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return False
    return True

# 1. Main Menu Keyboard
def get_main_menu():
    keyboard = [
        [
            InlineKeyboardButton("📤 Upload & Run", callback_data='upload'),
            InlineKeyboardButton("📂 My Files", callback_data='files')
        ],
        [
            InlineKeyboardButton("⚙️ Manage Running", callback_data='manage'),
            InlineKeyboardButton("📊 Server Stats", callback_data='stats')
        ],
        [
            InlineKeyboardButton("🆘 Help", callback_data='help')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# 2. Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update): return
    await update.message.reply_text(
        "<b>🤖 PHP Hosting Bot</b>\n\nUpload your <code>.php</code> files and get a live URL immediately.",
        reply_markup=get_main_menu(),
        parse_mode='HTML'
    )

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only Admin can use this
    if update.effective_user.id != ADMIN_ID:
        return
    
    try:
        new_id = int(context.args[0])
        ALLOWED_USERS.add(new_id)
        await update.message.reply_text(f"✅ User {new_id} added to authorized list.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /add <chat_id>")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS: return

    doc = update.message.document
    file_name = doc.file_name

    if not file_name.endswith('.php'):
        await update.message.reply_text("❌ Only .php files are allowed.")
        return

    # Download file
    user_id = update.effective_user.id
    user_dir = os.path.join(USER_FILES, str(user_id))
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    
    file = await context.bot.get_file(doc.file_id)
    save_path = os.path.join(user_dir, file_name)
    await file.download_to_drive(save_path)

    # Generate Link
    web_link = f"{RENDER_URL}/host/{user_id}/{file_name}"
    
    await update.message.reply_text(
        f"✅ <b>File Uploaded!</b>\n\n"
        f"📄 File: <code>{file_name}</code>\n"
        f"🔗 <b>Live URL:</b>\n{web_link}\n\n"
        f"<i>This URL acts as your private webhook.</i>",
        parse_mode='HTML',
        reply_markup=get_main_menu()
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'upload':
        await query.edit_message_text("📤 Please send me a <b>.php</b> file now.", parse_mode='HTML')
    
    elif data == 'files':
        user_id = query.from_user.id
        user_dir = os.path.join(USER_FILES, str(user_id))
        if os.path.exists(user_dir) and os.listdir(user_dir):
            files = os.listdir(user_dir)
            file_list = "\n".join([f"• <code>{f}</code>" for f in files])
            text = f"<b>📂 Your Files:</b>\n\n{file_list}"
        else:
            text = "📂 You have no files uploaded."
        
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_menu())

    elif data == 'stats':
        # Simple stats
        import shutil
        total, used, free = shutil.disk_usage("/")
        text = (
            f"<b>📊 Server Stats</b>\n\n"
            f"💾 Disk Free: {free // (2**20)} MB\n"
            f"🖥️ Platform: Render.com\n"
            f"🐍 Python: {os.sys.version.split()[0]}\n"
            f"🐘 PHP: Enabled"
        )
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_menu())
        
    elif data == 'help':
        text = (
            "<b>🆘 Help Guide</b>\n\n"
            "1. Click 'Upload & Run' or send a .php file.\n"
            "2. Bot gives you a URL.\n"
            "3. Use that URL in your browser or as a Webhook.\n\n"
            "<i>Note: Files are deleted if the server restarts (Free Tier).</i>"
        )
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=get_main_menu())
    
    elif data == 'manage':
        await query.edit_message_text("⚙️ PHP Scripts run on-demand. No background processes to manage.", reply_markup=get_main_menu())

if __name__ == '__main__':
    # Start Flask in a background thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Start Telegram Bot
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_user))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("Bot is running...")
    application.run_polling()
