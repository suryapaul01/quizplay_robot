# 🎯 Quiz Master Bot

A comprehensive Telegram bot for creating, organizing, and running interactive quizzes in groups!

## Features

- **📝 Create Quiz Groups** - Organize related quizzes together
- **🎮 Group Play** - Run quizzes in Telegram groups using native quiz polls
- **📊 Leaderboards** - Track scores per quiz, group, and globally
- **🔗 Share Links** - Generate shareable links for your quiz groups
- **🎯 Bulk Question Import** - Add multiple questions at once with a simple format

## Setup

### 1. Create a Bot

1. Talk to [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot with `/newbot`
3. Copy your bot token

### 2. Set up MongoDB

1. Create a free cluster at [MongoDB Atlas](https://www.mongodb.com/atlas)
2. Create a database user
3. Get your connection string

### 3. Configure Environment

1. Copy `.env.example` to `.env`
2. Fill in your values:

```env
BOT_TOKEN=your_bot_token_here
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/quizbot
ADMIN_IDS=your_telegram_user_id
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the Bot

```bash
python bot.py
```

## Commands

### Private Chat
| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/create` | Create a new Quiz Group |
| `/myquizzes` | View your Quiz Groups |
| `/browse` | Browse public quizzes |
| `/stats` | View your statistics |
| `/help` | Show help |

### Group Chat
| Command | Description |
|---------|-------------|
| `/startquiz QG_xxx` | Start a quiz |
| `/leaderboard` | View group leaderboard |
| `/stop` | Stop current quiz |

### Admin Only
| Command | Description |
|---------|-------------|
| `/broadcast <msg>` | Send message to all users |
| `/adminstats` | View bot statistics |
| `/banuser <id>` | Ban a user |
| `/unbanuser <id>` | Unban a user |
| `/addadmin <id>` | Add new admin |

## Creating Quizzes

### Bulk Question Format

Add multiple questions at once using this format:

```
What is the capital of France?
London
Paris ✅
Berlin
Madrid

The Earth is flat. True or False?
True
False ✅

Which programming language is this bot written in?
Java
Python ✅
JavaScript
C++
Ruby
Go
```

**Rules:**
- First line = Question
- Following lines = Options (2-10 for MCQ, 2 for True/False)
- Mark correct answer with ✅
- Blank line separates questions

## Project Structure

```
QuizMasterBot/
├── bot.py                # Main entry point
├── config.py             # Configuration
├── requirements.txt      # Dependencies
├── .env.example          # Environment template
│
├── database/
│   ├── connection.py     # MongoDB connection
│   └── models.py         # Data models
│
├── handlers/
│   ├── start.py          # /start, /help
│   ├── create.py         # Quiz creation
│   ├── myquizzes.py      # User's quizzes
│   ├── browse.py         # Browse public
│   ├── stats.py          # Statistics
│   ├── group.py          # Group play
│   └── admin.py          # Admin commands
│
└── utils/
    ├── keyboards.py      # Keyboard generators
    ├── quiz_parser.py    # Bulk format parser
    └── helpers.py        # Utility functions
```

## License

MIT License
