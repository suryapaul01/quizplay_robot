"""
Group Chat Quiz Handler - Using Telegram Native Quiz Polls
Admin-only quiz starting, countdown timer display, new scoring system
"""
import asyncio
from datetime import datetime
from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, PollAnswerHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest

from database.models import (
    get_quiz_group, get_group_questions, create_active_game, get_active_game,
    update_active_game, add_player_to_game, update_player_score,
    delete_active_game, save_score, get_chat_leaderboard, create_user
)
from utils.helpers import (
    escape_html, format_leaderboard,
    format_question_for_poll, calculate_score
)
from config import JOIN_COUNTDOWN, DEFAULT_QUESTION_TIME


# Store active polls: {poll_id: {...}}
active_polls = {}
# Store countdown tasks: {chat_id: task}
countdown_tasks = {}


def join_quiz_keyboard(group_id: str) -> InlineKeyboardMarkup:
    """Join quiz button"""
    keyboard = [[InlineKeyboardButton("🎮 Join Quiz!", callback_data=f"join_{group_id}")]]
    return InlineKeyboardMarkup(keyboard)


async def startquiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /startquiz command in groups - ADMIN ONLY"""
    chat = update.effective_chat
    user = update.effective_user
    
    # Check if in group
    if chat.type == "private":
        await update.message.reply_text(
            "⚠️ This command works only in groups!\n\n"
            "Add me to a group and use /startquiz there."
        )
        return
    
    # Check if user is admin
    try:
        member = await chat.get_member(user.id)
        if member.status not in ['creator', 'administrator']:
            await update.message.reply_text("❌ Only group admins can start quizzes!")
            return
    except Exception:
        await update.message.reply_text("❌ Could not verify admin status.")
        return
    
    # Check for group_id argument
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "❌ Please provide a Quiz ID!\n\n"
            "Usage: <code>/startquiz QG_xxxxx</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    group_id = context.args[0]
    
    # Check if there's already an active game
    existing_game = await get_active_game(chat.id)
    if existing_game:
        await update.message.reply_text(
            "⚠️ A quiz is already running!\n\n"
            "Use /stop to end it first."
        )
        return
    
    # Get quiz group
    quiz_group = await get_quiz_group(group_id)
    if not quiz_group:
        await update.message.reply_text("❌ Quiz not found!")
        return
    
    # Get questions
    questions = await get_group_questions(group_id)
    if not questions:
        await update.message.reply_text("❌ This quiz has no questions!")
        return
    
    # Create active game
    await create_active_game(
        chat_id=chat.id,
        group_id=group_id,
        quiz_id=group_id,
        started_by=user.id
    )
    
    # Store settings in chat_data
    context.chat_data['extra_points'] = quiz_group.get('extra_points', True)
    context.chat_data['time_limit'] = DEFAULT_QUESTION_TIME
    context.chat_data['group_id'] = group_id
    
    # Show join message with countdown
    extra_text = "⚡ Speed Bonus: ON" if quiz_group.get('extra_points', True) else "📝 Speed Bonus: OFF"
    
    text = f"🎯 <b>{escape_html(quiz_group['name'])}</b>\n\n"
    text += f"❓ Questions: {len(questions)}\n"
    text += f"⏱️ Time per question: {DEFAULT_QUESTION_TIME}s\n"
    text += f"{extra_text}\n\n"
    text += f"Click below to join!\n\n"
    text += f"⏰ <b>Starting in {JOIN_COUNTDOWN} seconds...</b>"
    
    msg = await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=join_quiz_keyboard(group_id)
    )
    
    context.chat_data['join_message_id'] = msg.message_id
    context.chat_data['quiz_group'] = quiz_group
    context.chat_data['question_count'] = len(questions)
    
    # Cancel any existing countdown
    if chat.id in countdown_tasks:
        countdown_tasks[chat.id].cancel()
    
    # Start countdown with timer updates
    task = asyncio.create_task(
        countdown_and_start(context.bot, chat.id, group_id, msg.message_id, quiz_group, len(questions), context.chat_data)
    )
    countdown_tasks[chat.id] = task


async def countdown_and_start(bot, chat_id: int, group_id: str, message_id: int, quiz_group: dict, question_count: int, chat_data: dict):
    """Countdown with timer updates and start the quiz"""
    extra_text = "⚡ Speed Bonus: ON" if quiz_group.get('extra_points', True) else "📝 Speed Bonus: OFF"
    
    # Countdown updates at 20, 10, 5 seconds
    countdown_times = [JOIN_COUNTDOWN]
    if JOIN_COUNTDOWN > 20:
        countdown_times.append(20)
    if JOIN_COUNTDOWN > 10:
        countdown_times.append(10)
    if JOIN_COUNTDOWN > 5:
        countdown_times.append(5)
    countdown_times.append(0)
    
    for i in range(len(countdown_times) - 1):
        current = countdown_times[i]
        next_time = countdown_times[i + 1]
        wait_time = current - next_time
        
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        if next_time > 0:
            try:
                text = f"🎯 <b>{escape_html(quiz_group['name'])}</b>\n\n"
                text += f"❓ Questions: {question_count}\n"
                text += f"⏱️ Time per question: {DEFAULT_QUESTION_TIME}s\n"
                text += f"{extra_text}\n\n"
                text += f"Click below to join!\n\n"
                text += f"⏰ <b>Starting in {next_time} seconds...</b>"
                
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=join_quiz_keyboard(group_id)
                )
            except BadRequest:
                pass
            except Exception:
                pass
    
    # Clean up countdown task
    if chat_id in countdown_tasks:
        del countdown_tasks[chat_id]
    
    # Get the game
    game = await get_active_game(chat_id)
    if not game:
        return
    
    players = game.get('players', {})
    
    if len(players) == 0:
        await bot.send_message(chat_id=chat_id, text="❌ No players joined! Quiz cancelled.")
        await delete_active_game(chat_id)
        return
    
    # Get questions
    questions = await get_group_questions(group_id)
    if not questions:
        await bot.send_message(chat_id=chat_id, text="❌ No questions found! Quiz cancelled.")
        await delete_active_game(chat_id)
        return
    
    # Announce start
    player_names = [p['username'] for p in players.values()][:10]
    await bot.send_message(
        chat_id=chat_id,
        text=f"🎮 <b>{len(players)} players joined!</b>\n"
             f"👥 {', '.join(player_names)}\n\n"
             f"🚀 Starting now!",
        parse_mode=ParseMode.HTML
    )
    
    await asyncio.sleep(2)
    
    # Start quiz
    extra_points = chat_data.get('extra_points', True)
    await run_quiz(bot, chat_id, questions, game, extra_points)


async def join_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle join button click"""
    query = update.callback_query
    user = update.effective_user
    chat = update.effective_chat
    
    # Create user as group participant (not bot user)
    await create_user(user.id, user.username, user.first_name, is_bot_user=False)
    
    # Add player to game
    success = await add_player_to_game(chat.id, user.id, user.first_name or user.username or "Player")
    
    if success:
        await query.answer(f"✅ You joined the quiz!")
    else:
        await query.answer(f"❌ Could not join. Quiz may have started.", show_alert=True)


