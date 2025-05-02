import os
import time
import asyncio
import datetime
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
from telethon import TelegramClient
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact
from telethon.errors import FloodWaitError

# === API & Token ===
API_ID = 23374112
API_HASH = '35f9ae3c219d6f765cd59641c9a54d5e'
BOT_TOKEN = '7072897444:AAFJffx-vh9jwPnvc5KxveVpjrDR4KWddDY'
ADMIN_USER_ID = 6635274543  # আপনার টেলিগ্রাম ইউজার আইডি

# === States ===
ASK_SUBSCRIPTION, ASK_PHONE, ASK_CODE, CHECKING_NUMBERS = range(4)

sessions = {}
users_subscription = {}  # user_id: expiry_date

# === Subscription Check ===
def is_subscribed(user_id):
    expiry = users_subscription.get(user_id)
    if not expiry:
        return False
    return expiry > datetime.datetime.now()

# === Start Command ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if not is_subscribed(user_id):
        await update.message.reply_text(
            f"""
Ⓜ️ Welcome to Number Check Bot

💁🏻‍♂️ Your User ID: {user_id}

💎 Subscription Plans:

🎁 7 days : $3
🎉 15 days : $5

🌀 Payment Methods:
Bkash
Nagad
USD

📩 To subscribe send message @Rhmatollah89
            """
        )
        return ConversationHandler.END

    await update.message.reply_text("আপনার টেলিগ্রাম নাম্বার (+ সহ) দিন 📱")
    return ASK_PHONE

# === Receive Phone Number ===
async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    user_id = update.message.from_user.id
    session_name = f"session_{user_id}"

    client = TelegramClient(session_name, API_ID, API_HASH)
    sessions[user_id] = {'client': client, 'phone': phone}

    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        await update.message.reply_text("একটি কোড পাঠানো হয়েছে। কোডটি দিন 📨")
        return ASK_CODE
    else:
        await update.message.reply_text("ইতোমধ্যে লগইন করা হয়েছে। ✅ এখন T.ME লিংক সহ নাম্বারগুলো পাঠান:")
        return CHECKING_NUMBERS

# === Receive Code ===
async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user_id = update.message.from_user.id

    client = sessions[user_id]['client']
    phone = sessions[user_id]['phone']

    try:
        await client.sign_in(phone=phone, code=code)
        await update.message.reply_text("লগইন সফল! ✅ এখন t.me/ সহ নাম্বার পাঠান:")
        return CHECKING_NUMBERS
    except Exception as e:
        await update.message.reply_text(f"কোড ভুল অথবা লগইন ব্যর্থ ❌ {str(e)}")
        return ASK_PHONE

# === Handle t.me Links ===
async def check_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    client = sessions[user_id]['client']
    text = update.message.text
    lines = text.splitlines()

    valid_numbers = []

    for line in lines:
        line = line.strip()
        if not line.startswith("t.me/"):
            continue

        phone = line.replace("t.me/", "").replace("@", "")
        try:
            contact = InputPhoneContact(client_id=0, phone=phone, first_name="Temp", last_name="User")
            result = await client(ImportContactsRequest([contact]))
            user = result.users[0] if result.users else None

            if user:
                await update.message.reply_text(f" {line} Telegram ✅")
                valid_numbers.append(line)
                await client(DeleteContactsRequest(id=[user]))
            else:
                await update.message.reply_text(f" {line} Telegram ❌")

            await asyncio.sleep(6)

        except FloodWaitError as e:
            await update.message.reply_text(f"⏳ FloodWait: {e.seconds} সেকেন্ড অপেক্ষা করুন...")
            await asyncio.sleep(e.seconds + 2)
        except Exception as e:
            await update.message.reply_text(f" ত্রুটি: ⚠️ {line} — {str(e)}")

    if valid_numbers:
        result_file = f"valid_{user_id}.txt"
        with open(result_file, "w", encoding="utf-8") as f:
            f.write("\n".join(valid_numbers))

        await update.message.reply_document(
            document=InputFile(result_file),
            caption="যেই নাম্বারগুলোতে টেলিগ্রাম আছে, সেই নাম্বারগুলো এখানে ✅"
        )
        os.remove(result_file)
    else:
        await update.message.reply_text("কোনো বৈধ Telegram নাম্বার পাওয়া যায়নি।❗")

    return CHECKING_NUMBERS

# === Admin Give Subscription ===
async def admin_give_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_USER_ID:
        await update.message.reply_text("🚫 আপনার এডমিন অধিকার নেই।")
        return

    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("❗ ব্যবহারবিধি: /adminsub <user_id> <days>")
            return

        target_user_id = int(args[0])
        days = int(args[1])
        expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)

        users_subscription[target_user_id] = expiry_date
        await update.message.reply_text(f" {target_user_id} ইউজারকে {days} দিনের জন্য সাবস্ক্রিপশন দেওয়া হয়েছে। ✅")

    except Exception as e:
        await update.message.reply_text(f"ত্রুটি ⚠️ {str(e)}")

# === Admin Panel ===
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_USER_ID:
        await update.message.reply_text("🚫 আপনার এডমিন প্যানেলে অ্যাক্সেস নেই।")
        return

    msg = "👮‍♂️ Admin Panel\n\nসাবস্ক্রিপশন ইউজার তালিকা:\n"
    if not users_subscription:
        msg += "❗ কোনো সাবস্ক্রিপশন নেই।"
    else:
        for uid, expiry in users_subscription.items():
            status = "প্রিমিয়াম ✅" if expiry > datetime.datetime.now() else "মেয়াদ শেষ ❌"
            msg += f"🆔 {uid} — {status} (মেয়াদ: {expiry.strftime('%Y-%m-%d %H:%M')})\n"

    await update.message.reply_text(msg)

# === Error Handler ===
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"Error⚠️ {context.error}")
    try:
        if update and hasattr(update, "message") and update.message:
            await update.message.reply_text("একটি সমস্যা হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন। ❌")
    except Exception as e:
        print(f"Error sending error message ⚠️ {e}")

# === Main ===
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
            ASK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
            CHECKING_NUMBERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_links)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('adminsub', admin_give_subscription))
    app.add_handler(CommandHandler('admin', admin_panel))
    app.add_error_handler(error_handler)

    print("🤖 Bot is running...")
    app.run_polling()
