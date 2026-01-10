"""
My Quizzes Handler - View and manage user's Quizzes with pagination
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode

from config import QUIZZES_PER_PAGE, MAX_QUIZZES_DISPLAY
from database.models import (
    get_user_quiz_groups, get_quiz_group, get_group_questions,
    delete_quiz_group, update_quiz_group, delete_question
)
from utils.keyboards import main_menu_keyboard
from utils.helpers import get_category_name, escape_html


def quiz_list_keyboard(quizzes: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Generate keyboard for quiz list with pagination"""
    keyboard = []
    
    for quiz in quizzes:
        visibility = "🔓" if quiz.get('is_public') else "🔒"
        keyboard.append([
            InlineKeyboardButton(
                f"{visibility} {quiz['name'][:30]} ({quiz.get('total_questions', 0)} Qs)",
                callback_data=f"viewq_{quiz['group_id']}"
            )
        ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("« Prev", callback_data=f"qpage_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next »", callback_data=f"qpage_{page + 1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    return InlineKeyboardMarkup(keyboard)


def quiz_detail_keyboard(group_id: str) -> InlineKeyboardMarkup:
    """Keyboard for quiz detail view"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Stats", callback_data=f"qstats_{group_id}"),
            InlineKeyboardButton("🔗 Share", callback_data=f"qshare_{group_id}")
        ],
        [
            InlineKeyboardButton("➕ Add Questions", callback_data=f"qadd_{group_id}"),
            InlineKeyboardButton("📝 View Questions", callback_data=f"qview_{group_id}")
        ],
        [
            InlineKeyboardButton("✏️ Edit", callback_data=f"qedit_{group_id}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"qdel_{group_id}")
        ],
        [InlineKeyboardButton("« Back to List", callback_data="qpage_0")]
    ]
    return InlineKeyboardMarkup(keyboard)


def confirm_delete_keyboard(group_id: str) -> InlineKeyboardMarkup:
    """Confirm deletion keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f"qconfirm_{group_id}"),
            InlineKeyboardButton("❌ No, Keep", callback_data=f"viewq_{group_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def myquizzes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /myquizzes command"""
    user = update.effective_user
    page = 0
    
    quiz_groups = await get_user_quiz_groups(user.id, skip=0, limit=MAX_QUIZZES_DISPLAY)
    
    if not quiz_groups:
        await update.message.reply_text(
            "📚 You haven't created any quizzes yet!\n\n"
            "Use /create to make your first one.",
            reply_markup=main_menu_keyboard()
        )
        return
    
    total = len(quiz_groups)
    total_pages = (total + QUIZZES_PER_PAGE - 1) // QUIZZES_PER_PAGE
    
    # Get quizzes for current page
    start = page * QUIZZES_PER_PAGE
    end = start + QUIZZES_PER_PAGE
    page_quizzes = quiz_groups[start:end]
    
    text = f"📚 <b>Your Quizzes</b> ({total} total)\n\n"
    text += "Select a quiz to view details:"
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=quiz_list_keyboard(page_quizzes, page, total_pages)
    )


async def myquizzes_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle My Quizzes button from main menu"""
    if update.message.text == "📚 My Quizzes":
        return await myquizzes_command(update, context)


async def quiz_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pagination"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "noop":
        return
    
    user = update.effective_user
    page = int(query.data.replace("qpage_", ""))
    
    quiz_groups = await get_user_quiz_groups(user.id, skip=0, limit=MAX_QUIZZES_DISPLAY)
    
    if not quiz_groups:
        await query.edit_message_text("📚 You haven't created any quizzes yet!")
        return
    
    total = len(quiz_groups)
    total_pages = (total + QUIZZES_PER_PAGE - 1) // QUIZZES_PER_PAGE
    
    start = page * QUIZZES_PER_PAGE
    end = start + QUIZZES_PER_PAGE
    page_quizzes = quiz_groups[start:end]
    
    text = f"📚 <b>Your Quizzes</b> ({total} total)\n\n"
    text += "Select a quiz to view details:"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=quiz_list_keyboard(page_quizzes, page, total_pages)
    )


async def view_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View quiz details"""
    query = update.callback_query
    await query.answer()
    
    group_id = query.data.replace("viewq_", "")
    user = update.effective_user
    
    quiz_group = await get_quiz_group(group_id)
    if not quiz_group:
        await query.edit_message_text("❌ Quiz not found!")
        return
    
    if quiz_group['creator_id'] != user.id:
        await query.edit_message_text("❌ You don't own this quiz!")
        return
    
    category = get_category_name(quiz_group.get('category', 'other'))
    visibility = "✅ Public" if quiz_group.get('is_public') else "🔒 Private"
    extra = "⚡ Speed Bonus" if quiz_group.get('extra_points', True) else "📝 No Speed Bonus"
    
    text = f"📚 <b>{escape_html(quiz_group['name'])}</b>\n\n"
    text += f"📝 {escape_html(quiz_group.get('description', 'No description'))}\n\n"
    text += f"{category}\n"
    text += f"{visibility}\n"
    text += f"{extra}\n"
    text += f"❓ Questions: {quiz_group.get('total_questions', 0)}\n"
    text += f"🎮 Plays: {quiz_group.get('total_plays', 0)}\n"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=quiz_detail_keyboard(group_id)
    )


async def quiz_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show quiz statistics"""
    query = update.callback_query
    await query.answer()
    
    group_id = query.data.replace("qstats_", "")
    quiz_group = await get_quiz_group(group_id)
    
    if not quiz_group:
        await query.answer("Quiz not found!", show_alert=True)
        return
    
    text = f"📊 <b>Stats for {escape_html(quiz_group['name'])}</b>\n\n"
    text += f"❓ Total Questions: {quiz_group.get('total_questions', 0)}\n"
    text += f"🎮 Total Plays: {quiz_group.get('total_plays', 0)}\n"
    text += f"📅 Created: {quiz_group.get('created_at', 'Unknown')}\n"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=quiz_detail_keyboard(group_id)
    )


async def quiz_share_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show share link"""
    query = update.callback_query
    await query.answer()
    
    group_id = query.data.replace("qshare_", "")
    quiz_group = await get_quiz_group(group_id)
    
    if not quiz_group:
        await query.answer("Quiz not found!", show_alert=True)
        return
    
    text = f"🔗 <b>Share Link</b>\n\n"
    text += f"<code>t.me/{context.bot.username}?start={group_id}</code>\n\n"
    text += f"Or use in groups:\n<code>/startquiz {group_id}</code>"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=quiz_detail_keyboard(group_id)
    )