async def run_quiz(bot, chat_id: int, questions: list, game: dict, extra_points: bool = True):
    """Run the quiz questions"""
    total_questions = len(questions)
    time_limit = DEFAULT_QUESTION_TIME
    
    for i, question in enumerate(questions):
        # Check if game still exists (might have been stopped)
        current_game = await get_active_game(chat_id)
        if not current_game:
            return
        
        # Update current question
        await update_active_game(chat_id, current_question=i)
        
        # Send question as poll
        poll_data = format_question_for_poll(question)
        
        try:
            poll_msg = await bot.send_poll(
                chat_id=chat_id,
                question=f"Q{i+1}/{total_questions}: {poll_data['question']}",
                options=poll_data['options'],
                type=Poll.QUIZ,
                correct_option_id=poll_data['correct_option_id'],
                is_anonymous=False,
                open_period=time_limit
            )
            
            # Store poll info
            poll_id = poll_msg.poll.id
            active_polls[poll_id] = {
                'chat_id': chat_id,
                'question_index': i,
                'correct_option': poll_data['correct_option_id'],
                'start_time': datetime.utcnow(),
                'question_id': question['question_id'],
                'answered_users': set(),
                'extra_points': extra_points,
                'time_limit': time_limit
            }
            
            # Update game with current poll
            await update_active_game(chat_id, current_poll_id=poll_id)
            
        except Exception as e:
            continue
        
        # Wait for poll to close
        await asyncio.sleep(time_limit + 2)
        
        # Clean up poll from tracking
        if poll_id in active_polls:
            del active_polls[poll_id]
        
        # Show intermediate leaderboard every 5 questions
        if (i + 1) % 5 == 0 and i + 1 < total_questions:
            current_game = await get_active_game(chat_id)
            if current_game:
                scores_data = current_game.get('scores', {})
                if scores_data:
                    leaderboard_text = "📊 <b>Current Standings:</b>\n\n"
                    sorted_scores = sorted(scores_data.items(), key=lambda x: x[1], reverse=True)[:5]
                    
                    players = current_game.get('players', {})
                    medals = ["🥇", "🥈", "🥉"]
                    for rank, (uid, score) in enumerate(sorted_scores, 1):
                        username = players.get(uid, {}).get('username', 'Unknown')
                        medal = medals[rank-1] if rank <= 3 else f"{rank}."
                        leaderboard_text += f"{medal} {escape_html(username)} - {score} pts\n"
                    
                    await bot.send_message(chat_id=chat_id, text=leaderboard_text, parse_mode=ParseMode.HTML)
    
    # Quiz complete - show final results
    await show_final_results(bot, chat_id, game['group_id'], total_questions)


