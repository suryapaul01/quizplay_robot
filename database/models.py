"""
Database Models and CRUD Operations
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
import shortuuid
from database.connection import get_db


# ============= USER OPERATIONS =============

async def create_user(user_id: int, username: str = None, first_name: str = None, is_bot_user: bool = True) -> dict:
    """Create or update a user"""
    db = get_db()
    
    # Fields only set on insert (new user)
    insert_only = {
        "user_id": user_id,
        "total_quizzes_created": 0,
        "total_groups_created": 0,
        "total_quizzes_played": 0,
        "total_score": 0,
        "is_banned": False,
        "is_admin": False,
        "is_bot_user": is_bot_user,  # True = started bot in private, False = only joined via group
        "created_at": datetime.utcnow()
    }
    
    # Fields updated every time
    update_fields = {
        "username": username,
        "first_name": first_name,
        "last_active": datetime.utcnow()
    }
    
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$setOnInsert": insert_only,
            "$set": update_fields
        },
        upsert=True
    )
    return await get_user(user_id)


async def get_user(user_id: int) -> Optional[dict]:
    """Get user by ID"""
    db = get_db()
    return await db.users.find_one({"user_id": user_id})


async def update_user_stats(user_id: int, **kwargs) -> bool:
    """Update user statistics"""
    db = get_db()
    result = await db.users.update_one(
        {"user_id": user_id},
        {"$inc": kwargs}
    )
    return result.modified_count > 0


async def ban_user(user_id: int, ban: bool = True) -> bool:
    """Ban or unban a user"""
    db = get_db()
    result = await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"is_banned": ban}}
    )
    return result.modified_count > 0


async def set_admin(user_id: int, is_admin: bool = True) -> bool:
    """Set or remove admin status"""
    db = get_db()
    result = await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"is_admin": is_admin}}
    )
    return result.modified_count > 0


async def get_all_users() -> List[dict]:
    """Get all BOT users for broadcast (excludes group-only participants)"""
    db = get_db()
    # Include users where is_bot_user is True OR field doesn't exist (legacy users)
    cursor = db.users.find({
        "is_banned": False,
        "$or": [
            {"is_bot_user": True},
            {"is_bot_user": {"$exists": False}}
        ]
    })
    return await cursor.to_list(length=None)


async def get_user_count() -> int:
    """Get total BOT user count (excludes group-only participants)"""
    db = get_db()
    # Include users where is_bot_user is True OR field doesn't exist (legacy users)
    return await db.users.count_documents({
        "$or": [
            {"is_bot_user": True},
            {"is_bot_user": {"$exists": False}}
        ]
    })


# ============= PREMIUM OPERATIONS =============

async def is_premium_user(user_id: int) -> bool:
    """Check if user has active premium"""
    db = get_db()
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        return False
    
    if not user.get("is_premium"):
        return False
    
    expiry = user.get("premium_expiry")
    if not expiry:
        return False
    
    return expiry > datetime.utcnow()


async def get_premium_expiry(user_id: int) -> Optional[datetime]:
    """Get premium expiry date for user"""
    db = get_db()
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        return None
    return user.get("premium_expiry")


async def add_premium(user_id: int, days: int, premium_type: str = "code") -> datetime:
    """Add premium to user. If already premium, extends from expiry date."""
    from datetime import timedelta
    db = get_db()
    
    # Get current expiry
    user = await db.users.find_one({"user_id": user_id})
    current_expiry = None
    if user and user.get("is_premium") and user.get("premium_expiry"):
        current_expiry = user.get("premium_expiry")
        if current_expiry < datetime.utcnow():
            current_expiry = None
    
    # Calculate new expiry (extend if already premium)
    if current_expiry:
        new_expiry = current_expiry + timedelta(days=days)
    else:
        new_expiry = datetime.utcnow() + timedelta(days=days)
    
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "is_premium": True,
                "premium_expiry": new_expiry,
                "premium_type": premium_type
            }
        }
    )
    return new_expiry


async def remove_premium(user_id: int) -> bool:
    """Remove premium from user"""
    db = get_db()
    result = await db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "is_premium": False,
                "premium_expiry": None,
                "premium_type": None
            }
        }
    )
    return result.modified_count > 0


async def get_premium_users_count() -> int:
    """Get count of active premium users"""
    db = get_db()
    return await db.users.count_documents({
        "is_premium": True,
        "premium_expiry": {"$gt": datetime.utcnow()}
    })


# ============= QUIZ GROUP OPERATIONS =============

async def create_quiz_group(
    creator_id: int,
    name: str,
    description: str,
    category: str,
    is_public: bool = True,
    extra_points: bool = True
) -> dict:
    """Create a new Quiz Group"""
    db = get_db()
    group_id = f"QG_{shortuuid.uuid()[:8]}"
    
    quiz_group = {
        "group_id": group_id,
        "creator_id": creator_id,
        "name": name,
        "description": description,
        "category": category,
        "is_public": is_public,
        "extra_points": extra_points,  # True = speed bonus enabled
        "total_questions": 0,
        "total_plays": 0,
        "created_at": datetime.utcnow()
    }
    
    await db.quiz_groups.insert_one(quiz_group)
    await update_user_stats(creator_id, total_quizzes_created=1)
    return quiz_group


async def get_quiz_group(group_id: str) -> Optional[dict]:
    """Get Quiz Group by ID"""
    db = get_db()
    return await db.quiz_groups.find_one({"group_id": group_id})


async def get_user_quiz_groups(user_id: int, skip: int = 0, limit: int = 10) -> List[dict]:
    """Get all Quiz Groups created by a user"""
    db = get_db()
    cursor = db.quiz_groups.find({"creator_id": user_id}).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


async def get_public_quiz_groups(category: str = None, skip: int = 0, limit: int = 10, min_plays: int = 0) -> List[dict]:
    """Get public Quiz Groups, optionally filtered by category and minimum plays"""
    db = get_db()
    query = {"is_public": True}
    if category:
        query["category"] = category
    if min_plays > 0:
        query["total_plays"] = {"$gte": min_plays}
    cursor = db.quiz_groups.find(query).sort("total_plays", -1).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


async def count_public_quiz_groups(category: str = None, min_plays: int = 0) -> int:
    """Count public Quiz Groups by category"""
    db = get_db()
    query = {"is_public": True}
    if category:
        query["category"] = category
    if min_plays > 0:
        query["total_plays"] = {"$gte": min_plays}
    return await db.quiz_groups.count_documents(query)


async def update_quiz_group_stats(group_id: str, **kwargs) -> bool:
    """Update Quiz Group statistics"""
    db = get_db()
    result = await db.quiz_groups.update_one(
        {"group_id": group_id},
        {"$inc": kwargs}
    )
    return result.modified_count > 0


async def delete_quiz_group(group_id: str) -> bool:
    """Delete a Quiz Group and all its quizzes/questions"""
    db = get_db()
    # Get all quizzes in this group
    quizzes = await db.quizzes.find({"group_id": group_id}).to_list(length=None)
    quiz_ids = [q["quiz_id"] for q in quizzes]
    
    # Delete questions
    await db.questions.delete_many({"quiz_id": {"$in": quiz_ids}})
    # Delete quizzes
    await db.quizzes.delete_many({"group_id": group_id})
    # Delete the group
    result = await db.quiz_groups.delete_one({"group_id": group_id})
    return result.deleted_count > 0


# ============= QUIZ OPERATIONS =============

async def create_quiz(
    group_id: str,
    title: str,
    creator_id: int,
    difficulty: str = "medium",
    time_limit: int = 20
) -> dict:
    """Create a new Quiz within a Quiz Group"""
    db = get_db()
    quiz_id = f"QZ_{shortuuid.uuid()[:8]}"
    
    quiz = {
        "quiz_id": quiz_id,
        "group_id": group_id,
        "title": title,
        "creator_id": creator_id,
        "difficulty": difficulty,
        "time_limit": time_limit,
        "total_questions": 0,
        "created_at": datetime.utcnow()
    }
    
    await db.quizzes.insert_one(quiz)
    await update_quiz_group_stats(group_id, total_quizzes=1)
    await update_user_stats(creator_id, total_quizzes_created=1)
    return quiz


async def get_quiz(quiz_id: str) -> Optional[dict]:
    """Get Quiz by ID"""
    db = get_db()
    return await db.quizzes.find_one({"quiz_id": quiz_id})


async def get_quizzes_in_group(group_id: str) -> List[dict]:
    """Get all quizzes in a Quiz Group"""
    db = get_db()
    cursor = db.quizzes.find({"group_id": group_id})
    return await cursor.to_list(length=None)


async def update_quiz_question_count(quiz_id: str, count: int = 1) -> bool:
    """Update question count for a quiz"""
    db = get_db()
    result = await db.quizzes.update_one(
        {"quiz_id": quiz_id},
        {"$inc": {"total_questions": count}}
    )
    return result.modified_count > 0


# ============= QUESTION OPERATIONS =============

async def add_question(
    quiz_id: str,
    group_id: str,
    question_text: str,
    options: List[str],
    correct_index: int,
    question_type: str = "mcq"
) -> dict:
    """Add a question to a quiz"""
    db = get_db()
    question_id = f"Q_{shortuuid.uuid()[:10]}"
    
    question = {
        "question_id": question_id,
        "quiz_id": quiz_id,
        "group_id": group_id,
        "question_text": question_text,
        "question_type": question_type,
        "options": options,
        "correct_index": correct_index,
        "created_at": datetime.utcnow()
    }
    
    await db.questions.insert_one(question)
    await update_quiz_question_count(quiz_id)
    await update_quiz_group_stats(group_id, total_questions=1)
    return question


async def get_quiz_questions(quiz_id: str) -> List[dict]:
    """Get all questions for a quiz"""
    db = get_db()
    cursor = db.questions.find({"quiz_id": quiz_id})
    return await cursor.to_list(length=None)


async def get_group_questions(group_id: str) -> List[dict]:
    """Get all questions for a quiz group"""
    db = get_db()
    cursor = db.questions.find({"group_id": group_id})
    return await cursor.to_list(length=None)


# ============= LEADERBOARD OPERATIONS =============

async def save_score(
    quiz_id: str,
    group_id: str,
    user_id: int,
    username: str,
    score: int,
    correct_answers: int,
    total_questions: int,
    chat_id: int = None
) -> dict:
    """Save a quiz score entry"""
    db = get_db()
    
    entry = {
        "quiz_id": quiz_id,
        "group_id": group_id,
        "user_id": user_id,
        "username": username,
        "score": score,
        "correct_answers": correct_answers,
        "total_questions": total_questions,
        "chat_id": chat_id,
        "played_at": datetime.utcnow()
    }
    
    await db.leaderboard.insert_one(entry)
    await update_user_stats(user_id, total_quizzes_played=1, total_score=score)
    await update_quiz_group_stats(group_id, total_plays=1)
    return entry


async def get_quiz_leaderboard(quiz_id: str, limit: int = 10) -> List[dict]:
    """Get leaderboard for a specific quiz"""
    db = get_db()
    cursor = db.leaderboard.find({"quiz_id": quiz_id}).sort("score", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_group_leaderboard(group_id: str, limit: int = 10) -> List[dict]:
    """Get aggregated leaderboard for a quiz group"""
    db = get_db()
    pipeline = [
        {"$match": {"group_id": group_id}},
        {"$group": {
            "_id": "$user_id",
            "username": {"$first": "$username"},
            "total_score": {"$sum": "$score"},
            "games_played": {"$count": {}}
        }},
        {"$sort": {"total_score": -1}},
        {"$limit": limit}
    ]
    cursor = db.leaderboard.aggregate(pipeline)
    return await cursor.to_list(length=limit)


async def get_chat_leaderboard(chat_id: int, limit: int = 10) -> List[dict]:
    """Get leaderboard for a specific chat/group"""
    db = get_db()
    pipeline = [
        {"$match": {"chat_id": chat_id}},
        {"$group": {
            "_id": "$user_id",
            "username": {"$first": "$username"},
            "total_score": {"$sum": "$score"},
            "games_played": {"$count": {}}
        }},
        {"$sort": {"total_score": -1}},
        {"$limit": limit}
    ]
    cursor = db.leaderboard.aggregate(pipeline)
    return await cursor.to_list(length=limit)


# ============= ACTIVE GAMES OPERATIONS =============

async def create_active_game(
    chat_id: int,
    group_id: str,
    quiz_id: str,
    started_by: int
) -> dict:
    """Create an active game session"""
    db = get_db()
    
    game = {
        "chat_id": chat_id,
        "group_id": group_id,
        "quiz_id": quiz_id,
        "started_by": started_by,
        "players": {},
        "current_question": 0,
        "current_poll_id": None,
        "scores": {},
        "started_at": datetime.utcnow()
    }
    
    await db.active_games.insert_one(game)
    return game


async def get_active_game(chat_id: int) -> Optional[dict]:
    """Get active game for a chat"""
    db = get_db()
    return await db.active_games.find_one({"chat_id": chat_id})


async def update_active_game(chat_id: int, **kwargs) -> bool:
    """Update active game data"""
    db = get_db()
    result = await db.active_games.update_one(
        {"chat_id": chat_id},
        {"$set": kwargs}
    )
    return result.modified_count > 0


async def add_player_to_game(chat_id: int, user_id: int, username: str) -> bool:
    """Add a player to an active game"""
    db = get_db()
    result = await db.active_games.update_one(
        {"chat_id": chat_id},
        {"$set": {f"players.{user_id}": {"username": username, "score": 0, "correct": 0}}}
    )
    return result.modified_count > 0


async def update_player_score(chat_id: int, user_id: int, points: int, correct: bool = True) -> bool:
    """Update a player's score in active game"""
    db = get_db()
    update = {"$inc": {f"scores.{user_id}": points}}
    if correct:
        update["$inc"][f"players.{user_id}.correct"] = 1
    result = await db.active_games.update_one(
        {"chat_id": chat_id},
        update
    )
    return result.modified_count > 0


