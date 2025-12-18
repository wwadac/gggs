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
ADMIN_ID = 8593061718  # <-- ВАШ TELEGRAM ID

if not token:
    logger.error("Токен не задан!")
    exit(1)

bot = Bot(token=token)
dp = Dispatcher()

# ==================== ХРАНИЛИЩЕ ДАННЫХ ====================

DATA_FILE = "bot_data.json"
MESSAGES_CACHE = {}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"channels": [], "connected_users": []}

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

# ==================== ФОРМАТИРОВАНИЕ ЮЗЕРА ====================

def format_user(user_data: dict) -> str:
    """Форматирует информацию о пользователе"""
    first_name = user_data.get('first_name', 'Unknown')
    username = user_data.get('username')
    
    if username:
        return f"{first_name} (@{username})"
    return first_name

def format_user_from_message(user) -> str:
    """Форматирует пользователя из объекта Message"""
    if not user:
        return "Unknown"
    
    if user.username:
        return f"{user.first_name} (@{user.username})"
    return user.first_name

# ==================== ПРОВЕРКА ПОДПИСКИ ====================

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
                not_subscribed.append({
                    "id": channel_id,
                    "title": chat.title,
                    "username": chat.username
                })
        except Exception as e:
            logger.error(f"Ошибка проверки подписки на {channel_id}: {e}")
    
    return len(not_subscribed) == 0, not_subscribed

