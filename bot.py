import os
import re
import sqlite3
import asyncio
from aiohttp import web
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    KeyboardButton
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ConversationHandler, 
    ContextTypes, 
    filters
)

# Configuration
BOT_TOKEN = "8839102402:AAEZfufycqS2VmyfFakdFlMv2pPWixg7aaw"
ADMIN_ID = 8865474356
CHANNEL_USERNAME = "@easygmailseller"
CHANNEL_LINK = "https://t.me/easygmailseller"
SUPPORT_LINK = "https://t.me/xyzort"

# Rates
RATE_PER_GMAIL = 15.0
REFER_BONUS = 2.0
MIN_WITHDRAW = 15.0

# States
SUBMIT_EMAIL, SUBMIT_PASS, WITHDRAW_NUM, WITHDRAW_AMOUNT = range(4)

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        lang TEXT DEFAULT 'bn',
        balance REAL DEFAULT 0.0,
        hold_balance REAL DEFAULT 0.0,
        total_withdrawn REAL DEFAULT 0.0,
        referred_by INTEGER,
        refer_rewarded INTEGER DEFAULT 0
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        email TEXT,
        password TEXT,
        status TEXT DEFAULT 'pending'
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        number TEXT,
        amount REAL,
        status TEXT DEFAULT 'pending'
    )
    """)
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect("database.db")

# --- Helper: Channel Join Verification ---
async def check_channel_join(bot, user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception:
        return True # Fallback if channel admin permission missing

# --- Keyboards ---
def main_menu(lang='bn'):
    if lang == 'bn':
        kb = [
            [KeyboardButton("📥 জিমেইল জমা দিন (Submit your own)")],
            [KeyboardButton("👤 প্রোফাইল (My Profile)"), KeyboardButton("📂 আমার অ্যাকাউন্টস (My Accounts)")],
            [KeyboardButton("💳 উইথড্র (Withdraw)"), KeyboardButton("👥 রেফার ও আয় (Refer & Earn)")],
            [KeyboardButton("💬 সাপোর্ট (Support)")]
        ]
    else:
        kb = [
            [KeyboardButton("📥 Submit your own")],
            [KeyboardButton("👤 My Profile"), KeyboardButton("📂 My Accounts")],
            [KeyboardButton("💳 Withdraw"), KeyboardButton("👥 Refer & Earn")],
            [KeyboardButton("💬 Support")]
        ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    referrer_id = None
    if args and args[0].isdigit():
        ref = int(args[0])
        if ref != user_id:
            referrer_id = ref

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (user_id, referrer_id))
        conn.commit()
    conn.close()

    inline_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lang_bn"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ])
    await update.message.reply_text(
        "👋 Welcome! / স্বাগতম!\n\nPlease select language / ভাষা নির্বাচন করুন:",
        reply_markup=inline_kb
    )

async def lang_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = "bn" if query.data == "lang_bn" else "en"

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, query.from_user.id))
    conn.commit()
    conn.close()

    is_joined = await check_channel_join(context.bot, query.from_user.id)
    if not is_joined:
        join_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Checked / যোগ দিয়েছি", callback_data="check_join")]
        ])
        msg = "⚠️ আপনি আমাদের চ্যানেলে যোগ দেননি! আগে চ্যানেলে যোগ দিন:" if lang == 'bn' else "⚠️ You must join our channel first:"
        await query.message.edit_text(msg, reply_markup=join_btn)
    else:
        text = "🎉 স্বাগতম! আপনি এখন বট ব্যবহার করতে পারেন।" if lang == 'bn' else "🎉 Welcome! You can now use the bot."
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id, text=text, reply_markup=main_menu(lang))

async def check_join_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    lang = row[0] if row else 'bn'
    conn.close()

    if await check_channel_join(context.bot, user_id):
        await query.message.delete()
        await context.bot.send_message(chat_id=user_id, text="✅ ভেরিফিকেশন সফল!", reply_markup=main_menu(lang))
    else:
        await query.answer("❌ আগে চ্যানেলে যোগ দিন!", show_alert=True)

async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await check_channel_join(context.bot, user_id):
        join_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Official Channel", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Verify Join", callback_data="check_join")]
        ])
        await update.message.reply_text("⚠️ আমাদের চ্যানেলে যোগ দেওয়া বাধ্যতামূলক:", reply_markup=join_btn)
        return False
    return True

# --- Submit Gmail Conversation ---
async def submit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update, context): return ConversationHandler.END
    text = (
        "⚠️ **সতর্কতা ও নিয়মাবলী:**\n"
        "• শুধুমাত্র পরিষ্কার ফ্রেশ Gmail হতে হবে।\n"
        "• 2FA অন থাকা যাবে না।\n"
        "• Recovery Email বা Phone থাকা যাবে না।\n\n"
        "👉 আপনার **Gmail ID** টি লিখুন (@gmail.com সহ, কোনো স্পেস ছাড়া):"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
    return SUBMIT_EMAIL

async def submit_email_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    pattern = r"^[a-zA-Z0-9_.+-]+@gmail\.com$"
    if " " in email or not re.match(pattern, email):
        await update.message.reply_text("❌ ভুল ফরম্যাট! কোনো স্পেস ছাড়া সঠিক @gmail.com দিন:")
        return SUBMIT_EMAIL

    context.user_data['submitted_email'] = email
    await update.message.reply_text("🔑 এবার আপনার Gmail-এর **Password** টি লিখুন (কোনো স্পেস ছাড়া):", parse_mode="Markdown")
    return SUBMIT_PASS

async def submit_pass_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    if " " in password:
        await update.message.reply_text("❌ পাসওয়ার্ডে কোনো স্পেস দেওয়া যাবে না! আবার দিন:")
        return SUBMIT_PASS

    email = context.user_data['submitted_email']
    user_id = update.effective_user.id

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO tasks (user_id, email, password) VALUES (?, ?, ?)", (user_id, email, password))
    task_id = cur.lastrowid
    cur.execute("UPDATE users SET hold_balance = hold_balance + ? WHERE user_id = ?", (RATE_PER_GMAIL, user_id))
    conn.commit()
    conn.close()

    admin_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"app_{task_id}"),
         InlineKeyboardButton("❌ Reject", callback_data=f"rej_{task_id}")]
    ])
    admin_msg = (
        f"📩 **নতুন জিমেইল সাবমিট!**\n\n"
        f"🆔 User ID: `{user_id}`\n"
        f"📧 Email: `{email}`\n"
        f"🔑 Pass: `{password}`\n"
        f"Task ID: #{task_id}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown", reply_markup=admin_btn)
    await update.message.reply_text("✅ সফলভাবে জমা হয়েছে! অ্যাডমিন চেক করে Approve করলেই ব্যালেন্স যোগ হবে।")
    return ConversationHandler.END

# --- Profile ---
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update, context): return
    user_id = update.effective_user.id

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance, hold_balance, total_withdrawn FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    bal, hold, withdrawn = row if row else (0.0, 0.0, 0.0)
    text = (
        f"👤 **আপনার প্রোফাইল ড্যাশবোর্ড**\n\n"
        f"🆔 User ID: `{user_id}`\n"
        f"💰 উপলব্ধ ব্যালেন্স: `{bal:.2f} TK`\n"
        f"⏳ হোল্ড ব্যালেন্স: `{hold:.2f} TK`\n"
        f"💳 মোট উত্তোলন: `{withdrawn:.2f} TK`\n"
        f"💵 প্রতি জিমেইল: {RATE_PER_GMAIL:.0f} TK"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# --- My Accounts ---
async def my_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update, context): return
    user_id = update.effective_user.id

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT email, status FROM tasks WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
    tasks = cur.fetchall()
    conn.close()

    if not tasks:
        await update.message.reply_text("📂 আপনি এখনো কোনো অ্যাকাউন্ট জমা দেননি।")
        return

    text = "📂 **সাম্প্রতিক জিমেইল স্ট্যাটাস:**\n\n"
    for email, status in tasks:
        icon = "⏳ Pending" if status == 'pending' else ("✅ Approved" if status == 'approved' else "❌ Rejected")
        text += f"• `{email}` - {icon}\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# --- Withdraw ---
async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update, context): return ConversationHandler.END
    user_id = update.effective_user.id

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    bal = cur.fetchone()[0]
    conn.close()

    if bal < MIN_WITHDRAW:
        await update.message.reply_text(f"❌ ব্যালেন্স নেই! সর্বনিম্ন উত্তোলন `{MIN_WITHDRAW} TK`। আপনার ব্যালেন্স `{bal:.2f} TK`।", parse_mode="Markdown")
        return ConversationHandler.END

    await update.message.reply_text(
        "💳 **বিকাশ উত্তোলন (bKash)**\n\n"
        "📢 মনে রাখবেন: পেমেন্ট প্রতি **শুক্রবার** এবং **সোমবার** দেওয়া হয়।\n\n"
        "👉 আপনার বিকাশ পার্সোনাল নম্বর দিন:"
    )
    return WITHDRAW_NUM

async def withdraw_num_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    num = update.message.text.strip()
    if len(num) < 11 or not num.isdigit():
        await update.message.reply_text("❌ সঠিক ১১ ডিজিটের নম্বর দিন:")
        return WITHDRAW_NUM

    context.user_data['bkash_num'] = num
    await update.message.reply_text("💵 কত টাকা তুলতে চান লিখুন:")
    return WITHDRAW_AMOUNT

async def withdraw_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_str = update.message.text.strip()
    try:
        amount = float(amount_str)
    except ValueError:
        await update.message.reply_text("❌ সংখ্যায় সঠিক টাকার পরিমাণ দিন:")
        return WITHDRAW_AMOUNT

    user_id = update.effective_user.id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    bal = cur.fetchone()[0]

    if amount < MIN_WITHDRAW or amount > bal:
        conn.close()
        await update.message.reply_text(f"❌ অবৈধ পরিমাণ! আপনি সর্বনিম্ন {MIN_WITHDRAW} TK থেকে সর্বোচ্চ {bal:.2f} TK তুলতে পারবেন।")
        return WITHDRAW_AMOUNT

    cur.execute("UPDATE users SET balance = balance - ?, total_withdrawn = total_withdrawn + ? WHERE user_id = ?", (amount, amount, user_id))
    cur.execute("INSERT INTO withdrawals (user_id, number, amount) VALUES (?, ?, ?)", (user_id, context.user_data['bkash_num'], amount))
    w_id = cur.lastrowid
    conn.commit()
    conn.close()

    admin_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Paid", callback_data=f"paid_{w_id}"),
         InlineKeyboardButton("❌ Reject", callback_data=f"wrej_{w_id}")]
    ])
    admin_text = (
        f"🚨 **নতুন বিকাশ পেমেন্ট রিকোয়েস্ট!**\n\n"
        f"🆔 User ID: `{user_id}`\n"
        f"📱 Number: `{context.user_data['bkash_num']}`\n"
        f"💰 Amount: `{amount} TK`\n"
        f"Req ID: #{w_id}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown", reply_markup=admin_btn)
    await update.message.reply_text("✅ আপনার রিকোয়েস্ট জমা হয়েছে! শুক্রবার বা সোমবার বিকাশ পৌঁছে যাবে।")
    return ConversationHandler.END

# --- Refer & Support ---
async def refer_earn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update, context): return
    bot_info = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={update.effective_user.id}"
    text = (
        "👥 **রেফার করে আয় করুন**\n\n"
        "প্রতি রেফারে পাবেন **২ টাকা** (রেফার করা ইউজারকে অবশ্যই কমপক্ষে ১টি জিমেইল অ্যাপ্রুভ করাতে হবে)।\n\n"
        f"🔗 আপনার রেফার লিংক:\n`{ref_link}`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("💬 যোগাযোগ করুন (Support)", url=SUPPORT_LINK)]])
    await update.message.reply_text("📞 সাহায্যের জন্য যোগাযোগ করুন:", reply_markup=btn)

# --- Admin Callbacks ---
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        return
    data = query.data
    conn = get_db()
    cur = conn.cursor()

    if data.startswith("app_"):
        task_id = int(data.split("_")[1])
        cur.execute("SELECT user_id, status FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        if row and row[1] == 'pending':
            uid = row[0]
            cur.execute("UPDATE tasks SET status = 'approved' WHERE id = ?", (task_id,))
            cur.execute("UPDATE users SET balance = balance + ?, hold_balance = hold_balance - ? WHERE user_id = ?", (RATE_PER_GMAIL, RATE_PER_GMAIL, uid))

            cur.execute("SELECT referred_by, refer_rewarded FROM users WHERE user_id = ?", (uid,))
            ref_data = cur.fetchone()
            if ref_data and ref_data[0] and ref_data[1] == 0:
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REFER_BONUS, ref_data[0]))
                cur.execute("UPDATE users SET refer_rewarded = 1 WHERE user_id = ?", (uid,))
                try:
                    await context.bot.send_message(chat_id=ref_data[0], text=f"🎉 আপনার রেফারের ইউজার ১টি জিমেইল জমা দিয়েছে! বোনাস পেয়েছেন {REFER_BONUS} TK!")
                except Exception:
                    pass

            conn.commit()
            await query.edit_message_text(f"{query.message.text}\n\n✅ APPROVED")
            await context.bot.send_message(chat_id=uid, text="🎉 আপনার জিমেইল অনুমোদিত হয়েছে এবং ১৫ টাকা ব্যালেন্সে যোগ হয়েছে!")

    elif data.startswith("rej_"):
        task_id = int(data.split("_")[1])
        cur.execute("SELECT user_id, status FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        if row and row[1] == 'pending':
            cur.execute("UPDATE tasks SET status = 'rejected' WHERE id = ?", (task_id,))
            cur.execute("UPDATE users SET hold_balance = hold_balance - ? WHERE user_id = ?", (RATE_PER_GMAIL, row[0]))
            conn.commit()
            await query.edit_message_text(f"{query.message.text}\n\n❌ REJECTED")
            await context.bot.send_message(chat_id=row[0], text="❌ আপনার জিমেইলটি সঠিক না থাকায় রিজেক্ট করা হয়েছে।")

    elif data.startswith("paid_"):
        w_id = int(data.split("_")[1])
        cur.execute("UPDATE withdrawals SET status = 'paid' WHERE id = ?", (w_id,))
        cur.execute("SELECT user_id, amount FROM withdrawals WHERE id = ?", (w_id,))
        uid, amt = cur.fetchone()
        conn.commit()
        await query.edit_message_text(f"{query.message.text}\n\n✅ PAID SUCCESS")
        await context.bot.send_message(chat_id=uid, text=f"🎉 আপনার {amt} TK উইথড্র পেমেন্ট পাঠিয়ে দেওয়া হয়েছে!")

    elif data.startswith("wrej_"):
        w_id = int(data.split("_")[1])
        cur.execute("SELECT user_id, amount, status FROM withdrawals WHERE id = ?", (w_id,))
        uid, amt, st = cur.fetchone()
        if st == 'pending':
            cur.execute("UPDATE withdrawals SET status = 'rejected' WHERE id = ?", (w_id,))
            cur.execute("UPDATE users SET balance = balance + ?, total_withdrawn = total_withdrawn - ? WHERE user_id = ?", (amt, amt, uid))
            conn.commit()
            await query.edit_message_text(f"{query.message.text}\n\n❌ REJECTED (REFUNDED)")
            await context.bot.send_message(chat_id=uid, text=f"❌ উত্তোলন বাতিল হয়েছে এবং {amt} TK ব্যাক দেওয়া হয়েছে।")

    conn.close()

# --- Combined Main Function ---
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    init_db()

    # Setup Bot
    application = Application.builder().token(BOT_TOKEN).build()

    submit_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(📥 জিমেইল জমা দিন|📥 Submit your own)$"), submit_start)],
        states={
            SUBMIT_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_email_input)],
            SUBMIT_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_pass_input)]
        },
        fallbacks=[CommandHandler("start", start)]
    )

    withdraw_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(💳 উইথড্র|💳 Withdraw)$"), withdraw_start)],
        states={
            WITHDRAW_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_num_input)],
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount_input)]
        },
        fallbacks=[CommandHandler("start", start)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(lang_selected, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(check_join_btn, pattern="^check_join$"))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^(app_|rej_|paid_|wrej_)"))
    application.add_handler(submit_conv)
    application.add_handler(withdraw_conv)
    application.add_handler(MessageHandler(filters.Regex("^(👤 প্রোফাইল|👤 My Profile)$"), show_profile))
    application.add_handler(MessageHandler(filters.Regex("^(📂 আমার অ্যাকাউন্টস|📂 My Accounts)$"), my_accounts))
    application.add_handler(MessageHandler(filters.Regex("^(👥 রেফার ও আয়|👥 Refer & Earn)$"), refer_earn))
    application.add_handler(MessageHandler(filters.Regex("^(💬 সাপোর্ট|💬 Support)$"), support))

    # Setup Web Server for Render
    server = web.Application()
    server.router.add_get('/', handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    # Start Bot Polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    print("Bot is successfully running!")

    # Keep alive loop
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
