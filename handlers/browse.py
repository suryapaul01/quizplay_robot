"""
Browse Public Quizzes Handler - with Solo Play Feature and Translation
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode
import asyncio
from datetime import datetime

from database.models import (
    get_public_quiz_groups, get_quiz_group, get_group_questions,
    count_public_quiz_groups, save_score, create_user, get_user_language
)
from utils.helpers import get_category_name, escape_html, format_question_for_poll, calculate_score
from utils.translator import translate_questions_batch
from config import CATEGORIES, DEFAULT_QUESTION_TIME, SUPPORTED_LANGUAGES

QUIZZES_PER_PAGE = 5
MIN_PLAYS_REQUIRED = 2


def browse_categories_keyboard():
    """Category selection keyboard for browse"""
    keyboard = []
    for key, value in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(value, callback_data=f"browse_{key}")])
    return InlineKeyboardMarkup(keyboard)


def quiz_list_keyboard(quizzes: list, category: str, page: int, total_pages: int):
    """Keyboard showing quizzes with pagination"""
    keyboard = []
    
    for quiz in quizzes:
        plays = quiz.get('total_plays', 0)
        questions = quiz.get('total_questions', 0)
        keyboard.append([
            InlineKeyboardButton(
                f"📚 {quiz['name'][:25]} ({questions}Q • {plays} plays)",
                callback_data=f"viewquiz_{quiz['group_id']}"
            )
        ])
    
    # Pagination
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("« Prev", callback_data=f"browsepage_{category}_{page-1}"))
    nav_row.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next »", callback_data=f"browsepage_{category}_{page+1}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    keyboard.append([InlineKeyboardButton("« Back to Categories", callback_data="browse_back")])
    
    return InlineKeyboardMarkup(keyboard)


def quiz_options_keyboard(group_id: str):
    """Options for a selected quiz"""
    keyboard = [
        [InlineKeyboardButton("🎮 Play Solo (Learn Mode)", callback_data=f"playsolo_{group_id}")],
        [InlineKeyboardButton("📋 Copy Group Command", callback_data=f"copygroup_{group_id}")],
        [InlineKeyboardButton("« Back", callback_data=f"backtolist_{group_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def browse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /browse command"""
    await update.message.reply_text(
        "🔍 <b>Browse Popular Quizzes</b>\n\n"
        "Select a category to explore:",
        parse_mode=ParseMode.HTML,
        reply_markup=browse_categories_keyboard()
    )


async def browse_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Browse Quizzes button from main menu"""
    if update.message.text == "🔍 Browse Quizzes":
        return await browse_command(update, context)


async def browse_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle category selection for browsing"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "browse_back":
        await query.edit_message_text(
            "🔍 <b>Browse Popular Quizzes</b>\n\n"
            "Select a category to explore:",
            parse_mode=ParseMode.HTML,
            reply_markup=browse_categories_keyboard()
        )
        return
    
    if data == "noop":
        return
    
    # Extract category
    category = data.replace("browse_", "")
    context.user_data['browse_category'] = category
    
    await show_quiz_list(query, context, category, page=0)


async def show_quiz_list(query, context, category: str, page: int = 0):
    """Show paginated quiz list for a category"""
    # Get quizzes with minimum plays
    total_count = await count_public_quiz_groups(category=category, min_plays=MIN_PLAYS_REQUIRED)
    
    if total_count == 0:
        await query.edit_message_text(
            f"{get_category_name(category)}\n\n"
            f"No popular quizzes in this category yet!\n"
            f"(Quizzes need {MIN_PLAYS_REQUIRED}+ plays to appear here)\n\n"
            f"Create one with /create",
            reply_markup=browse_categories_keyboard()
        )
        return
    
    total_pages = (total_count + QUIZZES_PER_PAGE - 1) // QUIZZES_PER_PAGE
    skip = page * QUIZZES_PER_PAGE
    
    quizzes = await get_public_quiz_groups(
        category=category, 
        skip=skip, 
        limit=QUIZZES_PER_PAGE,
        min_plays=MIN_PLAYS_REQUIRED
    )
    
    text = f"📚 <b>{get_category_name(category)}</b>\n\n"
    text += f"🔥 Popular Quizzes ({total_count} total):\n"
    text += "Select a quiz to play:"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=quiz_list_keyboard(quizzes, category, page, total_pages)
    )


async def browse_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pagination in browse"""
    query = update.callback_query
    await query.answer()
    
    # Parse: browsepage_category_page
    parts = query.data.split("_")
    category = parts[1]
    page = int(parts[2])
    
    await show_quiz_list(query, context, category, page)


