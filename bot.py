"""
فروشگاه کانفیگ تلگرام
نیاز: pip install python-telegram-bot==20.7
"""

import os, json, datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ─── تنظیمات ────────────────────────────────────────────────
TOKEN       = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID    = int(os.getenv("ADMIN_ID", "123456789"))  # آیدی عددی ادمین

DB_FILE     = "data.json"

# ─── مراحل ConversationHandler ──────────────────────────────
AWAIT_RECEIPT = 1   # انتظار برای رسید پرداخت

# ─── دیتابیس ساده (JSON) ────────────────────────────────────
def load_db():
    if not os.path.exists(DB_FILE):
        return {"products": [], "orders": [], "next_order_id": 1}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def init_db():
    db = load_db()
    if not db["products"]:
        db["products"] = [
            {"id": 1, "name": "کانفیگ ۱ ماهه",  "desc": "سرعت بالا | ترافیک نامحدود", "price": 50000,  "active": True},
            {"id": 2, "name": "کانفیگ ۳ ماهه",  "desc": "سرعت بالا | ترافیک نامحدود", "price": 130000, "active": True},
            {"id": 3, "name": "کانفیگ ۶ ماهه",  "desc": "سرعت بالا | ترافیک نامحدود", "price": 230000, "active": True},
            {"id": 4, "name": "سرویس اختصاصی",   "desc": "سرور اختصاصی | پشتیبانی VIP", "price": 500000, "active": True},
        ]
        save_db(db)
    return db

