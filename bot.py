import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler
)
from dotenv import load_dotenv
from collections import defaultdict

# Environment variables load karo
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Logging setup karo
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Game data
games = {}
leaderboard = defaultdict(int)

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "🎲 Word Guess Bot me aapka swagat hai!\n\n"
        "Naya game shuru karne ke liye /startgame command use karo"
    )

async def start_game(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    if chat_id in games:
        await update.message.reply_text("⚠️ Ek game already chal raha hai!")
        return

    user = update.effective_user
    games[chat_id] = {
        'word': None,
        'hinter': user.id,
        'hints': [],
        'guessed': [],
        'attempts': 0
    }

    await context.bot.send_message(
        chat_id=user.id,
        text="🔐 Private chat me game ka word bhejo (sirf aapko dikhega)"
    )

async def set_word(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    private_chat = update.effective_chat.type == "private"

    for chat_id, game in games.items():
        if game['hinter'] == user.id and game['word'] is None and private_chat:
            game['word'] = update.message.text.lower()
            await update.message.reply_text(
                "✅ Word set ho gaya! Ab group me hints de sakte ho\n"
                "Hint dene ke liye: /hint [apna hint]"
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🎮 Naya game shuru! {user.first_name} ne word choose kiya hai\n\n"
                     f"Guess karne ke liye niche buttons use karo 👇",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💡 Hint maango", callback_data="request_hint"),
                    InlineKeyboardButton("🏆 Leaderboard", callback_data="show_leaderboard")
                ]])
            )

async def give_hint(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in games or games[chat_id]['hinter'] != user.id:
        return

    hint = ' '.join(context.args)
    if not hint:
        await update.message.reply_text("⚠️ Hint ke saath command use karo\nExample: /hint Ye ek fruit hai")
        return

    games[chat_id]['hints'].append(hint)
    await update.message.reply_text(f"🔔 Naya hint: {hint}")

async def handle_guess(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    user = update.effective_user
    guess = update.message.text.lower()

    if chat_id not in games or user.id in games[chat_id]['guessed']:
        return

    game = games[chat_id]
    game['attempts'] += 1

    if guess == game['word']:
        points = max(10 - len(game['hints']), 1)
        leaderboard[user.id] += points
        game['guessed'].append(user.id)

        await update.message.reply_text(
            f"🎉 Sahi jawab! {user.mention_markdown()} ne sahi guess kiya!\n"
            f"🏅 Aapko mile {points} points!",
            parse_mode="Markdown"
        )

        if len(game['guessed']) == 1:
            await end_game(chat_id, context)
    else:
        await update.message.reply_text("❌ Galat guess! Phir try karo")

async def end_game(chat_id: int, context: CallbackContext) -> None:
    game = games.pop(chat_id, None)
    if not game:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ Game already khatam ho chuka ya nahi mila.")
        return

    word = game['word']
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🏁 Game khatam! Sahi word tha: {word}\n\n"
             f"Total attempts: {game['attempts']}\n"
             f"Total hints used: {len(game['hints'])}"
    )

async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "request_hint":
        chat_id = query.message.chat_id
        if chat_id in games and games[chat_id]['hints']:
            hint = games[chat_id]['hints'][-1]
            await query.edit_message_text(
                text=f"🔍 Last hint: {hint}\n\n{query.message.text}",
                reply_markup=query.message.reply_markup
            )
    elif query.data == "show_leaderboard":
        leaders = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:10]
        lines = []
        for i, (uid, score) in enumerate(leaders):
            try:
                user = await context.bot.get_chat(uid)
                name = user.first_name
            except:
                name = "Unknown"
            lines.append(f"{i+1}. {name}: {score}")
        await query.edit_message_text(
            text="🏆 Top 10 Players:\n\n" + "\n".join(lines),
            reply_markup=query.message.reply_markup
        )

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("startgame", start_game))
    application.add_handler(CommandHandler("hint", give_hint))
    application.add_handler(MessageHandler(filters.TEXT & filters.PRIVATE, set_word))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))
    application.add_handler(CallbackQueryHandler(button_handler))

    if os.getenv("RENDER"):
        PORT = int(os.environ.get("PORT", 8443))
        WEBHOOK_URL = f"https://deepsik-thinking-game.onrender.com/{TOKEN}"
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=WEBHOOK_URL
        )
    else:
        application.run_polling()

if __name__ == "__main__":
    main()