async def view_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show quiz details with play options"""
    query = update.callback_query
    await query.answer()
    
    group_id = query.data.replace("viewquiz_", "")
    quiz = await get_quiz_group(group_id)
    
    if not quiz:
        await query.answer("Quiz not found!", show_alert=True)
        return
    
    # Store for back navigation
    context.user_data['last_quiz_category'] = quiz.get('category', 'general')
    
    text = f"📚 <b>{escape_html(quiz['name'])}</b>\n\n"
    text += f"📝 {escape_html(quiz.get('description', 'No description'))}\n\n"
    text += f"📂 {get_category_name(quiz.get('category', 'general'))}\n"
    text += f"❓ Questions: {quiz.get('total_questions', 0)}\n"
    text += f"🎮 Plays: {quiz.get('total_plays', 0)}\n"
    text += f"⚡ Speed Bonus: {'Yes' if quiz.get('extra_points', True) else 'No'}\n\n"
    text += "Choose how to play:"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=quiz_options_keyboard(group_id)
    )


async def back_to_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to quiz list"""
    query = update.callback_query
    await query.answer()
    
    group_id = query.data.replace("backtolist_", "")
    quiz = await get_quiz_group(group_id)
    category = quiz.get('category', 'general') if quiz else context.user_data.get('browse_category', 'general')
    
    await show_quiz_list(query, context, category, page=0)


