"""
Premium Subscription Handler - CryptoPay, UPI, Redeem Codes
"""
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

from config import (
    ADMIN_IDS, PREMIUM_PRICES, CRYPTOBOT_TOKEN, UPI_ID,
    FREE_MAX_QUIZZES, FREE_MAX_QUESTIONS, PREMIUM_MAX_QUESTIONS
)
from database.models import (
    is_premium_user, get_premium_expiry, add_premium, get_user,
    get_redeem_code, use_redeem_code, create_payment, get_payment_by_invoice,
    complete_payment, get_user_quiz_count
)
from utils.helpers import escape_html


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def premium_plans_keyboard(is_crypto: bool = True):
    """Keyboard for selecting premium plan"""
    keyboard = []
    
    for plan_id, plan in PREMIUM_PRICES.items():
        days = plan["days"]
        inr = plan["inr"]
        usd = plan["usd"]
        
        label = f"{plan_id.capitalize()} - ₹{inr} / ${usd}"
        keyboard.append([
            InlineKeyboardButton(label, callback_data=f"buyplan_{plan_id}")
        ])
    
    keyboard.append([InlineKeyboardButton("« Back", callback_data="premium_back")])
    return InlineKeyboardMarkup(keyboard)


def payment_method_keyboard(plan_id: str):
    """Keyboard for selecting payment method"""
    keyboard = [
        [InlineKeyboardButton("💳 Crypto (USDT/TON/BTC)", callback_data=f"paycrypto_{plan_id}")],
        [InlineKeyboardButton("📱 UPI / PayPal", callback_data=f"payupi_{plan_id}")],
        [InlineKeyboardButton("« Back", callback_data="premium_plans")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium status and plans"""
    user = update.effective_user
    
    is_premium = await is_premium_user(user.id)
    expiry = await get_premium_expiry(user.id)
    quiz_count = await get_user_quiz_count(user.id)
    
    if is_premium and expiry:
        expiry_str = expiry.strftime("%d %b %Y, %H:%M UTC")
        text = f"""💎 <b>Premium Status</b>

✅ You are a <b>Premium</b> user!

📅 Expires: <b>{expiry_str}</b>

<b>Your Benefits:</b>
• Unlimited quizzes
• Up to {PREMIUM_MAX_QUESTIONS} questions per quiz
• Speed bonus scoring
• Custom time limits
• Quiz analytics
• No ads

Use /redeem to extend your premium!"""
    else:
        text = f"""💎 <b>Premium Plans</b>

You are currently on the <b>Free</b> plan.

<b>Free Plan Limits:</b>
• Max {FREE_MAX_QUIZZES} quizzes ({quiz_count}/{FREE_MAX_QUIZZES} used)
• Max {FREE_MAX_QUESTIONS} questions per quiz
• No speed bonus
• Basic categories only

<b>Premium Features:</b>
✨ Unlimited quizzes
✨ Up to {PREMIUM_MAX_QUESTIONS} questions per quiz
✨ Speed bonus scoring
✨ Custom time limits (10s, 20s, 30s, 60s)
✨ Quiz analytics
✨ No ads

Choose a plan to upgrade:"""
    
    keyboard = []
    for plan_id, plan in PREMIUM_PRICES.items():
        label = f"💎 {plan_id.capitalize()} - ₹{plan['inr']} / ${plan['usd']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"buyplan_{plan_id}")])
    
    if not is_premium:
        keyboard.append([InlineKeyboardButton("🎁 Redeem Code", callback_data="redeem_prompt")])
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def buy_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plan selection"""
    query = update.callback_query
    await query.answer()
    
    plan_id = query.data.replace("buyplan_", "")
    
    if plan_id not in PREMIUM_PRICES:
        await query.answer("Invalid plan!", show_alert=True)
        return
    
    plan = PREMIUM_PRICES[plan_id]
    
    text = f"""💎 <b>{plan_id.capitalize()} Plan</b>

📅 Duration: {plan['days']} days
💰 Price: ₹{plan['inr']} / ${plan['usd']}

Select payment method:"""
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=payment_method_keyboard(plan_id)
    )


async def pay_crypto_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle CryptoPay payment"""
    query = update.callback_query
    await query.answer()
    
    plan_id = query.data.replace("paycrypto_", "")
    user = query.from_user
    
    if plan_id not in PREMIUM_PRICES:
        await query.answer("Invalid plan!", show_alert=True)
        return
    
    plan = PREMIUM_PRICES[plan_id]
    
    if not CRYPTOBOT_TOKEN:
        await query.edit_message_text(
            "❌ Crypto payments are not configured.\n\n"
            "Please use UPI/PayPal instead.",
            reply_markup=payment_method_keyboard(plan_id)
        )
        return
    
    # Create CryptoPay invoice
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "asset": "USDT",
                "amount": str(plan["usd"]),
                "description": f"Quiz Master Bot - {plan_id.capitalize()} Premium",
                "hidden_message": f"Thank you for purchasing {plan_id} premium!",
                "paid_btn_name": "callback",
                "paid_btn_url": f"https://t.me/{context.bot.username}",
                "payload": f"{user.id}_{plan_id}_{plan['days']}"
            }
            
            headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
            
            async with session.post(
                "https://pay.crypt.bot/api/createInvoice",
                json=payload,
                headers=headers
            ) as resp:
                data = await resp.json()
                
                if data.get("ok"):
                    invoice = data["result"]
                    invoice_url = invoice["bot_invoice_url"]
                    invoice_id = str(invoice["invoice_id"])
                    
                    # Save payment
                    await create_payment(
                        user_id=user.id,
                        amount=plan["usd"],
                        currency="USDT",
                        method="crypto",
                        duration_days=plan["days"],
                        invoice_id=invoice_id
                    )
                    
                    keyboard = [
                        [InlineKeyboardButton("💳 Pay Now", url=invoice_url)],
                        [InlineKeyboardButton("✅ I've Paid", callback_data=f"checkpay_{invoice_id}")],
                        [InlineKeyboardButton("« Back", callback_data=f"buyplan_{plan_id}")]
                    ]
                    
                    await query.edit_message_text(
                        f"💳 <b>CryptoPay Invoice Created</b>\n\n"
                        f"Plan: {plan_id.capitalize()}\n"
                        f"Amount: ${plan['usd']} USDT\n\n"
                        f"Click 'Pay Now' to complete payment.\n"
                        f"After payment, click 'I've Paid' to activate premium.",
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await query.edit_message_text(
                        f"❌ Failed to create invoice: {data.get('error', 'Unknown error')}\n\n"
                        f"Please try again or use UPI.",
                        reply_markup=payment_method_keyboard(plan_id)
                    )
    except Exception as e:
        await query.edit_message_text(
            f"❌ Error creating invoice. Please try again.\n\n"
            f"Or use UPI payment instead.",
            reply_markup=payment_method_keyboard(plan_id)
        )


async def check_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if CryptoPay invoice is paid"""
    query = update.callback_query
    user = query.from_user
    
    invoice_id = query.data.replace("checkpay_", "")
    
    if not CRYPTOBOT_TOKEN:
        await query.answer("Payment system error!", show_alert=True)
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
            
            async with session.get(
                f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}",
                headers=headers
            ) as resp:
                data = await resp.json()
                
                if data.get("ok") and data["result"]["items"]:
                    invoice = data["result"]["items"][0]
                    status = invoice["status"]
                    
                    if status == "paid":
                        # Get payment from DB
                        payment = await get_payment_by_invoice(invoice_id)
                        
                        if payment and payment["status"] != "completed":
                            # Add premium
                            days = payment["duration_days"]
                            new_expiry = await add_premium(user.id, days, "crypto")
                            await complete_payment(payment["transaction_id"])
                            
                            await query.edit_message_text(
                                f"✅ <b>Payment Successful!</b>\n\n"
                                f"💎 Premium activated for {days} days\n"
                                f"📅 Expires: {new_expiry.strftime('%d %b %Y, %H:%M UTC')}\n\n"
                                f"Thank you for your purchase! 🎉",
                                parse_mode=ParseMode.HTML
                            )
                        elif payment and payment["status"] == "completed":
                            await query.answer("✅ Already activated!", show_alert=True)
                        else:
                            await query.answer("Payment not found!", show_alert=True)
                    elif status == "expired":
                        await query.answer("❌ Invoice expired! Please create a new one.", show_alert=True)
                    else:
                        await query.answer(f"⏳ Payment pending. Status: {status}", show_alert=True)
                else:
                    await query.answer("Could not check payment status.", show_alert=True)
    except Exception as e:
        await query.answer("Error checking payment!", show_alert=True)