async def poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle poll answers for both group and solo play"""
    answer = update.poll_answer
    poll_id = answer.poll_id
    user_id = answer.user.id
    
    # Check for solo play poll first
    solo_key = f"solo_{poll_id}"
    if solo_key in context.bot_data:
        poll_info = context.bot_data[solo_key]
        
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
        return
    
    # Handle group poll
    if poll_id not in active_polls:
        return
    
    poll_info = active_polls[poll_id]
    
    # Check if user already answered
    if user_id in poll_info['answered_users']:
        return
    
    poll_info['answered_users'].add(user_id)
    
    # Calculate response time
    response_time = (datetime.utcnow() - poll_info['start_time']).total_seconds()
    
    # Check if correct
    selected_option = answer.option_ids[0] if answer.option_ids else -1
    is_correct = selected_option == poll_info['correct_option']
    
    # Calculate score with new system
    extra_points = poll_info.get('extra_points', True)
    time_limit = poll_info.get('time_limit', DEFAULT_QUESTION_TIME)
    points = calculate_score(is_correct, response_time, time_limit, extra_points)
    
    # Update player score
    if points > 0:
        await update_player_score(poll_info['chat_id'], user_id, points, is_correct)


async def show_final_results(bot, chat_id: int, group_id: str, total_questions: int):
    """Show final quiz results"""
    game = await get_active_game(chat_id)
    if not game:
        return
    
    players = game.get('players', {})
    scores = game.get('scores', {})
    
    # Build final leaderboard
    text = "🏆 <b>Quiz Complete!</b>\n\n"
    text += "<b>Final Leaderboard:</b>\n\n"
    
    if not scores:
        text += "No scores recorded!\n"
    else:
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        medals = ["🥇", "🥈", "🥉"]
        
        for rank, (uid, score) in enumerate(sorted_scores[:10], 1):
            username = players.get(uid, {}).get('username', 'Unknown')
            correct = players.get(uid, {}).get('correct', 0)
            
            medal = medals[rank-1] if rank <= 3 else f"{rank}."
            text += f"{medal} {escape_html(username)} - {score} pts ({correct}/{total_questions})\n"
            
            # Save score to leaderboard
            await save_score(
                quiz_id=group_id,
                group_id=group_id,
                user_id=int(uid),
                username=username,
                score=score,
                correct_answers=correct,
                total_questions=total_questions,
                chat_id=chat_id
            )
    
    text += "\n🎮 Play again with /startquiz!"
    
    await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
    
    # Clean up
    await delete_active_game(chat_id)


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop the current quiz - ADMIN ONLY"""
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type == "private":
        await update.message.reply_text("⚠️ This command works only in groups!")
        return
    
    # Check if user is admin
    try:
        member = await chat.get_member(user.id)
        is_admin = member.status in ['creator', 'administrator']
    except Exception:
        is_admin = False
    
    game = await get_active_game(chat.id)
    
    # Check for countdown task first
    if chat.id in countdown_tasks:
        countdown_tasks[chat.id].cancel()
        del countdown_tasks[chat.id]
        if game:
            await delete_active_game(chat.id)
        await update.message.reply_text("🛑 Quiz cancelled!")
        return
    
    if not game:
        await update.message.reply_text("❌ No quiz is currently running!")
        return
    
    is_starter = game.get('started_by') == user.id
    
    if not is_admin and not is_starter:
        await update.message.reply_text("❌ Only admins can stop the quiz!")
        return
    
    await delete_active_game(chat.id)
    await update.message.reply_text("🛑 Quiz stopped!")


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group leaderboard"""
    chat = update.effective_chat
    
    if chat.type == "private":
        await update.message.reply_text("⚠️ This command works only in groups!")
        return
    
    leaderboard = await get_chat_leaderboard(chat.id)
    
    if not leaderboard:
        await update.message.reply_text(
            "📊 No quiz scores in this group yet!\n\n"
            "Start a quiz with /startquiz"
        )
        return
    
    text = format_leaderboard(leaderboard, "🏆 Group Leaderboard")
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


def get_group_handlers():
    """Return list of handlers for group module"""
    return [
        CommandHandler("startquiz", startquiz_command),
        CommandHandler("stop", stop_command),
        CommandHandler("leaderboard", leaderboard_command),
        CallbackQueryHandler(join_quiz_callback, pattern="^join_"),
        PollAnswerHandler(poll_answer_handler),
    ]
