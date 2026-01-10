"""
Keyboard Generators for the Quiz Bot
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import CATEGORIES, DIFFICULTY_LEVELS


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main menu reply keyboard"""
    keyboard = [
        [KeyboardButton("📝 Create Quiz"), KeyboardButton("📚 My Quizzes")],
        [KeyboardButton("🔍 Browse Quizzes"), KeyboardButton("📊 My Stats")],
        [KeyboardButton("❓ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def category_keyboard() -> InlineKeyboardMarkup:
    """Category selection inline keyboard"""
    keyboard = []
    for key, value in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(value, callback_data=f"cat_{key}")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)


def visibility_keyboard() -> InlineKeyboardMarkup:
    """Public/Private visibility keyboard"""
    keyboard = [
        [InlineKeyboardButton("✅ Public - Anyone can discover", callback_data="vis_public")],
        [InlineKeyboardButton("🔒 Private - Only with link", callback_data="vis_private")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def difficulty_keyboard() -> InlineKeyboardMarkup:
    """Difficulty level selection keyboard"""
    keyboard = []
    for key, value in DIFFICULTY_LEVELS.items():
        keyboard.append([InlineKeyboardButton(value, callback_data=f"diff_{key}")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)


def time_limit_keyboard() -> InlineKeyboardMarkup:
    """Time limit selection keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("10s", callback_data="time_10"),
            InlineKeyboardButton("15s", callback_data="time_15"),
            InlineKeyboardButton("20s", callback_data="time_20")
        ],
        [
            InlineKeyboardButton("30s", callback_data="time_30"),
            InlineKeyboardButton("45s", callback_data="time_45"),
            InlineKeyboardButton("60s", callback_data="time_60")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def question_input_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for question input mode"""
    keyboard = [
        [InlineKeyboardButton("✅ Done - Finish this Quiz", callback_data="questions_done")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def add_quiz_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for adding another quiz"""
    keyboard = [
        [InlineKeyboardButton("➕ Add Another Quiz", callback_data="add_quiz")],
        [InlineKeyboardButton("✅ Done - Finish Quiz Group", callback_data="group_done")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def quiz_group_actions_keyboard(group_id: str) -> InlineKeyboardMarkup:
    """Actions for a Quiz Group"""
    keyboard = [
        [
            InlineKeyboardButton("▶️ Play", callback_data=f"play_{group_id}"),
            InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{group_id}")
        ],
        [
            InlineKeyboardButton("📊 Stats", callback_data=f"stats_{group_id}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{group_id}")
        ],
        [InlineKeyboardButton("🔗 Share Link", callback_data=f"share_{group_id}")],
        [InlineKeyboardButton("« Back", callback_data="my_quizzes")]
    ]
    return InlineKeyboardMarkup(keyboard)


def confirm_delete_keyboard(group_id: str) -> InlineKeyboardMarkup:
    """Confirm deletion keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_del_{group_id}"),
            InlineKeyboardButton("❌ No, Keep", callback_data=f"view_{group_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def browse_categories_keyboard() -> InlineKeyboardMarkup:
    """Browse by category keyboard"""
    keyboard = []
    for key, value in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(value, callback_data=f"browse_{key}")])
    keyboard.append([InlineKeyboardButton("🔍 Search", callback_data="search_quizzes")])
    return InlineKeyboardMarkup(keyboard)


def pagination_keyboard(current_page: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
    """Pagination keyboard"""
    buttons = []
    if current_page > 0:
        buttons.append(InlineKeyboardButton("« Prev", callback_data=f"{prefix}_page_{current_page - 1}"))
    buttons.append(InlineKeyboardButton(f"{current_page + 1}/{total_pages}", callback_data="noop"))
    if current_page < total_pages - 1:
        buttons.append(InlineKeyboardButton("Next »", callback_data=f"{prefix}_page_{current_page + 1}"))
    
    keyboard = [buttons] if buttons else []
    keyboard.append([InlineKeyboardButton("« Back", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)


def join_quiz_keyboard(group_id: str) -> InlineKeyboardMarkup:
    """Join quiz keyboard for group play"""
    keyboard = [
        [InlineKeyboardButton("🎮 Join Quiz!", callback_data=f"join_{group_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)


def select_quiz_keyboard(quizzes: list) -> InlineKeyboardMarkup:
    """Select which quiz to play from a group"""
    keyboard = []
    for quiz in quizzes:
        keyboard.append([
            InlineKeyboardButton(
                f"📝 {quiz['title']} ({quiz['total_questions']} Qs)",
                callback_data=f"startq_{quiz['quiz_id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🎲 Play All Randomly", callback_data="play_all")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_game")])
    return InlineKeyboardMarkup(keyboard)
