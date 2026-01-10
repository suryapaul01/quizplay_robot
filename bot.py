"""
Quiz Master Bot - Main Entry Point
"""
import logging
from telegram.ext import Application

from config import BOT_TOKEN
from database.connection import connect_db, close_db

# Import handlers
from handlers.start import get_start_handlers
from handlers.create import get_create_handler
from handlers.myquizzes import get_myquizzes_handlers
from handlers.browse import get_browse_handlers
from handlers.stats import get_stats_handlers
from handlers.group import get_group_handlers
from handlers.admin import get_admin_handlers
from handlers.premium import get_premium_handlers

# Configure logging - reduced verbosity
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def post_init(application: Application) -> None:
    """Initialize after application start"""
    # Connect to database
    connected = await connect_db()
    if not connected:
        logger.error("Failed to connect to database!")
        return
    
    # Set bot commands
    await application.bot.set_my_commands([
        ("start", "Start the bot"),
        ("create", "Create a new Quiz"),
        ("myquizzes", "View your Quizzes"),
        ("browse", "Browse public quizzes"),
        ("stats", "Your statistics"),
        ("premium", "Premium plans"),
        ("help", "Show help"),
    ])
    
    logger.info("Bot initialized successfully!")


async def post_shutdown(application: Application) -> None:
    """Cleanup on shutdown"""
    await close_db()
    logger.info("Bot shut down.")


async def error_handler(update, context):
    """Handle errors gracefully"""
    import telegram.error
    
    error = context.error
    
    # Ignore network timeouts - these are normal
    if isinstance(error, telegram.error.TimedOut):
        logger.debug("Network timeout - this is normal, retrying...")
        return
    
    if isinstance(error, telegram.error.NetworkError):
        logger.warning(f"Network error: {error}")
        return
    
    # Log other errors
    logger.error(f"Error: {error}")


def main():
    """Main function to run the bot"""
    if not BOT_TOKEN:
        logger.error("[ERROR] BOT_TOKEN not set! Please set it in .env file.")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Add conversation handler for quiz creation (must be added before other handlers)
    application.add_handler(get_create_handler())
    
    # Add start handlers
    for handler in get_start_handlers():
        application.add_handler(handler)
    
    # Add my quizzes handlers
    for handler in get_myquizzes_handlers():
        application.add_handler(handler)
    
    # Add browse handlers
    for handler in get_browse_handlers():
        application.add_handler(handler)
    
    # Add stats handlers
    for handler in get_stats_handlers():
        application.add_handler(handler)
    
    # Add premium handlers
    for handler in get_premium_handlers():
        application.add_handler(handler)
    
    # Add group handlers
    for handler in get_group_handlers():
        application.add_handler(handler)
    
    # Add admin handlers
    for handler in get_admin_handlers():
        application.add_handler(handler)
    
    # Start the bot
    logger.info("[START] Starting Quiz Master Bot...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

