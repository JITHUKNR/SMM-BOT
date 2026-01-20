import os
import logging
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from pymongo import MongoClient

# --- CONFIGURATION ---
TOKEN = os.environ.get('TOKEN')
MONGO_URI = os.environ.get('MONGO_URI')
SMM_API_URL = os.environ.get('SMM_API_URL') 
SMM_API_KEY = os.environ.get('SMM_API_KEY') 
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
PORT = int(os.environ.get('PORT', 8443))

# ✅ ADMIN ID
ADMIN_ID = 7567364364 

# ✅ REWARDS SETTINGS
REFERRAL_BONUS = 1.0  
DAILY_BONUS_AMOUNT = 0.50 

# ✅ QR CODE FILE ID
QR_CODE_FILE_ID = "AgACAgQAAxkBAAI0UGluU4Bg0onFlgUgedyzb0RO0uYCAALYDGsbpjJwU0ieEncrdtqiAQADAgADeAADOAQ"

# ✅ UPI ID
MY_UPI_ID = "7567364364@ybl" 

# --- SERVICE LIST ---
SERVICES = {
    "11142": {"name": "Instagram Likes (Fast) ❤️", "price": 30, "cat": "ig"},
    "11377": {"name": "IG Followers (Cheap) 👤", "price": 100, "cat": "ig"},
    "363":   {"name": "IG Followers (Non-Drop) ⭐", "price": 400, "cat": "ig"},
    "8965":  {"name": "Telegram Members 🇮🇳", "price": 40, "cat": "tg"},
    "7939":  {"name": "YouTube Views ▶️", "price": 180, "cat": "yt"}
}

# --- DATABASE ---
client = MongoClient(MONGO_URI)
db = client["SMMBot"]
users_col = db["users"]

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- KEYBOARDS ---
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Check Balance", callback_data='balance'),
         InlineKeyboardButton("📋 Services", callback_data='categories')],
        [InlineKeyboardButton("💳 Add Funds (QR)", callback_data='add_funds_request'),
         InlineKeyboardButton("🎁 Daily Bonus", callback_data='daily_bonus')],
        [InlineKeyboardButton("🤝 Invite & Earn", callback_data='invite_link')]
    ]
    return InlineKeyboardMarkup(keyboard)

def category_keyboard():
    keyboard = [
        [InlineKeyboardButton("📸 Instagram", callback_data='cat_ig'),
         InlineKeyboardButton("✈️ Telegram", callback_data='cat_tg')],
        [InlineKeyboardButton("▶️ YouTube", callback_data='cat_yt')],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    existing_user = users_col.find_one({"user_id": user_id})

    if not existing_user:
        referrer_id = None
        if context.args:
            try:
                referrer_id = int(context.args[0])
                if referrer_id != user_id:
                    referrer = users_col.find_one({"user_id": referrer_id})
                    if referrer:
                        users_col.update_one({"user_id": referrer_id}, {"$inc": {"balance": REFERRAL_BONUS}})
                        await context.bot.send_message(referrer_id, f"🎉 **New Referral!**\n💰 You earned ₹{REFERRAL_BONUS}!")
            except ValueError:
                pass

        users_col.insert_one({"user_id": user_id, "balance": 0, "mode": "normal", "referred_by": referrer_id})
        await update.message.reply_text(f"👋 **Welcome, {user.first_name}!**")
    else:
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})

    await update.message.reply_text(
        "🚀 **Premium SMM Store**\nBoost your social media instantly!",
        reply_markup=main_menu_keyboard(),
        parse_mode='Markdown'
    )

# 🔥 BROADCAST FEATURE (NEW) 🔥
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Security: Only Admin can use
    if update.effective_user.id != ADMIN_ID:
        return

    # Check if message is provided
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("❌ Usage: `/broadcast Your Message Here`")
        return

    status_msg = await update.message.reply_text("⏳ **Broadcasting started...**")

    # Get all users
    users = users_col.find({}, {"user_id": 1})
    success_count = 0
    fail_count = 0

    for user in users:
        try:
            await context.bot.send_message(chat_id=user['user_id'], text=f"📢 **ANNOUNCEMENT**\n\n{message}")
            success_count += 1
        except Exception:
            fail_count += 1 # Blocked users or errors

    await status_msg.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"📩 Sent to: {success_count}\n"
        f"🚫 Failed: {fail_count}"
    )

