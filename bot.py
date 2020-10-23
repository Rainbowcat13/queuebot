from uuid import uuid4
from time import strftime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, \
    InputTextMessageContent, ParseMode, CallbackQuery
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, InlineQueryHandler, CallbackQueryHandler
import pymongo
import re

from start import update_homeworks
from bot_model import TELEGRAMTOKEN, TEACHERS, collection_users, collection_students, collection_homeworks, \
    collection_admins, collection_queues, collection_chats_with_broadcast

START_KEYBOARD = [[InlineKeyboardButton('Встать в очередь',
                                        switch_inline_query_current_chat='Начните писать номер или название ДЗ: ')],
                  [InlineKeyboardButton('Отозвать заявку',
                                        switch_inline_query_current_chat='Начните писать название заявки: ')]
                  ]


def callback_start(update, context):
    user_id = update.message.chat.id
    login_keyboard = [[InlineKeyboardButton('Ввести данные',
                                            switch_inline_query_current_chat='Начните писать фамилию: ')]]

    if collection_users.find_one({'user_id': user_id}) is None:
        update.message.reply_text(f'Здравствуйте! Введите, пожалуйста, ваши настоящие имя, фамилию и группу. '
                                  f'Это необходимо лишь в первый раз.',
                                  reply_markup=InlineKeyboardMarkup(login_keyboard, resize_keyboard=True))
    else:
        show_status(user_id)


def getElapsedTime():  # todo: return real time
    return 1337 % 55  # is negative time allowed?


def show_status(user_id):
    user_in_queues = collection_queues.find({'user_id': user_id})

    shortName = ' '.join(collection_users.find_one({'user_id': user_id})['name'].split()[:2])
    text = f'Студент: {shortName}\nВремя до конца практики: {getElapsedTime()} минут\n\n'

    if not user_in_queues.count():
        text += 'У Вас нет активных заявок'
    else:
        text += 'Активные заявки:\n'
        for u in user_in_queues:
            shortTeacherName = ''.join(map(lambda x: x[0], u["teacher"].split()[1::-1]))
            text += f'{u["problem"]} — {u["place"]} место ({shortTeacherName})\n'

    bot.send_message(chat_id=user_id, text=text,
                     reply_markup=InlineKeyboardMarkup(START_KEYBOARD, resize_keyboard=True))


def callback_logout(update, context):
    user_id = update.message.chat.id
    if collection_users.find_one({'user_id': user_id}):
        collection_users.delete_one({'user_id': user_id})
        update.message.reply_text('Деавторизация успешна')


