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

# ✅ NEW QR CODE FILE ID (Updated)
QR_CODE_FILE_ID = "AgACAgQAAxkBAAI4X2lu6iQO7RNZ9FwOGpQ0u6XuHfc6AAK_C2sbxlR5U0SPAi2SVbwnAQADAgADeAADOAQ"

# ✅ NEW UPI ID (Updated)
MY_UPI_ID = "abhiixz@ybl" 

# --- SERVICE LIST ---
SERVICES = {
    # --- INSTAGRAM ---
    "8311":  {"name": "Insta Views (Super Fast) 🚀", "price": 10, "cat": "ig"},
    "11139": {"name": "Insta Reels Views 🎬", "price": 10, "cat": "ig"},
    "11467": {"name": "Insta Likes (High Quality) ❤️", "price": 25, "cat": "ig"},
    "360":   {"name": "Insta Likes (Indian) 🇮🇳", "price": 60, "cat": "ig"}, 
    "9759":  {"name": "IG Followers (Super Cheap) 📉", "price": 90, "cat": "ig"}, 
    "11377": {"name": "IG Followers (High Quality) 👤", "price": 120, "cat": "ig"},
    "11381": {"name": "IG Followers (30 Days Refill) ⭐", "price": 190, "cat": "ig"},
    
    # --- TELEGRAM ---
    "11144": {"name": "Telegram Members (Cheapest) 🔥", "price": 20, "cat": "tg"},
    "8965":  {"name": "Telegram Members (Indian) 🇮🇳", "price": 50, "cat": "tg"}, 
    "10690": {"name": "Telegram Members (No Drop) ⭐", "price": 90, "cat": "tg"},
    "11303": {"name": "Telegram Post Views 👁️", "price": 10, "cat": "tg"},
    
    # --- YOUTUBE ---
    "10051": {"name": "YouTube Views (Lifetime) ▶️", "price": 100, "cat": "yt"},
    "6680":  {"name": "YouTube Likes 👍", "price": 50, "cat": "yt"}, 
    
    # --- FACEBOOK ---
    "138":   {"name": "Facebook Video Views 🔵", "price": 20, "cat": "fb"},
    "10522": {"name": "Facebook Post Likes 👍", "price": 40, "cat": "fb"},
    
    # --- TWITTER / X ---
    "11222": {"name": "X (Twitter) Video Views 🐦", "price": 10, "cat": "tw"}
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
        [InlineKeyboardButton("▶️ YouTube", callback_data='cat_yt'),
         InlineKeyboardButton("🔵 Facebook", callback_data='cat_fb')],
        [InlineKeyboardButton("🐦 Twitter (X)", callback_data='cat_tw')],
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
            except ValueError: pass

        users_col.insert_one({"user_id": user_id, "balance": 0, "mode": "normal", "referred_by": referrer_id})
        await update.message.reply_text(f"👋 **Welcome, {user.first_name}!**")
    else:
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})

    await update.message.reply_text("🚀 **Premium SMM Store**\nBoost your social media instantly!", reply_markup=main_menu_keyboard(), parse_mode='Markdown')

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    message = " ".join(context.args)
    if not message: return await update.message.reply_text("Usage: `/broadcast message`")
    users = users_col.find({}, {"user_id": 1})
    count = 0
    for user in users:
        try:
            await context.bot.send_message(user['user_id'], f"📢 **ANNOUNCEMENT**\n\n{message}")
            count += 1
        except: pass
    await update.message.reply_text(f"✅ Sent to {count} users.")

