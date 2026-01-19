import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pymongo import MongoClient

# --- CONFIGURATION ---
TOKEN = os.environ.get('TOKEN')
MONGO_URI = os.environ.get('MONGO_URI')
# നിങ്ങളുടെ SMM പ്രൊവൈഡറുടെ API ലിങ്ക് (താഴെ ഉദാഹരണം കൊടുക്കുന്നു)
SMM_API_URL = os.environ.get('SMM_API_URL') 
# നിങ്ങളുടെ SMM പ്രൊവൈഡറുടെ API KEY
SMM_API_KEY = os.environ.get('SMM_API_KEY') 

# ✅ ADMIN ID (നിങ്ങളുടെ ID കൊടുക്കുക, എങ്കിലേ ബാലൻസ് ആഡ് ചെയ്യാൻ പറ്റൂ)
ADMIN_ID = 123456789 

# --- DATABASE ---
client = MongoClient(MONGO_URI)
db = client["SMMBot"]
users_col = db["users"]

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # യൂസറെ ഡാറ്റാബേസിൽ ചേർക്കുന്നു (Balance: 0)
    users_col.update_one(
        {"user_id": user.id},
        {"$setOnInsert": {"balance": 0}},
        upsert=True
    )
    await update.message.reply_text(
        f"👋 **Welcome to SMM Store!** 🚀\n\n"
        "Buy Instagram Followers, Likes & More!\n\n"
        "💰 **Check Balance:** /balance\n"
        "🛒 **Order:** `/order <service_id> <link> <quantity>`\n"
        "ℹ️ **Services:** /services\n\n"
        "_(Contact Admin to add funds)_"
    )

# --- CHECK BALANCE ---
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = users_col.find_one({"user_id": user_id})
    bal = user_data.get("balance", 0)
    await update.message.reply_text(f"💰 **Your Wallet:** ₹{bal}")

# --- SHOW SERVICES (Example List) ---
async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ഇവിടെ നിങ്ങൾക്ക് ലഭ്യമായ സർവീസുകൾ എഴുതി വെക്കാം
    await update.message.reply_text(
        "📋 **Available Services:**\n\n"
        "🆔 **ID: 101** - Instagram Followers (₹50/1k)\n"
        "🆔 **ID: 102** - Instagram Likes (₹10/1k)\n"
        "🆔 **ID: 103** - YouTube Views (₹80/1k)\n\n"
        "⚠️ _To order: use /order command_"
    )

# --- PLACE ORDER ---
async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = users_col.find_one({"user_id": user_id})
    current_bal = user_data.get("balance", 0)

    try:
        # Command format: /order 101 https://link.com 1000
        service_id = context.args[0]
        link = context.args[1]
        quantity = int(context.args[2])
    except (IndexError, ValueError):
        await update.message.reply_text("❌ **Usage:** `/order <service_id> <link> <quantity>`")
        return

    # ⚠️ ശ്രദ്ധിക്കുക: ഇവിടെ ഒരു 'Rate' കാൽക്കുലേഷൻ വെക്കണം. 
    # ഉദാഹരണത്തിന് 1000 എണ്ണത്തിന് 50 രൂപ ആണെങ്കിൽ:
    # cost = (quantity / 1000) * 50
    # തൽക്കാലം ഞാൻ ഒരു ഡമ്മി വില (₹10) ഇടുന്നു. നിങ്ങൾ ഇത് മാറ്റണം.
    estimated_cost = 10 

    if current_bal < estimated_cost:
        await update.message.reply_text("❌ **Insufficient Balance!** Please add funds.")
        return

    await update.message.reply_text("⏳ **Placing Order...**")

    # --- SMM API CALL ---
    params = {
        'key': SMM_API_KEY,
        'action': 'add',
        'service': service_id,
        'link': link,
        'quantity': quantity
    }
    
    try:
        # API-ലേക്ക് റിക്വസ്റ്റ് അയക്കുന്നു
        res = requests.post(SMM_API_URL, data=params).json()
        
        if 'order' in res:
            # ഓർഡർ സക്സസ്! ബാലൻസ് കുറയ്ക്കുന്നു
            new_bal = current_bal - estimated_cost
            users_col.update_one({"user_id": user_id}, {"$set": {"balance": new_bal}})
            
            await update.message.reply_text(
                f"✅ **Order Successful!**\n"
                f"🆔 Order ID: {res['order']}\n"
                f"💰 Deducted: ₹{estimated_cost}\n"
                f"📉 New Balance: ₹{new_bal}"
            )
        else:
            await update.message.reply_text(f"❌ **Order Failed:** {res.get('error', 'Unknown Error')}")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# --- ADMIN: ADD FUNDS ---
async def add_funds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        # /addfunds 12345678 100 (User_ID Amount)
        target_id = int(context.args[0])
        amount = float(context.args[1])
        
        users_col.update_one(
            {"user_id": target_id},
            {"$inc": {"balance": amount}},
            upsert=True
        )
        await update.message.reply_text(f"✅ Added ₹{amount} to User {target_id}")
        await context.bot.send_message(target_id, f"✅ **Deposit Received:** ₹{amount} added to your wallet!")
    except:
        await update.message.reply_text("Usage: `/addfunds <user_id> <amount>`")

# --- MAIN ---
def main():
    if not TOKEN:
        print("Error: TOKEN missing.")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("services", services))
    app.add_handler(CommandHandler("order", order))
    app.add_handler(CommandHandler("addfunds", add_funds))

    print("SMM Bot Started... 🔥")
    app.run_webhook(listen="0.0.0.0", port=int(os.environ.get("PORT", 8443)), url_path=TOKEN, webhook_url=f"{os.environ.get('WEBHOOK_URL')}/{TOKEN}")

if __name__ == "__main__":
    main()
