from telethon import TelegramClient, events, Button

# ВСТАВЬ СВОИ ДАННЫЕ ЗДЕСЬ
api_id = 29385016                    # Твой API ID
api_hash = '3c57df8805ab5de5a23a032ed39b9af9'          # Твой API Hash
bot_token = '8334964804:AAHdieIWn4McjFWkSeoLq6UthsUodP1N5lY'         # Токен бота от BotFather

client = TelegramClient('bot_session', api_id, api_hash).start(bot_token=bot_token)

@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    keyboard = [
        [Button.inline("Мой айди", b'my_id')],
        [Button.inline("Айди другого", b'other_id')]
    ]
    await event.reply('Выберите опцию:', buttons=keyboard)

@client.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    
    if event.data == b'my_id':
        await event.edit(f"🆔 Ваш ID: {user_id}")
    
    elif event.data == b'other_id':
        await event.edit("📩 Перешлите сообщение от нужного пользователя или напишите его юзернейм")

@client.on(events.NewMessage)
async def message_handler(event):
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