async def quiz_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm quiz deletion"""
    query = update.callback_query
    await query.answer()
    
    group_id = query.data.replace("qdel_", "")
    quiz_group = await get_quiz_group(group_id)
    
    if not quiz_group:
        await query.answer("Quiz not found!", show_alert=True)
        return
    
    await query.edit_message_text(
        f"⚠️ <b>Delete Quiz?</b>\n\n"
        f"Are you sure you want to delete <b>{escape_html(quiz_group['name'])}</b>?\n\n"
        f"This will delete all {quiz_group.get('total_questions', 0)} questions!",
        parse_mode=ParseMode.HTML,
        reply_markup=confirm_delete_keyboard(group_id)
    )


async def quiz_confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute quiz deletion"""
    query = update.callback_query
    await query.answer()
    
    group_id = query.data.replace("qconfirm_", "")
    user = update.effective_user
    
    quiz_group = await get_quiz_group(group_id)
    if not quiz_group or quiz_group['creator_id'] != user.id:
        await query.edit_message_text("❌ Could not delete quiz!")
        return
    
    await delete_quiz_group(group_id)
    
    await query.edit_message_text(
        f"✅ Quiz deleted successfully!",
        parse_mode=ParseMode.HTML
    )


async def quiz_view_questions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View questions in quiz"""
    query = update.callback_query
    await query.answer()
    
    group_id = query.data.replace("qview_", "")
    
    questions = await get_group_questions(group_id)
    
    if not questions:
        await query.answer("No questions in this quiz!", show_alert=True)
        return
    
    text = f"❓ <b>Questions</b> ({len(questions)} total)\n\n"
    
    for i, q in enumerate(questions[:10], 1):  # Show first 10
        text += f"{i}. {escape_html(q['question_text'][:50])}...\n"
    
    if len(questions) > 10:
        text += f"\n... and {len(questions) - 10} more"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=quiz_detail_keyboard(group_id)
    )


async def quiz_add_questions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt to add more questions"""
    query = update.callback_query
    await query.answer()
    
    group_id = query.data.replace("qadd_", "")
    context.user_data['adding_to_quiz'] = group_id
    
    await query.edit_message_text(
        "➕ <b>Add Questions</b>\n\n"
        "Send questions in this format:\n\n"
        "<code>Question text?\n"
        "Option A ✅\n"
        "Option B\n"
        "Option C\n"
        "Option D</code>\n\n"
        "Send /done when finished.",
        parse_mode=ParseMode.HTML
    )


