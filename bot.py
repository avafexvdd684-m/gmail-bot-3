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

# --- Helper: Get Channel ID ---
async def resolve_channel_id(bot):
    global CACHED_CHANNEL_ID
    if CACHED_CHANNEL_ID:
        return CACHED_CHANNEL_ID
    try:
        chat = await bot.get_chat(CHANNEL_USERNAME)
        CACHED_CHANNEL_ID = chat.id
        return CACHED_CHANNEL_ID
    except Exception:
        return CHANNEL_USERNAME

# --- Helper: Channel Join Verification ---
async def check_channel_join(bot, user_id):
    try:
        chat_id = await resolve_channel_id(bot)
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator', 'restricted']:
            return True
        return False
    except Exception:
        return True 

# --- Keyboards ---
def main_menu(user_id):
    kb = [
        [KeyboardButton("📥 জিমেইল সেল করুন")],
        [KeyboardButton("👤 ড্যাশবোর্ড"), KeyboardButton("📂 সেলস হিস্টোরি")],
        [KeyboardButton("💳 টাকা উত্তোলন"), KeyboardButton("🎁 রেফার ও ইনভাইট")],
        [KeyboardButton("💬 কাস্টমার কেয়ার")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton("👑 অ্যাডমিন কন্ট্রোল")])
        
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def back_menu():
    return ReplyKeyboardMarkup([[KeyboardButton("🔙 ফিরে যান (Back)")]], resize_keyboard=True)

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
            [InlineKeyboardButton("📢 জয়েন করুন আমাদের চ্যানেল", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ জয়েন সম্পন্ন করেছি", callback_data="check_join")]
        ])
        msg = (
            "✦ ━━━━━━━━━━━━━━━━━━ ✦\n"
            "   👑  𝐖 𝐄 𝐋 𝐂 𝐎 𝐌 𝐄  👑\n"
            "✦ ━━━━━━━━━━━━━━━━━━ ✦\n\n"
            "👋 হ্যালো প্রিয় বন্ধু,\n"
            "আমাদের বটের সব সেবা সক্রিয় করতে অফিসিয়াল চ্যানেলে যুক্ত থাকা প্রয়োজন।\n\n"
            "👉 নিচের লিংকে ক্লিক করে চ্যানেলে জয়েন করুন এবং ভেরিফাই বাটনে চাপ দিন।"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=join_btn)
    else:
        welcome_text = (
            "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n"
            "   ⚡  𝐐𝐔𝐈𝐂𝐊 𝐆𝐌𝐀𝐈𝐋 𝐒𝐄𝐋𝐋𝐄𝐑  ⚡\n"
            "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n\n"
            "🎉 **স্বাগতম আমাদের অফিসিয়াল প্ল্যাটফর্মে!**\n"
            "ঘরে বসেই ফ্রেশ জিমেইল সেল করে নিশ্চিত ইনকাম করুন।\n\n"
            "💵 **প্রতি জিমেইল রেট:** `১৫.০০ টাকা`\n"
            "🎁 **প্রতি সফল রেফারেল:** `৩.০০ টাকা`\n"
            "📱 **পেমেন্ট মেথড:** `বিকাশ পার্সোনাল`\n\n"
            "👇 কাজ শুরু করতে নিচের মেনু থেকে অপশন বেছে নিন:"
        )
        await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=main_menu(user_id))

async def check_join_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if await check_channel_join(context.bot, user_id):
        try:
            await query.message.delete()
        except Exception:
            pass
        succ_msg = (
            "✦ ━━━━━━━━━━━━━━━━━━ ✦\n"
            "   ✅  𝐕𝐄𝐑𝐈𝐅𝐈𝐄𝐃 𝐔𝐒𝐄𝐑  ✅\n"
            "✦ ━━━━━━━━━━━━━━━━━━ ✦\n\n"
            "অসাধারণ! আপনার ভেরিফিকেশন সফল হয়েছে। এখন আপনি কাজ শুরু করতে পারেন।"
        )
        await context.bot.send_message(chat_id=user_id, text=succ_msg, parse_mode="Markdown", reply_markup=main_menu(user_id))
    else:
        await query.answer("❌ আপনি এখনো চ্যানেলে যোগ দেননি! অনুগ্রহ করে জয়েন করুন।", show_alert=True)

