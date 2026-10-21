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
BOT_TOKEN = "8839102402:AAH_CDCklkidfV2QbvRu_2U0bbjRrfXxXco"
ADMIN_ID = 8865474356
CHANNEL_USERNAME = "@easygmailseller"
CHANNEL_LINK = "https://t.me/easygmailseller"
SUPPORT_LINK = "https://t.me/xyzort"

# Rates
RATE_PER_GMAIL = 15.0
REFER_BONUS = 3.0
MIN_WITHDRAW = 15.0

# Global Channel ID Cache
CACHED_CHANNEL_ID = None

# States
SUBMIT_EMAIL, SUBMIT_PASS, WITHDRAW_NUM, WITHDRAW_AMOUNT, BROADCAST_MSG = range(5)

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
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

# --- Helper: Get Exact Channel Chat ID ---
async def resolve_channel_id(bot):
    global CACHED_CHANNEL_ID
    if CACHED_CHANNEL_ID:
        return CACHED_CHANNEL_ID
    try:
        chat = await bot.get_chat(CHANNEL_USERNAME)
        CACHED_CHANNEL_ID = chat.id
        return CACHED_CHANNEL_ID
    except Exception as e:
        print(f"Channel Resolve Error: {e}")
        return CHANNEL_USERNAME

# --- Helper: Channel Join Verification ---
async def check_channel_join(bot, user_id):
    try:
        chat_id = await resolve_channel_id(bot)
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator', 'restricted']:
            return True
        return False
    except Exception as e:
        print(f"Channel check warning: {e}")
        return True 

# --- Keyboards ---
def main_menu(user_id):
    kb = [
        [KeyboardButton("📥 জিমেইল জমা দিন")],
        [KeyboardButton("👤 প্রোফাইল"), KeyboardButton("📂 আমার অ্যাকাউন্টস")],
        [KeyboardButton("💳 উইথড্র"), KeyboardButton("👥 রেফার ও আয়")],
        [KeyboardButton("💬 সাপোর্ট")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton("👑 Admin Panel")])
        
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def back_menu():
    return ReplyKeyboardMarkup([[KeyboardButton("🔙 ফিরে যান")]], resize_keyboard=True)

# --- Start Handler ---
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

    is_joined = await check_channel_join(context.bot, user_id)
    if not is_joined:
        join_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 অফিসিয়াল চ্যানেলে যোগ দিন", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ যোগ দিয়েছি (Verify)", callback_data="check_join")]
        ])
        welcome_join = (
            "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
            "   👋 **স্বাগতম জিমেইল সেলার বটে!**\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "⚠️ বটটি ব্যবহার করতে আমাদের অফিসিয়াল চ্যানেলে জয়েন থাকা বাধ্যতামূলক। জয়েন করে নিচের বাটনে চাপ দিন:"
        )
        await update.message.reply_text(welcome_join, parse_mode="Markdown", reply_markup=join_btn)
    else:
        welcome_msg = (
            "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
            "   ✨ **সহজ জিমেইল সেলিং প্ল্যাটফর্ম** ✨\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "🎉 **স্বাগতম!** নিচের মেনু থেকে আপনার কাঙ্ক্ষিত অপশনটি বেছে নিন:"
        )
        await update.message.reply_text(welcome_msg, parse_mode="Markdown", reply_markup=main_menu(user_id))

async def check_join_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if await check_channel_join(context.bot, user_id):
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(chat_id=user_id, text="✅ **ভেরিফিকেশন সফল হয়েছে!**", parse_mode="Markdown", reply_markup=main_menu(user_id))
    else:
        await query.answer("❌ আপনি এখনো চ্যানেলে যোগ দেননি! আগে জয়েন করুন।", show_alert=True)

# --- Back to Menu ---
async def cancel_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    await update.message.reply_text("🔙 **মূল মেনুতে ফিরে আসা হয়েছে।**", parse_mode="Markdown", reply_markup=main_menu(user_id))
    return ConversationHandler.END