async def copy_group_command_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show command to use in group"""
    query = update.callback_query
    await query.answer()
    
    group_id = query.data.replace("copygroup_", "")
    quiz = await get_quiz_group(group_id)
    
    if not quiz:
        await query.answer("Quiz not found!", show_alert=True)
        return
    
    text = f"📋 <b>Play in Group</b>\n\n"
    text += f"Add the bot to your group and send:\n\n"
    text += f"<code>/startquiz {group_id}</code>\n\n"
    text += f"Or share this link:\n"
    text += f"<code>t.me/{context.bot.username}?start={group_id}</code>"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=quiz_options_keyboard(group_id)
    )


async def play_solo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start solo play mode"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    group_id = query.data.replace("playsolo_", "")
    
    # Create/update user
    await create_user(user.id, user.username, user.first_name, is_bot_user=True)
    
    quiz = await get_quiz_group(group_id)
    if not quiz:
        await query.answer("Quiz not found!", show_alert=True)
        return
    
    questions = await get_group_questions(group_id)
    if not questions:
        await query.answer("No questions in this quiz!", show_alert=True)
        return
    
    # Get user's preferred language
    user_lang = await get_user_language(user.id)
    lang_name = SUPPORTED_LANGUAGES.get(user_lang, user_lang)
    
    await query.edit_message_text(
        f"🎮 <b>Starting Solo Quiz!</b>\n\n"
        f"📚 {escape_html(quiz['name'])}\n"
        f"❓ {len(questions)} questions\n"
        f"🌐 Language: {lang_name}\n\n"
        f"Get ready...",
        parse_mode=ParseMode.HTML
    )
    
    # Translate questions if not English
    if user_lang != "en":
        questions = await translate_questions_batch(questions, user_lang)
    
    await asyncio.sleep(2)
    
    # Run solo quiz
    await run_solo_quiz(context, query.message.chat_id, user, quiz, questions)


async def run_solo_quiz(context, chat_id: int, user, quiz: dict, questions: list):
    """Run solo quiz for a user - moves to next question immediately when answered"""
    total_questions = len(questions)
    time_limit = DEFAULT_QUESTION_TIME
    extra_points = quiz.get('extra_points', True)
    
    total_score = 0
    correct_count = 0
    
    for i, question in enumerate(questions):
        poll_data = format_question_for_poll(question)
        
        # Send quiz poll
        poll_msg = await context.bot.send_poll(
            chat_id=chat_id,
            question=f"Q{i+1}/{total_questions}: {poll_data['question']}",
            options=poll_data['options'],
            type=Poll.QUIZ,
            correct_option_id=poll_data['correct_option_id'],
            is_anonymous=False,
            open_period=time_limit
        )
        
        # Store poll info for tracking
        poll_id = poll_msg.poll.id
        context.bot_data[f"solo_{poll_id}"] = {
            'user_id': user.id,
            'correct_option': poll_data['correct_option_id'],
            'start_time': datetime.utcnow(),
            'time_limit': time_limit,
            'extra_points': extra_points,
            'question_num': i
        }
        
        # Wait for user to answer OR timeout
        # Check every 0.5 seconds if user has answered
        result_key = f"solo_result_{poll_id}"
        elapsed = 0
        answered = False
        
        while elapsed < time_limit + 1:
            await asyncio.sleep(0.5)
            elapsed += 0.5
            
            # Check if user answered
            if result_key in context.bot_data:
                answered = True
                # Small delay to show the correct answer
                await asyncio.sleep(1.5)
                break
        
        # Get result if stored
        if result_key in context.bot_data:
            result = context.bot_data.pop(result_key)
            total_score += result['points']
            if result['correct']:
                correct_count += 1
        
        # Cleanup
        if f"solo_{poll_id}" in context.bot_data:
            del context.bot_data[f"solo_{poll_id}"]
    
    # Show final results
    percentage = (correct_count / total_questions * 100) if total_questions > 0 else 0
    
    result_text = f"🏆 <b>Quiz Complete!</b>\n\n"
    result_text += f"📚 {escape_html(quiz['name'])}\n\n"
    result_text += f"✅ Correct: {correct_count}/{total_questions} ({percentage:.0f}%)\n"
    result_text += f"⭐ Score: {total_score} points\n\n"
    
    if percentage >= 80:
        result_text += "🌟 Excellent! You're a master!"
    elif percentage >= 60:
        result_text += "👍 Good job! Keep learning!"
    elif percentage >= 40:
        result_text += "📚 Not bad! Practice more!"
    else:
        result_text += "💪 Keep trying! You'll improve!"
    
    # Save score
    await save_score(
        quiz_id=quiz['group_id'],
        group_id=quiz['group_id'],
        user_id=user.id,
        username=user.first_name or user.username or "Player",
        score=total_score,
        correct_answers=correct_count,
        total_questions=total_questions,
        chat_id=chat_id
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Play Again", callback_data=f"playsolo_{quiz['group_id']}")],
        [InlineKeyboardButton("🔍 Browse More", callback_data="browse_back")]
    ]
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=result_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def solo_poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle solo play poll answers"""
    answer = update.poll_answer
    poll_id = answer.poll_id
    user_id = answer.user.id
    
    key = f"solo_{poll_id}"
    if key not in context.bot_data:
        return
    
    poll_info = context.bot_data[key]
    
    # Verify user
    if poll_info['user_id'] != user_id:
        return
    
    # Calculate response time
    response_time = (datetime.utcnow() - poll_info['start_time']).total_seconds()
    
    # Check if correct
    selected = answer.option_ids[0] if answer.option_ids else -1
    is_correct = selected == poll_info['correct_option']
    
    # Calculate score
    points = calculate_score(
        is_correct, 
        response_time, 
        poll_info['time_limit'], 
        poll_info['extra_points']
    )
    
    # Store result
    context.bot_data[f"solo_result_{poll_id}"] = {
        'correct': is_correct,
        'points': points
    }


def get_browse_handlers():
    """Return list of handlers for browse module"""
    return [
        CommandHandler("browse", browse_command),
        MessageHandler(filters.Regex("^🔍 Browse Quizzes$"), browse_button),
        CallbackQueryHandler(browse_category_callback, pattern="^browse_"),
        CallbackQueryHandler(browse_page_callback, pattern="^browsepage_"),
        CallbackQueryHandler(view_quiz_callback, pattern="^viewquiz_"),
        CallbackQueryHandler(back_to_list_callback, pattern="^backtolist_"),
        CallbackQueryHandler(copy_group_command_callback, pattern="^copygroup_"),
        CallbackQueryHandler(play_solo_callback, pattern="^playsolo_"),
    ]