# --- Back to Menu ---
async def cancel_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    await update.message.reply_text("🔙 **মেনুতে ফিরে আসা হয়েছে।**", parse_mode="Markdown", reply_markup=main_menu(user_id))
    return ConversationHandler.END

# --- Submit Gmail Flow ---
async def submit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n"
        "   📥  𝐒𝐔𝐁𝐌𝐈𝐓 𝐘𝐎𝐔𝐑 𝐆𝐌𝐀𝐈𝐋  📥\n"
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n\n"
        "⚠️ **সতর্কতা ও কাজের নিয়মাবলী:**\n"
        "├─ 📌 সম্পূর্ণ নতুন ও ফ্রেশ Gmail হতে হবে।\n"
        "├─ 🔐 **2FA (Two-Factor)** অফ থাকতে হবে।\n"
        "└─ 📵 কোনো রিকভারি মেইল বা ফোন নম্বর থাকা চলবে না।\n\n"
        "👉 আপনার **Gmail ID** টি নিচে লিখুন (@gmail.com সহ):"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=back_menu())
    return SUBMIT_EMAIL

async def submit_email_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip().lower()
    if email == "🔙 ফিরে যান (Back)":
        return await cancel_to_menu(update, context)

    pattern = r"^[a-zA-Z0-9_.+-]+@gmail\.com$"
    if " " in email or not re.match(pattern, email):
        await update.message.reply_text("❌ **ভুল ফরম্যাট!** কোনো স্পেস ছাড়া সঠিক `@gmail.com` দিন:")
        return SUBMIT_EMAIL

    context.user_data['submitted_email'] = email
    await update.message.reply_text("🔑 এবার আপনার জিমেইলের **পাসওয়ার্ড (Password)** দিন (স্পেস ছাড়া):", parse_mode="Markdown", reply_markup=back_menu())
    return SUBMIT_PASS

