"""
Start and Help Command Handlers - with Force Subscribe check
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode, ChatMemberStatus

from config import MESSAGES, ADMIN_IDS
from database.models import create_user, get_user, get_quiz_group, get_force_sub_channels
from utils.keyboards import main_menu_keyboard
from utils.helpers import escape_html


async def check_force_subscribe(user_id: int, context) -> tuple:
    """
    Check if user is subscribed to all force sub channels
    Returns: (is_subscribed: bool, channels_to_join: list)
    """
    channels = await get_force_sub_channels()
    
    if not channels:
        return True, []
    
    channels_to_join = []
    
    for channel in channels:
        try:
            member = await context.bot.get_chat_member(channel['channel_id'], user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                channels_to_join.append(channel)
        except Exception:
            # If we can't check, skip this channel
            pass
    
    return len(channels_to_join) == 0, channels_to_join


def force_sub_keyboard(channels: list) -> InlineKeyboardMarkup:
    """Create keyboard with channel join links"""
    keyboard = []
    
    for channel in channels:
        username = channel.get('channel_username')
        title = channel.get('channel_title', 'Channel')
        
        if username:
            keyboard.append([
                InlineKeyboardButton(f"📢 Join {title[:20]}", url=f"https://t.me/{username}")
            ])
        else:
            keyboard.append([
                InlineKeyboardButton(f"📢 {title[:25]}", url=f"https://t.me/c/{str(channel['channel_id'])[4:]}")
            ])
    
    keyboard.append([InlineKeyboardButton("✅ I've Joined", callback_data="check_forcesub")])
    
    return InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    # Create/update user in database (is_bot_user=True since they started bot in private)
    await create_user(user.id, user.username, user.first_name, is_bot_user=True)
    
    # Check force subscribe
    is_subscribed, channels_to_join = await check_force_subscribe(user.id, context)
    
    if not is_subscribed:
        await update.message.reply_text(
            "📢 <b>Please join our channel(s) to use this bot!</b>\n\n"
            "Click the buttons below to join, then click 'I've Joined':",
            parse_mode=ParseMode.HTML,
            reply_markup=force_sub_keyboard(channels_to_join)
        )
        return
    
    # Check for deep link (Quiz Group ID)
    if context.args and len(context.args) > 0:
        group_id = context.args[0]
        if group_id.startswith("QG_"):
            # User clicked a quiz group share link
            quiz_group = await get_quiz_group(group_id)
            if quiz_group:
                await update.message.reply_text(
                    f"🎯 You found: <b>{escape_html(quiz_group['name'])}</b>\n\n"
                    f"{escape_html(quiz_group.get('description', ''))}\n\n"
                    f"Add me to a group and use:\n"
                    f"<code>/startquiz {group_id}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=main_menu_keyboard()
                )
                return
    
    # Regular start
    await update.message.reply_text(
        MESSAGES["welcome"],
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard()
    )


async def check_forcesub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 'I've Joined' button click"""
    query = update.callback_query
    user = query.from_user
    
    is_subscribed, channels_to_join = await check_force_subscribe(user.id, context)
    
    if not is_subscribed:
        await query.answer("❌ You haven't joined all channels yet!", show_alert=True)
        return
    
    await query.answer("✅ Welcome!")
    
    await query.edit_message_text(
        MESSAGES["welcome"],
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Send main menu
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Choose an option:",
        reply_markup=main_menu_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    await update.message.reply_text(
        MESSAGES["help"],
        parse_mode=ParseMode.MARKDOWN
    )


async def help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Help button from main menu"""
    if update.message.text == "❓ Help":
        await help_command(update, context)


def get_start_handlers():
    """Return list of handlers for start module"""
    return [
        CommandHandler("start", start_command),
        CommandHandler("help", help_command),
        CallbackQueryHandler(check_forcesub_callback, pattern="^check_forcesub$"),
        MessageHandler(filters.Regex("^❓ Help$"), help_button),
    ]
