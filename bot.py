import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pymongo import MongoClient

# --- CONFIGURATION ---
TOKEN = os.environ.get('TOKEN')
MONGO_URI = os.environ.get('MONGO_URI')
SMM_API_URL = os.environ.get('SMM_API_URL') 
SMM_API_KEY = os.environ.get('SMM_API_KEY') 
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
PORT = int(os.environ.get('PORT', 8443))

# ✅ ADMIN ID (നിങ്ങളുടെ ID ഇവിടെ മാറ്റാൻ മറക്കരുത്!)
ADMIN_ID = 7567364364 

# --- SERVICE LIST (ID, Name, Your Selling Price) ---
# Format: "SERVICE_ID": {"name": "NAME", "price": PRICE_PER_1000}
SERVICES = {
    "11142": {"name": "Instagram Likes (Fast) ❤️", "price": 30},      # Cost: ~20
    "11395": {"name": "IG Followers (Cheap) 👤", "price": 100},       # Cost: ~75
    "363":   {"name": "IG Followers (Non-Drop 365 Days) ⭐", "price": 400}, # Cost: ~317
    "8965":  {"name": "Telegram Members (Indian) 🇮🇳", "price": 40},   # Cost: ~25
    "7939":  {"name": "YouTube Views (Lifetime) ▶️", "price": 180}    # Cost: ~135
}

# --- DATABASE ---
client = MongoClient(MONGO_URI)
db = client["SMMBot"]
users_col = db["users"]

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users_col.update_one({"user_id": user.id}, {"$setOnInsert": {"balance": 0}}, upsert=True)
    
    await update.message.reply_text(
        f"👋 **Welcome, {user.first_name}!** 🚀\n\n"
        "Best SMM Panel Bot for Instagram & Telegram Services.\n\n"
        "💰 **Check Balance:** /balance\n"
        "📋 **View Services:** /services\n"
        "🛒 **To Order:** `/order <service_id> <link> <quantity>`\n\n"
        "_(Contact Admin to add money to wallet)_"
    )

# --- CHECK BALANCE ---
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = users_col.find_one({"user_id": user_id})
    bal = user_data.get("balance", 0) if user_data else 0
    await update.message.reply_text(f"💰 **Your Wallet Balance:** ₹{round(bal, 2)}")

# --- SHOW SERVICES ---
async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📋 **Available Services & Prices (Per 1000):**\n\n"
    
    for s_id, data in SERVICES.items():
        msg += f"🆔 **ID: {s_id}**\n📌 {data['name']}\n💵 Price: ₹{data['price']} / 1000\n------------------\n"
    
    msg += "\n⚠️ **How to Order:**\n`/order 11142 https://instagram.com/p/xyz 1000`"
    await update.message.reply_text(msg)

# --- PLACE ORDER ---
async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = users_col.find_one({"user_id": user_id})
    current_bal = user_data.get("balance", 0)

    try:
        # Command: /order 11142 link 1000
        service_id = context.args[0]
        link = context.args[1]
        quantity = int(context.args[2])
    except (IndexError, ValueError):
        await update.message.reply_text("❌ **Format Wrong!**\nUse: `/order <service_id> <link> <quantity>`")
        return

    # Check if Service Exists
    if service_id not in SERVICES:
        await update.message.reply_text("❌ **Invalid Service ID!** Check /services")
        return

    # Calculate Cost (Based on YOUR Selling Price)
    price_per_1k = SERVICES[service_id]['price']
    total_cost = (price_per_1k / 1000) * quantity

    if quantity < 10: # Minimum limit check
        await update.message.reply_text("❌ Minimum quantity is 10.")
        return

    if current_bal < total_cost:
        await update.message.reply_text(f"❌ **Insufficient Balance!**\nNeed: ₹{total_cost}\nYour Bal: ₹{current_bal}")
        return

    status_msg = await update.message.reply_text("⏳ **Processing Order...**")

    # --- SEND ORDER TO MAIN PROVIDER ---
    params = {
        'key': SMM_API_KEY,
        'action': 'add',
        'service': service_id,
        'link': link,
        'quantity': quantity
    }
    
    try:
        # Request to xmediasmm
        res = requests.post(SMM_API_URL, data=params).json()
        
        if 'order' in res:
            # Success! Deduct Balance
            new_bal = current_bal - total_cost
            users_col.update_one({"user_id": user_id}, {"$set": {"balance": new_bal}})
            
            await status_msg.edit_text(
                f"✅ **Order Successful!** 🚀\n\n"
                f"🆔 Order ID: `{res['order']}`\n"
                f"📉 Cost Deducted: ₹{total_cost}\n"
                f"💰 Remaining Balance: ₹{round(new_bal, 2)}"
            )
            
            # Notify Admin (You)
            await context.bot.send_message(ADMIN_ID, f"🔔 **New Order!**\nUser: {user_id}\nService: {service_id}\nProfit Made! 🤑")
            
        else:
            error_msg = res.get('error', 'Unknown Error')
            await status_msg.edit_text(f"❌ **Order Failed!**\nServer Error: {error_msg}")

    except Exception as e:
        await status_msg.edit_text(f"❌ Connection Error: {e}")

# --- ADMIN: ADD FUNDS ---
async def add_funds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        target_id = int(context.args[0])
        amount = float(context.args[1])
        
        users_col.update_one({"user_id": target_id}, {"$inc": {"balance": amount}}, upsert=True)
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
    app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")

if __name__ == "__main__":
    main()
