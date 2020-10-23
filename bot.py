import bson
import math
from uuid import uuid4

from time import strftime, time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, \
    InputTextMessageContent, ParseMode, CallbackQuery
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, InlineQueryHandler, CallbackQueryHandler
import pymongo
import re

from start import update_homeworks
from bot_model import TELEGRAMTOKEN, TEACHERS, collection_users, collection_students, collection_homeworks, \
    collection_admins, collection_queues, collection_chats_with_broadcast, collection_settings

START_KEYBOARD = [[InlineKeyboardButton('Обновить',
                                        callback_data='callback_refresh_statictics')],
                  [InlineKeyboardButton('Встать в очередь',
                                        switch_inline_query_current_chat='Начните писать номер или название ДЗ: ')],
                  [InlineKeyboardButton('Отозвать заявку',
                                        switch_inline_query_current_chat='Начните писать название заявки: ')]
                  ]

# PRACTICE_DEADLINE = 920 # 15:20

def callback_start(update, context):
    user_id = update.message.chat.id
    
    if not is_real_user(update):
        return
    login_keyboard = [[InlineKeyboardButton('Ввести данные',
                                            switch_inline_query_current_chat='Начните писать фамилию: ')]]

    if collection_users.find_one({'user_id': user_id}) is None:
        update.message.reply_text(f'Здравствуйте! Введите, пожалуйста, ваши настоящие имя, фамилию и группу. '
                                  f'Это необходимо лишь в первый раз.',
                                  reply_markup=InlineKeyboardMarkup(login_keyboard, resize_keyboard=True))
    else:
        show_status(user_id)


def getElapsedTime():
    t = math.ceil((collection_settings['ending'] - time()) / 60)
    t = t if t >= 0 else 0
    d = [' минут', ' минуты', ' минута']
    
    if t % 10 >= 5:
        t = str(t) + d[0]
    elif t % 10 >= 2:
        t = str(t) + d[1]
    else:
        t = str(t) + d[2]
        
    return t


def is_real_user(update):
    return update.message.chat.type == "private"


def show_status(user_id):
    bot.send_message(chat_id=user_id, text=getStatus(user_id),
                     reply_markup=InlineKeyboardMarkup(START_KEYBOARD, resize_keyboard=True))    


def getStatus(user_id):
    user_in_queues = collection_queues.find({'user_id': user_id})

    shortName = ' '.join(collection_users.find_one({'user_id': user_id})['name'].split()[:2])
    text = f'Студент: {shortName}\nВремя до конца практики: {getElapsedTime()}\n\n'

    if not user_in_queues.count():
        text += 'У Вас нет активных заявок'
    else:
        text += 'Активные заявки:\n'
        for u in user_in_queues:
            shortTeacherName = ''.join(map(lambda x: x[0], u["teacher"].split()[1::-1]))
            text += f'{u["problem"]} — {u["place"]} место ({shortTeacherName})\n'

    return text


