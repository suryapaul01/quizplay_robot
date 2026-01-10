"""
Quiz Master Bot - Configuration Module
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Reduce logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/quizbot")

# Admin IDs (comma-separated in .env)
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

# CryptoPay Configuration
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "")

# UPI Configuration
UPI_ID = os.getenv("UPI_ID", "")

# Quiz Settings
DEFAULT_QUESTION_TIME = int(os.getenv("DEFAULT_QUESTION_TIME", "20"))
JOIN_COUNTDOWN = int(os.getenv("JOIN_COUNTDOWN", "30"))

# Pagination
QUIZZES_PER_PAGE = 5
MAX_QUIZZES_DISPLAY = 20

# ============= PREMIUM CONFIGURATION =============

# Free User Limits
FREE_MAX_QUIZZES = 3
FREE_MAX_QUESTIONS = 20

# Premium User Limits
PREMIUM_MAX_QUESTIONS = 100

# Time Limit Options (premium only can change)
TIME_LIMIT_OPTIONS = [10, 20, 30, 60]

# Premium Pricing
PREMIUM_PRICES = {
    "weekly": {"days": 7, "inr": 49, "usd": 0.99},
    "monthly": {"days": 30, "inr": 149, "usd": 1.99},
    "yearly": {"days": 365, "inr": 899, "usd": 9.99},
}

# Categories
CATEGORIES = {
    "education": "🎓 Education",
    "entertainment": "🎬 Entertainment",
    "sports": "⚽ Sports",
    "general": "🧠 General Knowledge",
    "science": "🔬 Science & Tech",
    "other": "📦 Other"
}

# Difficulty Levels
DIFFICULTY_LEVELS = {
    "easy": "🟢 Easy",
    "medium": "🟡 Medium",
    "hard": "🔴 Hard"
}

# Scoring System
CORRECT_ANSWER_POINTS = 5

# Extra points based on time remaining percentage
# 90%+ = 10 pts, 80%+ = 8 pts, 60%+ = 5 pts, 50%+ = 3 pts, <50% = 0 pts
SPEED_BONUS = {
    90: 10,
    80: 8,
    60: 5,
    50: 3,
    0: 0
}

# Conversation States
class States:
    # Simplified Quiz Creation
    QUIZ_NAME = 1
    QUIZ_DESCRIPTION = 2
    QUIZ_CATEGORY = 3
    QUIZ_EXTRA_POINTS = 4
    QUIZ_VISIBILITY = 5
    QUIZ_QUESTIONS = 6
    QUIZ_TIME_LIMIT = 7
    
    # Broadcast
    BROADCAST_MESSAGE = 50

# Bot Messages
MESSAGES = {
    "welcome": """
🎯 *Welcome to Quiz Master Bot!*

Create, share, and play interactive quizzes with friends and groups!

*What you can do:*
📝 Create Quizzes with bulk questions
🎮 Play quizzes in groups using polls
🏆 Compete on leaderboards
📊 Track your stats
💎 Get Premium for more features

Use the buttons below or type /help for commands!
""",
    "help": """
📚 *Quiz Master Bot - Help*

*Private Chat Commands:*
/start - Main menu
/create - Create a new Quiz
/myquizzes - View your Quizzes
/browse - Browse public quizzes
/stats - Your statistics
/premium - View premium plans
/redeem - Redeem a code
/help - This help message

*Group Chat Commands:*
/startquiz [ID] - Start a quiz (Admin only)
/leaderboard - View group leaderboard
/stop - Stop current quiz (Admin only)

*Question Format:*
```
Question text here?
Option A ✅
Option B
Option C
Option D
```
Mark correct answer with ✅
"""
}