# ─── /start ─────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    kb = [
        [InlineKeyboardButton("🛍️ محصولات", callback_data="products"),
         InlineKeyboardButton("📦 سفارشات من", callback_data="my_orders")],
        [InlineKeyboardButton("📞 پشتیبانی", callback_data="support")],
    ]
    text = (
        f"سلام {user.first_name} عزیز 👋\n\n"
        "به فروشگاه کانفیگ و سرویس شبکه خوش اومدی 🌐\n"
        "از منوی زیر انتخاب کن:"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ─── نمایش محصولات ──────────────────────────────────────────
async def show_products(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    products = [p for p in db["products"] if p["active"]]
    query = update.callback_query
    await query.answer()

    if not products:
        await query.edit_message_text("❌ محصولی موجود نیست.")
        return

    kb = []
    for p in products:
        label = f"{p['name']} — {p['price']:,} تومان"
        kb.append([InlineKeyboardButton(label, callback_data=f"product_{p['id']}")])
    kb.append([InlineKeyboardButton("🏠 بازگشت", callback_data="home")])

    await query.edit_message_text(
        "🛍️ *محصولات موجود:*\nیه محصول انتخاب کن:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ─── جزئیات محصول ───────────────────────────────────────────
async def product_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[1])
    db = load_db()
    p = next((x for x in db["products"] if x["id"] == pid), None)
    if not p:
        await query.edit_message_text("محصول پیدا نشد.")
        return

    ctx.user_data["selected_product"] = pid
    kb = [
        [InlineKeyboardButton("✅ خرید این محصول", callback_data=f"buy_{pid}")],
        [InlineKeyboardButton("🔙 برگشت به محصولات", callback_data="products")],
    ]
    text = (
        f"📦 *{p['name']}*\n\n"
        f"📝 {p['desc']}\n\n"
        f"💰 قیمت: *{p['price']:,} تومان*"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

# ─── شروع خرید ──────────────────────────────────────────────
async def buy_product(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[1])
    db = load_db()
    p = next((x for x in db["products"] if x["id"] == pid), None)
    if not p:
        await query.edit_message_text("محصول پیدا نشد.")
        return

    ctx.user_data["pending_product"] = pid
    text = (
        f"💳 *روش پرداخت:*\n\n"
        f"مبلغ: *{p['price']:,} تومان*\n\n"
        f"شماره کارت:\n`6219 8610 XXXX XXXX`\n\n"
        f"بعد از واریز، رسید (اسکرین‌شات یا شماره پیگیری) رو اینجا بفرست 📸"
    )
    kb = [[InlineKeyboardButton("❌ انصراف", callback_data="products")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return AWAIT_RECEIPT

# ─── دریافت رسید ────────────────────────────────────────────
async def receive_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    pid = ctx.user_data.get("pending_product")
    p = next((x for x in db["products"] if x["id"] == pid), None)
    user = update.effective_user

    if not p:
        await update.message.reply_text("⚠️ مشکلی پیش اومد. دوباره /start بزن.")
        return ConversationHandler.END

    order_id = db["next_order_id"]
    db["next_order_id"] += 1
    order = {
        "id": order_id,
        "user_id": user.id,
        "username": user.username or "",
        "first_name": user.first_name,
        "product_id": pid,
        "product_name": p["name"],
        "price": p["price"],
        "status": "pending",  # pending / approved / rejected
        "created_at": datetime.datetime.now().isoformat(),
        "config": ""
    }
    db["orders"].append(order)
    save_db(db)

    # پیام تأیید به کاربر
    await update.message.reply_text(
        f"✅ سفارش #{order_id} ثبت شد!\n"
        "رسید دریافت شد و در حال بررسی‌ه. بعد از تأیید، کانفیگ برات ارسال می‌شه 🙏"
    )

    # اطلاع به ادمین
    caption = (
        f"🔔 *سفارش جدید #{order_id}*\n\n"
        f"👤 کاربر: {user.first_name} (@{user.username or '-'})\n"
        f"🆔 آیدی: `{user.id}`\n"
        f"📦 محصول: {p['name']}\n"
        f"💰 مبلغ: {p['price']:,} تومان"
    )
    kb_admin = [
        [
            InlineKeyboardButton("✅ تأیید و ارسال کانفیگ", callback_data=f"approve_{order_id}"),
            InlineKeyboardButton("❌ رد", callback_data=f"reject_{order_id}"),
        ]
    ]
    try:
        if update.message.photo:
            await ctx.bot.send_photo(
                ADMIN_ID, update.message.photo[-1].file_id,
                caption=caption, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb_admin)
            )
        elif update.message.document:
            await ctx.bot.send_document(
                ADMIN_ID, update.message.document.file_id,
                caption=caption, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb_admin)
            )
        else:
            await ctx.bot.send_message(
                ADMIN_ID,
                caption + f"\n\n💬 متن: {update.message.text}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb_admin)
            )
    except Exception as e:
        print(f"ارسال به ادمین خطا: {e}")

    ctx.user_data.pop("pending_product", None)
    return ConversationHandler.END

# ─── تأیید سفارش توسط ادمین ─────────────────────────────────
async def admin_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ دسترسی ندارید.", show_alert=True)
        return

    order_id = int(query.data.split("_")[1])
    db = load_db()
    order = next((o for o in db["orders"] if o["id"] == order_id), None)
    if not order:
        await query.answer("سفارش پیدا نشد.")
        return

    await query.answer()
    # از ادمین می‌خواد کانفیگ رو بفرسته
    ctx.bot_data[f"approve_order_{query.from_user.id}"] = order_id
    await query.edit_message_caption(
        query.message.caption + "\n\n⏳ *کانفیگ رو بفرست تا ارسال بشه:*",
        parse_mode="Markdown"
    )
    # state رو در user_data ادمین نگه می‌داریم
    ctx.user_data["awaiting_config_for"] = order_id

# ─── دریافت کانفیگ از ادمین ─────────────────────────────────
async def admin_send_config(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    order_id = ctx.user_data.get("awaiting_config_for")
    if not order_id:
        return

    db = load_db()
    order = next((o for o in db["orders"] if o["id"] == order_id), None)
    if not order:
        await update.message.reply_text("سفارش پیدا نشد.")
        ctx.user_data.pop("awaiting_config_for", None)
        return

    config_text = update.message.text or ""
    order["status"] = "approved"
    order["config"] = config_text
    save_db(db)

    # ارسال کانفیگ به کاربر
    try:
        await ctx.bot.send_message(
            order["user_id"],
            f"🎉 سفارش #{order_id} تأیید شد!\n\n"
            f"📦 *{order['product_name']}*\n\n"
            f"🔑 *کانفیگ شما:*\n`{config_text}`\n\n"
            "ممنون از خریدت 🙏 اگه مشکلی بود پیام بده.",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ کانفیگ سفارش #{order_id} ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطا در ارسال: {e}")

    ctx.user_data.pop("awaiting_config_for", None)

# ─── رد سفارش توسط ادمین ────────────────────────────────────
async def admin_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ دسترسی ندارید.", show_alert=True)
        return

    order_id = int(query.data.split("_")[1])
    db = load_db()
    order = next((o for o in db["orders"] if o["id"] == order_id), None)
    if not order:
        await query.answer("سفارش پیدا نشد.")
        return

    order["status"] = "rejected"
    save_db(db)
    await query.answer("رد شد.")
    await query.edit_message_caption(
        (query.message.caption or "") + "\n\n❌ رد شد.",
        parse_mode="Markdown"
    )
    try:
        await ctx.bot.send_message(
            order["user_id"],
            f"❌ متأسفانه سفارش #{order_id} تأیید نشد.\n"
            "لطفاً با پشتیبانی تماس بگیر."
        )
    except:
        pass

# ─── سفارشات کاربر ──────────────────────────────────────────
async def my_orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    uid = query.from_user.id
    orders = [o for o in db["orders"] if o["user_id"] == uid]

    if not orders:
        kb = [[InlineKeyboardButton("🏠 بازگشت", callback_data="home")]]
        await query.edit_message_text("📦 سفارشی ثبت نکردی.", reply_markup=InlineKeyboardMarkup(kb))
        return

    status_map = {"pending": "⏳ در انتظار", "approved": "✅ تأیید شده", "rejected": "❌ رد شده"}
    text = "📦 *سفارشات من:*\n\n"
    for o in reversed(orders[-5:]):
        text += f"#{o['id']} | {o['product_name']} | {status_map.get(o['status'], o['status'])}\n"

    kb = [[InlineKeyboardButton("🏠 بازگشت", callback_data="home")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

# ─── پشتیبانی ───────────────────────────────────────────────
async def support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [[InlineKeyboardButton("🏠 بازگشت", callback_data="home")]]
    await query.edit_message_text(
        "📞 *پشتیبانی:*\n\n"
        "برای هر مشکلی مستقیم پیام بده:\n"
        "@your_support_username",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ─── پنل ادمین ──────────────────────────────────────────────
async def admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ دسترسی ندارید.")
        return
    db = load_db()
    total = len(db["orders"])
    pending = sum(1 for o in db["orders"] if o["status"] == "pending")
    approved = sum(1 for o in db["orders"] if o["status"] == "approved")
    revenue = sum(o["price"] for o in db["orders"] if o["status"] == "approved")

    kb = [
        [InlineKeyboardButton("📋 سفارشات در انتظار", callback_data="admin_pending")],
        [InlineKeyboardButton("📦 همه سفارشات", callback_data="admin_all_orders")],
    ]
    await update.message.reply_text(
        f"🛠️ *پنل ادمین*\n\n"
        f"📊 کل سفارشات: {total}\n"
        f"⏳ در انتظار: {pending}\n"
        f"✅ تأیید شده: {approved}\n"
        f"💰 درآمد کل: {revenue:,} تومان",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def admin_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔", show_alert=True); return
    await query.answer()
    db = load_db()
    orders = [o for o in db["orders"] if o["status"] == "pending"]
    if not orders:
        await query.edit_message_text("⏳ سفارش در انتظاری نیست.")
        return
    text = "⏳ *سفارشات در انتظار:*\n\n"
    for o in orders:
        text += f"#{o['id']} | {o['first_name']} | {o['product_name']} | {o['price']:,}ت\n"
    await query.edit_message_text(text, parse_mode="Markdown")

# ─── main ────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    # conversation برای خرید
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_product, pattern=r"^buy_\d+$")],
        states={
            AWAIT_RECEIPT: [
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_receipt)
            ]
        },
        fallbacks=[CallbackQueryHandler(show_products, pattern="^products$")],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(start,           pattern="^home$"))
    app.add_handler(CallbackQueryHandler(show_products,   pattern="^products$"))
    app.add_handler(CallbackQueryHandler(product_detail,  pattern=r"^product_\d+$"))
    app.add_handler(CallbackQueryHandler(my_orders,       pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(support,         pattern="^support$"))
    app.add_handler(CallbackQueryHandler(admin_approve,   pattern=r"^approve_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_reject,    pattern=r"^reject_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_pending,   pattern="^admin_pending$"))

    # ادمین وقتی کانفیگ می‌فرسته
    app.add_handler(MessageHandler(
        filters.TEXT & filters.User(ADMIN_ID) & ~filters.COMMAND,
        admin_send_config
    ))

    print("✅ ربات شروع به کار کرد...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