async def submit_pass_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    if password == "🔙 ফিরে যান (Back)":
        return await cancel_to_menu(update, context)

    if " " in password:
        await update.message.reply_text("❌ **পাসওয়ার্ডে কোনো স্পেস গ্রহণযোগ্য নয়!** আবার দিন:")
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
    
    dup_warning = "\n🚨 **সতর্কতা: এই জিমেইলটি আগেও ব্যবহার করা হয়েছিল!**\n" if is_duplicate else ""

    admin_msg = (
        f"✦ ━━━━━━━━━━━━━━━━━━ ✦\n"
        f"   📩 **NEW TASK REVIEW** 📩\n"
        f"✦ ━━━━━━━━━━━━━━━━━━ ✦\n"
        f"{dup_warning}\n"
        f"👤 **ইউজার:** {user_full_name}\n"
        f"🏷 **ইউজারনেম:** {username}\n"
        f"🆔 **ইউজার আইডি:** `{user_id}`\n"
        f"📧 **জিমেইল:** `{email}`\n"
        f"🔑 **পাসওয়ার্ড:** `{password}`\n"
        f"🔢 **টাস্ক কোড:** `#{task_id}`"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown", reply_markup=admin_btn)
    except Exception:
        pass

    success_alert = (
        "✦ ━━━━━━━━━━━━━━━━━━ ✦\n"
        "   ✅  **জমা সফল হয়েছে**  ✅\n"
        "✦ ━━━━━━━━━━━━━━━━━━ ✦\n\n"
        "আপনার জিমেইলটি সফলভাবে সাবমিট হয়েছে।\n"
        "অ্যাডমিন ভেরিফাই করে অ্যাপ্রুভ করলেই ব্যালেন্সে **১৫.০০ টাকা** যোগ হয়ে যাবে।"
    )
    await update.message.reply_text(success_alert, parse_mode="Markdown", reply_markup=main_menu(user_id))
    return ConversationHandler.END

# --- Profile Dashboard ---
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance, hold_balance, total_withdrawn FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    bal, hold, withdrawn = row if row else (0.0, 0.0, 0.0)
    profile_text = (
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n"
        "   👤  **𝐔𝐒𝐄𝐑 𝐃𝐀𝐒𝐇𝐁𝐎𝐀𝐑𝐃**  👤\n"
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n\n"
        f"🆔 **আপনার আইডি:** `{user_id}`\n\n"
        f"💰 **উত্তোলনযোগ্য ব্যালেন্স:** `{bal:.2f} BDT`\n"
        f"⏳ **পেন্ডিং / হোল্ড ব্যালেন্স:** `{hold:.2f} BDT`\n"
        f"💳 **মোট উত্তোলনকৃত টাকা:** `{withdrawn:.2f} BDT`\n\n"
        "────────────────────\n"
        f"💎 প্রতি জিমেইল মূল্য: `{RATE_PER_GMAIL:.0f} TK`\n"
        f"🎁 প্রতি সফল রেফার বোনাস: `{REFER_BONUS:.0f} TK`\n"
        "────────────────────"
    )
    await update.message.reply_text(profile_text, parse_mode="Markdown")

# --- My Accounts History ---
async def my_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT email, status FROM tasks WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
    tasks = cur.fetchall()
    conn.close()

    if not tasks:
        await update.message.reply_text("📂 **আপনার জমা দেওয়া কোনো অ্যাকাউন্ট এখনো পাওয়া যায়নি।**")
        return

    text = (
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n"
        "   📂  **𝐑𝐄𝐂𝐄𝐍𝐓 𝐇𝐈𝐒𝐓𝐎𝐑𝐘**  📂\n"
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n\n"
    )
    for email, status in tasks:
        icon = "⏳ Pending" if status == 'pending' else ("✅ Approved" if status == 'approved' else "❌ Rejected")
        text += f"▪️ `{email}`\n   └ স্ট্যাটাস: **{icon}**\n\n"

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
        err_msg = (
            "✦ ━━━━━━━━━━━━━━━━━━ ✦\n"
            "   ⚠️  **অপ্রতুল ব্যালেন্স**  ⚠️\n"
            "✦ ━━━━━━━━━━━━━━━━━━ ✦\n\n"
            f"❌ আপনার ব্যালেন্স পর্যাপ্ত নয়!\n\n"
            f"🔹 সর্বনিম্ন উত্তোলন: `{MIN_WITHDRAW:.2f} TK`\n"
            f"🔹 আপনার বর্তমান ব্যালেন্স: `{bal:.2f} TK`"
        )
        await update.message.reply_text(err_msg, parse_mode="Markdown")
        return ConversationHandler.END

    msg = (
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n"
        "   💳  **𝐁𝐊𝐀𝐒𝐇 𝐖𝐈𝐓𝐇𝐃𝐑𝐀𝐖**  💳\n"
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n\n"
        "📢 **পেমেন্ট শিডিউল:**\n"
        "প্রতি **শুক্রবার** এবং **সোমবার** সমস্ত পেমেন্ট ক্লিয়ার করা হয়।\n\n"
        "👉 আপনার **১১ ডিজিটের বিকাশ নম্বর** লিখুন:"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=back_menu())
    return WITHDRAW_NUM

async def withdraw_num_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    num = update.message.text.strip()
    if num == "🔙 ফিরে যান (Back)":
        return await cancel_to_menu(update, context)

    if len(num) < 11 or not num.isdigit():
        await update.message.reply_text("❌ **সঠিক ১১ ডিজিটের বিকাশ নম্বর দিন:**")
        return WITHDRAW_NUM

    context.user_data['bkash_num'] = num
    await update.message.reply_text("💵 **কত টাকা উত্তোলন করতে চান লিখুন:**", parse_mode="Markdown", reply_markup=back_menu())
    return WITHDRAW_AMOUNT

async def withdraw_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_str = update.message.text.strip()
    if amount_str == "🔙 ফিরে যান (Back)":
        return await cancel_to_menu(update, context)

    try:
        amount = float(amount_str)
    except ValueError:
        await update.message.reply_text("❌ সংখ্যায় সঠিক টাকার পরিমাণ লিখুন:")
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
        await update.message.reply_text(f"❌ অবৈধ পরিমাণ! আপনি সর্বনিম্ন `{MIN_WITHDRAW}` TK থেকে সর্বোচ্চ `{bal:.2f}` TK তুলতে পারবেন।", parse_mode="Markdown")
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
        f"✦ ━━━━━━━━━━━━━━━━━━ ✦\n"
        f"   🚨 **NEW WITHDRAW REQ** 🚨\n"
        f"✦ ━━━━━━━━━━━━━━━━━━ ✦\n\n"
        f"👤 **ইউজার:** {user_full_name}\n"
        f"🏷 **ইউজারনেম:** {username}\n"
        f"🆔 **আইডি:** `{user_id}`\n"
        f"📱 **বিকাশ নম্বর:** `{context.user_data['bkash_num']}`\n"
        f"💰 **পরিমাণ:** `{amount:.2f} TK`\n"
        f"🔢 **রিকোয়েস্ট আইডি:** `#{w_id}`"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown", reply_markup=admin_btn)
    except Exception:
        pass
        
    conf_msg = (
        "✦ ━━━━━━━━━━━━━━━━━━ ✦\n"
        "   ✅  **রিকোয়েস্ট সফল**  ✅\n"
        "✦ ━━━━━━━━━━━━━━━━━━ ✦\n\n"
        f"💵 টাকার পরিমাণ: `{amount:.2f} TK`\n"
        f"📱 বিকাশ নম্বর: `{context.user_data['bkash_num']}`\n\n"
        "আপনার রিকোয়েস্ট জমা হয়েছে। নির্ধারিত সময়ে আপনার নম্বরে টাকা পৌঁছে যাবে।"
    )
    await update.message.reply_text(conf_msg, parse_mode="Markdown", reply_markup=main_menu(user_id))
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

    share_text = f"🔥 প্রতি জিমেইল সেল করে ১৫ টাকা ইনকাম করুন! বিকাশ পেমেন্ট। এখনই যোগ দিন: {ref_link}"
    share_url = f"https://t.me/share/url?url={ref_link}&text={share_text}"

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 বন্ধুদের ইনভাইট করুন (Share Link)", url=share_url)]
    ])

    text = (
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n"
        "   👥  **𝐑𝐄𝐅𝐄𝐑 & 𝐄𝐀𝐑𝐍**  👥\n"
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n\n"
        "🎁 প্রতি সফল রেফারে পাবেন: **৩.০০ টাকা**\n\n"
        "📌 **শর্ত:** আপনার রেফার করা ফ্রেন্ডকে কমপক্ষে ১টি জিমেইল অ্যাপ্রুভ করাতে হবে।\n\n"
        f"✅ অনুমোদিত রেফার (Approved): `{approved_ref}` জন\n"
        f"⏳ অপেক্ষমাণ রেফার (Pending): `{pending_ref}` জন\n\n"
        "👇 বন্ধুদের সাথে শেয়ার করতে নিচের বাটনে চাপ দিন:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=btn)

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("💬 সরাসরি সাপোর্ট ইনবক্স", url=SUPPORT_LINK)]])
    msg = (
        "✦ ━━━━━━━━━━━━━━━━━━ ✦\n"
        "   📞  **𝟐𝟒/𝟕 𝐒𝐔𝐏𝐏𝐎𝐑𝐓**  📞\n"
        "✦ ━━━━━━━━━━━━━━━━━━ ✦\n\n"
        "যেকোনো জিজ্ঞাসা, পেমেন্ট সংক্রান্ত তথ্য বা সমস্যার সমাধানের জন্য আমাদের হেল্প সেন্টারে যোগাযোগ করতে নিচের বাটনে চাপ দিন:"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=btn)

