"""
Language Handler - /setlang command for private chat
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

from config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from database.models import get_user, update_user_language


def language_keyboard():
    """Create language selection keyboard (2 columns)"""
    keyboard = []
    items = list(SUPPORTED_LANGUAGES.items())
    
    for i in range(0, len(items), 2):
        row = []
        for j in range(2):
            if i + j < len(items):
                code, name = items[i + j]
                row.append(InlineKeyboardButton(name, callback_data=f"setlang_{code}"))
        keyboard.append(row)
    
    return InlineKeyboardMarkup(keyboard)


async def setlang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setlang command in private chat"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Only works in private chat
    if chat.type != "private":
        await update.message.reply_text(
            "❌ Use this command in private chat with the bot!"
        )
        return
    
    # Get current language
    user_data = await get_user(user.id)
    current_lang = user_data.get('language', DEFAULT_LANGUAGE) if user_data else DEFAULT_LANGUAGE
    current_name = SUPPORTED_LANGUAGES.get(current_lang, current_lang)
    
    await update.message.reply_text(
        f"🌐 <b>Language Settings</b>\n\n"
        f"Current: {current_name}\n\n"
        f"Select your preferred language for quizzes:",
        parse_mode=ParseMode.HTML,
        reply_markup=language_keyboard()
    )


async def setlang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang_code = query.data.replace("setlang_", "")
    
    if lang_code not in SUPPORTED_LANGUAGES:
        await query.answer("Invalid language!", show_alert=True)
        return
    
    # Update user language
    await update_user_language(user.id, lang_code)
    
    lang_name = SUPPORTED_LANGUAGES[lang_code]
    
    await query.edit_message_text(
        f"✅ Language set to {lang_name}\n\n"
        f"All quizzes you play will be translated to this language.",
        parse_mode=ParseMode.HTML
    )


def get_language_handlers():
    """Return list of handlers for language module"""
    return [
        CommandHandler("setlang", setlang_command),
        CallbackQueryHandler(setlang_callback, pattern="^setlang_"),
    ]