async def add_questions_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle adding questions to existing quiz"""
    group_id = context.user_data.get('adding_to_quiz')
    if not group_id:
        return
    
    text = update.message.text.strip()
    
    from utils.quiz_parser import parse_bulk_questions
    questions, errors = parse_bulk_questions(text)
    
    if not questions:
        await update.message.reply_text(
            "❌ Could not parse questions. Try again or /done to finish."
        )
        return
    
    # Add questions
    from database.models import add_questions_bulk
    questions_to_add = []
    for q in questions:
        questions_to_add.append({
            "question_text": q['question_text'],
            "options": q['options'],
            "correct_index": q['correct_index'],
            "question_type": q['question_type']
        })
    
    added = await add_questions_bulk(group_id, questions_to_add)
    
    await update.message.reply_text(
        f"✅ Added {added} question(s)!\n\n"
        f"Send more or /done to finish."
    )


async def done_adding_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish adding questions"""
    group_id = context.user_data.pop('adding_to_quiz', None)
    
    if group_id:
        quiz = await get_quiz_group(group_id)
        await update.message.reply_text(
            f"✅ Done! Quiz now has {quiz.get('total_questions', 0)} questions.",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text("Nothing to finish.")


async def quiz_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show edit options"""
    query = update.callback_query
    await query.answer()
    
    group_id = query.data.replace("qedit_", "")
    
    keyboard = [
        [InlineKeyboardButton("📝 Edit Name", callback_data=f"editname_{group_id}")],
        [InlineKeyboardButton("📄 Edit Description", callback_data=f"editdesc_{group_id}")],
        [InlineKeyboardButton("🔒 Toggle Visibility", callback_data=f"editvis_{group_id}")],
        [InlineKeyboardButton("⚡ Toggle Extra Points", callback_data=f"editextra_{group_id}")],
        [InlineKeyboardButton("« Back", callback_data=f"viewq_{group_id}")]
    ]
    
    await query.edit_message_text(
        "✏️ <b>Edit Quiz</b>\n\nSelect what to edit:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def toggle_visibility_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle quiz visibility"""
    query = update.callback_query
    
    group_id = query.data.replace("editvis_", "")
    quiz = await get_quiz_group(group_id)
    
    if not quiz:
        await query.answer("Quiz not found!", show_alert=True)
        return
    
    new_visibility = not quiz.get('is_public', True)
    await update_quiz_group(group_id, is_public=new_visibility)
    
    status = "Public" if new_visibility else "Private"
    await query.answer(f"Visibility changed to {status}!", show_alert=True)
    
    # Refresh view
    await view_quiz_callback.__wrapped__(update, context)


async def toggle_extra_points_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle extra points"""
    query = update.callback_query
    
    group_id = query.data.replace("editextra_", "")
    quiz = await get_quiz_group(group_id)
    
    if not quiz:
        await query.answer("Quiz not found!", show_alert=True)
        return
    
    new_extra = not quiz.get('extra_points', True)
    await update_quiz_group(group_id, extra_points=new_extra)
    
    status = "Enabled" if new_extra else "Disabled"
    await query.answer(f"Extra points {status}!", show_alert=True)


def get_myquizzes_handlers():
    """Return list of handlers for myquizzes module"""
    return [
        CommandHandler("myquizzes", myquizzes_command),
        CommandHandler("done", done_adding_command),
        MessageHandler(filters.Regex("^📚 My Quizzes$"), myquizzes_button),
        CallbackQueryHandler(quiz_page_callback, pattern="^qpage_|^noop$"),
        CallbackQueryHandler(view_quiz_callback, pattern="^viewq_"),
        CallbackQueryHandler(quiz_stats_callback, pattern="^qstats_"),
        CallbackQueryHandler(quiz_share_callback, pattern="^qshare_"),
        CallbackQueryHandler(quiz_delete_callback, pattern="^qdel_"),
        CallbackQueryHandler(quiz_confirm_delete_callback, pattern="^qconfirm_"),
        CallbackQueryHandler(quiz_view_questions_callback, pattern="^qview_"),
        CallbackQueryHandler(quiz_add_questions_callback, pattern="^qadd_"),
        CallbackQueryHandler(quiz_edit_callback, pattern="^qedit_"),
        CallbackQueryHandler(toggle_visibility_callback, pattern="^editvis_"),
        CallbackQueryHandler(toggle_extra_points_callback, pattern="^editextra_"),
    ]