# --- Admin Panel ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    conn.close()

    admin_kb = [
        [KeyboardButton("📢 Broadcast Message")],
        [KeyboardButton("🔙 ফিরে যান (Back)")]
    ]
    await update.message.reply_text(
        f"✦ ━━━━━━━━━━━━━━━━━━ ✦\n"
        f"   👑  **ADMIN DASHBOARD**  👑\n"
        f"✦ ━━━━━━━━━━━━━━━━━━ ✦\n\n"
        f"📊 মোট বট ইউজার: `{total_users}` জন\n\n"
        "সবাইকে মেসেজ পাঠাতে ব্রডকাস্ট চাপুন:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(admin_kb, resize_keyboard=True)
    )

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("📝 **ব্রডকাস্ট নোটিশটি লিখুন:**", parse_mode="Markdown", reply_markup=back_menu())
    return BROADCAST_MSG

async def broadcast_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    msg_text = update.message.text
    if msg_text == "🔙 ফিরে যান (Back)":
        return await cancel_to_menu(update, context)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    conn.close()

    sent = 0
    await update.message.reply_text("⏳ নোটিশ পাঠানো হচ্ছে...")
    formatted_broadcast = (
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n"
        "   📢  **𝐎𝐅𝐅𝐈𝐂𝐈𝐀𝐋 𝐍𝐎𝐓𝐈𝐂𝐄**  📢\n"
        "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n\n"
        f"{msg_text}"
    )
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=formatted_broadcast, parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await update.message.reply_text(f"✅ সফলভাবে **{sent}** জন ইউজারের কাছে নোটিশ পৌঁছেছে!", parse_mode="Markdown", reply_markup=main_menu(ADMIN_ID))
    return ConversationHandler.END

