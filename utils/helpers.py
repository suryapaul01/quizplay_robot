"""
Helper Utility Functions
"""
import html
from typing import Optional
from config import CATEGORIES, DIFFICULTY_LEVELS


def escape_html(text: str) -> str:
    """Escape HTML special characters"""
    return html.escape(str(text))


def get_category_name(key: str) -> str:
    """Get category display name from key"""
    return CATEGORIES.get(key, "📦 Other")


def get_difficulty_name(key: str) -> str:
    """Get difficulty display name from key"""
    return DIFFICULTY_LEVELS.get(key, "🟡 Medium")


def format_leaderboard(entries: list, title: str = "🏆 Leaderboard") -> str:
    """Format leaderboard entries for display"""
    if not entries:
        return f"{title}\n\nNo entries yet!"
    
    text = f"{title}\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, entry in enumerate(entries):
        if i < 3:
            medal = medals[i]
        else:
            medal = f"{i + 1}."
        
        username = entry.get('username', 'Unknown')
        score = entry.get('total_score', entry.get('score', 0))
        
        text += f"{medal} {escape_html(username)} - {score} pts\n"
    
    return text


def format_quiz_group_info(group: dict, quizzes: list = None) -> str:
    """Format Quiz Group info for display"""
    category = get_category_name(group.get('category', 'other'))
    visibility = "✅ Public" if group.get('is_public') else "🔒 Private"
    
    text = f"""
📚 <b>{escape_html(group['name'])}</b>

{escape_html(group.get('description', 'No description'))}

{category}
{visibility}
🎯 Quizzes: {group.get('total_quizzes', 0)}
❓ Questions: {group.get('total_questions', 0)}
🎮 Total Plays: {group.get('total_plays', 0)}

🔗 Share: <code>t.me/BOTUSERNAME?start={group['group_id']}</code>
"""
    
    if quizzes:
        text += "\n📝 <b>Quizzes:</b>\n"
        for quiz in quizzes:
            diff = get_difficulty_name(quiz.get('difficulty', 'medium'))
            text += f"• {escape_html(quiz['title'])} ({quiz.get('total_questions', 0)} Qs) {diff}\n"
    
    return text


def format_user_stats(user: dict) -> str:
    """Format user statistics for display"""
    return f"""
📊 <b>Your Statistics</b>

🎯 Quiz Groups Created: {user.get('total_groups_created', 0)}
📝 Quizzes Created: {user.get('total_quizzes_created', 0)}
🎮 Quizzes Played: {user.get('total_quizzes_played', 0)}
⭐ Total Score: {user.get('total_score', 0)}

📅 Member since: {user.get('created_at', 'Unknown')}
"""


def format_bot_stats(stats: dict) -> str:
    """Format bot statistics for admin view"""
    return f"""
📊 <b>Bot Statistics</b>

👥 Bot Users: {stats.get('total_users', 0)}
📚 Total Quizzes: {stats.get('total_quiz_groups', 0)}
❓ Total Questions: {stats.get('total_questions', 0)}
🎮 Total Plays: {stats.get('total_plays', 0)}
"""


def format_question_for_poll(question: dict) -> dict:
    """Format question data for Telegram poll"""
    return {
        "question": question['question_text'][:300],  # Telegram limit
        "options": question['options'][:10],  # Max 10 options
        "correct_option_id": question['correct_index'],
        "is_anonymous": False,
        "type": "quiz"
    }


def calculate_score(is_correct: bool, response_time: float, max_time: int = 20, extra_points: bool = True) -> int:
    """
    Calculate score based on correctness and speed
    
    Scoring:
    - Correct answer: 5 points
    - Speed bonus (if extra_points enabled):
      - 90%+ time remaining: +10 points
      - 80%+ time remaining: +8 points
      - 60%+ time remaining: +5 points
      - 50%+ time remaining: +3 points
      - <50% time remaining: +0 points
    """
    if not is_correct:
        return 0
    
    # Base points for correct answer
    base_points = 5
    
    if not extra_points:
        return base_points
    
    # Calculate time remaining percentage
    time_remaining_pct = ((max_time - response_time) / max_time) * 100
    
    # Speed bonus based on time remaining
    if time_remaining_pct >= 90:
        speed_bonus = 10
    elif time_remaining_pct >= 80:
        speed_bonus = 8
    elif time_remaining_pct >= 60:
        speed_bonus = 5
    elif time_remaining_pct >= 50:
        speed_bonus = 3
    else:
        speed_bonus = 0
    
    return base_points + speed_bonus

