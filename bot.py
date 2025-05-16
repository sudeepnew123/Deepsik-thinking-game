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

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Game storage
games = {}
leaderboard = defaultdict(int)

# /start command
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "🎲 Word Guess Bot me aapka swagat hai!\n\n"
        "Naya game shuru karne ke liye /startgame command use karo\n"
        "Saare commands dekhne ke liye /help"
    )

# /help command
async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "📜 Commands:\n"
        "/start - Bot start karo\n"
        "/help - Commands list\n"
        "/startgame - Naya game shuru karo\n"
        "/hint <text> - Hint do (hinter only in group)\n"
        "Group me guess direct message se karo\n"
        "Private chat me word set karo"
    )

# Start new game
async def start_game(update: Update, context: CallbackContext) -> None:
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("⚠️ Yeh command sirf group me kaam karti hai.")
        return

    chat_id = chat.id
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
    await update.message.reply_text("📩 Word set karne ke liye aapko private chat me message bhejna hoga.")

# Set secret word in private chat
async def set_word(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    private_chat = update.effective_chat.type == "private"

    for chat_id, game in games.items():
        if game['hinter'] == user.id and game['word'] is None and private_chat:
            game['word'] = update.message.text.lower()
            await update.message.reply_text(
                "✅ Word set ho gaya! Ab group me hints de sakte ho\n\n"
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

# Give hint in group
async def give_hint(update: Update, context: CallbackContext) -> None:
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private" or games.get(chat.id, {}).get('hinter') != user.id:
        await update.message.reply_text("⚠️ Sirf word set karne wala hi hint de sakta hai, aur wo bhi group me.")
        return

    hint = ' '.join(context.args)
    if not hint:
        await update.message.reply_text("⚠️ Hint ke saath command use karo\nExample: /hint Ye ek fruit hai")
        return

    games[chat.id]['hints'].append(hint)
    await update.message.reply_text(f"🔔 Naya hint: {hint}")

# Handle guesses
async def handle_guess(update: Update, context: CallbackContext) -> None:
    chat = update.effective_chat
    user = update.effective_user
    guess = update.message.text.lower()

    if chat.id not in games or user.id in games[chat.id]['guessed']:
        return

    game = games[chat.id]
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
            await end_game(chat.id, context)
    else:
        await update.message.reply_text("❌ Galat guess! Phir try karo")

# End game
async def end_game(chat_id: int, context: CallbackContext) -> None:
    game = games.get(chat_id)
    if not game:
        return

    word = game['word']
    attempts = game['attempts']
    hints_used = len(game['hints'])

    del games[chat_id]
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🏁 Game khatam! Sahi word tha: {word}\n\n"
             f"Total attempts: {attempts}\n"
             f"Total hints used: {hints_used}"
    )

# Handle inline buttons
async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "request_hint":
        if chat_id in games and games[chat_id]['hints']:
            hint = games[chat_id]['hints'][-1]
            await query.edit_message_text(
                text=f"🔍 Last hint: {hint}\n\n{query.message.text}",
                reply_markup=query.message.reply_markup
            )
    elif query.data == "show_leaderboard":
        leaders = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:10]
        leader_text = ""
        for i, (user_id, score) in enumerate(leaders):
            try:
                user = await context.bot.get_chat(user_id)
                leader_text += f"{i+1}. {user.first_name}: {score}\n"
            except:
                leader_text += f"{i+1}. Unknown: {score}\n"

        await query.edit_message_text(
            text=f"🏆 Top 10 Players:\n\n{leader_text}",
            reply_markup=query.message.reply_markup
        )

# Main function
def main() -> None:
    application = Application.builder().token(TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("startgame", start_game))
    application.add_handler(CommandHandler("hint", give_hint))

    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Group(), handle_guess))
    application.add_handler(MessageHandler(filters.TEXT & filters.PRIVATE, set_word))

    # CallbackQuery handlers
    application.add_handler(CallbackQueryHandler(button_handler))

    # Webhook or polling
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