# --- Submit Gmail Flow ---
async def submit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "╭━━━〔 ⚠️ **নিয়মাবলী ও নির্দেশিকা** 〕━━━╮\n"
        "┃\n"
        "┣ 🔹 শুধুমাত্র সম্পূর্ণ ফ্রেশ Gmail হতে হবে।\n"
        "┣ 🔹 2FA বা টু-স্টেপ অন থাকা যাবে না।\n"
        "┣ 🔹 কোনো Recovery Email বা Phone থাকা যাবে না।\n"
        "┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "👉 আপনার **Gmail ID** টি লিখুন (@gmail.com সহ):"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=back_menu())
    return SUBMIT_EMAIL

async def submit_email_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()
    if "ফিরে যান" in raw_text or "back" in raw_text.lower() or "🔙" in raw_text:
        return await cancel_to_menu(update, context)

    email = raw_text.lower()
    pattern = r"^[a-zA-Z0-9_.+-]+@gmail\.com$"
    if " " in email or not re.match(pattern, email):
        await update.message.reply_text("❌ ভুল ফরম্যাট! কোনো স্পেস ছাড়া সঠিক @gmail.com দিন:", reply_markup=back_menu())
        return SUBMIT_EMAIL

    context.user_data['submitted_email'] = email
    await update.message.reply_text("🔑 এবার আপনার Gmail-এর **Password** টি লিখুন (কোনো স্পেস ছাড়া):", parse_mode="Markdown", reply_markup=back_menu())
    return SUBMIT_PASS

async def submit_pass_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    if "ফিরে যান" in password or "back" in password.lower() or "🔙" in password:
        return await cancel_to_menu(update, context)

    if " " in password:
        await update.message.reply_text("❌ পাসওয়ার্ডে কোনো স্পেস দেওয়া যাবে না! আবার দিন:", reply_markup=back_menu())
        return SUBMIT_PASS

    email = context.user_data['submitted_email']
    user = update.effective_user
    user_id = user.id
    user_full_name = user.full_name
    username = f"@{user.username}" if user.username else "নেই (None)"

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tasks WHERE LOWER(email) = ?", (email,))
    is_duplicate = cur.fetchone()[0] > 0

    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    cur.execute("INSERT INTO tasks (user_id, email, password, status) VALUES (?, ?, ?, 'pending')", (user_id, email, password))
    task_id = cur.lastrowid
    cur.execute("UPDATE users SET hold_balance = hold_balance + ? WHERE user_id = ?", (RATE_PER_GMAIL, user_id))
    conn.commit()
    conn.close()

    admin_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"app_{task_id}"),
         InlineKeyboardButton("❌ Reject", callback_data=f"rej_{task_id}")]
    ])
    
    dup_warning = "\n🚨 **সতর্কতা: এই জিমেইলটি আগেও ব্যবহার/সাবমিট করা হয়েছিল!**\n" if is_duplicate else ""

    admin_msg = (
        f"╭━━━〔 📩 **নতুন জিমেইল সাবমিট** 〕━━━╮\n"
        f"┃\n"
        f"┣ 👤 নাম: **{user_full_name}**\n"
        f"┣ 🏷 ইউজারনেম: {username}\n"
        f"┣ 🆔 আইডি: `{user_id}`\n"
        f"┣ 📧 ইমেইল: `{email}`\n"
        f"┣ 🔑 পাসওয়ার্ড: `{password}`\n"
        f"┣ 🔖 Task ID: #{task_id}\n"
        f"┃\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━╯"
        f"{dup_warning}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown", reply_markup=admin_btn)
    except Exception as e:
        print(f"Admin notify failed: {e}")

    await update.message.reply_text("✅ **আপনার জিমেইল সফলভাবে জমা হয়েছে!**\nঅ্যাডমিন চেক করে Approve করলেই ব্যালেন্স যোগ হবে।", parse_mode="Markdown", reply_markup=main_menu(user_id))
    return ConversationHandler.END

