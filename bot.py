from aiogram.types.business_connection import BusinessConnection
import asyncio
import logging
import os
from io import BytesIO
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    PhotoSize,
    Video,
    VideoNote,
    Document,
    BufferedInputFile,
    BusinessMessagesDeleted
)
from aiogram.filters import CommandStart, Command

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== НАСТРОЙКИ ==========
# !!! ВАЖНО: замени эти значения !!!
BOT_TOKEN = "8316728730:AAEMrNJN8O7Efbk7TIDPphqGy5-4VrnigN8"
ADMIN_ID = 8593061718  # Твой Telegram ID
# ===============================

if not BOT_TOKEN or BOT_TOKEN == "ВАШ_ТОКЕН_ТУТ":
    logger.error("❌ Токен не задан! Замени BOT_TOKEN на свой токен от @BotFather")
    exit(1)

if ADMIN_ID == 123456789:
    logger.error("❌ ID админа не задан! Укажи свой Telegram ID (узнай у @userinfobot)")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Кэш для предотвращения дублирования
processed_messages = set()

# ========== ОБРАБОТЧИКИ ==========

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Команда /start"""
    await message.answer(
        "👋 <b>Бот для сохранения одноразок!</b>\n\n"
        "<b>Как использовать:</b>\n"
        "1. Подключи меня к бизнес-аккаунту\n"
        "2. Клиент отправит фото/видео с таймером\n"
        "3. Ответь на это сообщение ЛЮБЫМ текстом\n"
        "4. Я пришлю тебе копию в этот чат!\n\n"
        "✅ <b>Бот готов к работе!</b>",
        parse_mode="HTML"
    )


@dp.business_message(F.reply_to_message)
async def handle_business_media(business_message: Message):
    """Обработка ответов админа на сообщения клиентов"""
    try:
        # Проверяем, что это ответ от админа (нас)
        business_conn: BusinessConnection = await bot.get_business_connection(
            business_message.business_connection_id
        )

        # Если отправитель ответа НЕ владелец бизнес-аккаунта (не мы), игнорируем
        if not business_message.from_user.id == business_conn.user.id:
            logger.info(f"Ответ не от админа, игнорируем: {business_message.from_user.id}")
            return
        
        target_message = business_message.reply_to_message
        
        # Проверяем, не обрабатывали ли уже это сообщение
        cache_key = f"{target_message.chat.id}_{target_message.message_id}"
        if cache_key in processed_messages:
            logger.info(f"Сообщение {cache_key} уже обработано")
            return
        
        logger.info(f"📨 Админ ответил на сообщение {target_message.message_id} от клиента")
        
        file_data = None
        filename = None
        caption = ""
        
        # Определяем тип сообщения
        if target_message.photo:
            logger.info(f"📸 Обнаружено фото")
            file_data, filename = await download_photo(target_message.photo)
            caption = f"📸 Фото от {target_message.from_user.first_name}"
            
        elif target_message.video:
            logger.info(f"🎬 Обнаружено видео")
            file_data, filename = await download_video(target_message.video)
            caption = f"🎬 Видео от {target_message.from_user.first_name}"
            
        elif target_message.video_note:
            logger.info(f"⭕ Обнаружено видеосообщение")
            file_data, filename = await download_video_note(target_message.video_note)
            caption = f"⭕ Видеосообщение от {target_message.from_user.first_name}"
            
        elif target_message.document:
            logger.info(f"📄 Обнаружен документ")
            file_data, filename = await download_document(target_message.document)
            caption = f"📄 Документ от {target_message.from_user.first_name}"
            
        elif target_message.text:
            logger.info(f"💬 Обнаружен текст")
            # Для текстовых сообщений
            caption = f"💬 Текст от {target_message.from_user.first_name}"
            await send_text_to_owner(
                business_conn.user.id,
                target_message.text,
                caption
            )
            processed_messages.add(cache_key)
            await business_message.reply("✅ Текст переслан!")
            return
        
        # Если есть медиафайл
        if file_data and filename:
            if target_message.caption:
                caption += f"\n\n📝 Подпись: {target_message.caption}"
            
            # Если есть текст в сообщении админа, добавляем его
            if business_message.text:
                caption += f"\n\n💬 Ваш ответ: {business_message.text}"
            
            await send_media_to_owner(
                business_conn.user.id,
                file_data,
                filename,
                caption,
                target_message
            )
            
            processed_messages.add(cache_key)
            
            # Подтверждение в чат
            await business_message.reply("✅ Переслано тебе в ЛС!")
            
        else:
            logger.warning(f"Неизвестный тип сообщения: {target_message}")
            await business_message.reply("❌ Не могу обработать этот тип сообщения")
                    
    except Exception as e:
        logger.error(f"Ошибка при обработке медиа: {e}", exc_info=True)
        try:
            await business_message.reply(f"❌ Ошибка: {str(e)}")
        except:
            pass


async def download_photo(photos: list[PhotoSize]) -> tuple[BytesIO, str]:   
    """Скачивание фото"""
    try:
        file_info = await bot.get_file(photos[-1].file_id)
        file_data = BytesIO()
        await bot.download_file(file_info.file_path, file_data)
        file_data.seek(0)
        
        filename = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        return file_data, filename
    except Exception as e:
        logger.error(f"Ошибка скачивания фото: {e}")
        raise


async def download_video(video: Video) -> tuple[BytesIO, str]:
    """Скачивание видео"""
    try:
        file_info = await bot.get_file(video.file_id)
        file_data = BytesIO()
        await bot.download_file(file_info.file_path, file_data)
        file_data.seek(0)
        
        filename = video.file_name or f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        return file_data, filename
    except Exception as e:
        logger.error(f"Ошибка скачивания видео: {e}")
        raise


async def download_video_note(video_note: VideoNote) -> tuple[BytesIO, str]:
    """Скачивание видеосообщения"""
    try:
        file_info = await bot.get_file(video_note.file_id)
        file_data = BytesIO()
        await bot.download_file(file_info.file_path, file_data)
        file_data.seek(0)
        
        filename = f"video_note_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        return file_data, filename
    except Exception as e:
        logger.error(f"Ошибка скачивания video note: {e}")
        raise


async def download_document(document: Document) -> tuple[BytesIO, str]:
    """Скачивание документа"""
    try:
        file_info = await bot.get_file(document.file_id)
        file_data = BytesIO()
        await bot.download_file(file_info.file_path, file_data)
        file_data.seek(0)
        
        filename = document.file_name or f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return file_data, filename
    except Exception as e:
        logger.error(f"Ошибка скачивания документа: {e}")
        raise


async def send_media_to_owner(
    owner_id: int,
    file_data: BytesIO,
    filename: str,
    caption: str,
    original_message: Message = None
):
    """Отправка медиа владельцу бота"""
    try:
        # Получаем данные файла
        file_bytes = file_data.getvalue()
        if len(file_bytes) == 0:
            logger.error("Пустой файл")
            return
        
        input_file = BufferedInputFile(file_bytes, filename=filename)
        
        # Определяем тип файла и отправляем
        filename_lower = filename.lower()
        
        if filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
            await bot.send_photo(
                chat_id=owner_id,
                photo=input_file,
                caption=caption[:1024] if caption else None,  # Ограничение длины подписи
                parse_mode="HTML"
            )
            
        elif filename_lower.endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            await bot.send_video(
                chat_id=owner_id,
                video=input_file,
                caption=caption[:1024] if caption else None,
                parse_mode="HTML"
            )
            
        elif 'video_note' in filename:
            await bot.send_video_note(
                chat_id=owner_id,
                video_note=input_file
            )
            if caption:
                await bot.send_message(
                    owner_id, 
                    caption[:1024], 
                    parse_mode="HTML"
                )
                
        else:
            # Для документов
            await bot.send_document(
                chat_id=owner_id,
                document=input_file,
                caption=caption[:1024] if caption else None,
                parse_mode="HTML"
            )
            
        logger.info(f"✅ Медиа отправлено владельцу: {filename}")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке медиа: {e}", exc_info=True)
        raise


async def send_text_to_owner(
    owner_id: int,
    text: str,
    caption: str = ""
):
    """Отправка текста владельцу бота"""
    try:
        full_text = f"{caption}\n\n💬 Текст клиента:\n{text}"
        await bot.send_message(
            owner_id,
            full_text[:4096],  # Ограничение Telegram
            parse_mode="HTML"
        )
        logger.info("✅ Текст отправлен владельцу")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке текста: {e}")
        raise


@dp.business_message()
async def handle_business_message(message: Message):
    """Логирование входящих бизнес-сообщений"""
    logger.info(f"📩 Новое сообщение от клиента: "
                f"{message.from_user.first_name} (@{message.from_user.username}) - "
                f"{message.text or message.caption or '[медиа]'}")


@dp.message(Command("test"))
async def cmd_test(message: Message):
    """Тестовая команда"""
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer("✅ Бот работает!")
    await bot.send_message(ADMIN_ID, "✅ Тестовое сообщение в ЛС")
    logger.info("✅ Тестовая команда выполнена")


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика"""
    if message.from_user.id != ADMIN_ID:
        return
    
    stats = f"""
    📊 <b>Статистика:</b>
    
    Обработано сообщений: {len(processed_messages)}
    Владелец: {ADMIN_ID}
    Бот работает: ✅
    
    <b>Последние 5 сообщений:</b>
    {list(processed_messages)[-5:] if processed_messages else 'Нет данных'}
    """
    
    await message.answer(stats, parse_mode="HTML")