def callback_refresh_statictics(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    message_id = query.message.message_id
    newStatus = getStatus(user_id).strip()
    
    if query.message.text != newStatus:
        bot.edit_message_text(chat_id=user_id, message_id=message_id,text=newStatus,
                              reply_markup=InlineKeyboardMarkup(START_KEYBOARD, resize_keyboard=True))
    
    query.answer('Обновлено!')
    

def callback_logout(update, context):
    user_id = update.message.chat.id
    if collection_users.find_one({'user_id': user_id}):
        collection_users.delete_one({'user_id': user_id}) # was_in_queue flag is erased here
        update.message.reply_text('Деавторизация успешна')


def callback_add(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    message_id = query.message.message_id
    user = collection_users.find_one({'user_id': user_id})

    if time() < collection_settings['starting'] and (not collection_admins.find_one({'user_id': user_id})):
        query.answer('Практика еще не началась!!!')
        return

    already_in_queue = collection_queues.find_one({'user_id': user_id,
                                                   'teacher': collection_users.find_one({'user_id': user_id})[
                                                       'teacher']})
    
    if already_in_queue is not None:# and False: #t2odo: delete this
        bot.edit_message_text(chat_id=user_id, message_id=message_id,
                          text='Вы уже в очереди!')
        return

    collection_queues.insert_one({'user_id': user_id, 'problem': user['problem'],
                                  'teacher': user['teacher'], 'place': 0, 'insert_time': time(),
                                  'first_time': user['problem'] not in user['was_in_queue']})
    if user['problem'] not in user['was_in_queue']:
        user['was_in_queue'].append(user['problem'])
    collection_users.find_one_and_update({'user_id': user_id}, {'$set': {'was_in_queue': user['was_in_queue']}})
    changed_entries = recalculate_queue(user['teacher'])
    new_place = 0
    for entry in changed_entries:
        if entry['user_id'] == user_id and entry['problem'] == user['problem'] and entry['teacher'] == user['teacher']:
            new_place = entry['place']
            break

    msg_text = 'Заявка создана!\nПреподаватель: {}\nЗадание: {}\nВаше место в очереди: {}\n'.format(
        user['teacher'], user['problem'],new_place)
    bot.edit_message_text(chat_id=user_id, message_id=message_id, text=msg_text)

    show_status(user_id)
    send_messages_to_top_queue(changed_entries)
    send_queue_updates(user['teacher'])


def callback_admin_clear_queue(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    if collection_admins.find_one({'user_id': user_id}) is None:
        update.message.reply_text('У вас недостаточно прав для очистки очереди')
        return
    for user in collection_users.find():
        collection_users.find_one_and_update({'user_id': user['user_id']}, {'$set': {'problem': '', 'teacher': '',
                                                                                     'was_in_queue': []}})
    collection_queues.delete_many({})
    query.message.reply_text('Очередь очищена')

    for teacher in TEACHERS:
        send_queue_updates(teacher)


def callback_delete(update, context):
    query = update.callback_query
    user_id = update.message.chat.id
    user = collection_users.find_one({'user_id': user_id})
    teacher = user['teacher']
    collection_queues.delete_many({'user_id': user_id, 'teacher': teacher, 'problem': user['problem']})
    send_messages_to_top_queue(recalculate_queue(teacher))
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
            if query in hw['name'].lower() in [s.lower() for s in collection_settings['actual_problems']]:
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
    
    if not is_real_user(update):
        return
    
    if collection_users.find_one({'user_id': user_id}) is not None:
        return

    if not collection_students.find_one({'name': name}):
        bot.send_message(chat_id=user_id, text='Произошла ошибка при выборе пользователя')
        return
    
    collection_users.insert_one({'user_id': user_id, 'name': name, 'group': group,
                                 'problem': '', 'teacher': '', 'was_in_queue': []})
    callback_start(update, context)


def callback_join_queue(update, context):
    keyboard1 = [[InlineKeyboardButton('Георгий Корнеев', callback_data='teacher_chosen0')],
                 [InlineKeyboardButton('Юлия Савон', callback_data='teacher_chosen1')],
                 [InlineKeyboardButton('Андрей Плотников', callback_data='teacher_chosen2')]]

    query = update.callback_query
    user_id = update.message.chat.id
    
    if not is_real_user(update):
        return
    
    user = collection_users.find_one({'user_id': user_id})
    
    if user is None:
        return

    hw = update.message.text.replace('ДЗ: ', '')
    
    if not collection_homeworks.find_one({'name':hw}):
        bot.send_message(chat_id=user_id, text='Произошла ошибка при выборе задачи')
        return
    
    collection_users.find_one_and_update({'user_id': user_id}, {'$set': {'problem': hw}})
    
    already_in_queue = collection_queues.find_one({'user_id': user_id, 'problem': hw})
    
    if already_in_queue is not None:
        bot.send_message(chat_id=user_id, text='Вы уже в очереди на это задание!')
    else:
        update.message.reply_text(f'Выбранная задача:\n{hw}\n\nНапоминаем, что сдавать две задачи подряд одному и тому же преподавателю не разрешается.\n\nВыберите преподавателя:',
                                  reply_markup=InlineKeyboardMarkup(keyboard1, resize_keyboard=True))


def callback_teacher_chosen(update, context):
    query = update.callback_query
    teacher_name = TEACHERS[int(query.data[-1])]
    user_id = query.message.chat.id
    collection_users.find_one_and_update({'user_id': user_id}, {'$set': {'teacher': teacher_name}})
    callback_add(update, context)


def callback_revoke(update, context):
    if not is_real_user(update):
        return
    query = update.callback_query
    user_id = update.message.chat.id
    user = collection_users.find_one({'user_id': user_id})
    if user is None:
        return

    problem = update.message.text.replace('Отозвать: ', '')

    entry = collection_queues.find_one({'user_id': user_id, 'problem': problem})
    if not entry:
        bot.send_message(chat_id=user_id, text='Вас нет в очереди на эту задачу!')
        return
    collection_users.find_one_and_update({'user_id': user_id}, {'$set': {'teacher': entry['teacher'], 'problem': problem}})
    callback_delete(update, context)
    show_status(user_id)


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
            try:
                if teacher not in messages_ids:
                    msg = bot.send_message(chat_id=chat['chat_id'], parse_mode=ParseMode.MARKDOWN_V2, text=text)
                    messages_ids[teacher] = msg['message_id']
                    collection_chats_with_broadcast.find_one_and_update({'chat_id': chat['chat_id']},
                                                                        {'$set': {'messages_id': messages_ids}})
                else:
                    bot.edit_message_text(chat_id=chat['chat_id'], message_id=messages_ids[teacher],
                                          parse_mode=ParseMode.MARKDOWN, text=text)
            except:
                print(f'Can not send queue updates in chat {chat}')


def callback_admin(update, context):
    user_id = update.message.chat.id
    if collection_admins.find_one({'user_id': user_id}) is None:
        update.message.reply_text('У вас недостаточно прав для этого действия')
        return
    admin_keyboard = [[InlineKeyboardButton('Очистить очередь', callback_data='admin_clear_queue'),
                       InlineKeyboardButton('Модерировать очередь', callback_data='admin_moderate_queue_s')]]

    update.message.reply_text('admin panel', reply_markup=InlineKeyboardMarkup(admin_keyboard, resize_keyboard=True))


def callback_admin_moderate_queue(update, context):
    query = update.callback_query
    user_id = query.message.chat.id

    if collection_admins.find_one({'user_id': user_id}) is None:
        update.message.reply_text('У вас недостаточно прав для этого действия')
        return

    command_info = query.data.replace('admin_moderate_queue_', '')
    if command_info == 's':
        keyboard_teacher = [[InlineKeyboardButton('Георгий Корнеев', callback_data='admin_moderate_queue_0'),
                             InlineKeyboardButton('Юлия Савон', callback_data='admin_moderate_queue_1'),
                             InlineKeyboardButton('Андрей Плотников', callback_data='admin_moderate_queue_2')]]
        query.edit_message_text(text='Select teacher',
                         reply_markup=InlineKeyboardMarkup(keyboard_teacher, resize_keyboard=True))
    elif command_info[0].isdigit():
        teacher = TEACHERS[int(command_info[0])]
        shortTeacherName = ''.join(map(lambda x: x[0], teacher.split()[1::-1]))
        head_queue = collection_queues.find_one({'teacher': teacher, 'place': 1})
        if head_queue:
            head_queue_name = collection_users.find_one({'user_id': head_queue['user_id']})['name']
            head_queue_problem = head_queue['problem']
            text = f'На первом месте к {shortTeacherName}: {head_queue_name} \nна задачу {head_queue_problem}. Удалить?'
            cd = 'admin_moderate_queue_d_' + str(head_queue['user_id']) + '_' + str(head_queue['_id'])
            query.edit_message_text(text=text, parse_mode=ParseMode.MARKDOWN,
                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('удалить', callback_data=cd)]]))
    elif command_info[0] == 'd':
        command_info = command_info.split('_')
        head_queue = collection_queues.find_one({'user_id': int(command_info[1]), '_id': bson.objectid.ObjectId(command_info[2])})
        if head_queue:
            print(head_queue)
            teacher = head_queue['teacher']
            old_place = head_queue['place']
            collection_queues.delete_many({'user_id': int(command_info[1]), '_id': bson.objectid.ObjectId(command_info[2])})
            send_messages_to_top_queue(recalculate_queue(teacher))
            send_queue_updates(teacher)
            query.edit_message_text(text=f'Пользователь удален')
        else:
            bot.send_message(text=f'Выбранный пользватель не найден')