# --- Profile ---
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance, hold_balance, total_withdrawn FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    bal, hold, withdrawn = row if row else (0.0, 0.0, 0.0)
    text = (
        "╭━━━〔 👤 **আপনার প্রোফাইল ড্যাশবোর্ড** 〕━━━╮\n"
        "┃\n"
        f"┣ 🆔 ইউজার আইডি: `{user_id}`\n"
        f"┣ 💰 মূল ব্যালেন্স: `{bal:.2f} TK`\n"
        f"┣ ⏳ হোল্ড ব্যালেন্স: `{hold:.2f} TK`\n"
        f"┣ 💳 মোট উত্তোলন: `{withdrawn:.2f} TK`\n"
        "┃\n"
        f"┣ 💵 প্রতি জিমেইল: {RATE_PER_GMAIL:.0f} TK\n"
        f"┣ 👥 প্রতি সফল রেফার: {REFER_BONUS:.0f} TK\n"
        "┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# --- My Accounts ---
async def my_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT email, status FROM tasks WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
    tasks = cur.fetchall()
    conn.close()

    if not tasks:
        await update.message.reply_text("📂 **আপনি এখনো কোনো জিমেইল জমা দেননি।**", parse_mode="Markdown")
        return

    text = "╭━━━〔 📂 **সাম্প্রতিক জিমেইল হিস্টোরি** 〕━━━╮\n┃\n"
    for email, status in tasks:
        icon = "⏳ Pending" if status == 'pending' else ("✅ Approved" if status == 'approved' else "❌ Rejected")
        text += f"┣ • `{email}` ➔ {icon}\n"
    text += "┃\n╰━━━━━━━━━━━━━━━━━━━━━━━━━╯"

    await update.message.reply_text(text, parse_mode="Markdown")

# --- Withdraw Flow ---
async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    bal = row[0] if row else 0.0
    conn.close()

    if bal < MIN_WITHDRAW:
        await update.message.reply_text(f"❌ আপনার ব্যালেন্স পর্যাপ্ত নয়!\nসর্বনিম্ন উত্তোলন `{MIN_WITHDRAW} TK`। আপনার আছে `{bal:.2f} TK`।", parse_mode="Markdown")
        return ConversationHandler.END

    text = (
        "╭━━━〔 💳 **বিকাশ উত্তোলন (bKash)** 〕━━━╮\n"
        "┃\n"
        "┣ 📢 পেমেন্ট দেওয়া হয়: **শুক্রবার ও সোমবার**\n"
        f"┣ ⚡ সর্বনিম্ন উত্তোলন: `{MIN_WITHDRAW} TK`\n"
        "┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "👉 আপনার **bKash Personal Number** দিন:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=back_menu())
    return WITHDRAW_NUM

async def withdraw_num_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    num = update.message.text.strip()
    if "ফিরে যান" in num or "back" in num.lower() or "🔙" in num:
        return await cancel_to_menu(update, context)

    if len(num) < 11 or not num.isdigit():
        await update.message.reply_text("❌ সঠিক ১১ ডিজিটের বিকাশ নম্বর দিন:", reply_markup=back_menu())
        return WITHDRAW_NUM

    context.user_data['bkash_num'] = num
    await update.message.reply_text("💵 কত টাকা তুলতে চান লিখুন:", reply_markup=back_menu())
    return WITHDRAW_AMOUNT

async def withdraw_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_str = update.message.text.strip()
    if "ফিরে যান" in amount_str or "back" in amount_str.lower() or "🔙" in amount_str:
        return await cancel_to_menu(update, context)

    try:
        amount = float(amount_str)
    except ValueError:
        await update.message.reply_text("❌ সংখ্যায় সঠিক টাকার পরিমাণ দিন:", reply_markup=back_menu())
        return WITHDRAW_AMOUNT

    user = update.effective_user
    user_id = user.id
    user_full_name = user.full_name
    username = f"@{user.username}" if user.username else "নেই (None)"

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    bal = cur.fetchone()[0]

    if amount < MIN_WITHDRAW or amount > bal:
        conn.close()
        await update.message.reply_text(f"❌ অবৈধ পরিমাণ! আপনি সর্বনিম্ন {MIN_WITHDRAW} TK থেকে সর্বোচ্চ {bal:.2f} TK তুলতে পারবেন।", reply_markup=back_menu())
        return WITHDRAW_AMOUNT

    cur.execute("UPDATE users SET balance = balance - ?, total_withdrawn = total_withdrawn + ? WHERE user_id = ?", (amount, amount, user_id))
    cur.execute("INSERT INTO withdrawals (user_id, number, amount, status) VALUES (?, ?, ?, 'pending')", (user_id, context.user_data['bkash_num'], amount))
    w_id = cur.lastrowid
    conn.commit()
    conn.close()

    admin_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Paid", callback_data=f"paid_{w_id}"),
         InlineKeyboardButton("❌ Reject", callback_data=f"wrej_{w_id}")]
    ])
    admin_text = (
        f"╭━━━〔 🚨 **নতুন বিকাশ উইথড্র রিকোয়েস্ট** 〕━━━╮\n"
        f"┃\n"
        f"┣ 👤 নাম: **{user_full_name}**\n"
        f"┣ 🏷 ইউজারনেম: {username}\n"
        f"┣ 🆔 আইডি: `{user_id}`\n"
        f"┣ 📱 বিকাশ নম্বর: `{context.user_data['bkash_num']}`\n"
        f"┣ 💰 পরিমাণ: `{amount} TK`\n"
        f"┣ 🔖 Req ID: #{w_id}\n"
        f"┃\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown", reply_markup=admin_btn)
    except Exception:
        pass
        
    await update.message.reply_text("✅ **আপনার রিকোয়েস্ট সফলভাবে জমা হয়েছে!**\nপ্রতি শুক্রবার ও সোমবার বিকাশ পাঠিয়ে দেওয়া হবে।", parse_mode="Markdown", reply_markup=main_menu(user_id))
    return ConversationHandler.END

