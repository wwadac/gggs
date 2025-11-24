from telethon import TelegramClient, events, Button

# ВСТАВЬ СВОИ ДАННЫЕ ЗДЕСЬ
api_id = 29385016                    # Твой API ID
api_hash = '3c57df8805ab5de5a23a032ed39b9af9'          # Твой API Hash
bot_token = '8334964804:AAHdieIWn4McjFWkSeoLq6UthsUodP1N5lY'         # Токен бота от BotFather

# ID администратора (замени на свой)
ADMIN_ID = 8000395560

client = TelegramClient('bot_session', api_id, api_hash).start(bot_token=bot_token)

# Хранилище для статистики
user_stats = {}

def is_admin(user_id):
    return user_id == ADMIN_ID

@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user_id = event.sender_id
    keyboard = [
        [Button.inline("Мой айди", b'my_id')],
        [Button.inline("Айди другого", b'other_id')]
    ]
    
    # Добавляем админские кнопки только для админа
    if is_admin(user_id):
        keyboard.append([Button.inline("📊 Статистика", b'stats'), Button.inline("📢 Рассылка", b'broadcast')])
    
    await event.reply('Выберите опцию:', buttons=keyboard)

@client.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    
    if event.data == b'my_id':
        await event.edit(f"🆔 Ваш ID: {user_id}")
    
    elif event.data == b'other_id':
        await event.edit("📩 Перешлите сообщение от нужного пользователя или напишите его юзернейм")
    
    elif event.data == b'stats':
        if not is_admin(user_id):
            await event.edit("❌ Доступ запрещен")
            return
        total_users = len(user_stats)
        await event.edit(f"📊 Статистика бота:\n\n👥 Всего пользователей: {total_users}")
    
    elif event.data == b'broadcast':
        if not is_admin(user_id):
            await event.edit("❌ Доступ запрещен")
            return
        # Сохраняем ID пользователя для рассылки
        user_stats[user_id] = {'waiting_for_broadcast': True}
        await event.edit("📢 Введите сообщение для рассылки:")

@client.on(events.NewMessage)
async def message_handler(event):
    user_id = event.sender_id
    
    # Обновляем статистику
    if user_id not in user_stats:
        user_stats[user_id] = {}
    
    # Обработка рассылки для админа
    if is_admin(user_id) and user_stats.get(user_id, {}).get('waiting_for_broadcast'):
        user_stats[user_id]['waiting_for_broadcast'] = False
        message_text = event.message.text
        sent_count = 0
        
        await event.reply("🔄 Начинаю рассылку...")
        
        # Рассылаем сообщение всем пользователям
        for user in user_stats:
            if user != user_id:  # Не отправляем себе
                try:
                    await client.send_message(user, f"📢 Рассылка:\n\n{message_text}")
                    sent_count += 1
                except:
                    continue
        
        await event.reply(f"✅ Рассылка завершена\n\nОтправлено сообщений: {sent_count}")
        return
    
    # Игнорируем команды
    if event.message.text and event.message.text.startswith('/'):
        return
    
    # Обработка пересланных сообщений
    if event.message.forward:
        try:
            # Получаем ID отправителя пересланного сообщения
            forward_header = event.message.forward
            sender_id = forward_header.sender_id
            
            if sender_id:
                # Пытаемся получить информацию об отправителе
                try:
                    user = await client.get_entity(sender_id)
                    await event.reply(f"🆔 ID пользователя {user.first_name}: {user.id}")
                except:
                    await event.reply(f"🆔 ID пользователя: {sender_id}")
            else:
                await event.reply("❌ Не удалось получить ID отправителя")
        except Exception as e:
            await event.reply(f"❌ Ошибка при обработке пересланного сообщения: {str(e)}")
        return
    
    # Обработка юзернеймов (с @ и без)
    if event.message.text:
        text = event.message.text.strip()
        # Убираем @ если он есть
        if text.startswith('@'):
            text = text[1:]
        
        if text:  # Проверяем что текст не пустой
            try:
                user = await client.get_entity(text)
                await event.reply(f"🆔 ID пользователя {user.first_name}: {user.id}")
            except Exception as e:
                await event.reply("❌ Пользователь не найден")

print("Бот запущен...")
client.run_until_disconnected()