def recalculate_queue(teacher):
    priority = collection_settings['problems_priority']
    old_queue = collection_queues.find({'teacher': teacher})
    if old_queue:
        old_places = {}
        new_places = []
        with_changes = []
        old_queue = list(old_queue)
        old_queue.sort(key=lambda x: (
            0 if 'first_time' not in x else (0 if x['first_time'] else 1),
            0 if x['problem'] not in priority else priority[x['problem']],
            0 if 'insert_time' not in x else x['insert_time']))
        for el in old_queue:
            old_places[el['_id']] = el['place']
            new_places.append(el)
        i = 0
        for n_pl in new_places:
            i += 1
            if i != old_places[n_pl['_id']]:
                n_pl['place'] = i
                with_changes.append(n_pl)
                collection_queues.find_one_and_update({'_id': bson.objectid.ObjectId(n_pl['_id'])}, {'$set': {'place': i}})
        return with_changes
    return []


def send_messages_to_top_queue(entries):
    for entry in entries:
        tmp = 'Преподаватель: {}\nЗадание: {}\nВаше место в очереди: {}\n'.format(entry['teacher'], entry['problem'], entry['place'])
        if entry['place'] == 1:
            bot.send_message(chat_id=entry['user_id'], text=tmp + 'Идите сдавать. Удачи!')
        elif entry['place'] <= 3:
            bot.send_message(chat_id=entry['user_id'], text=tmp + 'Приготовьтесь!')


