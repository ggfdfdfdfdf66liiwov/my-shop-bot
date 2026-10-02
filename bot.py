import os, json, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

TOKEN    = os.getenv("BOT_TOKEN", "YOUR_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
DB_FILE  = "data.json"
AWAIT_RECEIPT = 1

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
            {"id": 1, "name": "کانفیگ نامحدود ۱ ماهه", "desc": "ترافیک نامحدود | سرعت بالا", "price": 50000, "type": "fixed", "active": True},
            {"id": 2, "name": "کانفیگ حجمی", "desc": "هر گیگابایت ۲٬۰۰۰ تومان | مناسب مصرف متوسط", "price": 2000, "type": "per_gb", "active": True},
            {"id": 3, "name": "کانفیگ حجمی بالا", "desc": "هر گیگابایت ۱٬۰۰۰ تومان | مناسب مصرف زیاد", "price": 1000, "type": "per_gb", "active": True},
        ]
        save_db(db)
    return db

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

async def show_products(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    products = [p for p in db["products"] if p["active"]]
    query = update.callback_query
    await query.answer()
    if not products:
        await query.edit_message_text("محصولی موجود نیست.")
        return
    kb = []
    for p in products:
        if p["type"] == "per_gb":
            label = f"{p['name']} — هر گیگ {p['price']:,} تومان"
        else:
            label = f"{p['name']} — {p['price']:,} تومان"
        kb.append([InlineKeyboardButton(label, callback_data=f"product_{p['id']}")])
    kb.append([InlineKeyboardButton("🏠 بازگشت", callback_data="home")])
    await query.edit_message_text("🛍️ محصولات موجود:\nیه محصول انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))

async def product_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[1])
    db = load_db()
    p = next((x for x in db["products"] if x["id"] == pid), None)
    if not p:
        await query.edit_message_text("محصول پیدا نشد.")
        return
    if p["type"] == "per_gb":
        price_str = f"هر گیگابایت: {p['price']:,} تومان\nمثلاً ۱۰ گیگ = {p['price']*10:,} تومان"
    else:
        price_str = f"{p['price']:,} تومان"
    kb = [
        [InlineKeyboardButton("✅ خرید این محصول", callback_data=f"buy_{p['id']}")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="products")],
    ]
    text = f"📦 {p['name']}\n\n📝 {p['desc']}\n\n💰 قیمت: {price_str}"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

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
    if p["type"] == "per_gb":
        price_info = (
            f"قیمت: هر گیگابایت {p['price']:,} تومان\n"
            f"لطفاً تعداد گیگ مورد نظرت رو هم در پیام رسید بنویس"
        )
    else:
        price_info = f"مبلغ: {p['price']:,} تومان"
    text = (
        f"💳 روش پرداخت:\n\n"
        f"📦 {p['name']}\n"
        f"{price_info}\n\n"
        f"برای دریافت شماره کارت و نهایی کردن خرید به ادمین پیام بده:\n"
        f"👤 @ph_am28\n\n"
        f"بعد از پرداخت، رسید رو اینجا بفرست 📸"
    )
    kb = [[InlineKeyboardButton("❌ انصراف", callback_data="products")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    return AWAIT_RECEIPT

async def receive_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    pid = ctx.user_data.get("pending_product")
    p = next((x for x in db["products"] if x["id"] == pid), None)
    user = update.effective_user
    if not p:
        await update.message.reply_text("مشکلی پیش اومد. دوباره /start بزن.")
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
        "status": "pending",
        "created_at": datetime.datetime.now().isoformat(),
        "config": ""
    }
    db["orders"].append(order)
    save_db(db)
    await update.message.reply_text(
        f"✅ سفارش #{order_id} ثبت شد!\n"
        "رسید دریافت شد و در حال بررسیه. بعد از تایید، کانفیگ برات ارسال میشه 🙏"
    )
    caption = (
        f"🔔 سفارش جدید #{order_id}\n\n"
        f"👤 کاربر: {user.first_name} (@{user.username or '-'})\n"
        f"🆔 آیدی: {user.id}\n"
        f"📦 محصول: {p['name']}\n"
        f"💰 قیمت: {p['price']:,} تومان"
    )
    kb_admin = [[
        InlineKeyboardButton("✅ تایید و ارسال کانفیگ", callback_data=f"approve_{order_id}"),
        InlineKeyboardButton("❌ رد", callback_data=f"reject_{order_id}"),
    ]]
    try:
        if update.message.photo:
            await ctx.bot.send_photo(ADMIN_ID, update.message.photo[-1].file_id,
                caption=caption, reply_markup=InlineKeyboardMarkup(kb_admin))
        elif update.message.document:
            await ctx.bot.send_document(ADMIN_ID, update.message.document.file_id,
                caption=caption, reply_markup=InlineKeyboardMarkup(kb_admin))
        else:
            await ctx.bot.send_message(ADMIN_ID,
                caption + f"\n\n💬 متن: {update.message.text}",
                reply_markup=InlineKeyboardMarkup(kb_admin))
    except Exception as e:
        print(f"خطا در ارسال به ادمین: {e}")
    ctx.user_data.pop("pending_product", None)
    return ConversationHandler.END

async def admin_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("دسترسی ندارید.", show_alert=True)
        return
    order_id = int(query.data.split("_")[1])
    ctx.user_data["awaiting_config_for"] = order_id
    await query.answer()
    try:
        await query.edit_message_caption(
            (query.message.caption or "") + "\n\n⏳ کانفیگ رو بفرست تا ارسال بشه:"
        )
    except:
        await ctx.bot.send_message(ADMIN_ID, f"سفارش #{order_id} تایید شد. کانفیگ رو بفرست:")

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
    try:
        await ctx.bot.send_message(
            order["user_id"],
            f"🎉 سفارش #{order_id} تایید شد!\n\n"
            f"📦 {order['product_name']}\n\n"
            f"🔑 کانفیگ شما:\n{config_text}\n\n"
            "ممنون از خریدت 🙏 اگه مشکلی بود پیام بده."
        )
        await update.message.reply_text(f"✅ کانفیگ سفارش #{order_id} ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"خطا در ارسال: {e}")
    ctx.user_data.pop("awaiting_config_for", None)

async def admin_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("دسترسی ندارید.", show_alert=True)
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
    try:
        await query.edit_message_caption((query.message.caption or "") + "\n\n❌ رد شد.")
    except:
        pass
    try:
        await ctx.bot.send_message(
            order["user_id"],
            f"❌ سفارش #{order_id} تایید نشد.\nبرای پیگیری با ادمین تماس بگیر: @ph_am28"
        )
    except:
        pass

async def my_orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_db()
    uid = query.from_user.id
    orders = [o for o in db["orders"] if o["user_id"] == uid]
    kb = [[InlineKeyboardButton("🏠 بازگشت", callback_data="home")]]
    if not orders:
        await query.edit_message_text("📦 سفارشی ثبت نکردی.", reply_markup=InlineKeyboardMarkup(kb))
        return
    status_map = {"pending": "⏳ در انتظار", "approved": "✅ تایید شده", "rejected": "❌ رد شده"}
    text = "📦 سفارشات من:\n\n"
    for o in reversed(orders[-5:]):
        text += f"#{o['id']} | {o['product_name']} | {status_map.get(o['status'], o['status'])}\n"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [[InlineKeyboardButton("🏠 بازگشت", callback_data="home")]]
    await query.edit_message_text(
        "📞 پشتیبانی:\n\nبرای هر مشکلی پیام بده:\n👤 @ph_am28",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("دسترسی ندارید.")
        return
    db = load_db()
    total = len(db["orders"])
    pending = sum(1 for o in db["orders"] if o["status"] == "pending")
    approved = sum(1 for o in db["orders"] if o["status"] == "approved")
    revenue = sum(o["price"] for o in db["orders"] if o["status"] == "approved")
    await update.message.reply_text(
        f"پنل ادمین\n\n"
        f"کل سفارشات: {total}\n"
        f"در انتظار: {pending}\n"
        f"تایید شده: {approved}\n"
        f"درآمد کل: {revenue:,} تومان"
    )

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_product, pattern=r"^buy_\d+$")],
        states={AWAIT_RECEIPT: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_receipt)]},
        fallbacks=[CallbackQueryHandler(show_products, pattern="^products$")],
        per_message=False,
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(start, pattern="^home$"))
    app.add_handler(CallbackQueryHandler(show_products, pattern="^products$"))
    app.add_handler(CallbackQueryHandler(product_detail, pattern=r"^product_\d+$"))
    app.add_handler(CallbackQueryHandler(my_orders, pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(support, pattern="^support$"))
    app.add_handler(CallbackQueryHandler(admin_approve, pattern=r"^approve_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_reject, pattern=r"^reject_\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID) & ~filters.COMMAND, admin_send_config))
    print("ربات شروع به کار کرد...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