# --- Refer & Support ---
async def refer_earn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_info = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE referred_by = ? AND refer_rewarded = 1", (user_id,))
    approved_ref = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE referred_by = ? AND refer_rewarded = 0", (user_id,))
    pending_ref = cur.fetchone()[0]
    conn.close()

    share_text = f"🔥 ঘরে বসেই প্রতি ফ্রেশ জিমেইল সেল করে ১৫ টাকা ইনকাম করুন! ইনস্ট্যান্ট বিকাশ পেমেন্ট। এখনই জয়েন করুন: {ref_link}"
    share_url = f"https://t.me/share/url?url={ref_link}&text={share_text}"

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 রেফারেল শেয়ার করুন (Share / Invite)", url=share_url)]
    ])

    text = (
        "╭━━━〔 👥 **রেফার ও আয় (Refer & Earn)** 〕━━━╮\n"
        "┃\n"
        "┣ 🎁 প্রতি সফল রেফারে পাবেন: **৩ টাকা**\n"
        "┣ ⚠️ রেফার করা ব্যক্তিকে কমপক্ষে ১টি জিমেইল\n"
        "┣    অ্যাপ্রুভ করাতে হবে।\n"
        "┃\n"
        f"┣ ✅ অনুমোদিত রেফার: `{approved_ref}` জন\n"
        f"┣ ⏳ অপেক্ষমাণ রেফার: `{pending_ref}` জন\n"
        "┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "👉 বন্ধুদের সরাসরি ইনভাইট পাঠাতে নিচের বাটনে চাপুন:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=btn)

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("💬 যোগাযোগ করুন (Support)", url=SUPPORT_LINK)]])
    await update.message.reply_text("📞 **যেকোনো সমস্যা বা সহযোগিতার জন্য সরাসরি অ্যাডমিনের সাথে কথা বলুন:**", parse_mode="Markdown", reply_markup=btn)