# def callback_set_practice_deadline(update, context):
#     user_id = update.message.chat.id
#     text = update.message.text
#
#     if not is_real_user(update):
#         return
#
#     if collection_admins.find_one({'user_id': user_id}) is None:
#         update.message.reply_text('У вас недостаточно прав для этого действия')
#         return
#
#     t = text.replace('/set_practice_deadline ', '')
#
#     if len(t) == 5 and t[:2].isdigit() and t[3:].isdigit() and t[2] == ':':
#         PRACTICE_DEADLINE = int(t[:2]) * 60 + int(t[3:])
#     else:
#         bot.send_message(chat_id=user_id,text=f'Ошибка')

if __name__ == '__main__':
    update_homeworks()
    if not collection_admins.find_one({'user_id':316671439}):
        collection_admins.insert_one({'user_id': 316671439})
    if not collection_admins.find_one({'user_id':487574745}):
        collection_admins.insert_one({'user_id': 487574745})
    if not collection_admins.find_one({'user_id':333728707}):
        collection_admins.insert_one({'user_id': 333728707})

    updater = Updater(TELEGRAMTOKEN, use_context=True)

    # debug purposes
    # collection_queues.delete_many({})

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    bot = updater.bot

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", callback_start))
    dp.add_handler(CommandHandler("restart", callback_start))
    dp.add_handler(CommandHandler("logout", callback_logout))

    # priveleged commands
    dp.add_handler(CommandHandler("admin", callback_admin))
    dp.add_handler(CommandHandler("start_broadcast_table", callback_start_broadcast_table))
    dp.add_handler(CommandHandler("stop_broadcast_table", callback_stop_broadcast_table))
    # dp.add_handler(CommandHandler("set_practice_deadline", callback_set_practice_deadline))

    # on callbacks
    dp.add_handler(CallbackQueryHandler(callback=callback_add, pattern='^add$'))
    dp.add_handler(CallbackQueryHandler(callback=callback_delete, pattern='^delete$'))
    dp.add_handler(CallbackQueryHandler(callback=callback_teacher_chosen, pattern='^teacher_chosen.*$'))
    dp.add_handler(CallbackQueryHandler(callback=callback_admin_clear_queue, pattern='^admin_clear_queue$'))
    dp.add_handler(CallbackQueryHandler(callback=callback_admin_moderate_queue, pattern='^admin_moderate_queue.*$'))
    dp.add_handler(CallbackQueryHandler(callback=callback_refresh_statictics, pattern='^callback_refresh_statictics$'))

    # messages and inline
    dp.add_handler(MessageHandler(Filters.regex('^Студент: .*$'), callback_reg_student))
    dp.add_handler(MessageHandler(Filters.regex('^ДЗ: .*$'), callback_join_queue))
    dp.add_handler(MessageHandler(Filters.regex('^Отозвать: .*$'), callback_revoke))
    dp.add_handler(InlineQueryHandler(callback_inline_query))

    # Start the Bot
    updater.start_polling()
    print("Start polling")

    updater.idle()