async def pay_upi_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show UPI payment details"""
    query = update.callback_query
    await query.answer()
    
    plan_id = query.data.replace("payupi_", "")
    user = query.from_user
    
    if plan_id not in PREMIUM_PRICES:
        await query.answer("Invalid plan!", show_alert=True)
        return
    
    plan = PREMIUM_PRICES[plan_id]
    
    upi_id = UPI_ID if UPI_ID else "your-upi@bank"
    
    text = f"""📱 <b>UPI / PayPal Payment</b>

Plan: <b>{plan_id.capitalize()}</b>
Amount: <b>₹{plan['inr']}</b> or <b>${plan['usd']}</b>

<b>UPI ID:</b>
<code>{upi_id}</code>

<b>Instructions:</b>
1. Pay ₹{plan['inr']} to the UPI ID above
2. Take a screenshot of payment
3. Send screenshot to admin with your User ID:
   <code>{user.id}</code>

<b>For PayPal:</b>
Contact admin with payment proof.

Admin will activate your premium within 24 hours."""
    
    keyboard = [
        [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/tataa_sumo")],
        [InlineKeyboardButton("« Back", callback_data=f"buyplan_{plan_id}")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /redeem command"""
    user = update.effective_user
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "🎁 <b>Redeem Code</b>\n\n"
            "Usage: <code>/redeem YOUR_CODE</code>\n\n"
            "Enter your premium code to activate!",
            parse_mode=ParseMode.HTML
        )
        return
    
    code = context.args[0].strip().upper()
    
    # Get code details
    code_data = await get_redeem_code(code)
    
    if not code_data:
        await update.message.reply_text("❌ Invalid code!")
        return
    
    if code_data.get("is_used"):
        await update.message.reply_text("❌ This code has already been used!")
        return
    
    # Use code and add premium
    days = code_data["duration_days"]
    
    # Mark code as used
    success = await use_redeem_code(code, user.id)
    
    if not success:
        await update.message.reply_text("❌ Could not redeem code. Please try again.")
        return
    
    # Add premium (extends if already premium)
    new_expiry = await add_premium(user.id, days, "code")
    
    await update.message.reply_text(
        f"✅ <b>Code Redeemed Successfully!</b>\n\n"
        f"💎 Premium added for {days} days\n"
        f"📅 New expiry: {new_expiry.strftime('%d %b %Y, %H:%M UTC')}\n\n"
        f"Enjoy your premium features! 🎉",
        parse_mode=ParseMode.HTML
    )


async def redeem_prompt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt for redeem code"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🎁 <b>Redeem Code</b>\n\n"
        "Send the /redeem command with your code:\n\n"
        "<code>/redeem YOUR_CODE_HERE</code>",
        parse_mode=ParseMode.HTML
    )


async def premium_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to premium menu"""
    query = update.callback_query
    await query.answer()
    await query.message.delete()


def get_premium_handlers():
    """Return list of handlers for premium module"""
    return [
        CommandHandler("premium", premium_command),
        CommandHandler("redeem", redeem_command),
        CallbackQueryHandler(buy_plan_callback, pattern="^buyplan_"),
        CallbackQueryHandler(pay_crypto_callback, pattern="^paycrypto_"),
        CallbackQueryHandler(check_payment_callback, pattern="^checkpay_"),
        CallbackQueryHandler(pay_upi_callback, pattern="^payupi_"),
        CallbackQueryHandler(redeem_prompt_callback, pattern="^redeem_prompt$"),
        CallbackQueryHandler(premium_back_callback, pattern="^premium_back$|^premium_plans$"),
    ]
