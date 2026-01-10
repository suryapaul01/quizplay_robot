"""
User Statistics Handler
"""
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.constants import ParseMode

from database.models import get_user
from utils.helpers import format_user_stats


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    user = update.effective_user
    
    user_data = await get_user(user.id)
    
    if not user_data:
        await update.message.reply_text(
            "📊 No statistics yet!\n\n"
            "Start creating or playing quizzes to build your stats."
        )
        return
    
    stats_text = format_user_stats(user_data)
    
    await update.message.reply_text(
        stats_text,
        parse_mode=ParseMode.HTML
    )


async def stats_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Stats button from main menu"""
    if update.message.text == "📊 My Stats":
        return await stats_command(update, context)


def get_stats_handlers():
    """Return list of handlers for stats module"""
    return [
        CommandHandler("stats", stats_command),
        MessageHandler(filters.Regex("^📊 My Stats$"), stats_button),
    ]
