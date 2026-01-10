"""
MongoDB Connection Module
"""
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI

client = None
db = None


async def connect_db():
    """Connect to MongoDB"""
    global client, db
    try:
        client = AsyncIOMotorClient(MONGO_URI)
        db = client.quizbot
        # Test connection
        await client.admin.command('ping')
        print("[OK] Connected to MongoDB successfully!")
        return True
    except Exception as e:
        print(f"[ERROR] MongoDB connection error: {e}")
        return False


async def close_db():
    """Close MongoDB connection"""
    global client
    if client:
        client.close()
        print("[INFO] MongoDB connection closed")


def get_db():
    """Get database instance"""
    return db