async def delete_active_game(chat_id: int) -> bool:
    """Delete an active game session"""
    db = get_db()
    result = await db.active_games.delete_one({"chat_id": chat_id})
    return result.deleted_count > 0


# ============= STATISTICS =============

async def get_bot_stats() -> dict:
    """Get overall bot statistics (bot users only, not group participants)"""
    db = get_db()
    
    # Include users where is_bot_user is True OR field doesn't exist (legacy users)
    total_users = await db.users.count_documents({
        "$or": [
            {"is_bot_user": True},
            {"is_bot_user": {"$exists": False}}
        ]
    })
    total_quiz_groups = await db.quiz_groups.count_documents({})
    total_questions = await db.questions.count_documents({})
    total_plays = await db.leaderboard.count_documents({})
    
    return {
        "total_users": total_users,
        "total_quiz_groups": total_quiz_groups,
        "total_questions": total_questions,
        "total_plays": total_plays
    }


async def get_all_quiz_links_by_category(category: str = None) -> List[dict]:
    """Get all quiz groups (public and private) by category for admin"""
    db = get_db()
    query = {}
    if category and category != "all":
        query["category"] = category
    
    cursor = db.quiz_groups.find(query).sort("created_at", -1)
    return await cursor.to_list(length=None)


async def update_quiz_group(group_id: str, **kwargs) -> bool:
    """Update quiz group fields"""
    db = get_db()
    result = await db.quiz_groups.update_one(
        {"group_id": group_id},
        {"$set": kwargs}
    )
    return result.modified_count > 0