# --- BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == 'main_menu':
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})
        await query.edit_message_text("👇 **Main Menu**", reply_markup=main_menu_keyboard(), parse_mode='Markdown')

    elif data == 'balance':
        user_data = users_col.find_one({"user_id": user_id})
        bal = user_data.get("balance", 0)
        await query.edit_message_text(f"💰 **Balance:** ₹{round(bal, 2)}\n\nUse 'Add Funds' or 'Daily Bonus' to earn.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]), parse_mode='Markdown')

    elif data == 'categories':
        await query.edit_message_text("📋 **Select Category:**", reply_markup=category_keyboard(), parse_mode='Markdown')

    # DAILY BONUS
    elif data == 'daily_bonus':
        user_data = users_col.find_one({"user_id": user_id})
        last_bonus = user_data.get("last_bonus")
        now = datetime.now()
        
        if last_bonus:
            if isinstance(last_bonus, str): last_bonus_time = datetime.fromisoformat(last_bonus)
            else: last_bonus_time = last_bonus
            time_diff = now - last_bonus_time
            if time_diff < timedelta(hours=24):
                wait_time = timedelta(hours=24) - time_diff
                hours, remainder = divmod(wait_time.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                await query.edit_message_text(f"⏳ **Wait Please!**\nCome back in: {hours}h {minutes}m", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]), parse_mode='Markdown')
                return

        users_col.update_one({"user_id": user_id}, {"$inc": {"balance": DAILY_BONUS_AMOUNT}, "$set": {"last_bonus": now}})
        await query.edit_message_text(f"🎉 **Daily Bonus Claimed!**\n💰 Added: **₹{DAILY_BONUS_AMOUNT}**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]), parse_mode='Markdown')

    elif data == 'invite_link':
        bot_username = context.bot.username
        link = f"https://t.me/{bot_username}?start={user_id}"
        text = f"🤝 **Invite & Earn!**\nLink: `{link}`\n💰 Reward: ₹{REFERRAL_BONUS} per user!"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]), parse_mode='Markdown')

    elif data == 'add_funds_request':
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "waiting_payment_proof"}})
        try:
            await query.message.reply_photo(photo=QR_CODE_FILE_ID, caption=f"💳 **Add Funds**\nUPI: `{MY_UPI_ID}`\nSend Screenshot.", parse_mode='Markdown')
        except:
            await query.message.reply_text(f"UPI: `{MY_UPI_ID}`\nSend Screenshot.", parse_mode='Markdown')

    elif data.startswith('approve_'):
        _, target_id, amount = data.split('_')
        users_col.update_one({"user_id": int(target_id)}, {"$inc": {"balance": float(amount)}})
        await query.edit_message_text(f"✅ Approved ₹{amount}")
        await context.bot.send_message(int(target_id), f"✅ **Deposit Confirmed:** ₹{amount} added!")

    elif data.startswith('reject_'):
        target_id = int(data.split('_')[1])
        await query.edit_message_text("❌ Rejected")
        await context.bot.send_message(target_id, "❌ Payment Rejected.")

    elif data.startswith('cat_'):
        cat = data.split('_')[1]
        keyboard = [[InlineKeyboardButton(f"{info['name']} - ₹{info['price']}", callback_data=f"srv_{s_id}")] for s_id, info in SERVICES.items() if info['cat'] == cat]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='categories')])
        await query.edit_message_text("👇 **Select Service:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith('srv_'):
        s_id = data.split('_')[1]
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "waiting_for_link", "temp_service": s_id}})
        await query.edit_message_text(f"✅ Selected: {SERVICES[s_id]['name']}\n🔗 **Step 1:** Send Link now.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data='main_menu')]]), parse_mode='Markdown')

# --- MESSAGE HANDLER ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    is_photo = bool(update.message.photo)
    text = update.message.caption if is_photo else update.message.text

    if user_id == ADMIN_ID and is_photo:
        user_data = users_col.find_one({"user_id": user_id})
        if user_data.get("mode") == "normal": 
            await update.message.reply_text(f"🆔 File ID:\n`{update.message.photo[-1].file_id}`", parse_mode='Markdown')
            return

    user_data = users_col.find_one({"user_id": user_id})
    if not user_data: return
    mode = user_data.get("mode", "normal")

    if mode == "waiting_payment_proof" and is_photo:
        await update.message.reply_text("⏳ Proof Sent!")
        keyboard = [[InlineKeyboardButton(f"✅ ₹{amt}", callback_data=f'approve_{user_id}_{amt}') for amt in [10, 50, 100, 500]], [InlineKeyboardButton("❌ Reject", callback_data=f'reject_{user_id}')]]
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, caption=f"🔔 **Payment!** User: {user.first_name}", reply_markup=InlineKeyboardMarkup(keyboard))
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})

    elif not is_photo and text:
        if mode == "waiting_for_link":
            users_col.update_one({"user_id": user_id}, {"$set": {"mode": "waiting_for_quantity", "temp_link": text}})
            await update.message.reply_text("✅ Link Saved! 🔢 **Step 2:** Quantity?")
        elif mode == "waiting_for_quantity":
            if not text.isdigit(): return await update.message.reply_text("⚠️ Numbers only!")
            quantity = int(text)
            service_id, link = user_data.get("temp_service"), user_data.get("temp_link")
            total_cost = (SERVICES[service_id]['price'] / 1000) * quantity
            
            if user_data.get("balance", 0) < total_cost:
                await update.message.reply_text(f"❌ Low Balance! Need: ₹{total_cost}")
            else:
                res = requests.post(SMM_API_URL, data={'key': SMM_API_KEY, 'action': 'add', 'service': service_id, 'link': link, 'quantity': quantity}).json()
                if 'order' in res:
                    users_col.update_one({"user_id": user_id}, {"$inc": {"balance": -total_cost}, "$set": {"mode": "normal"}})
                    await update.message.reply_text(f"✅ **Ordered!** ID: `{res['order']}`\n💰 Cost: ₹{total_cost}")
                    await context.bot.send_message(ADMIN_ID, f"🔔 Sale! ₹{total_cost} (User: {user_id})")
                else:
                    await update.message.reply_text(f"❌ Failed: {res.get('error')}")
            users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})

def main():
    if not TOKEN: return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast)) # New Command Added
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")

if __name__ == "__main__":
    main()
