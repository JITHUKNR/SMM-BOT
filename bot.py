import os
import logging
import requests
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

# ✅ ADMIN ID (നിങ്ങളുടെ ID)
ADMIN_ID = 7567364364 

# --- SERVICE LIST ---
SERVICES = {
    "11142": {"name": "Instagram Likes (Fast) ❤️", "price": 30, "cat": "ig"},
    "11377": {"name": "IG Followers (Cheap) 👤", "price": 100, "cat": "ig"},
    "363":   {"name": "IG Followers (Non-Drop 365 Days) ⭐", "price": 400, "cat": "ig"},
    "8965":  {"name": "Telegram Members (Indian) 🇮🇳", "price": 40, "cat": "tg"},
    "7939":  {"name": "YouTube Views (Lifetime) ▶️", "price": 180, "cat": "yt"}
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
        [InlineKeyboardButton("📞 Support / Add Funds", callback_data='support')]
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

def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]])

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users_col.update_one({"user_id": user.id}, {"$setOnInsert": {"balance": 0}}, upsert=True)
    
    await update.message.reply_text(
        f"👋 **Hello, {user.first_name}!**\n\n"
        "Welcome to the **Premium SMM Store**. 🚀\n"
        "Boost your social media instantly!\n\n"
        "👇 **Select an option below:**",
        reply_markup=main_menu_keyboard(),
        parse_mode='Markdown'
    )

# --- BUTTON HANDLER (The Magic) ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data

    # 1. Main Menu
    if data == 'main_menu':
        await query.edit_message_text(
            "👇 **Main Menu**\nSelect an option below:",
            reply_markup=main_menu_keyboard(),
            parse_mode='Markdown'
        )

    # 2. Check Balance
    elif data == 'balance':
        user_id = query.from_user.id
        user_data = users_col.find_one({"user_id": user_id})
        bal = user_data.get("balance", 0) if user_data else 0
        await query.edit_message_text(
            f"💰 **Your Wallet Balance:** ₹{round(bal, 2)}\n\n"
            "To add funds, contact Admin.",
            reply_markup=back_button(),
            parse_mode='Markdown'
        )

    # 3. Support
    elif data == 'support':
        await query.edit_message_text(
            "📞 **Support & Add Funds**\n\n"
            "To add money to your wallet, please message the admin:\n"
            "👤 **Admin:** @YourUsernameHere\n\n"
            "_(Send payment screenshot and your User ID)_",
            reply_markup=back_button(),
            parse_mode='Markdown'
        )

    # 4. Show Categories
    elif data == 'categories':
        await query.edit_message_text(
            "📋 **Select a Category:**",
            reply_markup=category_keyboard(),
            parse_mode='Markdown'
        )

    # 5. Show Services (Based on Category)
    elif data.startswith('cat_'):
        cat = data.split('_')[1]
        msg = "📋 **Available Services:**\n\n"
        
        for s_id, info in SERVICES.items():
            if info['cat'] == cat:
                msg += f"🆔 **ID: {s_id}**\n📌 {info['name']}\n💵 Price: ₹{info['price']} / 1000\n\n"
        
        msg += "⚠️ **To Order:** Copy the ID and send:\n`/order <id> <link> <quantity>`"
        
        # Add a "Back to Categories" button
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='categories')]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- ORDER COMMAND (Same as before) ---
async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = users_col.find_one({"user_id": user_id})
    current_bal = user_data.get("balance", 0)

    try:
        service_id = context.args[0]
        link = context.args[1]
        quantity = int(context.args[2])
    except (IndexError, ValueError):
        await update.message.reply_text("❌ **Usage:** `/order <service_id> <link> <quantity>`")
        return

    if service_id not in SERVICES:
        await update.message.reply_text("❌ **Invalid Service ID!** Check Menu.")
        return

    price_per_1k = SERVICES[service_id]['price']
    total_cost = (price_per_1k / 1000) * quantity

    if quantity < 10:
        await update.message.reply_text("❌ Minimum quantity is 10.")
        return

    if current_bal < total_cost:
        await update.message.reply_text(f"❌ **Low Balance!**\nCost: ₹{total_cost}\nYou have: ₹{current_bal}")
        return

    status_msg = await update.message.reply_text("⏳ **Placing Order...**")

    # API Call
    params = {
        'key': SMM_API_KEY,
        'action': 'add',
        'service': service_id,
        'link': link,
        'quantity': quantity
    }
    
    try:
        res = requests.post(SMM_API_URL, data=params).json()
        if 'order' in res:
            new_bal = current_bal - total_cost
            users_col.update_one({"user_id": user_id}, {"$set": {"balance": new_bal}})
            await status_msg.edit_text(
                f"✅ **Ordered Successfully!**\n🆔 Order ID: `{res['order']}`\n💰 Cost: ₹{total_cost}\n📉 Balance: ₹{new_bal}"
            )
            await context.bot.send_message(ADMIN_ID, f"🔔 **New Sale!** ₹{total_cost} (User: {user_id})")
        else:
            await status_msg.edit_text(f"❌ Failed: {res.get('error')}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}")

# --- ADMIN: ADD FUNDS ---
async def add_funds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_id = int(context.args[0])
        amount = float(context.args[1])
        users_col.update_one({"user_id": target_id}, {"$inc": {"balance": amount}}, upsert=True)
        await update.message.reply_text(f"✅ Added ₹{amount}")
        await context.bot.send_message(target_id, f"✅ **Account Credited:** ₹{amount}")
    except: await update.message.reply_text("Usage: `/addfunds <id> <amount>`")

# --- MAIN ---
def main():
    if not TOKEN: return
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("order", order))
    app.add_handler(CommandHandler("addfunds", add_funds))
    
    # Button Handler Added Here 👇
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")

if __name__ == "__main__":
    main()