async def add_questions_bulk(group_id: str, questions: List[dict]) -> int:
    """Add multiple questions at once"""
    db = get_db()
    if not questions:
        return 0
    
    # Add group_id to each question
    for q in questions:
        q["group_id"] = group_id
        q["question_id"] = f"Q_{shortuuid.uuid()[:10]}"
        q["created_at"] = datetime.utcnow()
    
    result = await db.questions.insert_many(questions)
    count = len(result.inserted_ids)
    
    # Update group stats
    await db.quiz_groups.update_one(
        {"group_id": group_id},
        {"$inc": {"total_questions": count}}
    )
    
    return count


async def delete_question(question_id: str) -> bool:
    """Delete a single question"""
    db = get_db()
    result = await db.questions.delete_one({"question_id": question_id})
    return result.deleted_count > 0


# ============= FORCE SUBSCRIBE OPERATIONS =============

MAX_FORCE_SUB_CHANNELS = 4

async def add_force_sub_channel(channel_id: int, channel_title: str, channel_username: str = None) -> bool:
    """Add a force subscribe channel (max 4)"""
    db = get_db()
    
    # Check current count
    count = await db.force_sub.count_documents({})
    if count >= MAX_FORCE_SUB_CHANNELS:
        return False
    
    # Check if already exists
    existing = await db.force_sub.find_one({"channel_id": channel_id})
    if existing:
        return False
    
    channel = {
        "channel_id": channel_id,
        "channel_title": channel_title,
        "channel_username": channel_username,
        "added_at": datetime.utcnow()
    }
    
    await db.force_sub.insert_one(channel)
    return True


