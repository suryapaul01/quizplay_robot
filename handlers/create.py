"""
Simplified Quiz Creation Flow Handler - with Premium Limits
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ConversationHandler, filters
)
from telegram.constants import ParseMode

from config import States, CATEGORIES, FREE_MAX_QUIZZES, FREE_MAX_QUESTIONS, PREMIUM_MAX_QUESTIONS
from database.models import (
    create_quiz_group, add_questions_bulk, get_quiz_group, update_quiz_group,
    is_premium_user, get_user_quiz_count
)
from utils.keyboards import (
    category_keyboard, visibility_keyboard, main_menu_keyboard
)
from utils.quiz_parser import parse_bulk_questions
from utils.helpers import get_category_name, escape_html


# States for quiz creation
QUIZ_NAME = 1
QUIZ_DESCRIPTION = 2
QUIZ_CATEGORY = 3
QUIZ_EXTRA_POINTS = 4
QUIZ_VISIBILITY = 5
QUIZ_QUESTIONS = 6
QUIZ_ADD_MORE = 7


def extra_points_keyboard(is_premium: bool = False):
    """Extra points selection keyboard"""
    if is_premium:
        keyboard = [
            [InlineKeyboardButton("⚡ Yes - Speed Bonus Enabled", callback_data="extra_yes")],
            [InlineKeyboardButton("📝 No - Only Correct Answer Points", callback_data="extra_no")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]
    else:
        # Free users can only choose No (show upgrade prompt)
        keyboard = [
            [InlineKeyboardButton("📝 No Speed Bonus (Free Plan)", callback_data="extra_no")],
            [InlineKeyboardButton("💎 Upgrade to Premium", callback_data="show_premium")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]
    return InlineKeyboardMarkup(keyboard)


def add_more_keyboard():
    """Add more questions keyboard"""
    keyboard = [
        [InlineKeyboardButton("➕ Add More Questions", callback_data="add_more")],
        [InlineKeyboardButton("✅ Done - Create Quiz", callback_data="done_creating")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def create_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the simplified quiz creation flow"""
    user = update.effective_user
    
    # Check premium status
    is_premium = await is_premium_user(user.id)
    quiz_count = await get_user_quiz_count(user.id)
    
    # Free user limit check
    if not is_premium and quiz_count >= FREE_MAX_QUIZZES:
        await update.message.reply_text(
            f"❌ <b>Quiz Limit Reached!</b>\n\n"
            f"Free users can create up to {FREE_MAX_QUIZZES} quizzes.\n"
            f"You have: {quiz_count}/{FREE_MAX_QUIZZES}\n\n"
            f"💎 Upgrade to Premium for unlimited quizzes!\n"
            f"Use /premium to view plans.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    # Store premium status for later use
    context.user_data['is_premium'] = is_premium
    
    max_q = PREMIUM_MAX_QUESTIONS if is_premium else FREE_MAX_QUESTIONS
    
    await update.message.reply_text(
        f"📝 <b>Create a New Quiz</b>\n\n"
        f"📊 Your quizzes: {quiz_count}/{FREE_MAX_QUIZZES if not is_premium else '∞'}\n"
        f"❓ Max questions: {max_q}\n\n"
        f"Enter a name for your quiz:\n"
        f"<i>Example: 'Ultimate Cricket Quiz' or 'Bollywood Trivia'</i>",
        parse_mode=ParseMode.HTML
    )
    return QUIZ_NAME


async def create_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Create Quiz button from main menu"""
    if update.message.text == "📝 Create Quiz":
        return await create_command(update, context)


async def quiz_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quiz name input"""
    name = update.message.text.strip()
    
    if len(name) < 3:
        await update.message.reply_text("❌ Name too short! Please enter at least 3 characters.")
        return QUIZ_NAME
    
    if len(name) > 100:
        await update.message.reply_text("❌ Name too long! Maximum 100 characters.")
        return QUIZ_NAME
    
    context.user_data['quiz'] = {'name': name, 'questions': []}
    
    await update.message.reply_text(
        f"✅ <b>{escape_html(name)}</b>\n\n"
        "Now add a description for your quiz:\n"
        "<i>(What's this quiz about?)</i>",
        parse_mode=ParseMode.HTML
    )
    return QUIZ_DESCRIPTION


async def quiz_description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quiz description input"""
    description = update.message.text.strip()
    
    if len(description) > 500:
        await update.message.reply_text("❌ Description too long! Maximum 500 characters.")
        return QUIZ_DESCRIPTION
    
    context.user_data['quiz']['description'] = description
    
    await update.message.reply_text(
        "📂 Choose a category for your quiz:",
        reply_markup=category_keyboard()
    )
    return QUIZ_CATEGORY


async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle category selection"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("❌ Quiz creation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END
    
    category = query.data.replace("cat_", "")
    context.user_data['quiz']['category'] = category
    
    is_premium = context.user_data.get('is_premium', False)
    
    await query.edit_message_text(
        f"📂 Category: {get_category_name(category)}\n\n"
        "⚡ <b>Extra Points for Speed?</b>\n\n"
        "Choose whether fast answers get bonus points:",
        parse_mode=ParseMode.HTML,
        reply_markup=extra_points_keyboard(is_premium)
    )
    return QUIZ_EXTRA_POINTS


async def extra_points_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle extra points selection"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("❌ Quiz creation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END
    
    if query.data == "show_premium":
        await query.edit_message_text(
            "💎 <b>Premium Features</b>\n\n"
            "Upgrade to enable:\n"
            "• ⚡ Speed Bonus scoring\n"
            "• Unlimited quizzes\n"
            "• Up to 100 questions\n\n"
            "Use /premium to view plans!",
            parse_mode=ParseMode.HTML
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    extra_points = query.data == "extra_yes"
    context.user_data['quiz']['extra_points'] = extra_points
    
    points_text = "⚡ Speed Bonus: Enabled" if extra_points else "📝 Speed Bonus: Disabled"
    
    await query.edit_message_text(
        f"{points_text}\n\n"
        "🔒 Choose visibility for your quiz:",
        reply_markup=visibility_keyboard()
    )
    return QUIZ_VISIBILITY


async def visibility_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle visibility selection"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("❌ Quiz creation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END
    
    is_public = query.data == "vis_public"
    context.user_data['quiz']['is_public'] = is_public
    
    visibility_text = "✅ Public" if is_public else "🔒 Private"
    quiz_data = context.user_data['quiz']
    is_premium = context.user_data.get('is_premium', False)
    max_q = PREMIUM_MAX_QUESTIONS if is_premium else FREE_MAX_QUESTIONS
    
    await query.edit_message_text(
        f"📝 <b>Quiz Summary</b>\n\n"
        f"📚 Name: {escape_html(quiz_data['name'])}\n"
        f"📂 Category: {get_category_name(quiz_data['category'])}\n"
        f"⚡ Extra Points: {'Yes' if quiz_data['extra_points'] else 'No'}\n"
        f"👁️ Visibility: {visibility_text}\n"
        f"❓ Max Questions: {max_q}\n\n"
        f"Now send me your questions in this format:\n\n"
        f"<code>Question text?\n"
        f"Option A ✅\n"
        f"Option B\n"
        f"Option C\n"
        f"Option D</code>\n\n"
        f"Mark correct answers with ✅\n"
        f"Separate questions with blank lines.",
        parse_mode=ParseMode.HTML
    )
    return QUIZ_QUESTIONS


async def questions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle questions input - first batch or additional"""
    text = update.message.text.strip()
    
    is_premium = context.user_data.get('is_premium', False)
    max_q = PREMIUM_MAX_QUESTIONS if is_premium else FREE_MAX_QUESTIONS
    
    # Parse questions
    questions, errors = parse_bulk_questions(text)
    
    if not questions:
        error_text = "\n".join(errors[:5]) if errors else "Invalid format"
        await update.message.reply_text(
            f"❌ Could not parse questions:\n{error_text}\n\n"
            "Please check the format and try again.\n"
            "Send /cancel to cancel.",
        )
        return QUIZ_QUESTIONS
    
    # Add to existing questions
    if 'questions' not in context.user_data['quiz']:
        context.user_data['quiz']['questions'] = []
    
    current_total = len(context.user_data['quiz']['questions'])
    
    # Check limit
    remaining = max_q - current_total
    if len(questions) > remaining:
        questions = questions[:remaining]
    
    context.user_data['quiz']['questions'].extend(questions)
    total = len(context.user_data['quiz']['questions'])
    
    response = f"✅ Added {len(questions)} question(s)!\n"
    response += f"📊 Total questions: {total}/{max_q}\n\n"
    
    if errors:
        response += f"⚠️ {len(errors)} question(s) had errors and were skipped.\n\n"
    
    if total >= max_q and not is_premium:
        response += f"⚠️ You've reached the free limit of {max_q} questions.\n"
        response += "💎 Upgrade to Premium for up to 100 questions!\n\n"
    
    response += "What would you like to do?"
    
    await update.message.reply_text(
        response,
        reply_markup=add_more_keyboard()
    )
    return QUIZ_ADD_MORE


async def add_more_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle add more questions"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "add_more":
        await query.edit_message_text(
            "📝 Send more questions in the same format:\n\n"
            "<code>Question text?\n"
            "Option A ✅\n"
            "Option B\n"
            "Option C\n"
            "Option D</code>",
            parse_mode=ParseMode.HTML
        )
        return QUIZ_QUESTIONS
    
    elif query.data == "done_creating":
        return await create_quiz_final(query, context)


async def create_quiz_final(query, context: ContextTypes.DEFAULT_TYPE):
    """Create the quiz in database"""
    user = query.from_user
    quiz_data = context.user_data.get('quiz', {})
    
    if not quiz_data.get('questions'):
        await query.edit_message_text("❌ No questions added! Quiz creation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END
    
    # Create the quiz group in database
    quiz_group = await create_quiz_group(
        creator_id=user.id,
        name=quiz_data['name'],
        description=quiz_data['description'],
        category=quiz_data['category'],
        is_public=quiz_data['is_public'],
        extra_points=quiz_data['extra_points']
    )
    
    # Add questions
    questions_to_add = []
    for q in quiz_data['questions']:
        questions_to_add.append({
            "question_text": q['question_text'],
            "options": q['options'],
            "correct_index": q['correct_index'],
            "question_type": q['question_type']
        })
    
    added = await add_questions_bulk(quiz_group['group_id'], questions_to_add)
    
    response = f"🎉 <b>Quiz Created Successfully!</b>\n\n"
    response += f"📚 <b>{escape_html(quiz_data['name'])}</b>\n"
    response += f"❓ Questions: {added}\n\n"
    response += f"🔗 Share Link:\n<code>t.me/{context.bot.username}?start={quiz_group['group_id']}</code>\n\n"
    response += f"To play in a group:\n<code>/startquiz {quiz_group['group_id']}</code>"
    
    await query.edit_message_text(response, parse_mode=ParseMode.HTML)
    
    # Send main menu
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Use the menu below:",
        reply_markup=main_menu_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Quiz creation cancelled.",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cancel button"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    await query.edit_message_text("❌ Quiz creation cancelled.")
    return ConversationHandler.END


def get_create_handler():
    """Return the conversation handler for quiz creation"""
    return ConversationHandler(
        entry_points=[
            CommandHandler("create", create_command),
            MessageHandler(filters.Regex("^📝 Create Quiz$"), create_button),
        ],
        states={
            QUIZ_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_name_handler)
            ],
            QUIZ_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_description_handler)
            ],
            QUIZ_CATEGORY: [
                CallbackQueryHandler(category_callback, pattern="^cat_|^cancel$")
            ],
            QUIZ_EXTRA_POINTS: [
                CallbackQueryHandler(extra_points_callback, pattern="^extra_|^cancel$|^show_premium$")
            ],
            QUIZ_VISIBILITY: [
                CallbackQueryHandler(visibility_callback, pattern="^vis_|^cancel$")
            ],
            QUIZ_QUESTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, questions_handler)
            ],
            QUIZ_ADD_MORE: [
                CallbackQueryHandler(add_more_callback, pattern="^add_more$|^done_creating$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, questions_handler)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            CallbackQueryHandler(cancel_callback, pattern="^cancel$")
        ],
        allow_reentry=True
    )
