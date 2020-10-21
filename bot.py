from uuid import uuid4
from time import strftime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, \
    InputTextMessageContent, ParseMode, CallbackQuery
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, InlineQueryHandler, CallbackQueryHandler
import pymongo

from start import update_homeworks
from bot_model import TELEGRAMTOKEN, TEACHERS, collection_users, collection_students, collection_homeworks, \
    collection_admins, collection_queues, collection_chats_with_broadcast

START_KEYBOARD = [[InlineKeyboardButton('Выбрать задачу',
                                        switch_inline_query_current_chat='Начните писать номер или название ДЗ: ')],
                  [InlineKeyboardButton('Выбрать преподавателя', callback_data='choose_teacher')],
                  [InlineKeyboardButton('Встать в очередь', callback_data='add')],
                  [InlineKeyboardButton('Уйти из очереди', callback_data='delete')],
                  [InlineKeyboardButton('Узнать место в очереди', callback_data='check')]
                  ]


def callback_start(update, context):
    user_id = update.message.chat.id
    keyboard2 = [[InlineKeyboardButton('Ввести данные',
                                       switch_inline_query_current_chat='Начните писать фамилию: ')]]

    if collection_users.find_one({'user_id': user_id}) is None:
        update.message.reply_text(f'Здравствуйте! Введите, пожалуйста, ваши настоящие имя, фамилию и группу. '
                                  f'Это необходимо лишь в первый раз.',
                                  reply_markup=InlineKeyboardMarkup(keyboard2, resize_keyboard=True))
    else:
        name = collection_users.find_one({'user_id': user_id})['name']
        update.message.reply_text(f'Вы — {name}. Что хотите сделать?',
                                  reply_markup=InlineKeyboardMarkup(START_KEYBOARD, resize_keyboard=True))


