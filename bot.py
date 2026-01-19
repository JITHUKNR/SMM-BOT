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

# ✅ ADMIN ID
ADMIN_ID = 7567364364 

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
    users_col.update_one({"user_id": user.id}, {"$setOnInsert": {"balance": 0, "mode": "normal"}}, upsert=True)
    
    await update.message.reply_text(
        f"👋 **Hello, {user.first_name}!**\n\n"
        "🚀 **Welcome to Premium SMM Store.**\n"
        "Click a button below to get started!",
        reply_markup=main_menu_keyboard(),
        parse_mode='Markdown'
    )

# --- BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # Main Menu
    if data == 'main_menu':
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})
        await query.edit_message_text("👇 **Main Menu**", reply_markup=main_menu_keyboard(), parse_mode='Markdown')

    # Balance
    elif data == 'balance':
        user_data = users_col.find_one({"user_id": user_id})
        bal = user_data.get("balance", 0)
        await query.edit_message_text(f"💰 **Balance:** ₹{round(bal, 2)}\n\nContact Admin to add funds.", reply_markup=back_button(), parse_mode='Markdown')

    # Categories
    elif data == 'categories':
        await query.edit_message_text("📋 **Select Category:**", reply_markup=category_keyboard(), parse_mode='Markdown')

    # Support
    elif data == 'support':
        await query.edit_message_text("📞 **Support:**\nContact Admin to add funds.", reply_markup=back_button(), parse_mode='Markdown')

    # Show Services
    elif data.startswith('cat_'):
        cat = data.split('_')[1]
        keyboard = []
        for s_id, info in SERVICES.items():
            if info['cat'] == cat:
                keyboard.append([InlineKeyboardButton(f"{info['name']} - ₹{info['price']}", callback_data=f"srv_{s_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='categories')])
        await query.edit_message_text("👇 **Select Service:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # SERVICE SELECTED -> ASK FOR LINK (STEP 1)
    elif data.startswith('srv_'):
        s_id = data.split('_')[1]
        service_name = SERVICES[s_id]['name']

        # Save Service ID and Set Mode to 'waiting_for_link'
        users_col.update_one(
            {"user_id": user_id}, 
            {"$set": {"mode": "waiting_for_link", "temp_service": s_id}}
        )

        await query.edit_message_text(
            f"✅ **Selected:** {service_name}\n\n"
            "🔗 **Step 1:** Please send the **Link** now.\n"
            "_(Example: Instagram Post Link or Profile Link)_",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data='main_menu')]]),
            parse_mode='Markdown'
        )

# --- TEXT HANDLER (STEP 2 & 3) ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    user_data = users_col.find_one({"user_id": user_id})
    mode = user_data.get("mode", "normal")

    # --- IF USER SENDS LINK (STEP 2) ---
    if mode == "waiting_for_link":
        # Check if it looks like a link
        if "http" not in text and "www" not in text and "@" not in text:
            await update.message.reply_text("⚠️ **Invalid Link!** Please send a correct link.")
            return

        # Save Link & Ask for Quantity
        users_col.update_one(
            {"user_id": user_id},
            {"$set": {"mode": "waiting_for_quantity", "temp_link": text}}
        )

        await update.message.reply_text(
            "✅ **Link Saved!**\n\n"
            "🔢 **Step 2:** How many do you want?\n"
            "_(Send a number only. Example: 100, 1000)_"
        )

    # --- IF USER SENDS QUANTITY (STEP 3 - FINAL) ---
    elif mode == "waiting_for_quantity":
        if not text.isdigit():
            await update.message.reply_text("⚠️ **Please send a valid number!** (Example: 500)")
            return

        quantity = int(text)
        service_id = user_data.get("temp_service")
        link = user_data.get("temp_link")
        
        # Validate Order
        if quantity < 10:
            await update.message.reply_text("❌ Minimum quantity is 10.")
            return

        price_per_1k = SERVICES[service_id]['price']
        total_cost = (price_per_1k / 1000) * quantity
        current_bal = user_data.get("balance", 0)

        if current_bal < total_cost:
            await update.message.reply_text(
                f"❌ **Insufficient Balance!**\n"
                f"Need: ₹{total_cost}\n"
                f"You have: ₹{round(current_bal, 2)}\n\n"
                "Please add funds via Admin."
            )
            # Reset mode
            users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})
            return

        status_msg = await update.message.reply_text("⏳ **Processing Order...**")

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
                
                # Reset User
                users_col.update_one(
                    {"user_id": user_id}, 
                    {"$set": {"balance": new_bal, "mode": "normal", "temp_service": None, "temp_link": None}}
                )
                
                await status_msg.edit_text(
                    f"✅ **Order Successful!** 🚀\n\n"
                    f"🆔 Order ID: `{res['order']}`\n"
                    f"📦 Service: {SERVICES[service_id]['name']}\n"
                    f"🔗 Link: {link}\n"
                    f"🔢 Quantity: {quantity}\n"
                    f"💰 Cost: ₹{total_cost}\n"
                    f"📉 Balance: ₹{round(new_bal, 2)}"
                )
                # Notify Admin
                await context.bot.send_message(ADMIN_ID, f"🔔 **New Order!** ₹{total_cost} (User: {user_id})")

            else:
                await status_msg.edit_text(f"❌ **Order Failed:** {res.get('error')}")
                # Reset mode on failure
                users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})

        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {e}")
            users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})

# --- ADMIN: ADD FUNDS ---
async def add_funds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_id = int(context.args[0])
        amount = float(context.args[1])
        users_col.update_one({"user_id": target_id}, {"$inc": {"balance": amount}}, upsert=True)
        await update.message.reply_text(f"✅ Added ₹{amount}")
        await context.bot.send_message(target_id, f"✅ **Wallet Credited:** ₹{amount}")
    except: await update.message.reply_text("Usage: `/addfunds <id> <amount>`")

# --- MAIN ---
def main():
    if not TOKEN: return
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addfunds", add_funds))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")

if __name__ == "__main__":
    main()