# --- Admin Callback Actions ---
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
                    await context.bot.send_message(chat_id=ref_id, text=f"🎉 **অভিনন্দন!**\nআপনার রেফারের ইউজার ১টি জিমেইল অ্যাপ্রুভ করিয়েছে। রেফার বোনাস **{REFER_BONUS:.0f} TK** যোগ হয়েছে!")
                except Exception:
                    pass

            conn.commit()
            await query.edit_message_text(f"{query.message.text}\n\n✅ 𝐀𝐏𝐏𝐑𝐎𝐕𝐄𝐃 (৳১৫ যোগ হয়েছে)")
            try:
                user_win = (
                    "✦ ━━━━━━━━━━━━━━━━━━ ✦\n"
                    "   🎉  **জিমেইল অনুমোদিত**  🎉\n"
                    "✦ ━━━━━━━━━━━━━━━━━━ ✦\n\n"
                    "আপনার জমা দেওয়া জিমেইলটি সফলভাবে ভেরিফাই হয়েছে।\n"
                    "💰 মূল ব্যালেন্সে **১৫.০০ টাকা** যোগ করা হয়েছে।"
                )
                await context.bot.send_message(chat_id=uid, text=user_win, parse_mode="Markdown")
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
            await query.edit_message_text(f"{query.message.text}\n\n❌ 𝐑𝐄𝐉𝐄𝐂𝐓𝐄𝐃")
            try:
                rej_msg = (
                    "✦ ━━━━━━━━━━━━━━━━━━ ✦\n"
                    "   ❌  **জিমেইল বাতিল হয়েছে**  ❌\n"
                    "✦ ━━━━━━━━━━━━━━━━━━ ✦\n\n"
                    "আপনার দেওয়া জিমেইলটিতে সমস্যা (2FA অন/ভুল পাসওয়ার্ড/রিকভারি যুক্ত) থাকায় এটি রিজেক্ট করা হয়েছে।"
                )
                await context.bot.send_message(chat_id=uid, text=rej_msg, parse_mode="Markdown")
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
                "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n"
                "   ✅  **𝐏𝐀𝐘𝐌𝐄𝐍𝐓 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐄**  ✅\n"
                "✦ ━━━━━━━━━━━━━━━━━━━━ ✦\n\n"
                f"💵 **টাকার পরিমাণ:** `{amt:.2f} BDT`\n"
                f"📱 **বিকাশ নম্বর:** `{masked_num}`\n"
                f"⚡ **পেমেন্ট মেথড:** `bKash Personal`\n"
                f"🕒 **স্ট্যাটাস:** `PAID (সফল)`\n\n"
                "────────────────────\n"
                "🤖 ঘরে বসেই প্রতিদিন আনলিমিটেড আয় করুন!\n"
                "👉 @easy_gmail_seller_bot"
            )
            
            target_chat_id = await resolve_channel_id(context.bot)
            try:
                await context.bot.send_message(chat_id=target_chat_id, text=channel_proof_msg, parse_mode="Markdown")
            except Exception:
                try:
                    await context.bot.send_message(chat_id=CHANNEL_USERNAME, text=channel_proof_msg, parse_mode="Markdown")
                except Exception:
                    pass

            await query.edit_message_text(f"{query.message.text}\n\n✅ 𝐏𝐀𝐈𝐃 𝐒𝐔𝐂𝐂𝐄𝐒𝐒")
            try:
                await context.bot.send_message(chat_id=uid, text=f"🎉 **অভিনন্দন!** আপনার `{amt:.2f} TK` বিকাশ উত্তোলন সফলভাবে পাঠানো হয়েছে!", parse_mode="Markdown")
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
            await query.edit_message_text(f"{query.message.text}\n\n❌ 𝐑𝐄𝐉𝐄𝐂𝐓𝐄𝐃 (Refunded)")
            try:
                await context.bot.send_message(chat_id=uid, text=f"❌ আপনার `{amt:.2f} TK` উত্তোলন রিকোয়েস্ট বাতিল করা হয়েছে এবং টাকা মূল ব্যালেন্সে ফেরত দেওয়া হয়েছে।", parse_mode="Markdown")
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
        entry_points=[MessageHandler(filters.Regex("^📥 জিমেইল সেল করুন$"), submit_start)],
        states={
            SUBMIT_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_email_input)],
            SUBMIT_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_pass_input)]
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙 ফিরে যান \(Back\)$"), cancel_to_menu), CommandHandler("start", start)]
    )

    withdraw_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💳 টাকা উত্তোলন$"), withdraw_start)],
        states={
            WITHDRAW_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_num_input)],
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount_input)]
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙 ফিরে যান \(Back\)$"), cancel_to_menu), CommandHandler("start", start)]
    )

    broadcast_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 Broadcast Message$"), broadcast_start)],
        states={
            BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_process)]
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙 ফিরে যান \(Back\)$"), cancel_to_menu), CommandHandler("start", start)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(check_join_btn, pattern="^check_join$"))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^(app_|rej_|paid_|wrej_)"))
    application.add_handler(submit_conv)
    application.add_handler(withdraw_conv)
    application.add_handler(broadcast_conv)
    application.add_handler(MessageHandler(filters.Regex("^🔙 ফিরে যান \(Back\)$"), cancel_to_menu))
    application.add_handler(MessageHandler(filters.Regex("^👤 ড্যাশবোর্ড$"), show_profile))
    application.add_handler(MessageHandler(filters.Regex("^📂 সেলস হিস্টোরি$"), my_accounts))
    application.add_handler(MessageHandler(filters.Regex("^🎁 রেফার ও ইনভাইট$"), refer_earn))
    application.add_handler(MessageHandler(filters.Regex("^💬 কাস্টমার কেয়ার$"), support))
    application.add_handler(MessageHandler(filters.Regex("^👑 অ্যাডমিন কন্ট্রোল$"), admin_panel))

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
    print("Bot is successfully running with Premium Font!")

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
