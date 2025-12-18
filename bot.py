from aiogram.types.business_connection import BusinessConnection
import asyncio
import logging
import json
import os
from io import BytesIO
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    PhotoSize,
    Video,
    VideoNote,
    Voice,
    Document,
    Sticker,
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BusinessMessagesDeleted
)
from aiogram.filters import Command, CommandStart
from aiogram.enums import ChatMemberStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

token = "8316728730:AAEMrNJN8O7Efbk7TIDPphqGy5-4VrnigN8"
ADMIN_ID = 8593061718

if not token:
    logger.error("Токен не задан!")
    exit(1)

bot = Bot(token=token)
dp = Dispatcher()

DATA_FILE = "bot_data.json"
MESSAGES_CACHE = {}

# ==================== ДАННЫЕ ====================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"channels": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_channels():
    return load_data().get("channels", [])

def add_channel(channel_id: str):
    data = load_data()
    if channel_id not in data["channels"]:
        data["channels"].append(channel_id)
        save_data(data)
        return True
    return False

def remove_channel(channel_id: str):
    data = load_data()
    if channel_id in data["channels"]:
        data["channels"].remove(channel_id)
        save_data(data)
        return True
    return False

# ==================== ФОРМАТИРОВАНИЕ ====================
def format_user(user_data: dict) -> str:
    first_name = user_data.get('first_name', 'Unknown')
    username = user_data.get('username')
    if username:
        return f"{first_name} (@{username})"
    return first_name

def format_user_from_msg(user) -> str:
    if not user:
        return "Unknown"
    if user.username:
        return f"{user.first_name} (@{user.username})"
    return user.first_name

# ==================== ПОДПИСКА ====================
async def check_subscription(user_id: int) -> tuple[bool, list]:
    channels = get_channels()
    if not channels:
        return True, []
    
    not_subscribed = []
    for channel_id in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                chat = await bot.get_chat(channel_id)
                not_subscribed.append({"id": channel_id, "title": chat.title, "username": chat.username})
        except:
            pass
    return len(not_subscribed) == 0, not_subscribed