# --- Admin Broadcast & Panel ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tasks WHERE status = 'approved'")
    approved_tasks = cur.fetchone()[0]
    conn.close()

    admin_kb = [
        [KeyboardButton("📢 Broadcast Message")],
        [KeyboardButton("💾 ব্যাকআপ নিন (Backup DB)")],
        [KeyboardButton("🔙 ফিরে যান")]
    ]
    text = (
        "╭━━━〔 👑 **Admin Control Panel** 〕━━━╮\n"
        "┃\n"
        f"┣ 📊 মোট রেজিস্টার্ড ইউজার: `{total_users}` জন\n"
        f"┣ 📧 মোট অনুমোদিত জিমেইল: `{approved_tasks}` টি\n"
        "┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(admin_kb, resize_keyboard=True))

# --- Database Backup & Restore ---
async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text(f"❌ আপনি এই কমান্ড ব্যবহার করতে পারবেন না।\nআপনার আইডি: `{user_id}` (অ্যাডমিন অনুমোদিত নয়)।", parse_mode="Markdown")
        return

    db_path = os.path.abspath("database.db")
    if not os.path.exists(db_path):
        init_db()

    try:
        await update.message.reply_text("⏳ ডাটাবেজ ব্যাকআপ তৈরি হচ্ছে...")
        with open(db_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename="database.db",
                caption="💾 **আপনার বটের বর্তমান ডাটাবেজ ব্যাকআপ ফাইল।**\n\n📌 সার্ভার রিস্টার্ট হয়ে ডাটা রিসেট হলে এই ফাইলটির ওপর রিপ্লাই দিয়ে `/restore` লিখুন।"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ ব্যাকআপ পাঠাতে সমস্যা হয়েছে: {e}")

async def restore_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ আপনার এই অনুমতি নেই!")
        return

    message = update.message
    doc = message.document
    if not doc and message.reply_to_message:
        doc = message.reply_to_message.document

    if doc and doc.file_name and doc.file_name.endswith(".db"):
        try:
            file = await doc.get_file()
            await file.download_to_drive(custom_path="database.db")
            await update.message.reply_text("🎉 **অভিনন্দন! পূর্বের সব ইউজারের তথ্য ও ব্যালেন্স সফলভাবে রিস্টোর হয়েছে!**", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ রিস্টোর করতে সমস্যা হয়েছে: {e}")
    else:
        await update.message.reply_text("⚠️ দয়া করে `.db` ব্যাকআপ ফাইলের রিপ্লাইয়ে `/restore` লিখুন।")

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "ব্যাকআপ নিন" in text:
        await backup_command(update, context)
    elif "ফিরে যান" in text:
        await cancel_to_menu(update, context)

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("📝 সব ইউজারকে যা পাঠাতে চান সেই মেসেজটি লিখুন:", reply_markup=back_menu())
    return BROADCAST_MSG

async def broadcast_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    msg_text = update.message.text
    if "ফিরে যান" in msg_text or "back" in msg_text.lower() or "🔙" in msg_text:
        return await cancel_to_menu(update, context)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    conn.close()

    sent = 0
    await update.message.reply_text("⏳ মেসেজ পাঠানো শুরু হয়েছে...")
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=f"📢 **অফিসিয়াল নোটিশ:**\n\n{msg_text}", parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await update.message.reply_text(f"✅ সফলভাবে {sent} জন ইউজারের কাছে মেসেজ পৌঁছেছে!", reply_markup=main_menu(ADMIN_ID))
    return ConversationHandler.END

# --- Admin Approval Actions ---
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return
    data = query.data
    conn = get_db()
    cur = conn.cursor()

    if data.startswith("app_"):
        task_id = int(data.split("_")[1])
        cur.execute("SELECT user_id, status FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        
        if row and row[1] == 'pending':
            uid = row[0]
            cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
            cur.execute("UPDATE tasks SET status = 'approved' WHERE id = ?", (task_id,))
            cur.execute("""
                UPDATE users 
                SET balance = balance + ?, 
                    hold_balance = MAX(0.0, hold_balance - ?) 
                WHERE user_id = ?
            """, (RATE_PER_GMAIL, RATE_PER_GMAIL, uid))

            # Refer 3 TK Bonus
            cur.execute("SELECT referred_by, refer_rewarded FROM users WHERE user_id = ?", (uid,))
            ref_data = cur.fetchone()
            if ref_data and ref_data[0] and ref_data[1] == 0:
                ref_id = ref_data[0]
                cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (ref_id,))
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REFER_BONUS, ref_id))
                cur.execute("UPDATE users SET refer_rewarded = 1 WHERE user_id = ?", (uid,))
                try:
                    await context.bot.send_message(chat_id=ref_id, text=f"🎉 আপনার রেফারের ইউজার ১টি জিমেইল অ্যাপ্রুভ করিয়েছে! বোনাস পেয়েছেন {REFER_BONUS:.0f} TK!")
                except Exception:
                    pass

            conn.commit()
            await query.edit_message_text(f"{query.message.text}\n\n✅ APPROVED (৳15 Added)")
            try:
                await context.bot.send_message(chat_id=uid, text="🎉 আপনার জিমেইলটি ভেরিফাই করে অ্যাপ্রুভ করা হয়েছে এবং ১৫ টাকা ব্যালেন্সে যোগ হয়েছে!")
            except Exception:
                pass

    elif data.startswith("rej_"):
        task_id = int(data.split("_")[1])
        cur.execute("SELECT user_id, status FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        if row and row[1] == 'pending':
            uid = row[0]
            cur.execute("UPDATE tasks SET status = 'rejected' WHERE id = ?", (task_id,))
            cur.execute("UPDATE users SET hold_balance = MAX(0.0, hold_balance - ?) WHERE user_id = ?", (RATE_PER_GMAIL, uid))
            conn.commit()
            await query.edit_message_text(f"{query.message.text}\n\n❌ REJECTED")
            try:
                await context.bot.send_message(chat_id=uid, text="❌ আপনার জিমেইলটি সঠিক না থাকায় বাতিল (Reject) করা হয়েছে।")
            except Exception:
                pass

    elif data.startswith("paid_"):
        w_id = int(data.split("_")[1])
        cur.execute("SELECT user_id, number, amount, status FROM withdrawals WHERE id = ?", (w_id,))
        row = cur.fetchone()
        
        if row and row[3] == 'pending':
            uid, number, amt, _ = row
            cur.execute("UPDATE withdrawals SET status = 'paid' WHERE id = ?", (w_id,))
            conn.commit()

            if len(number) >= 11:
                masked_num = f"{number[:3]}****{number[-4:]}"
            else:
                masked_num = f"{number[:2]}****"

            channel_proof_msg = (
                "╭━━━〔 ✅ **নতুন পেমেন্ট পরিশোধ** 〕━━━╮\n"
                "┃\n"
                f"┣ 💵 পরিমাণ: **{amt:.2f} TK**\n"
                f"┣ 📱 বিকাশ নম্বর: `{masked_num}`\n"
                f"┣ ⚡ মেথড: **bKash Personal**\n"
                f"┣ 🕒 স্ট্যাটাস: **PAID (সফল)**\n"
                "┃\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
                "🤖 জিমেইল সেল করে এখনই ইনস্ট্যান্ট আয় করুন:\n"
                "👉 @easy_gmail_seller_bot"
            )
            
            target_chat_id = await resolve_channel_id(context.bot)
            try:
                await context.bot.send_message(chat_id=target_chat_id, text=channel_proof_msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Channel post failed: {e}")
                try:
                    await context.bot.send_message(chat_id=CHANNEL_USERNAME, text=channel_proof_msg, parse_mode="Markdown")
                except Exception as ex2:
                    print(f"Fallback Channel Post Error: {ex2}")

            await query.edit_message_text(f"{query.message.text}\n\n✅ PAID (Req #{w_id} Cleared)")
            try:
                await context.bot.send_message(chat_id=uid, text=f"🎉 আপনার {amt} TK বিকাশ পেমেন্ট পাঠিয়ে দেওয়া হয়েছে!")
            except Exception:
                pass

    elif data.startswith("wrej_"):
        w_id = int(data.split("_")[1])
        cur.execute("SELECT user_id, amount, status FROM withdrawals WHERE id = ?", (w_id,))
        uid, amt, st = cur.fetchone()
        if st == 'pending':
            cur.execute("UPDATE withdrawals SET status = 'rejected' WHERE id = ?", (w_id,))
            cur.execute("UPDATE users SET balance = balance + ?, total_withdrawn = total_withdrawn - ? WHERE user_id = ?", (amt, amt, uid))
            conn.commit()
            await query.edit_message_text(f"{query.message.text}\n\n❌ REJECTED (REFUNDED)")
            try:
                await context.bot.send_message(chat_id=uid, text=f"❌ আপনার উত্তোলন বাতিল করা হয়েছে এবং {amt} TK ব্যালেন্সে ফেরত দেওয়া হয়েছে।")
            except Exception:
                pass

    conn.close()

# --- Server Keepalive ---
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    submit_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📥 জিমেইল জমা দিন$"), submit_start)],
        states={
            SUBMIT_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_email_input)],
            SUBMIT_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_pass_input)]
        },
        fallbacks=[MessageHandler(filters.Regex(r"(🔙|ফিরে যান|Back|back)"), cancel_to_menu), CommandHandler("start", start)]
    )

    withdraw_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💳 উইথড্র$"), withdraw_start)],
        states={
            WITHDRAW_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_num_input)],
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount_input)]
        },
        fallbacks=[MessageHandler(filters.Regex(r"(🔙|ফিরে যান|Back|back)"), cancel_to_menu), CommandHandler("start", start)]
    )

    broadcast_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 Broadcast Message$"), broadcast_start)],
        states={
            BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_process)]
        },
        fallbacks=[MessageHandler(filters.Regex(r"(🔙|ফিরে যান|Back|back)"), cancel_to_menu), CommandHandler("start", start)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(CommandHandler("restore", restore_database))
    application.add_handler(CallbackQueryHandler(check_join_btn, pattern="^check_join$"))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^(app_|rej_|paid_|wrej_)"))
    application.add_handler(submit_conv)
    application.add_handler(withdraw_conv)
    application.add_handler(broadcast_conv)
    application.add_handler(MessageHandler(filters.Regex(r"^(💾 ব্যাকআপ নিন|🔙 ফিরে যান)"), handle_admin_text))
    application.add_handler(MessageHandler(filters.Regex("^👤 প্রোফাইল$"), show_profile))
    application.add_handler(MessageHandler(filters.Regex("^📂 আমার অ্যাকাউন্টস$"), my_accounts))
    application.add_handler(MessageHandler(filters.Regex("^👥 রেফার ও আয়$"), refer_earn))
    application.add_handler(MessageHandler(filters.Regex("^💬 সাপোর্ট$"), support))
    application.add_handler(MessageHandler(filters.Regex("^👑 Admin Panel$"), admin_panel))

    # Web Server
    server = web.Application()
    server.router.add_get('/', handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    await application.initialize()
    await application.start()
    
    asyncio.create_task(resolve_channel_id(application.bot))

    await application.updater.start_polling(drop_pending_updates=True)
    print("Bot is successfully running!")

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
