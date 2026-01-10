"""
Admin Commands Handler - with Quiz Links, Force Subscribe, Premium, and Advanced Broadcast
"""
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ConversationHandler, filters
)
from telegram.constants import ParseMode, ChatMemberStatus

from config import ADMIN_IDS, States, CATEGORIES, PREMIUM_PRICES
from database.models import (
    get_bot_stats, get_all_users, ban_user, set_admin, get_user,
    get_all_quiz_links_by_category,
    add_force_sub_channel, remove_force_sub_channel, 
    get_force_sub_channels, get_force_sub_count,
    generate_bulk_codes, get_all_unused_codes, get_unused_codes_count,
    add_premium, remove_premium, get_premium_expiry, is_premium_user,
    get_premium_users_count
)
from utils.helpers import format_bot_stats, escape_html, get_category_name


def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    return user_id in ADMIN_IDS


def admin_category_keyboard():
    """Keyboard for selecting category to view quiz links"""
    keyboard = [
        [InlineKeyboardButton("📋 All Categories", callback_data="admincat_all")]
    ]
    for key, value in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(value, callback_data=f"admincat_{key}")])
    keyboard.append([InlineKeyboardButton("« Back", callback_data="admin_back")])
    return InlineKeyboardMarkup(keyboard)


def remove_channel_keyboard(channels: list):
    """Keyboard for removing force sub channels"""
    keyboard = []
    for ch in channels:
        title = ch.get('channel_title', 'Unknown')[:25]
        keyboard.append([
            InlineKeyboardButton(f"❌ {title}", callback_data=f"rmchannel_{ch['channel_id']}")
        ])
    keyboard.append([InlineKeyboardButton("« Back", callback_data="admin_back")])
    return InlineKeyboardMarkup(keyboard)


def confirm_remove_keyboard(channel_id: int):
    """Confirm channel removal"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Remove", callback_data=f"confirmrm_{channel_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="removeforcesub_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin commands - Admin only"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    text = """🔐 <b>Admin Commands:</b>

<b>Bot Management:</b>
/adminstats - View bot statistics
/broadcast - Broadcast message to users
/quizlinks - View all quiz links

<b>Force Subscribe:</b>
/forcesub - Add force sub channel
/removeforcesub - Remove force sub

<b>Premium Management:</b>
/generate - Generate redeem codes
/addpremium - Add premium to user
/removepremium - Remove premium

