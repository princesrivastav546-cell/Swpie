# file: main.py
import os, asyncio
from telegram import Update
from telegram.ext import Application
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
import uvicorn

from bot_code import start, text_router, handle_document, TOKEN  # import from previous snippet

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret-token")
BASE_URL = os.getenv("PUBLIC_URL")  # e.g. https://your-service.onrender.com

async def create_bot() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    return app

telegram_app: Application = None  # global

async def telegram_webhook(request: Request):
    global telegram_app
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return PlainTextResponse("Unauthorized", status_code=401)
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return PlainTextResponse("OK")

async def healthcheck(request: Request):
    return PlainTextResponse("OK")

async def startup():
    global telegram_app
    telegram_app = await create_bot()
    await telegram_app.bot.set_webhook(
        url=f"{BASE_URL}/telegram",
        secret_token=WEBHOOK_SECRET
    )

async def shutdown():
    await telegram_app.shutdown()

starlette_app = Starlette(
    routes=[Route("/telegram", telegram_webhook, methods=["POST"]),
            Route("/healthcheck", healthcheck, methods=["GET"])],
    on_startup=[startup],
    on_shutdown=[shutdown]
)

if __name__ == "__main__":
    uvicorn.run("main:starlette_app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