def callback_add(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    user = collection_users.find_one({'user_id': user_id})
    if user['problem']:
        if not user['teacher']:
            bot.send_message(chat_id=user_id, text='Вы не выбрали преподавателя, которому хотите сдать!')
            return
        already_in_queue = collection_queues.find_one({'user_id': user_id,
                                                       'teacher': collection_users.find_one({'user_id': user_id})[
                                                           'teacher']})
        if already_in_queue is not None:
            query.answer('Вы уже в очереди!')
            return
        new_place = collection_queues.find({'teacher': user['teacher'],
                                            'first_time': not user['was_in_queue']}).sort(
            [('place', pymongo.ASCENDING)]).limit(1)
        if new_place.count():
            new_place = list(new_place)[0]['place'] + 1
        else:
            new_place = 1
        if not user['was_in_queue']:
            size = collection_queues.find({'teacher': user['teacher']}).count()
            for p in range(size, new_place - 1, -1):
                collection_queues.find_one_and_update({'place': p, 'teacher': user['teacher']},
                                                      {'$set': {'place': p + 1}})
        collection_queues.insert_one({'user_id': user_id, 'problem': user['problem'],
                                      'teacher': user['teacher'], 'place': new_place,
                                      'first_time': not user['was_in_queue']})
        collection_users.find_one_and_update({'user_id': user_id}, {'$set': {'was_in_queue': True}})

        msg = f'Ваше место в очереди — {new_place}. Преподаватель — {user["teacher"]}.'
        if new_place == 1:
            bot.send_message(chat_id=user_id, text=msg + ' Идите сдавать. Удачи!')
        elif new_place <= 3:
            bot.send_message(chat_id=user_id, text=msg + ' Приготовьтесь!')
        query.answer('Хорошо, теперь вы в очереди.')
        send_queue_updates(user['teacher'], 0)
    else:
        bot.send_message(chat_id=user_id, text='Вы не выбрали задачу, которую хотите сдать!')


def callback_clear_queue(update, context):
    user_id = update.message.chat.id
    if collection_admins.find_one({'user_id': user_id}) is None:
        update.message.reply_text('У вас недостаточно прав для выполнения операции очистки.')
        return
    for user in collection_users.find():
        collection_users.find_one_and_update({'user_id': user['user_id']}, {'$set': {'problem': '', 'teacher': '',
                                                                                     'was_in_queue': False}})
    collection_queues.delete_many({})
    update.message.reply_text('Очередь очищена')


def callback_delete(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    user = collection_users.find_one({'user_id': user_id})
    if user['problem']:
        teacher = user['teacher']
        if not teacher:
            bot.send_message(chat_id=user_id, text=f'Вы не выбрали преподавателя, которому хотите сдавать!')
            return
        queue_place = collection_queues.find_one({'user_id': user_id, 'teacher': teacher})
        if queue_place is None:
            bot.send_message(chat_id=user_id, text='Вас нет в очереди к преподавателю, которого вы выбрали!')
            return
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
        query.answer('Хорошо, теперь вас нет в очереди.')
        send_queue_updates(teacher, 0)
    else:
        bot.send_message(chat_id=user_id, text='Вы не выбрали задачу, которую хотите сдавать!')


def callback_check_place_in_queue(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    user_in_queues = collection_queues.find({'user_id': user_id})
    if user_in_queues is None:
        query.message.reply_text('Вас нет в очереди!')
    else:
        text = 'Ваши места в очередях: '
        for u in user_in_queues:
            text += f'\n\tПреподаватель {u["teacher"]}: {u["place"]}.'
        query.message.reply_text(text)
    query.answer('Ответ в сообщении')


def callback_inline_query(update, context):
    results = []
    query: str = update.inline_query.query
    if query.startswith('Начните писать фамилию: '):
        query = query.replace('Начните писать фамилию: ', '').lower()
        for student in collection_students.find():
            if query in student['name'].lower():
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
    update.inline_query.answer(results[:20])


def callback_reg_student(update, context):
    user_id = update.message.chat.id
    text = update.message.text.replace('Студент: ', '')
    name, group = ' '.join(text.split()[:-1]), text.split()[-1]
    if collection_users.find_one({'user_id': user_id}) is not None:
        return
    collection_users.insert_one({'user_id': user_id, 'name': name, 'group': group,
                                 'problem': '', 'teacher': '', 'was_in_queue': False})
    callback_start(update, context)


def callback_change_problem(update, context):
    user_id = update.message.chat.id
    hw = update.message.text.replace('ДЗ: ', '')
    collection_users.find_one_and_update({'user_id': user_id}, {'$set': {'problem': hw}})
    callback_start(update, context)


def callback_choose_teacher(update, context):
    keyboard = []
    for i in range(len(TEACHERS)):
        tn = TEACHERS[i].split()
        keyboard.append([InlineKeyboardButton(' '.join(tn[1:]), callback_data='teacher_chosen' + str(i))])
    query = update.callback_query
    message_id = query.message.message_id
    user_id = query.message.chat.id
    bot.edit_message_text(chat_id=user_id, message_id=message_id, text='Выберите преподавателя: ',
                          reply_markup=InlineKeyboardMarkup(keyboard, resize_keyboard=True))


def callback_teacher_chosen(update, context):
    query = update.callback_query
    teacher_name = TEACHERS[int(query.data[-1])]
    user_id = query.message.chat.id
    collection_users.find_one_and_update({'user_id': user_id}, {'$set': {'teacher': teacher_name}})
    name = collection_users.find_one({'user_id': user_id})['name']
    bot.edit_message_text(chat_id=user_id, message_id=query.message.message_id,
                          text=f'Вы — {name}. Что хотите сделать?',
                          reply_markup=InlineKeyboardMarkup(START_KEYBOARD, resize_keyboard=True))
    query.answer('Преподаватель выбран')


def callback_start_broadcast_table(update, context):
    chat_id = update.message.chat.id
    if collection_chats_with_broadcast.find_one({'chat_id': chat_id}) is None:
        collection_chats_with_broadcast.insert_one({'chat_id': chat_id, 'messages_id': {}})
    for teacher in TEACHERS:
        send_queue_updates(teacher, 0)


def callback_stop_broadcast_table(update, context):
    chat_id = update.message.chat.id
    if collection_chats_with_broadcast.find_one({'chat_id': chat_id}) is not None:
        collection_chats_with_broadcast.delete_one({'chat_id': chat_id})


def send_queue_updates(teacher, update_line):
    # users_send_list = users.find({'teacher': teacher_name})
    # bot.send_message(chat_id=user_id, text=text)
    # users_send_list.sort([("place", pymongo.ASCENDING)])#.limit(3)#.sort(('place'))#.limit(3)
    # print(dir(users_send_list))
    # for user in users_send_list:
    #     print("usl", user)
    if teacher in TEACHERS:
        collection_queues.create_index('place')
        full_queue = collection_queues.find({'teacher': teacher, 'place': {'$gt': 0}}).sort('place')
        text = '*' + teacher + '*\n'
        # full_queue = full_queue
        free_queue = True
        for st in full_queue:
            free_queue = False
            user_name = collection_users.find_one({'user_id': st['user_id']})['name']
            text += str(st['place']) + ': ' + user_name + '\n'
        if free_queue:
            text += '_в очереди никого нет_\n'
        text += 'Время обновления: '+strftime("%H:%M:%S")
        for chat in collection_chats_with_broadcast.find():
            messages_ids = chat['messages_id']
            if teacher not in messages_ids:
                msg = bot.send_message(chat_id=chat['chat_id'], parse_mode=ParseMode.MARKDOWN_V2, text=text)
                messages_ids[teacher] = msg['message_id']
                collection_chats_with_broadcast.find_one_and_update({'chat_id': chat['chat_id']}, {'$set': {'messages_id': messages_ids}})
            else:
                bot.edit_message_text(chat_id=chat['chat_id'], message_id=messages_ids[teacher],
                                      parse_mode=ParseMode.MARKDOWN, text=text)

if __name__ == '__main__':
    update_homeworks()

    updater = Updater(TELEGRAMTOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    bot = updater.bot

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", callback_start))
    dp.add_handler(CommandHandler("restart", callback_start))
    dp.add_handler(CommandHandler("clear_queue", callback_clear_queue))
    dp.add_handler(CommandHandler("start_broadcast_table", callback_start_broadcast_table))
    dp.add_handler(CommandHandler("stop_broadcast_table", callback_stop_broadcast_table))

    # on callbacks
    dp.add_handler(CallbackQueryHandler(callback=callback_add, pattern='^add$'))
    dp.add_handler(CallbackQueryHandler(callback=callback_delete, pattern='^delete$'))
    dp.add_handler(CallbackQueryHandler(callback=callback_check_place_in_queue, pattern='^check$'))
    dp.add_handler(CallbackQueryHandler(callback=callback_choose_teacher, pattern='^choose_teacher$'))
    dp.add_handler(CallbackQueryHandler(callback=callback_teacher_chosen, pattern='^teacher_chosen.*$'))

    # messages and inline
    dp.add_handler(MessageHandler(Filters.regex('^Студент: .*$'), callback_reg_student))
    dp.add_handler(MessageHandler(Filters.regex('^ДЗ: .*$'), callback_change_problem))
    dp.add_handler(InlineQueryHandler(callback_inline_query))

    # Start the Bot
    updater.start_polling()

    updater.idle()
