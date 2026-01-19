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

# ✅ QR CODE FILE ID (നിങ്ങൾ തന്ന ശരിക്കുള്ള ID)
QR_CODE_FILE_ID = "AgACAgQAAxkBAAI0UGluU4Bg0onFlgUgedyzb0RO0uYCAALYDGsbpjJwU0ieEncrdtqiAQADAgADeAADOAQ"

# ⚠️ നിങ്ങളുടെ UPI ID ഇവിടെ മാറ്റാം (ഉദാഹരണത്തിന്: 9876543210@ybl)
MY_UPI_ID = "your-upi-id@okbank" 

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
        [InlineKeyboardButton("💳 Add Funds (QR)", callback_data='add_funds_request')]
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

    if data == 'main_menu':
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})
        await query.edit_message_text("👇 **Main Menu**", reply_markup=main_menu_keyboard(), parse_mode='Markdown')

    elif data == 'balance':
        user_data = users_col.find_one({"user_id": user_id})
        bal = user_data.get("balance", 0)
        await query.edit_message_text(f"💰 **Balance:** ₹{round(bal, 2)}\n\nUse 'Add Funds' to deposit money.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]), parse_mode='Markdown')

    elif data == 'categories':
        await query.edit_message_text("📋 **Select Category:**", reply_markup=category_keyboard(), parse_mode='Markdown')

    # ADD FUNDS REQUEST (SHOW QR)
    elif data == 'add_funds_request':
        users_col.update_one({"user_id": user_id}, {"$set": {"mode": "waiting_payment_proof"}})
        
        caption_text = (
            "💳 **Add Funds via UPI**\n\n"
            f"🆔 **UPI ID:** `{MY_UPI_ID}`\n\n"
            "1️⃣ Scan QR or Pay to UPI ID.\n"
            "2️⃣ Take a Screenshot.\n"
            "3️⃣ **Send the Screenshot here.**"
        )
        
        try:
            # Send QR Code Photo
            await query.message.reply_photo(photo=QR_CODE_FILE_ID, caption=caption_text, parse_mode='Markdown')
        except Exception as e:
            await query.message.reply_text(f"⚠️ QR Error. Use UPI ID:\n`{MY_UPI_ID}`\n\nSend Screenshot after payment.", parse_mode='Markdown')

    # ADMIN APPROVAL LOGIC
    elif data.startswith('approve_'):
        _, target_id, amount_str = data.split('_')
        target_id = int(target_id)
        amount = float(amount_str)

        users_col.update_one({"user_id": target_id}, {"$inc": {"balance": amount}})
        
        await query.edit_message_text(f"✅ **Approved!** Added ₹{amount} to User {target_id}")
        await context.bot.send_message(target_id, f"✅ **Deposit Confirmed!**\n₹{amount} has been added to your wallet. 💰")

    elif data.startswith('reject_'):
        target_id = int(data.split('_')[1])
        await query.edit_message_text(f"❌ **Rejected** payment for User {target_id}")
        await context.bot.send_message(target_id, "❌ **Payment Rejected.**\nPlease contact admin with valid proof.")

    elif data.startswith('cat_'):
        cat = data.split('_')[1]
        keyboard = []
        for s_id, info in SERVICES.items():
            if info['cat'] == cat:
                keyboard.append([InlineKeyboardButton(f"{info['name']} - ₹{info['price']}", callback_data=f"srv_{s_id}")])
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
    
    # Check if message is text or photo
    if update.message.photo:
        is_photo = True
        text = update.message.caption if update.message.caption else ""
    else:
        is_photo = False
        text = update.message.text if update.message.text else ""

    user_data = users_col.find_one({"user_id": user_id})
    mode = user_data.get("mode", "normal")

    # --- PAYMENT PROOF HANDLING ---
    if mode == "waiting_payment_proof":
        if is_photo:
            await update.message.reply_text("⏳ **Proof Received!** Sent to Admin for approval.")
            
            # Admin Buttons
            keyboard = [
                [InlineKeyboardButton("✅ Add ₹10", callback_data=f'approve_{user_id}_10'),
                 InlineKeyboardButton("✅ Add ₹50", callback_data=f'approve_{user_id}_50')],
                [InlineKeyboardButton("✅ Add ₹100", callback_data=f'approve_{user_id}_100'),
                 InlineKeyboardButton("✅ Add ₹500", callback_data=f'approve_{user_id}_500')],
                 [InlineKeyboardButton("❌ Reject", callback_data=f'reject_{user_id}')]
            ]
            
            # Forward photo to Admin
            await context.bot.send_photo(
                chat_id=ADMIN_ID, 
                photo=update.message.photo[-1].file_id,
                caption=f"🔔 **Payment Proof!**\nUser: {user.first_name} (ID: `{user_id}`)\n\nApprove amount below: 👇",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})
        else:
            await update.message.reply_text("⚠️ Please send the **Screenshot (Photo)** of payment.")
        return

    # --- ORDER HANDLING ---
    if not is_photo and text:
        if mode == "waiting_for_link":
            users_col.update_one({"user_id": user_id}, {"$set": {"mode": "waiting_for_quantity", "temp_link": text}})
            await update.message.reply_text("✅ Link Saved!\n🔢 **Step 2:** How many do you want? (Number only)")

        elif mode == "waiting_for_quantity":
            if not text.isdigit():
                await update.message.reply_text("⚠️ Send a number only!")
                return
            
            quantity = int(text)
            service_id = user_data.get("temp_service")
            link = user_data.get("temp_link")
            
            price_per_1k = SERVICES[service_id]['price']
            total_cost = (price_per_1k / 1000) * quantity
            current_bal = user_data.get("balance", 0)

            if current_bal < total_cost:
                await update.message.reply_text(f"❌ **Low Balance!** Need: ₹{total_cost}. Add funds.")
                users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})
                return

            status_msg = await update.message.reply_text("⏳ **Processing...**")
            
            params = {'key': SMM_API_KEY, 'action': 'add', 'service': service_id, 'link': link, 'quantity': quantity}
            try:
                res = requests.post(SMM_API_URL, data=params).json()
                if 'order' in res:
                    new_bal = current_bal - total_cost
                    users_col.update_one({"user_id": user_id}, {"$set": {"balance": new_bal, "mode": "normal"}})
                    await status_msg.edit_text(f"✅ **Ordered!** ID: `{res['order']}`\n💰 Cost: ₹{total_cost}\n📉 Bal: ₹{new_bal}")
                    await context.bot.send_message(ADMIN_ID, f"🔔 Sale! ₹{total_cost} (User: {user_id})")
                else:
                    error_msg = res.get('error', 'Unknown Error')
                    await status_msg.edit_text(f"❌ **Order Failed!**\nReason: {error_msg}")
                    if "balance" in str(error_msg).lower():
                        await context.bot.send_message(ADMIN_ID, "⚠️ **ADMIN ALERT:** Your Main SMM Account has Low Balance!")

            except Exception as e:
                await status_msg.edit_text(f"Error: {e}")
            
            users_col.update_one({"user_id": user_id}, {"$set": {"mode": "normal"}})

# --- MAIN ---
def main():
    if not TOKEN: return
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")

if __name__ == "__main__":
    main()