async def remove_force_sub_channel(channel_id: int) -> bool:
    """Remove a force subscribe channel"""
    db = get_db()
    result = await db.force_sub.delete_one({"channel_id": channel_id})
    return result.deleted_count > 0


async def get_force_sub_channels() -> List[dict]:
    """Get all force subscribe channels"""
    db = get_db()
    cursor = db.force_sub.find({})
    return await cursor.to_list(length=MAX_FORCE_SUB_CHANNELS)


async def get_force_sub_count() -> int:
    """Get count of force subscribe channels"""
    db = get_db()
    return await db.force_sub.count_documents({})


# ============= REDEEM CODE OPERATIONS =============

async def generate_redeem_code(days: int, created_by: int) -> str:
    """Generate a new redeem code"""
    import secrets
    import string
    
    db = get_db()
    
    # Generate unique code
    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))
    
    await db.redeem_codes.insert_one({
        "code": code,
        "duration_days": days,
        "created_by": created_by,
        "created_at": datetime.utcnow(),
        "used_by": None,
        "used_at": None,
        "is_used": False
    })
    
    return code


async def generate_bulk_codes(days: int, count: int, created_by: int) -> List[str]:
    """Generate multiple redeem codes"""
    codes = []
    for _ in range(count):
        code = await generate_redeem_code(days, created_by)
        codes.append(code)
    return codes