def get_subscribe_keyboard(channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        url = f"https://t.me/{ch['username']}" if ch.get("username") else f"https://t.me/c/{str(ch['id']).replace('-100', '')}"
        buttons.append([InlineKeyboardButton(text=f"📢 {ch['title']}", url=url)])
    buttons.append([InlineKeyboardButton(text="✅ Проверить", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ==================== КОМАНДЫ ====================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    is_sub, not_sub = await check_subscription(message.from_user.id)
    if not is_sub:
        await message.answer("❌ <b>Подпишитесь на каналы:</b>", reply_markup=get_subscribe_keyboard(not_sub), parse_mode="HTML")
        return
    
    await message.answer("""🤖 <b>Business Bot</b>

📸 Сохранение медиа
✏️ Отслеживание редактирования
🗑 Отслеживание удаления

<b>Подключение:</b>
Настройки → Telegram Business → Чат-боты → Найти бота
""", parse_mode="HTML")

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(callback: CallbackQuery):
    is_sub, _ = await check_subscription(callback.from_user.id)
    if is_sub:
        await callback.message.edit_text("✅ Подписка подтверждена!\n\nНажмите /start", parse_mode="HTML")
    else:
        await callback.answer("❌ Не подписаны!", show_alert=True)

@dp.message(Command("addchannel"))
async def cmd_add_channel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: <code>/addchannel -100xxx</code>", parse_mode="HTML")
        return
    channel_id = args[1].strip()
    try:
        chat = await bot.get_chat(channel_id)
        if add_channel(channel_id):
            await message.answer(f"✅ Добавлен: <b>{chat.title}</b>", parse_mode="HTML")
        else:
            await message.answer("⚠️ Уже добавлен")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("removechannel"))
async def cmd_remove_channel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: <code>/removechannel -100xxx</code>", parse_mode="HTML")
        return
    if remove_channel(args[1].strip()):
        await message.answer("✅ Удалён")
    else:
        await message.answer("❌ Не найден")

@dp.message(Command("channels"))
async def cmd_channels(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    channels = get_channels()
    if not channels:
        await message.answer("Нет каналов")
        return
    text = "📢 <b>Каналы:</b>\n"
    for ch in channels:
        try:
            chat = await bot.get_chat(ch)
            text += f"• {chat.title}: <code>{ch}</code>\n"
        except:
            text += f"• <code>{ch}</code>\n"
    await message.answer(text, parse_mode="HTML")

# ==================== БИЗНЕС ПОДКЛЮЧЕНИЕ ====================
@dp.business_connection()
async def handle_business_connection(bc: BusinessConnection):
    user = bc.user
    name = f"{user.first_name} (@{user.username})" if user.username else user.first_name
    
    if bc.is_enabled:
        await bot.send_message(user.id, f"✅ <b>Бот подключён!</b>\n\n👤 {name}\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}", parse_mode="HTML")
    else:
        try:
            await bot.send_message(user.id, "❌ <b>Бот отключён</b>", parse_mode="HTML")
        except:
            pass

# ==================== КЭШИРОВАНИЕ ====================
def cache_message(message: Message, owner_id: int):
    key = f"{message.chat.id}_{message.message_id}"
    
    media_type = None
    media_file_id = None
    media_kind = None

    if message.photo:
        media_type, media_kind, media_file_id = "📷", "photo", message.photo[-1].file_id
    elif message.video:
        media_type, media_kind, media_file_id = "🎥", "video", message.video.file_id
    elif message.video_note:
        media_type, media_kind, media_file_id = "⚪", "video_note", message.video_note.file_id
    elif message.voice:
        media_type, media_kind, media_file_id = "🎤", "voice", message.voice.file_id
    elif message.document:
        media_type, media_kind, media_file_id = "📎", "document", message.document.file_id
    elif message.sticker:
        media_type, media_kind, media_file_id = "🎭", "sticker", message.sticker.file_id

    MESSAGES_CACHE[key] = {
        "owner_id": owner_id,
        "from_user": {
            "id": message.from_user.id if message.from_user else None,
            "first_name": message.from_user.first_name if message.from_user else "Unknown",
            "username": message.from_user.username if message.from_user else None
        },
        "text": message.text or message.caption or "",
        "media_type": media_type,
        "media_kind": media_kind,
        "media_file_id": media_file_id,
        "date": message.date.strftime('%d.%m.%Y %H:%M') if message.date else None
    }

@dp.business_message(F.reply_to_message)  # ОБРАТИТЕ ВНИМАНИЕ: этот обработчик ДОЛЖЕН быть ПЕРЕД общим business_message
async def handle_reply_media(message: Message):
    """Обработчик для сохранения медиа при ответе на сообщение"""
    try:
        bc = await bot.get_business_connection(message.business_connection_id)
        if message.from_user.id != bc.user.id:
            return
        
        target = message.reply_to_message
        
        # Проверяем, что целевое сообщение содержит медиа
        if not (target.photo or target.video or target.video_note or target.voice or target.document or target.sticker):
            return
        
        # Скачиваем медиа
        file_data, filename, caption = await download_media_from_message(target)
        
        if file_data and filename:
            # Добавляем информацию об авторе
            author = format_user_from_msg(target.from_user)
            final_caption = f"👤 {author}"
            if caption:
                final_caption += f"\n📝 {caption}"
            
            await send_media_to_owner(bc.user.id, file_data, filename, final_caption)
                
    except Exception as e:
        logger.error(f"Reply media error: {e}")

@dp.business_message()
async def cache_messages(message: Message):
    """Кэширование всех бизнес-сообщений"""
    try:
        bc = await bot.get_business_connection(message.business_connection_id)
        cache_message(message, bc.user.id)
    except Exception as e:
        logger.error(f"Cache error: {e}")

# ==================== РЕДАКТИРОВАНИЕ ====================
@dp.edited_business_message()
async def handle_edited(message: Message):
    try:
        bc = await bot.get_business_connection(message.business_connection_id)
        owner_id = bc.user.id
        
        key = f"{message.chat.id}_{message.message_id}"
        old = MESSAGES_CACHE.get(key)
        
        author = format_user_from_msg(message.from_user)
        old_text = old.get("text", "") if old else ""
        new_text = message.text or message.caption or ""
        
        text = f"✏️ <b>Изменено</b>\n\n👤 {author}\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        text += f"<b>Было:</b> {old_text or '<i>пусто</i>'}\n<b>Стало:</b> {new_text or '<i>пусто</i>'}"
        
        await bot.send_message(owner_id, text, parse_mode="HTML")
        cache_message(message, owner_id)
        
    except Exception as e:
        logger.error(f"Edit error: {e}")

# ==================== УДАЛЕНИЕ ====================
@dp.deleted_business_messages()
async def handle_deleted(deleted: BusinessMessagesDeleted):
    try:
        bc = await bot.get_business_connection(deleted.business_connection_id)
        owner_id = bc.user.id
        
        chat_name = deleted.chat.first_name or deleted.chat.title or 'Чат'
        if deleted.chat.username:
            chat_name += f" (@{deleted.chat.username})"
        
        count = len(deleted.message_ids)
        
        if count >= 5:
            await bulk_delete_to_txt(owner_id, deleted, chat_name)
        else:
            await single_delete(owner_id, deleted)
            
    except Exception as e:
        logger.error(f"Delete error: {e}")

async def bulk_delete_to_txt(owner_id: int, deleted: BusinessMessagesDeleted, chat_name: str):
    txt = f"🗑 УДАЛЁН ЧАТ: {chat_name}\n"
    txt += f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    txt += f"📊 Сообщений: {len(deleted.message_ids)}\n"
    txt += "=" * 40 + "\n\n"

    saved = 0
    for msg_id in deleted.message_ids:
        key = f"{deleted.chat.id}_{msg_id}"
        cached = MESSAGES_CACHE.pop(key, None)
        
        if cached:
            author = format_user(cached['from_user'])
            txt += f"👤 {author}\n"
            txt += f"⏰ {cached.get('date', '?')}\n"
            if cached.get('media_type'):
                txt += f"📎 {cached['media_type']}\n"
            txt += f"📝 {cached.get('text') or '(пусто)'}\n"
            txt += "-" * 30 + "\n"
            saved += 1

    await bot.send_message(owner_id, f"🗑 <b>Чат удалён</b>\n\n💬 {chat_name}\n📊 {len(deleted.message_ids)} сообщений\n💾 Сохранено: {saved}", parse_mode="HTML")

    if saved > 0:
        safe_name = "".join(c if c.isalnum() or c in ' _-' else '_' for c in chat_name)[:30]
        filename = f"chat_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        await bot.send_document(owner_id, BufferedInputFile(txt.encode('utf-8'), filename), caption="📄 История чата")

async def single_delete(owner_id: int, deleted: BusinessMessagesDeleted):
    for msg_id in deleted.message_ids:
        key = f"{deleted.chat.id}_{msg_id}"
        cached = MESSAGES_CACHE.pop(key, None)
        
        if cached:
            author = format_user(cached['from_user'])
            text = cached.get('text', '')
            media = cached.get('media_type', '')
            
            msg = f"🗑 <b>Удалено</b>\n\n👤 {author}\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            if media:
                msg += f"\n📎 {media}"
            msg += f"\n\n📝 {text or '<i>пусто</i>'}"
            
            await bot.send_message(owner_id, msg, parse_mode="HTML")
            
            if cached.get('media_file_id'):
                await send_cached_media(owner_id, cached)
        else:
            await bot.send_message(owner_id, f"🗑 <b>Удалено</b>\n\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n📝 <i>не сохранено</i>", parse_mode="HTML")

async def send_cached_media(owner_id: int, cached: dict):
    try:
        kind = cached.get('media_kind')
        fid = cached['media_file_id']
        
        if kind == "photo":
            await bot.send_photo(owner_id, fid)
        elif kind == "video":
            await bot.send_video(owner_id, fid)
        elif kind == "video_note":
            await bot.send_video_note(owner_id, fid)
        elif kind == "voice":
            await bot.send_voice(owner_id, fid)
        elif kind == "document":
            await bot.send_document(owner_id, fid)
        elif kind == "sticker":
            await bot.send_sticker(owner_id, fid)
    except Exception as e:
        logger.error(f"Send cached media error: {e}")

# ==================== УТИЛИТЫ ДЛЯ СКАЧИВАНИЯ МЕДИА ====================
async def download_media_from_message(message: Message):
    """Скачивает медиа из сообщения и возвращает (данные, имя файла, подпись)"""
    try:
        file_data = None
        filename = None
        caption = message.caption or ""
        
        if message.photo:
            file_data, filename = await download_photo(message.photo)
        elif message.video:
            file_data, filename = await download_video(message.video)
        elif message.video_note:
            file_data, filename = await download_video_note(message.video_note)
        elif message.voice:
            file_data, filename = await download_voice(message.voice)
        elif message.document:
            file_data, filename = await download_document(message.document)
        elif message.sticker:
            file_data, filename = await download_sticker(message.sticker)
        
        return file_data, filename, caption
    except Exception as e:
        logger.error(f"Download media error: {e}")
        return None, None, ""

async def download_photo(photos: list[PhotoSize]) -> tuple[BytesIO, str]:
    f = await bot.get_file(photos[-1].file_id)
    data = BytesIO()
    await bot.download_file(f.file_path, data)
    data.seek(0)
    return data, f"photo_{photos[-1].file_id}.jpg"

async def download_video(video: Video) -> tuple[BytesIO, str]:
    f = await bot.get_file(video.file_id)
    data = BytesIO()
    await bot.download_file(f.file_path, data)
    data.seek(0)
    return data, video.file_name or f"video_{video.file_id}.mp4"

async def download_video_note(vn: VideoNote) -> tuple[BytesIO, str]:
    f = await bot.get_file(vn.file_id)
    data = BytesIO()
    await bot.download_file(f.file_path, data)
    data.seek(0)
    return data, f"videonote_{vn.file_id}.mp4"

async def download_voice(voice: Voice) -> tuple[BytesIO, str]:
    f = await bot.get_file(voice.file_id)
    data = BytesIO()
    await bot.download_file(f.file_path, data)
    data.seek(0)
    return data, f"voice_{voice.file_id}.ogg"

async def download_document(document: Document) -> tuple[BytesIO, str]:
    f = await bot.get_file(document.file_id)
    data = BytesIO()
    await bot.download_file(f.file_path, data)
    data.seek(0)
    return data, document.file_name or f"document_{document.file_id}"

async def download_sticker(sticker: Sticker) -> tuple[BytesIO, str]:
    f = await bot.get_file(sticker.file_id)
    data = BytesIO()
    await bot.download_file(f.file_path, data)
    data.seek(0)
    return data, f"sticker_{sticker.file_id}.webp"

async def send_media_to_owner(owner_id: int, file_data: BytesIO, filename: str, caption: str):
    """Отправляет медиа владельцу"""
    try:
        inp = BufferedInputFile(file_data.read(), filename)
        
        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            await bot.send_photo(owner_id, inp, caption=caption[:1024] if caption else None)
        elif 'videonote' in filename.lower():
            await bot.send_video_note(owner_id, inp)
            if caption:
                await bot.send_message(owner_id, caption)
        elif filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
            await bot.send_video(owner_id, inp, caption=caption[:1024] if caption else None)
        elif filename.lower().endswith(('.ogg', '.mp3', '.wav')):
            await bot.send_voice(owner_id, inp, caption=caption[:1024] if caption else None)
        else:
            await bot.send_document(owner_id, inp, caption=caption[:1024] if caption else None)
            
    except Exception as e:
        logger.error(f"Send to owner error: {e}")

# ==================== ЗАПУСК ====================
async def main():
    logger.info("Bot started")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
