import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

# ---------------- CONFIG ----------------
API_ID = 1234567
API_HASH = "your_api_hash"
BOT_TOKEN = "your_bot_token"
ADMIN_ID = 123456789
DB_CHANNEL_ID = -1001234567890
MONGO_URI = "mongodb+srv://..."

# ---------------- DATABASE ----------------
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["MovieBotDB"]
movies_col = db["movies"]

admin_cache = {}

# ---------------- BOT ----------------
app = Client(
    "MovieStoreBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ---------------- ADMIN ADD ----------------
@app.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_start(client, message):
    admin_cache[message.from_user.id] = {"step": "WAIT_FILE"}
    await message.reply_text(
        "📥 **Admin Mode Activated**\n\n"
        "Send the **movie file** (video or document)."
    )

@app.on_message(filters.user(ADMIN_ID) & (filters.document | filters.video | filters.text))
async def admin_handler(client, message):
    uid = message.from_user.id
    if uid not in admin_cache:
        return

    state = admin_cache[uid]

    # STEP 1: FILE
    if state["step"] == "WAIT_FILE":
        if message.document or message.video:
            forwarded = await message.forward(DB_CHANNEL_ID)
            file_id = message.document.file_id if message.document else message.video.file_id

            admin_cache[uid] = {
                "step": "WAIT_NAME",
                "file_id": file_id,
                "db_msg_id": forwarded.id
            }

            await message.reply_text(
                "✅ **File saved successfully!**\n\n"
                "Now send:\n`/name Movie Name`"
            )
        else:
            await message.reply_text("❌ Please send a valid file.")

    # STEP 2: NAME
    elif state["step"] == "WAIT_NAME":
        if message.text and message.text.startswith("/name"):
            movie_name = message.text.replace("/name", "").strip()
            if not movie_name:
                await message.reply_text("❌ Usage: `/name Avatar 2`")
                return

            data = admin_cache[uid]

            await movies_col.insert_one({
                "name": movie_name.lower(),
                "display_name": movie_name,
                "file_id": data["file_id"],
                "db_msg_id": data["db_msg_id"]
            })

            del admin_cache[uid]

            await message.reply_text(
                f"🎉 **Movie Added Successfully!**\n\n"
                f"🎬 **Movie:** {movie_name}"
            )

# ---------------- USER SEARCH ----------------
@app.on_message(filters.text & ~filters.command(["start", "add", "name"]))
async def search_movie(client, message):
    query = message.text.lower()
    msg = await message.reply_text("🔍 Searching database...")

    cursor = movies_col.find(
        {"name": {"$regex": query, "$options": "i"}}
    )

    found = False
    async for movie in cursor:
        found = True
        try:
            await client.send_cached_media(
                chat_id=message.chat.id,
                file_id=movie["file_id"],
                caption=f"🎬 **{movie['display_name']}**\n💎 Quality: Bluray",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📥 Download", callback_data="dl")]]
                )
            )
        except:
            await client.copy_message(
                message.chat.id,
                DB_CHANNEL_ID,
                movie["db_msg_id"]
            )

    if not found:
        await msg.edit(
            "❌ **No movie found!**\n\nTry another name."
        )
    else:
        await msg.delete()

# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "✨ **Welcome to Movie Vault Bot** ✨\n\n"
        "🎬 Send any movie name to get the file instantly.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("📢 Join Channel", url="https://t.me/your_link")]]
        )
    )

print("Bot is running...")
app.run()