# --- HANDLERS ---
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
        await query.edit_message_text(f"💰 **Balance:** ₹{round(bal, 2)}\n\nUse 'Add Funds' or 'Invite' to earn.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]), parse_mode='Markdown')

    elif data == 'categories':
        await query.edit_message_text("📋 **Select Category:**", reply_markup=category_keyboard(), parse_mode='Markdown')

    elif data == 'daily_bonus':
        user_data = users_col.find_one({"user_id": user_id})
        last_bonus = user_data.get("last_bonus")
        now = datetime.now()
        if last_bonus:
            if isinstance(last_bonus, str): last_bonus_time = datetime.fromisoformat(last_bonus)
            else: last_bonus_time = last_bonus
            if now - last_bonus_time < timedelta(hours=24):
                return await query.edit_message_text("⏳ **Wait 24 Hours!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]), parse_mode='Markdown')
        
        users_col.update_one({"user_id": user_id}, {"$inc": {"balance": DAILY_BONUS_AMOUNT}, "$set": {"last_bonus": now}})
        await query.edit_message_text(f"🎉 **Bonus Claimed!** Added ₹{DAILY_BONUS_AMOUNT}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]), parse_mode='Markdown')

    elif data == 'invite_link':
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        await query.edit_message_text(f"🤝 **Invite Link:**\n`{link}`\n\nReward: ₹{REFERRAL_BONUS}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]), parse_mode='Markdown')

    elif data == 'add_funds_request':
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "waiting_payment_proof"}})
        try: await query.message.reply_photo(photo=QR_CODE_FILE_ID, caption=f"💳 **UPI:** `{MY_UPI_ID}`\nSend Screenshot.", parse_mode='Markdown')
        except: await query.message.reply_text(f"UPI: `{MY_UPI_ID}`\nSend Screenshot.", parse_mode='Markdown')

    elif data.startswith('approve_'):
        _, tid, amt = data.split('_')
        users_col.update_one({"user_id": int(tid)}, {"$inc": {"balance": float(amt)}})
        await query.edit_message_text(f"✅ Approved ₹{amt}")
        await context.bot.send_message(int(tid), f"✅ **Credited:** ₹{amt}")

    elif data.startswith('reject_'):
        tid = int(data.split('_')[1])
        await query.edit_message_text("❌ Rejected")
        await context.bot.send_message(tid, "❌ Payment Rejected")

    elif data.startswith('cat_'):
        cat = data.split('_')[1]
        keyboard = [[InlineKeyboardButton(f"{info['name']} - ₹{info['price']}", callback_data=f"srv_{s_id}")] for s_id, info in SERVICES.items() if info['cat'] == cat]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='categories')])
        await query.edit_message_text("👇 **Select Service:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith('srv_'):
        s_id = data.split('_')[1]
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "waiting_for_link", "temp_service": s_id}})
        await query.edit_message_text(f"✅ Selected: {SERVICES[s_id]['name']}\n🔗 **Step 1:** Send Link.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data='main_menu')]]), parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    is_photo = bool(update.message.photo)
    text = update.message.caption if is_photo else update.message.text

    if user_id == ADMIN_ID and is_photo:
        user_data = users_col.find_one({"user_id": user_id})
        if user_data and user_data.get("mode") == "normal":
            return await update.message.reply_text(f"🆔 File ID:\n`{update.message.photo[-1].file_id}`", parse_mode='Markdown')

    user_data = users_col.find_one({"user_id": user_id})
    if not user_data: return
    mode = user_data.get("mode", "normal")

    if mode == "waiting_payment_proof" and is_photo:
        await update.message.reply_text("⏳ Proof Sent!")
        keyboard = [[InlineKeyboardButton(f"✅ ₹{a}", callback_data=f'approve_{user_id}_{a}') for a in [10, 50, 100, 500]], [InlineKeyboardButton("❌ Reject", callback_data=f'reject_{user_id}')]]
        await context.bot.send_photo(ADMIN_ID, update.message.photo[-1].file_id, caption=f"🔔 Payment from {user.first_name}", reply_markup=InlineKeyboardMarkup(keyboard))
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})

    elif not is_photo and text:
        if mode == "waiting_for_link":
            users_col.update_one({"user_id": user_id}, {"$set": {"mode": "waiting_for_quantity", "temp_link": text}})
            await update.message.reply_text("✅ Link Saved! 🔢 **Step 2:** Quantity?")
        elif mode == "waiting_for_quantity":
            if not text.isdigit(): return await update.message.reply_text("⚠️ Numbers only!")
            qty = int(text)
            s_id, link = user_data.get("temp_service"), user_data.get("temp_link")
            cost = (SERVICES[s_id]['price'] / 1000) * qty
            if user_data.get("balance", 0) < cost:
                await update.message.reply_text(f"❌ Low Balance! Need: ₹{cost}")
            else:
                res = requests.post(SMM_API_URL, data={'key': SMM_API_KEY, 'action': 'add', 'service': s_id, 'link': link, 'quantity': qty}).json()
                if 'order' in res:
                    users_col.update_one({"user_id": user_id}, {"$inc": {"balance": -cost}, "$set": {"mode": "normal"}})
                    await update.message.reply_text(f"✅ **Ordered!** ID: `{res['order']}`\n💰 Cost: ₹{cost}")
                    await context.bot.send_message(ADMIN_ID, f"🔔 Sale! ₹{cost}")
                else:
                    await update.message.reply_text(f"❌ Failed: {res.get('error')}")
            users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})

def main():
    if not TOKEN: return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")

if __name__ == "__main__":
    main()