def get_subscribe_keyboard(channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for channel in channels:
        if channel.get("username"):
            buttons.append([InlineKeyboardButton(
                text=f"📢 {channel['title']}",
                url=f"https://t.me/{channel['username']}"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text=f"📢 {channel['title']}",
                url=f"https://t.me/c/{str(channel['id']).replace('-100', '')}"
            )])
    
    buttons.append([InlineKeyboardButton(
        text="✅ Проверить подписку",
        callback_data="check_sub"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ==================== КОМАНДА /START ====================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    is_subscribed, not_subscribed = await check_subscription(message.from_user.id)
    
    if not is_subscribed:
        await message.answer(
            "❌ <b>Для использования бота необходимо подписаться на каналы:</b>",
            reply_markup=get_subscribe_keyboard(not_subscribed),
            parse_mode="HTML"
        )
        return
    
    welcome_text = """
🤖 <b>Добро пожаловать в DoCCER Bot!</b>

Этот бот поможет вам отслеживать сообщения в бизнес-чатах:
• 📸 Сохранение фото, видео, кружков
• ✏️ Отслеживание редактирования сообщений
• 🗑 Отслеживание удаления сообщений

━━━━━━━━━━━━━━━━━━━━━━
📖 <b>КАК ПОДКЛЮЧИТЬ БОТА:</b>
━━━━━━━━━━━━━━━━━━━━━━

<b>Шаг 1:</b> Откройте Telegram на телефоне

<b>Шаг 2:</b> Перейдите в Настройки → Telegram Business
(Нужен Telegram Premium)

<b>Шаг 3:</b> Выберите "Чат-боты"

<b>Шаг 4:</b> Найдите этого бота и подключите

<b>Шаг 5:</b> Выберите чаты для мониторинга

✅ После подключения бот пришлет уведомление!

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>КАК ИСПОЛЬЗОВАТЬ:</b>
━━━━━━━━━━━━━━━━━━━━━━

• Ответьте на медиа-сообщение в бизнес-чате
• Бот автоматически сохранит его вам

• При удалении/редактировании сообщений
  бот пришлет уведомление с содержимым

━━━━━━━━━━━━━━━━━━━━━━
🔗 Статус: <code>Активен</code>
"""
    
    await message.answer(welcome_text, parse_mode="HTML")

# ==================== CALLBACK ПРОВЕРКИ ПОДПИСКИ ====================

@dp.callback_query(F.data == "check_sub")
async def check_subscription_callback(callback: CallbackQuery):
    is_subscribed, not_subscribed = await check_subscription(callback.from_user.id)
    
    if is_subscribed:
        await callback.message.edit_text(
            "✅ <b>Вы подписаны на все каналы!</b>\n\n"
            "Нажмите /start чтобы начать использовать бота.",
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Вы ещё не подписались на все каналы!", show_alert=True)

# ==================== АДМИН КОМАНДЫ ====================

@dp.message(Command("addchannel"))
async def cmd_add_channel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для этой команды!")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "📢 <b>Добавление канала для подписки</b>\n\n"
            "Использование: <code>/addchannel CHANNEL_ID</code>\n\n"
            "Пример: <code>/addchannel -1001234567890</code>\n\n"
            "⚠️ Бот должен быть админом в канале!",
            parse_mode="HTML"
        )
        return
    
    channel_id = args[1].strip()
    
    try:
        chat = await bot.get_chat(channel_id)
        if add_channel(channel_id):
            await message.answer(
                f"✅ Канал добавлен!\n\n"
                f"📢 <b>{chat.title}</b>\n"
                f"🆔 <code>{channel_id}</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer("⚠️ Этот канал уже добавлен!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}\n\nУбедитесь что бот админ в канале!")

@dp.message(Command("removechannel"))
async def cmd_remove_channel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для этой команды!")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        channels = get_channels()
        if channels:
            text = "📢 <b>Текущие каналы:</b>\n\n"
            for ch in channels:
                try:
                    chat = await bot.get_chat(ch)
                    text += f"• {chat.title}: <code>{ch}</code>\n"
                except:
                    text += f"• <code>{ch}</code>\n"
            text += "\nИспользование: <code>/removechannel CHANNEL_ID</code>"
        else:
            text = "📢 Нет добавленных каналов"
        await message.answer(text, parse_mode="HTML")
        return
    
    channel_id = args[1].strip()
    if remove_channel(channel_id):
        await message.answer(f"✅ Канал <code>{channel_id}</code> удален!", parse_mode="HTML")
    else:
        await message.answer("❌ Канал не найден в списке!")

@dp.message(Command("channels"))
async def cmd_channels(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для этой команды!")
        return
    
    channels = get_channels()
    if not channels:
        await message.answer("📢 Нет добавленных каналов\n\nДобавьте: /addchannel CHANNEL_ID")
        return
    
    text = "📢 <b>Каналы для подписки:</b>\n\n"
    for ch in channels:
        try:
            chat = await bot.get_chat(ch)
            text += f"• <b>{chat.title}</b>\n  └ <code>{ch}</code>\n\n"
        except:
            text += f"• <code>{ch}</code> (недоступен)\n\n"
    
    await message.answer(text, parse_mode="HTML")

# ==================== ПОДКЛЮЧЕНИЕ БИЗНЕС-БОТА ====================

@dp.business_connection()
async def handle_business_connection(business_connection: BusinessConnection):
    user = business_connection.user
    user_display = f"{user.first_name}"
    if user.username:
        user_display += f" (@{user.username})"
    
    if business_connection.is_enabled:
        text = f"""
✅ <b>Успешно подключено!</b>

👤 <b>Пользователь:</b> {user_display}
🆔 <b>ID:</b> <code>{user.id}</code>
📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

━━━━━━━━━━━━━━━━━━━━━━
🎉 Бот теперь отслеживает ваши бизнес-чаты!

<b>Что я умею:</b>
• 📸 Сохранять медиа (ответьте на сообщение)
• ✏️ Уведомлять о редактировании
• 🗑 Уведомлять об удалении

Приятного использования! 🚀
"""
        await bot.send_message(user.id, text, parse_mode="HTML")
        logger.info(f"Бизнес-бот подключен: {user.id} ({user_display})")
        
    else:
        text = """
❌ <b>Бот отключен от бизнес-аккаунта</b>

Вы можете снова подключить его в настройках Telegram Business.
"""
        try:
            await bot.send_message(user.id, text, parse_mode="HTML")
        except:
            pass
        logger.info(f"Бизнес-бот отключен: {user.id}")

# ==================== КЭШИРОВАНИЕ СООБЩЕНИЙ ====================

def cache_message(message: Message, owner_id: int):
    """Сохранить сообщение в кэш"""
    key = f"{message.chat.id}_{message.message_id}"
    
    # Определяем тип медиа
    media_type = None
    if message.photo:
        media_type = "📷 Фото"
    elif message.video:
        media_type = "🎥 Видео"
    elif message.video_note:
        media_type = "⚪ Кружок"
    elif message.voice:
        media_type = "🎤 Голосовое"
    elif message.document:
        media_type = "📎 Файл"
    elif message.sticker:
        media_type = "🎭 Стикер"
    
    MESSAGES_CACHE[key] = {
        "owner_id": owner_id,
        "chat_id": message.chat.id,
        "message_id": message.message_id,
        "from_user": {
            "id": message.from_user.id if message.from_user else None,
            "first_name": message.from_user.first_name if message.from_user else "Unknown",
            "username": message.from_user.username if message.from_user else None
        },
        "text": message.text or message.caption or "",
        "media_type": media_type,
        "date": message.date.strftime('%d.%m.%Y %H:%M:%S') if message.date else None,
        "media_file_id": None
    }
    
    # Сохраняем file_id для медиа
    if message.photo:
        MESSAGES_CACHE[key]["media_file_id"] = message.photo[-1].file_id
        MESSAGES_CACHE[key]["media_kind"] = "photo"
    elif message.video:
        MESSAGES_CACHE[key]["media_file_id"] = message.video.file_id
        MESSAGES_CACHE[key]["media_kind"] = "video"
    elif message.video_note:
        MESSAGES_CACHE[key]["media_file_id"] = message.video_note.file_id
        MESSAGES_CACHE[key]["media_kind"] = "video_note"
    elif message.voice:
        MESSAGES_CACHE[key]["media_file_id"] = message.voice.file_id
        MESSAGES_CACHE[key]["media_kind"] = "voice"
    elif message.document:
        MESSAGES_CACHE[key]["media_file_id"] = message.document.file_id
        MESSAGES_CACHE[key]["media_kind"] = "document"
    elif message.sticker:
        MESSAGES_CACHE[key]["media_file_id"] = message.sticker.file_id
        MESSAGES_CACHE[key]["media_kind"] = "sticker"

# ==================== КЭШИРОВАНИЕ ВСЕХ СООБЩЕНИЙ ====================

@dp.business_message()
async def cache_all_business_messages(message: Message):
    """Кэшируем все бизнес-сообщения"""
    try:
        business_conn = await bot.get_business_connection(message.business_connection_id)
        cache_message(message, business_conn.user.id)
    except Exception as e:
        logger.error(f"Ошибка кэширования: {e}")

# ==================== РЕДАКТИРОВАНИЕ СООБЩЕНИЙ ====================

@dp.edited_business_message()
async def handle_edited_message(message: Message):
    """Отслеживание редактирования"""
    try:
        business_conn = await bot.get_business_connection(message.business_connection_id)
        owner_id = business_conn.user.id
        
        key = f"{message.chat.id}_{message.message_id}"
        old_data = MESSAGES_CACHE.get(key)
        
        # Форматируем автора
        author = format_user_from_message(message.from_user)
        
        # Форматируем чат
        chat_name = message.chat.first_name or message.chat.title or 'Неизвестный'
        if message.chat.username:
            chat_name += f" (@{message.chat.username})"
        
        text = f"""
✏️ <b>СООБЩЕНИЕ ОТРЕДАКТИРОВАНО</b>

⏰ <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Автор:</b> {author}
💬 <b>Чат:</b> {chat_name}

"""
        if old_data and old_data.get("text"):
            text += f"📝 <b>БЫЛО:</b>\n{old_data['text']}\n\n"
        else:
            text += "📝 <b>БЫЛО:</b> <i>(не сохранено)</i>\n\n"
        
        new_text = message.text or message.caption or ""
        text += f"📝 <b>СТАЛО:</b>\n{new_text}"
        
        await bot.send_message(owner_id, text, parse_mode="HTML")
        
        # Обновляем кэш
        cache_message(message, owner_id)
        
    except Exception as e:
        logger.error(f"Ошибка обработки редактирования: {e}")

# ==================== УДАЛЕНИЕ СООБЩЕНИЙ ====================

@dp.deleted_business_messages()
async def handle_deleted_messages(deleted: BusinessMessagesDeleted):
    """Отслеживание удаления сообщений"""
    try:
        business_conn = await bot.get_business_connection(deleted.business_connection_id)
        owner_id = business_conn.user.id
        
        # Форматируем чат
        chat_name = deleted.chat.first_name or deleted.chat.title or 'Неизвестный'
        if deleted.chat.username:
            chat_name += f" (@{deleted.chat.username})"
        
        # Определяем - это массовое удаление (удаление чата) или одиночное
        deleted_count = len(deleted.message_ids)
        is_bulk_delete = deleted_count >= 5  # Если 5+ сообщений - считаем массовым
        
        if is_bulk_delete:
            # ==================== МАССОВОЕ УДАЛЕНИЕ - СОХРАНЯЕМ В TXT ====================
            await handle_bulk_delete(owner_id, deleted, chat_name)
        else:
            # ==================== ОДИНОЧНОЕ УДАЛЕНИЕ ====================
            await handle_single_delete(owner_id, deleted, chat_name)
                
    except Exception as e:
        logger.error(f"Ошибка обработки удаления: {e}")


async def handle_bulk_delete(owner_id: int, deleted: BusinessMessagesDeleted, chat_name: str):
    """Обработка массового удаления (удаление чата) - сохраняем в TXT"""
    
    # Собираем все сообщения для файла
    txt_content = f"🗑 УДАЛЕН ЧАТ / МАССОВОЕ УДАЛЕНИЕ\n"
    txt_content += f"{'='*50}\n"
    txt_content += f"💬 Чат: {chat_name}\n"
    txt_content += f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
    txt_content += f"📊 Удалено сообщений: {len(deleted.message_ids)}\n"
    txt_content += f"{'='*50}\n\n"
    
    saved_count = 0
    
    for msg_id in deleted.message_ids:
        key = f"{deleted.chat.id}_{msg_id}"
        cached = MESSAGES_CACHE.get(key)
        
        if cached:
            author = format_user(cached['from_user'])
            date = cached.get('date', 'Неизвестно')
            text = cached.get('text', '')
            media_type = cached.get('media_type', '')
            
            txt_content += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            txt_content += f"👤 Автор: {author}\n"
            txt_content += f"⏰ Дата: {date}\n"
            
            if media_type:
                txt_content += f"📎 Медиа: {media_type}\n"
            
            if text:
                txt_content += f"📝 Текст:\n{text}\n"
            else:
                txt_content += f"📝 Текст: (пусто)\n"
            
            txt_content += "\n"
            saved_count += 1
            
            # Удаляем из кэша
            del MESSAGES_CACHE[key]
    
    txt_content += f"{'='*50}\n"
    txt_content += f"✅ Сохранено сообщений: {saved_count}\n"
    
    # Отправляем уведомление
    notification = f"""
🗑 <b>ЧАТ УДАЛЕН / МАССОВОЕ УДАЛЕНИЕ</b>

⏰ <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━
💬 <b>Чат:</b> {chat_name}
📊 <b>Удалено:</b> {len(deleted.message_ids)} сообщений
💾 <b>Сохранено:</b> {saved_count} сообщений

📄 История чата сохранена в файл ⬇️
"""
    await bot.send_message(owner_id, notification, parse_mode="HTML")
    
    # Отправляем TXT файл
    if saved_count > 0:
        # Создаем безопасное имя файла
        safe_chat_name = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in chat_name)
        filename = f"deleted_chat_{safe_chat_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        file_data = txt_content.encode('utf-8')
        input_file = BufferedInputFile(file_data, filename=filename)
        
        await bot.send_document(
            chat_id=owner_id,
            document=input_file,
            caption="📄 История удаленного чата"
        )


async def handle_single_delete(owner_id: int, deleted: BusinessMessagesDeleted, chat_name: str):
    """Обработка одиночного удаления - отправляем уведомление + медиа"""
    
    for msg_id in deleted.message_ids:
        key = f"{deleted.chat.id}_{msg_id}"
        cached = MESSAGES_CACHE.get(key)
        
        if cached:
            author = format_user(cached['from_user'])
            text = cached.get('text', '')
            media_type = cached.get('media_type', '')
            
            notification = f"""
🗑 <b>СООБЩЕНИЕ УДАЛЕНО</b>

⏰ <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Автор:</b> {author}
💬 <b>Чат:</b> {chat_name}
"""
            if media_type:
                notification += f"📎 <b>Медиа:</b> {media_type}\n"
            
            notification += f"\n📝: {text if text else '<i>(пусто)</i>'}"
            
            await bot.send_message(owner_id, notification, parse_mode="HTML")
            
            # Отправляем медиа если есть
            if cached.get('media_file_id'):
                try:
                    await send_deleted_media(owner_id, cached)
                except Exception as e:
                    logger.error(f"Не удалось отправить медиа: {e}")
            
            # Удаляем из кэша
            del MESSAGES_CACHE[key]
        else:
            # Сообщение не было в кэше
            notification = f"""
🗑 <b>СООБЩЕНИЕ УДАЛЕНО</b>

⏰ <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━
💬 <b>Чат:</b> {chat_name}

📝: <i>(содержимое не сохранено)</i>
"""
            await bot.send_message(owner_id, notification, parse_mode="HTML")


async def send_deleted_media(owner_id: int, cached: dict):
    """Отправка удаленного медиа"""
    media_kind = cached.get('media_kind')
    file_id = cached['media_file_id']
    
    if media_kind == "photo":
        await bot.send_photo(owner_id, file_id, caption="📷 Удаленное фото")
    elif media_kind == "video":
        await bot.send_video(owner_id, file_id, caption="🎥 Удаленное видео")
    elif media_kind == "video_note":
        await bot.send_video_note(owner_id, file_id)
    elif media_kind == "voice":
        await bot.send_voice(owner_id, file_id, caption="🎤 Удаленное голосовое")
    elif media_kind == "document":
        await bot.send_document(owner_id, file_id, caption="📎 Удаленный файл")
    elif media_kind == "sticker":
        await bot.send_sticker(owner_id, file_id)

# ==================== СОХРАНЕНИЕ МЕДИА ПО ОТВЕТУ ====================

@dp.business_message(F.reply_to_message)
async def handle_business_media(business_message: Message):
    """Сохранение медиа при ответе"""
    try:
        business_conn = await bot.get_business_connection(
            business_message.business_connection_id
        )

        if not business_message.from_user.id == business_conn.user.id:
            return
        
        target_message = business_message.reply_to_message
        
        file_data = None
        filename = None
        caption = None
        
        # Форматируем автора сообщения
        author = format_user_from_message(target_message.from_user)
        
        if target_message.photo:
            file_data, filename = await download_photo(target_message.photo)
            caption = f"📷 Фото от {author}"
            
        elif target_message.video:
            file_data, filename = await download_video(target_message.video)
            caption = f"🎥 Видео от {author}"
            
        elif target_message.video_note:
            file_data, filename = await download_video_note(target_message.video_note)
            caption = f"⚪ Кружок от {author}"
        
        if file_data and filename:
            if target_message.caption:
                caption += f"\n\n📝 Подпись: {target_message.caption}"
            
            await send_to_owner(
                business_conn.user.id,
                file_data,
                filename,
                caption
            )
                    
    except Exception as e:
        logger.error(f"Ошибка при обработке медиа: {e}")

# ==================== ФУНКЦИИ ЗАГРУЗКИ ====================

async def download_photo(photos: list[PhotoSize]) -> tuple[BytesIO, str]:   
    file_info = await bot.get_file(photos[-1].file_id)
    file_data = BytesIO()
    await bot.download_file(file_info.file_path, file_data)
    file_data.seek(0)
    filename = f"photo_{photos[-1].file_id}.jpg"
    return file_data, filename

async def download_video(video: Video) -> tuple[BytesIO, str]:
    file_info = await bot.get_file(video.file_id)
    file_data = BytesIO()
    await bot.download_file(file_info.file_path, file_data)
    file_data.seek(0)
    filename = video.file_name or f"video_{video.file_id}.mp4"
    return file_data, filename

async def download_video_note(video_note: VideoNote) -> tuple[BytesIO, str]:
    file_info = await bot.get_file(video_note.file_id)
    file_data = BytesIO()
    await bot.download_file(file_info.file_path, file_data)
    file_data.seek(0)
    filename = f"video_note_{video_note.file_id}.mp4"
    return file_data, filename

async def send_to_owner(owner_id: int, file_data: BytesIO, filename: str, caption: str):
    try:
        input_file = BufferedInputFile(file_data.read(), filename=filename)
        
        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            await bot.send_photo(chat_id=owner_id, photo=input_file, caption=caption)
        elif 'video_note' in filename:
            await bot.send_video_note(chat_id=owner_id, video_note=input_file)
            if caption:
                await bot.send_message(owner_id, caption)
        else:
            await bot.send_video(chat_id=owner_id, video=input_file, caption=caption)
            
    except Exception as e:
        logger.error(f"Ошибка при отправке: {e}")
        raise

# ==================== ЗАПУСК ====================

async def main():
    logger.info("Бот запущен!")
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    finally:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