# ========== ЗАПУСК ==========
async def main():
    """Запуск бота"""
    try:
        # Проверяем соединение
        me = await bot.get_me()
        logger.info(f"🚀 Бот запущен: @{me.username}")
        logger.info(f"👤 Владелец: {ADMIN_ID}")
        logger.info(f"📝 Используй /start для инструкций")
        
        # Очищаем вебхук
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Запускаем поллинг
        await dp.start_polling(bot)
        
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
    finally:
        # Закрываем сессию
        await bot.session.close()


if __name__ == '__main__':
    # Проверяем настройки
    print("=" * 50)
    print("🤖 БОТ ДЛЯ СОХРАНЕНИЯ ОДНОРАЗОК")
    print("=" * 50)
    
    if BOT_TOKEN == "ВАШ_ТОКЕН_ТУТ":
        print("❌ ОШИБКА: Замени BOT_TOKEN на свой токен от @BotFather")
        exit(1)
    
    if ADMIN_ID == 123456789:
        print("❌ ОШИБКА: Замени ADMIN_ID на свой Telegram ID")
        print("👉 Узнай свой ID у @userinfobot")
        exit(1)
    
    print(f"✅ Токен установлен: {'*' * 10}{BOT_TOKEN[-5:]}")
    print(f"✅ ID владельца: {ADMIN_ID}")
    print("=" * 50)
    print("Запуск...")
    
    asyncio.run(main())