async def get_redeem_code(code: str) -> Optional[dict]:
    """Get redeem code details"""
    db = get_db()
    return await db.redeem_codes.find_one({"code": code.upper()})


async def use_redeem_code(code: str, user_id: int) -> bool:
    """Mark redeem code as used"""
    db = get_db()
    result = await db.redeem_codes.update_one(
        {"code": code.upper(), "is_used": False},
        {
            "$set": {
                "used_by": user_id,
                "used_at": datetime.utcnow(),
                "is_used": True
            }
        }
    )
    return result.modified_count > 0


async def get_unused_codes_count() -> int:
    """Get count of unused redeem codes"""
    db = get_db()
    return await db.redeem_codes.count_documents({"is_used": False})


async def get_all_unused_codes() -> List[dict]:
    """Get all unused redeem codes"""
    db = get_db()
    cursor = db.redeem_codes.find({"is_used": False}).sort("created_at", -1)
    return await cursor.to_list(length=100)


# ============= PAYMENT TRANSACTIONS =============

async def create_payment(
    user_id: int,
    amount: float,
    currency: str,
    method: str,
    duration_days: int,
    invoice_id: str = None
) -> str:
    """Create a payment transaction"""
    db = get_db()
    
    transaction_id = f"TXN_{shortuuid.uuid()[:10]}"
    
    await db.payments.insert_one({
        "transaction_id": transaction_id,
        "user_id": user_id,
        "amount": amount,
        "currency": currency,
        "method": method,  # crypto, upi, code
        "duration_days": duration_days,
        "invoice_id": invoice_id,
        "status": "pending",
        "created_at": datetime.utcnow(),
        "completed_at": None
    })
    
    return transaction_id


async def complete_payment(transaction_id: str) -> bool:
    """Mark payment as completed"""
    db = get_db()
    result = await db.payments.update_one(
        {"transaction_id": transaction_id},
        {
            "$set": {
                "status": "completed",
                "completed_at": datetime.utcnow()
            }
        }
    )
    return result.modified_count > 0


async def get_payment(transaction_id: str) -> Optional[dict]:
    """Get payment by transaction ID"""
    db = get_db()
    return await db.payments.find_one({"transaction_id": transaction_id})


async def get_payment_by_invoice(invoice_id: str) -> Optional[dict]:
    """Get payment by CryptoPay invoice ID"""
    db = get_db()
    return await db.payments.find_one({"invoice_id": invoice_id})


async def get_user_quiz_count(user_id: int) -> int:
    """Get count of quizzes created by user"""
    db = get_db()
    return await db.quiz_groups.count_documents({"creator_id": user_id})