<b>User Management:</b>
/banuser - Ban a user
/unbanuser - Unban a user
/addadmin - Add new admin"""
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def adminstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics - Admin only"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    stats = await get_bot_stats()
    stats_text = format_bot_stats(stats)
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)


async def quizlinks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get all quiz links by category - Admin only"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    await update.message.reply_text(
        "📋 <b>Quiz Links</b>\n\nSelect a category:",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_category_keyboard()
    )


async def admincat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin category selection for quiz links"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    if not is_admin(user.id):
        await query.edit_message_text("❌ Admin only!")
        return
    
    category = query.data.replace("admincat_", "")
    
    quiz_groups = await get_all_quiz_links_by_category(category if category != "all" else None)
    
    if not quiz_groups:
        await query.edit_message_text(
            f"No quizzes found in this category.",
            reply_markup=admin_category_keyboard()
        )
        return
    
    # Build message with all quiz links
    cat_name = "All Categories" if category == "all" else get_category_name(category)
    text = f"📋 <b>{cat_name}</b>\n\n"
    
    for q in quiz_groups[:30]:  # Limit to 30
        visibility = "🔓" if q.get('is_public') else "🔒"
        text += f"{visibility} <b>{escape_html(q['name'][:25])}</b>\n"
        text += f"   ID: <code>{q['group_id']}</code>\n"
        text += f"   Creator: <code>{q['creator_id']}</code>\n"
        text += f"   Qs: {q.get('total_questions', 0)} | Plays: {q.get('total_plays', 0)}\n\n"
    
    if len(quiz_groups) > 30:
        text += f"\n... and {len(quiz_groups) - 30} more"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=admin_category_keyboard()
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start broadcast - Admin only"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📢 <b>Broadcast Message</b>\n\n"
        "Send the message you want to broadcast to all users.\n"
        "You can send:\n"
        "• Text\n"
        "• Photo with caption\n"
        "• Video with caption\n"
        "• Document\n"
        "• Forward a message\n\n"
        "Send /cancel to cancel.",
        parse_mode=ParseMode.HTML
    )
    return States.BROADCAST_MESSAGE


async def broadcast_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast message and send to all users"""
    user = update.effective_user
    
    if not is_admin(user.id):
        return ConversationHandler.END
    
    # Get all bot users
    users = await get_all_users()
    
    if not users:
        await update.message.reply_text("❌ No users to broadcast to!")
        return ConversationHandler.END
    
    # Send initial status
    status_msg = await update.message.reply_text(
        f"📤 Starting broadcast to {len(users)} users...\n"
        f"Progress: 0/{len(users)}"
    )
    
    success = 0
    failed = 0
    blocked = 0
    
    # Determine message type
    message = update.message
    
    for i, user_data in enumerate(users):
        try:
            if message.text:
                await context.bot.send_message(
                    chat_id=user_data['user_id'],
                    text=message.text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            elif message.photo:
                await context.bot.send_photo(
                    chat_id=user_data['user_id'],
                    photo=message.photo[-1].file_id,
                    caption=message.caption,
                    parse_mode=ParseMode.HTML
                )
            elif message.video:
                await context.bot.send_video(
                    chat_id=user_data['user_id'],
                    video=message.video.file_id,
                    caption=message.caption,
                    parse_mode=ParseMode.HTML
                )
            elif message.document:
                await context.bot.send_document(
                    chat_id=user_data['user_id'],
                    document=message.document.file_id,
                    caption=message.caption,
                    parse_mode=ParseMode.HTML
                )
            elif message.animation:
                await context.bot.send_animation(
                    chat_id=user_data['user_id'],
                    animation=message.animation.file_id,
                    caption=message.caption,
                    parse_mode=ParseMode.HTML
                )
            elif message.sticker:
                await context.bot.send_sticker(
                    chat_id=user_data['user_id'],
                    sticker=message.sticker.file_id
                )
            else:
                # Try to copy the message
                await context.bot.copy_message(
                    chat_id=user_data['user_id'],
                    from_chat_id=message.chat_id,
                    message_id=message.message_id
                )
            
            success += 1
            
        except Exception as e:
            error_str = str(e).lower()
            if 'blocked' in error_str or 'deactivated' in error_str:
                blocked += 1
            else:
                failed += 1
        
        # Update progress every 50 users
        if (i + 1) % 50 == 0:
            try:
                await status_msg.edit_text(
                    f"📤 Broadcasting...\n"
                    f"Progress: {i + 1}/{len(users)}\n"
                    f"✅ Success: {success}\n"
                    f"❌ Failed: {failed}\n"
                    f"🚫 Blocked: {blocked}"
                )
            except Exception:
                pass
        
        # Rate limiting
        await asyncio.sleep(0.05)
    
    # Final status
    await status_msg.edit_text(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"📤 Total: {len(users)}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n"
        f"🚫 Blocked/Deactivated: {blocked}",
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END


async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel broadcast"""
    await update.message.reply_text("❌ Broadcast cancelled.")
    return ConversationHandler.END


async def banuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user - Admin only"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Usage: <code>/banuser USER_ID</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID!")
        return
    
    target_user = await get_user(target_id)
    if not target_user:
        await update.message.reply_text("❌ User not found!")
        return
    
    await ban_user(target_id, ban=True)
    
    await update.message.reply_text(f"✅ User {target_id} banned!")


async def unbanuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user - Admin only"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Usage: <code>/unbanuser USER_ID</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID!")
        return
    
    await ban_user(target_id, ban=False)
    
    await update.message.reply_text(f"✅ User {target_id} unbanned!")


async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new admin - Admin only"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Usage: <code>/addadmin USER_ID</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID!")
        return
    
    target_user = await get_user(target_id)
    if not target_user:
        await update.message.reply_text("❌ User not found! They need to start the bot first.")
        return
    
    await set_admin(target_id, is_admin=True)
    
    await update.message.reply_text(
        f"✅ User {target_id} marked as admin in DB!\n\n"
        f"⚠️ Also add their ID to ADMIN_IDS in .env for full access."
    )


def get_broadcast_handler():
    """Return conversation handler for broadcast"""
    return ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_command)],
        states={
            States.BROADCAST_MESSAGE: [
                MessageHandler(
                    filters.TEXT | filters.PHOTO | filters.VIDEO | 
                    filters.Document.ALL | filters.ANIMATION | filters.Sticker.ALL,
                    broadcast_message_handler
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_broadcast)],
        allow_reentry=True
    )


async def admin_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin action inputs from menu (ban/unban/addadmin)"""
    user = update.effective_user
    
    if not is_admin(user.id):
        return
    
    # Only process if there's a pending admin action
    has_pending = any([
        context.user_data.get('awaiting_ban'),
        context.user_data.get('awaiting_unban'),
        context.user_data.get('awaiting_addadmin'),
        context.user_data.get('awaiting_broadcast')
    ])
    
    if not has_pending:
        return  # Let other handlers process this message
    
    text = update.message.text.strip()
    
    # Handle cancel
    if text == "/cancel":
        context.user_data.pop('awaiting_ban', None)
        context.user_data.pop('awaiting_unban', None)
        context.user_data.pop('awaiting_addadmin', None)
        context.user_data.pop('awaiting_broadcast', None)
        await update.message.reply_text(
            "❌ Cancelled.",
            reply_markup=admin_menu_keyboard() if is_admin(user.id) else None
        )
        return
    
    # Handle broadcast from menu
    if context.user_data.get('awaiting_broadcast'):
        context.user_data.pop('awaiting_broadcast', None)
        # Trigger broadcast
        update.message.text = text  # ensure text is set
        return await broadcast_message_handler(update, context)
    
    # Handle ban user
    if context.user_data.get('awaiting_ban'):
        context.user_data.pop('awaiting_ban', None)
        try:
            target_id = int(text)
            target_user = await get_user(target_id)
            if not target_user:
                await update.message.reply_text("❌ User not found!", reply_markup=back_to_admin_keyboard())
                return
            await ban_user(target_id, ban=True)
            await update.message.reply_text(f"✅ User {target_id} banned!", reply_markup=back_to_admin_keyboard())
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!", reply_markup=back_to_admin_keyboard())
        return
    
    # Handle unban user
    if context.user_data.get('awaiting_unban'):
        context.user_data.pop('awaiting_unban', None)
        try:
            target_id = int(text)
            await ban_user(target_id, ban=False)
            await update.message.reply_text(f"✅ User {target_id} unbanned!")
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!")
        return
    
    # Handle add admin
    if context.user_data.get('awaiting_addadmin'):
        context.user_data.pop('awaiting_addadmin', None)
        try:
            target_id = int(text)
            target_user = await get_user(target_id)
            if not target_user:
                await update.message.reply_text("❌ User not found!")
                return
            await set_admin(target_id, is_admin=True)
            await update.message.reply_text(
                f"✅ User {target_id} marked as admin!\n\n"
                f"⚠️ Also add to ADMIN_IDS in .env"
            )
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!")
        return


# ============= FORCE SUBSCRIBE COMMANDS =============

async def forcesub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start force subscribe setup - Admin only"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    # Check current count
    count = await get_force_sub_count()
    if count >= 4:
        await update.message.reply_text(
            "❌ Maximum 4 force subscribe channels allowed!\n\n"
            "Use /removeforcesub to remove one first."
        )
        return
    
    context.user_data['awaiting_forcesub'] = True
    
    await update.message.reply_text(
        "📢 <b>Add Force Subscribe Channel</b>\n\n"
        f"Currently: {count}/4 channels\n\n"
        "Forward a message from the channel you want to add.\n"
        "⚠️ Bot must be admin of the channel!\n\n"
        "Send /cancel to cancel.",
        parse_mode=ParseMode.HTML
    )


async def forcesub_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle forwarded message for force subscribe"""
    user = update.effective_user
    message = update.message
    
    if not is_admin(user.id):
        return
    
    if not context.user_data.get('awaiting_forcesub'):
        return
    
    context.user_data.pop('awaiting_forcesub', None)
    
    # Try to get channel from forwarded message
    channel_id = None
    channel_title = None
    channel_username = None
    
    # PTB v21 uses forward_origin
    if hasattr(message, 'forward_origin') and message.forward_origin:
        origin = message.forward_origin
        # MessageOriginChannel has sender_chat attribute
        if hasattr(origin, 'chat'):
            chat = origin.chat
            if chat.type == "channel":
                channel_id = chat.id
                channel_title = chat.title
                channel_username = getattr(chat, 'username', None)
            else:
                await update.message.reply_text("❌ Please forward from a channel, not a group!")
                return
        else:
            await update.message.reply_text(
                "❌ Please forward from a channel!\n\n"
                "The message must be from a public or private channel where I'm an admin."
            )
            return
    else:
        await update.message.reply_text("❌ Please forward a message from a channel!")
        return
    
    if not channel_id:
        await update.message.reply_text("❌ Could not detect channel. Please forward from a channel!")
        return
    
    # Check if bot is admin
    try:
        bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
        if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await update.message.reply_text(
                f"❌ I'm not an admin in <b>{escape_html(channel_title)}</b>!\n\n"
                "Please make me admin first.",
                parse_mode=ParseMode.HTML
            )
            return
    except Exception as e:
        await update.message.reply_text(
            f"❌ Could not verify admin status.\n\n"
            f"Make sure I'm an admin in the channel."
        )
        return
    
    # Add to database
    success = await add_force_sub_channel(channel_id, channel_title, channel_username)
    
    if success:
        count = await get_force_sub_count()
        await update.message.reply_text(
            f"✅ <b>Force Subscribe Added!</b>\n\n"
            f"📢 {escape_html(channel_title)}\n"
            f"📊 Total: {count}/4 channels",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "❌ Could not add channel!\n\n"
            "It may already be added or limit reached."
        )


async def removeforcesub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show force sub channels to remove - Admin only"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    channels = await get_force_sub_channels()
    
    if not channels:
        await update.message.reply_text("📢 No force subscribe channels set.")
        return
    
    await update.message.reply_text(
        "📢 <b>Force Subscribe Channels</b>\n\n"
        "Select a channel to remove:",
        parse_mode=ParseMode.HTML,
        reply_markup=remove_channel_keyboard(channels)
    )


async def remove_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel removal selection"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    if not is_admin(user.id):
        await query.edit_message_text("❌ Admin only!")
        return
    
    if query.data == "admin_back":
        await query.message.delete()
        return
    
    if query.data == "removeforcesub_menu":
        channels = await get_force_sub_channels()
        if not channels:
            await query.edit_message_text("📢 No force subscribe channels set.")
            return
        await query.edit_message_text(
            "📢 <b>Force Subscribe Channels</b>\n\n"
            "Select a channel to remove:",
            parse_mode=ParseMode.HTML,
            reply_markup=remove_channel_keyboard(channels)
        )
        return
    
    if query.data.startswith("rmchannel_"):
        channel_id = int(query.data.replace("rmchannel_", ""))
        
        # Get channel info
        channels = await get_force_sub_channels()
        channel = next((c for c in channels if c['channel_id'] == channel_id), None)
        
        if not channel:
            await query.answer("Channel not found!", show_alert=True)
            return
        
        await query.edit_message_text(
            f"⚠️ Remove <b>{escape_html(channel['channel_title'])}</b> from force subscribe?",
            parse_mode=ParseMode.HTML,
            reply_markup=confirm_remove_keyboard(channel_id)
        )
        return
    
    if query.data.startswith("confirmrm_"):
        channel_id = int(query.data.replace("confirmrm_", ""))
        
        success = await remove_force_sub_channel(channel_id)
        
        if success:
            await query.edit_message_text("✅ Channel removed from force subscribe!")
        else:
            await query.edit_message_text("❌ Failed to remove channel.")


# ============= PREMIUM ADMIN COMMANDS =============

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate redeem codes - Admin only
    Usage: /generate <days> <count>
    """
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) < 2:
        # Show help and current unused codes count
        unused_count = await get_unused_codes_count()
        
        text = f"""🎁 <b>Generate Redeem Codes</b>

Usage: <code>/generate &lt;days&gt; &lt;count&gt;</code>

<b>Examples:</b>
<code>/generate 7 5</code> - 5 codes for 7 days
<code>/generate 30 10</code> - 10 codes for 30 days
<code>/generate 365 1</code> - 1 code for 1 year

📊 Unused codes: {unused_count}

<b>Duration Options:</b>
• 7 days (Weekly)
• 30 days (Monthly)
• 365 days (Yearly)"""
        
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return
    
    try:
        days = int(context.args[0])
        count = int(context.args[1])
        
        if days < 1 or days > 365:
            await update.message.reply_text("❌ Days must be between 1 and 365!")
            return
        
        if count < 1 or count > 50:
            await update.message.reply_text("❌ Count must be between 1 and 50!")
            return
        
    except ValueError:
        await update.message.reply_text("❌ Invalid numbers! Usage: /generate <days> <count>")
        return
    
    # Generate codes
    await update.message.reply_text(f"⏳ Generating {count} codes for {days} days...")
    
    codes = await generate_bulk_codes(days, count, user.id)
    
    # Format codes list
    codes_text = "\n".join([f"<code>{code}</code>" for code in codes])
    
    await update.message.reply_text(
        f"✅ <b>Generated {count} Codes ({days} days each)</b>\n\n"
        f"{codes_text}\n\n"
        f"Users can redeem with:\n"
        f"<code>/redeem CODE</code>",
        parse_mode=ParseMode.HTML
    )


async def addpremium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add premium to user - Admin only
    Usage: /addpremium <user_id> <days>
    """
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: <code>/addpremium USER_ID DAYS</code>\n\n"
            "Example: <code>/addpremium 123456789 30</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        target_id = int(context.args[0])
        days = int(context.args[1])
        
        if days < 1 or days > 365:
            await update.message.reply_text("❌ Days must be between 1 and 365!")
            return
        
    except ValueError:
        await update.message.reply_text("❌ Invalid values!")
        return
    
    # Add premium
    new_expiry = await add_premium(target_id, days, "admin")
    
    await update.message.reply_text(
        f"✅ <b>Premium Added!</b>\n\n"
        f"👤 User ID: <code>{target_id}</code>\n"
        f"📅 Days: {days}\n"
        f"⏰ Expires: {new_expiry.strftime('%d %b %Y, %H:%M UTC')}",
        parse_mode=ParseMode.HTML
    )


async def removepremium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove premium from user - Admin only
    Usage: /removepremium <user_id>
    """
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "Usage: <code>/removepremium USER_ID</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID!")
        return
    
    success = await remove_premium(target_id)
    
    if success:
        await update.message.reply_text(f"✅ Premium removed from user {target_id}!")
    else:
        await update.message.reply_text(f"❌ Could not remove premium. User may not have premium.")


def get_admin_handlers():
    """Return list of handlers for admin module"""
    return [
        get_broadcast_handler(),
        CommandHandler("admin", admin_command),
        CommandHandler("adminstats", adminstats_command),
        CommandHandler("quizlinks", quizlinks_command),
        CommandHandler("forcesub", forcesub_command),
        CommandHandler("removeforcesub", removeforcesub_command),
        # Premium management
        CommandHandler("generate", generate_command),
        CommandHandler("addpremium", addpremium_command),
        CommandHandler("removepremium", removepremium_command),
        # User management
        CommandHandler("banuser", banuser_command),
        CommandHandler("unbanuser", unbanuser_command),
        CommandHandler("addadmin", addadmin_command),
        CallbackQueryHandler(admincat_callback, pattern="^admincat_"),
        CallbackQueryHandler(remove_channel_callback, pattern="^rmchannel_|^confirmrm_|^removeforcesub_|^admin_back$"),
        # IMPORTANT: Forwarded handler must come BEFORE TEXT handler
        MessageHandler(filters.ForwardedFrom(chat_id=False) | filters.FORWARDED, forcesub_message_handler),
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_action_handler),
    ]