def callback_add(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    message_id = query.message.message_id
    user = collection_users.find_one({'user_id': user_id})

    already_in_queue = collection_queues.find_one({'user_id': user_id,
                                                   'teacher': collection_users.find_one({'user_id': user_id})[
                                                       'teacher']})
    
    if already_in_queue is not None:
        bot.edit_message_text(chat_id=user_id, message_id=message_id,
                          text='Вы уже в очереди!')
        return

    new_place = collection_queues.find({'teacher': user['teacher'],
                                        'first_time': not user['was_in_queue']}).sort(
        [('place', pymongo.ASCENDING)]).limit(1)
    new_place = list(new_place)

    if new_place:
        new_place = new_place[0]['place'] + 1
    else:
        new_place = 1

    if not user['was_in_queue']:
        size = collection_queues.find({'teacher': user['teacher']}).count()
        for p in range(size, new_place - 1, -1):
            collection_queues.find_one_and_update({'place': p, 'teacher': user['teacher']}, {'$set': {'place': p + 1}})

    collection_queues.insert_one({'user_id': user_id, 'problem': user['problem'],
                                  'teacher': user['teacher'], 'place': new_place,
                                  'first_time': not user['was_in_queue']})

    collection_users.find_one_and_update({'user_id': user_id}, {'$set': {'was_in_queue': True}})
    
    bot.edit_message_text(chat_id=user_id, message_id=message_id,
                          text=f'Заявка создана!\nВаше место в очереди - {new_place}\n\nЗадача:\n{user["problem"]}\n\nПреподаватель:\n{user["teacher"]}')

    if new_place == 1:
        bot.send_message(chat_id=user_id, text='Идите сдавать. Удачи!')
    elif new_place <= 3:
        bot.send_message(chat_id=user_id, text='Приготовьтесь!')

    show_status(user_id)

    send_queue_updates(user['teacher'])


def callback_clear_queue(update, context):
    user_id = update.message.chat.id
    if collection_admins.find_one({'user_id': user_id}) is None:
        update.message.reply_text('У вас недостаточно прав для очистки очереди')
        return
    for user in collection_users.find():
        collection_users.find_one_and_update({'user_id': user['user_id']}, {'$set': {'problem': '', 'teacher': '',
                                                                                     'was_in_queue': False}})
    collection_queues.delete_many({})
    update.message.reply_text('Очередь очищена')

    for teacher in TEACHERS:
        send_queue_updates(teacher)


def callback_delete(update, context):
    query = update.callback_query
    user_id = update.message.chat.id
    user = collection_users.find_one({'user_id': user_id})
    teacher = user['teacher']

    queue_place = collection_queues.find_one({'user_id': user_id, 'teacher': teacher})
    old_place = queue_place['place']

    collection_queues.delete_many({'user_id': user_id, 'teacher': teacher})
    size = collection_queues.find({'teacher': teacher}).count()

    for p in range(old_place + 1, size + 2):
        collection_queues.find_one_and_update({'place': p, 'teacher': teacher}, {'$set': {'place': p - 1}})

    for p in range(1, min(4, size + 1)):
        user_id = collection_queues.find_one({'place': p, 'teacher': teacher})['user_id']
        text = f'Ваше место в очереди — {p}. Преподаватель {teacher}. '
        if p == 1:
            text += 'Идите сдавать. Удачи!'
        else:
            text += 'Приготовьтесь!'
        bot.send_message(chat_id=user_id, text=text)
    send_queue_updates(teacher)


def callback_inline_query(update, context):
    results = []
    query: str = update.inline_query.query
    cache_time = 300
    is_personal = False
    if query.startswith('Начните писать фамилию: '):
        query = query.replace('Начните писать фамилию: ', '')
        regex = re.compile(re.escape(query), re.IGNORECASE)

        for student in collection_students.find({'name': {'$regex': regex}}):
            s = f"{student['name']} {student['group']}"
            results.append(InlineQueryResultArticle(
                id=str(uuid4()),
                title=s,
                input_message_content=InputTextMessageContent("Студент: " + s)))
    elif query.startswith('Начните писать номер или название ДЗ: '):
        query = query.replace('Начните писать номер или название ДЗ: ', '').lower()
        for hw in collection_homeworks.find():
            if query in hw['name'].lower():
                results.append(InlineQueryResultArticle(
                    id=str(uuid4()),
                    title=hw['name'],
                    input_message_content=InputTextMessageContent("ДЗ: " + hw['name'])))
    elif query.startswith('Начните писать название заявки: '):
        query = query.replace('Начните писать название заявки: ', '').lower()
        user_id = update.inline_query.from_user.id
        is_personal = True
        cache_time = 0
        for request in collection_queues.find({'user_id': user_id}):
            if query in request['problem'].lower():
                results.append(InlineQueryResultArticle(
                    id=str(uuid4()),
                    title=request['problem'],
                    input_message_content=InputTextMessageContent("Отозвать: " + request['problem'])))
    update.inline_query.answer(results[:20], cache_time=cache_time, is_personal=is_personal)


def callback_reg_student(update, context):
    user_id = update.message.chat.id
    text = update.message.text.replace('Студент: ', '')
    name, group = ' '.join(text.split()[:-1]), text.split()[-1]
    
    if collection_users.find_one({'user_id': user_id}) is not None:
        return

    if not collection_students.find_one({'name': name}):
        bot.send_message(chat_id=user_id, text='Произошла ошибка при выборе пользователя')
        return
    
    collection_users.insert_one({'user_id': user_id, 'name': name, 'group': group,
                                 'problem': '', 'teacher': '', 'was_in_queue': False})
    callback_start(update, context)


def callback_join_queue(update, context):
    keyboard1 = [[InlineKeyboardButton('Георгий Корнеев', callback_data='teacher_chosen0')],
                 [InlineKeyboardButton('Юлия Савон', callback_data='teacher_chosen1')],
                 [InlineKeyboardButton('Андрей Плотников', callback_data='teacher_chosen2')]]

    query = update.callback_query
    user_id = update.message.chat.id
    user = collection_users.find_one({'user_id': user_id})

    hw = update.message.text.replace('ДЗ: ', '')
    
    if not collection_homeworks.find_one({'name':hw}):
        bot.send_message(chat_id=user_id, text='Произошла ошибка при выборе задачи')
        return
    
    collection_users.find_one_and_update({'user_id': user_id}, {'$set': {'problem': hw}})
    
    already_in_queue = collection_queues.find_one({'user_id': user_id,
                                                   'problem': hw})
    
    if already_in_queue is not None:
        bot.send_message(chat_id=user_id, text='Вы уже в очереди!')
    else:
        update.message.reply_text(f'Текущая задача:\n{hw}\n\nВыберите преподавателя:',
                                  reply_markup=InlineKeyboardMarkup(keyboard1, resize_keyboard=True))


def callback_teacher_chosen(update, context):
    query = update.callback_query
    teacher_name = TEACHERS[int(query.data[-1])]
    user_id = query.message.chat.id
    collection_users.find_one_and_update({'user_id': user_id}, {'$set': {'teacher': teacher_name}})
    callback_add(update, context)


def callback_revoke(update, context):
    query = update.callback_query
    user_id = update.message.chat.id
    problem = update.message.text.replace('Отозвать: ', '')

    t = collection_queues.find_one({'user_id': user_id, 'problem': problem})

    if not t:
        bot.send_message(chat_id=user_id, text='Ошибка!')
        return

    collection_users.find_one_and_update({'user_id': user_id}, {'$set': {'teacher': t['teacher'], 'problem': problem}})
    callback_delete(update, context)
    show_status(user_id)
    send_queue_updates(t['teacher'])


def callback_start_broadcast_table(update, context):
    chat_id = update.message.chat.id
    if collection_chats_with_broadcast.find_one({'chat_id': chat_id}) is None:
        collection_chats_with_broadcast.insert_one({'chat_id': chat_id, 'messages_id': {}})
    for teacher in TEACHERS:
        send_queue_updates(teacher)


def callback_stop_broadcast_table(update, context):
    chat_id = update.message.chat.id
    if collection_chats_with_broadcast.find_one({'chat_id': chat_id}) is not None:
        collection_chats_with_broadcast.delete_one({'chat_id': chat_id})


def send_queue_updates(teacher):
    if teacher in TEACHERS:
        collection_queues.create_index('place')
        full_queue = collection_queues.find({'teacher': teacher, 'place': {'$gt': 0}}).sort('place')
        text = '*' + teacher + '*\n'
        free_queue = True
        for st in full_queue:
            free_queue = False
            user_name = collection_users.find_one({'user_id': st['user_id']})['name']
            text += str(st['place']) + ': ' + user_name + '\n'
        if free_queue:
            text += '_в очереди никого нет_\n'
        text += 'Время обновления: ' + strftime("%H:%M:%S")
        for chat in collection_chats_with_broadcast.find():
            messages_ids = chat['messages_id']
            if teacher not in messages_ids:
                msg = bot.send_message(chat_id=chat['chat_id'], parse_mode=ParseMode.MARKDOWN_V2, text=text)
                messages_ids[teacher] = msg['message_id']
                collection_chats_with_broadcast.find_one_and_update({'chat_id': chat['chat_id']},
                                                                    {'$set': {'messages_id': messages_ids}})
            else:
                bot.edit_message_text(chat_id=chat['chat_id'], message_id=messages_ids[teacher],
                                      parse_mode=ParseMode.MARKDOWN, text=text)


if __name__ == '__main__':
    update_homeworks()

    updater = Updater(TELEGRAMTOKEN, use_context=True)

    # debug purposes
    # queues.delete_many({})

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    bot = updater.bot

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", callback_start))
    dp.add_handler(CommandHandler("restart", callback_start))
    dp.add_handler(CommandHandler("logout", callback_logout))

    # priveleged commands
    dp.add_handler(CommandHandler("clear_queue", callback_clear_queue))
    dp.add_handler(CommandHandler("start_broadcast_table", callback_start_broadcast_table))
    dp.add_handler(CommandHandler("stop_broadcast_table", callback_stop_broadcast_table))

    # on callbacks
    dp.add_handler(CallbackQueryHandler(callback=callback_add, pattern='^add$'))
    dp.add_handler(CallbackQueryHandler(callback=callback_delete, pattern='^delete$'))
    dp.add_handler(CallbackQueryHandler(callback=callback_teacher_chosen, pattern='^teacher_chosen.*$'))

    # messages and inline
    dp.add_handler(MessageHandler(Filters.regex('^Студент: .*$'), callback_reg_student))
    dp.add_handler(MessageHandler(Filters.regex('^ДЗ: .*$'), callback_join_queue))
    dp.add_handler(MessageHandler(Filters.regex('^Отозвать: .*$'), callback_revoke))
    dp.add_handler(InlineQueryHandler(callback_inline_query))

    # Start the Bot
    updater.start_polling()
    print("Start polling")

    updater.idle()
