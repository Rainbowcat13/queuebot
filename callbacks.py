import bson
from uuid import uuid4
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, \
    InputTextMessageContent, ParseMode

from functions import *
from bot import queuebot
from lesson_settings import *

db = queuebot.db


def callback_start(update, context):
    user_id = update.message.chat.id

    if not real_user(update):
        return
    login_keyboard = [[InlineKeyboardButton('Ввести данные',
                                            switch_inline_query_current_chat='Начните писать фамилию: ')]]

    if db.aggregate_one('users', {'user_id': user_id}) is None:
        update.message.reply_text(f'Здравствуйте! Введите, пожалуйста, ваши настоящие имя, фамилию и группу. '
                                  f'Это необходимо лишь в первый раз.',
                                  reply_markup=InlineKeyboardMarkup(login_keyboard, resize_keyboard=True))
    else:
        queuebot.show_status(user_id)


def callback_refresh_statistics(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    message_id = query.message.message_id
    new_status = queuebot.get_status(user_id).strip()

    if query.message.text != new_status:
        queuebot.bot.edit_message_text(chat_id=user_id, message_id=message_id, text=new_status,
                                       reply_markup=InlineKeyboardMarkup(queuebot.START_KEYBOARD, resize_keyboard=True))

    query.answer('Обновлено!')


def callback_logout(update, context):
    user_id = update.message.chat.id
    if db.aggregate_one('users', {'user_id': user_id}):
        db.aggregate_one('users', {'user_id': user_id}, delete=True)
        update.message.reply_text('Деавторизация успешна')


def callback_add(update, context):  # NOT REFACTORED
    query = update.callback_query
    user_id = query.message.chat.id
    message_id = query.message.message_id
    user = db.aggregate_one('users', {'user_id': user_id})

    if time() < lesson_settings['starting'] and not db.aggregate_one('admins', {'user_id': user_id}):
        query.answer('Практика еще не началась!!!')
        return

    already_in_queue = db.aggregate_one('queues', {'user_id': user_id,
                                                   'teacher': db.aggregate_one('users',
                                                                               {'user_id': user_id})['teacher']})

    if already_in_queue is not None:  # and False: #t2odo: delete this
        queuebot.bot.edit_message_text(chat_id=user_id, message_id=message_id,
                                       text='Вы уже в очереди!')
        return

    was_in_queue_to_teacher = user['problem'] not in user['was_in_queue']
    db.add_one('queues', {'user_id': user_id, 'problem': user['problem'],
                          'teacher': user['teacher'], 'place': 0, 'insert_time': time(),
                          'first_time': was_in_queue_to_teacher})

    if not was_in_queue_to_teacher:
        user['was_in_queue'].append(user['problem'])
    db.aggregate_one('users', {'user_id': user_id}, update={'was_in_queue': user['was_in_queue']})

    changed_entries = queuebot.recalculate_queue(user['teacher'])
    new_place = 0
    for entry in changed_entries:
        if entry['user_id'] == user_id and entry['problem'] == user['problem'] and entry['teacher'] == user['teacher']:
            new_place = entry['place']
            break

    msg_text = 'Заявка создана!\nПреподаватель: {}\nЗадание: {}\nВаше место в очереди: {}\n'.format(
        user['teacher'], user['problem'], new_place)
    queuebot.bot.edit_message_text(chat_id=user_id, message_id=message_id, text=msg_text)

    queuebot.show_status(user_id)
    queuebot.send_messages_to_top_queue(changed_entries)
    queuebot.send_queue_updates(user['teacher'])


def callback_admin_clear_queue(update, context):  # NOT REFACTORED
    query = update.callback_query
    user_id = query.message.chat.id
    if db.aggregate_one('admins', {'user_id': user_id}) is None:
        update.message.reply_text('У вас недостаточно прав для очистки очереди')
        return

    db.aggregate_many('users', {'user_id': user_id}, update={'problem': '',
                                                             'teacher': '',
                                                             'was_in_queue': []})
    db.aggregate_many('queues', delete=True)
    query.message.reply_text('Очередь очищена')

    for teacher in TEACHERS:
        queuebot.send_queue_updates(teacher)


def callback_delete(update, context):
    user_id = update.message.chat.id
    user = db.aggregate_one('users', {'user_id': user_id})
    teacher = user['teacher']
    db.aggregate_many('queues', {'user_id': user_id, 'teacher': teacher, 'problem': user['problem']}, delete=True)
    queuebot.send_messages_to_top_queue(queuebot.recalculate_queue(teacher))
    queuebot.send_queue_updates(teacher)


def callback_inline_query(update, context):  # NOT REFACTORED
    results = []
    query: str = update.inline_query.query
    cache_time = 300
    is_personal = False
    if query.startswith('Начните писать фамилию: '):
        query = query.replace('Начните писать фамилию: ', '')
        regex = re.compile(re.escape(query), re.IGNORECASE)

        for student in db.aggregate_many('students', {'name': {'$regex': regex}}):
            s = f"{student['name']} {student['group']}"
            results.append(InlineQueryResultArticle(
                id=str(uuid4()),
                title=s,
                input_message_content=InputTextMessageContent("Студент: " + s)))
    elif query.startswith('Начните писать номер или название ДЗ: '):
        query = query.replace('Начните писать номер или название ДЗ: ', '').lower()
        for hw in db['homeworks'].find():
            if query in hw['name'].lower() in [s.lower() for s in lesson_settings['actual_problems']]:
                results.append(InlineQueryResultArticle(
                    id=str(uuid4()),
                    title=hw['name'],
                    input_message_content=InputTextMessageContent("ДЗ: " + hw['name'])))
    elif query.startswith('Начните писать название заявки: '):
        query = query.replace('Начните писать название заявки: ', '').lower()
        user_id = update.inline_query.from_user.id
        is_personal = True
        cache_time = 0
        for request in db.aggregate_many('queues', {'user_id': user_id}):
            if query in request['problem'].lower():
                results.append(InlineQueryResultArticle(
                    id=str(uuid4()),
                    title=request['problem'],
                    input_message_content=InputTextMessageContent("Отозвать: " + request['problem'])))
    update.inline_query.answer(results[:20], cache_time=cache_time, is_personal=is_personal)


def callback_reg_student(update, context):  # NOT REFACTORED
    user_id = update.message.chat.id
    text = update.message.text.replace('Студент: ', '')
    name, group = ' '.join(text.split()[:-1]), text.split()[-1]

    if not real_user(update):
        return

    if db.aggregate_one('users', {'user_id': user_id}) is not None:
        return

    if not db.aggregate_one('students', {'name': name}):
        queuebot.bot.send_message(chat_id=user_id, text='Произошла ошибка при выборе пользователя')
        return

    db.add_one('users', {'user_id': user_id, 'name': name, 'group': group,
                         'problem': '', 'teacher': '', 'was_in_queue': []})
    callback_start(update, context)


def callback_join_queue(update, context):  # NOT REFACTORED
    keyboard1 = [[InlineKeyboardButton('Георгий Корнеев', callback_data='teacher_chosen0')],
                 [InlineKeyboardButton('Юлия Савон', callback_data='teacher_chosen1')],
                 [InlineKeyboardButton('Андрей Плотников', callback_data='teacher_chosen2')]]

    user_id = update.message.chat.id

    if not real_user(update):
        return

    user = db.aggregate_one('users', {'user_id': user_id})

    if user is None:
        return

    hw = update.message.text.replace('ДЗ: ', '')

    if not db.aggregate_one('homeworks', {'name': hw}):
        queuebot.bot.send_message(chat_id=user_id, text='Произошла ошибка при выборе задачи')
        return

    db.aggregate_one('users', {'user_id': user_id}, update={'problem': hw})

    already_in_queue = db.aggregate_one('queues', {'user_id': user_id, 'problem': hw})

    if already_in_queue is not None:
        queuebot.bot.send_message(chat_id=user_id, text='Вы уже в очереди на это задание!')
    else:
        update.message.reply_text(
            f'Выбранная задача:\n{hw}\n\nНапоминаем, что сдавать две задачи подряд одному и '
            'тому же преподавателю не разрешается.\n\nВыберите преподавателя:',
            reply_markup=InlineKeyboardMarkup(keyboard1, resize_keyboard=True))


def callback_teacher_chosen(update, context):
    query = update.callback_query
    teacher_name = TEACHERS[int(query.data[-1])]
    user_id = query.message.chat.id
    db.aggregate_one('users', {'user_id': user_id}, update={'teacher': teacher_name})
    callback_add(update, context)


def callback_revoke(update, context):  # NOT REFACTORED
    if not real_user(update):
        return
    user_id = update.message.chat.id
    user = db.aggregate_one('users', {'user_id': user_id})
    if user is None:
        return

    problem = update.message.text.replace('Отозвать: ', '')

    entry = db.aggregate_one('queues', {'user_id': user_id, 'problem': problem})
    if not entry:
        queuebot.bot.send_message(chat_id=user_id, text='Вас нет в очереди на эту задачу!')
        return
    db.aggregate_one('users', {'user_id': user_id},
                     update={'teacher': entry['teacher'], 'problem': problem})
    callback_delete(update, context)
    queuebot.show_status(user_id)


def callback_start_broadcast_table(update, context):
    chat_id = update.message.chat.id
    if db.aggregate_one('chats_with_broadcast', {'chat_id': chat_id}) is None:
        db.add_one('chats_with_broadcast', {'chat_id': chat_id, 'messages_id': {}})
    for teacher in TEACHERS:
        queuebot.send_queue_updates(teacher)


def callback_stop_broadcast_table(update, context):
    chat_id = update.message.chat.id
    if db.aggregate_one('chats_with_broadcast', {'chat_id': chat_id}) is not None:
        db.aggregate_one('chats_with_broadcast', {'chat_id': chat_id}, delete=True)


def callback_admin(update, context):
    user_id = update.message.chat.id
    if db.aggregate_one('admins', {'user_id': user_id}) is None:
        update.message.reply_text('У вас недостаточно прав для этого действия')
        return
    admin_keyboard = [[InlineKeyboardButton('Очистить очередь', callback_data='admin_clear_queue'),
                       InlineKeyboardButton('Модерировать очередь', callback_data='admin_moderate_queue_s')]]

    update.message.reply_text('admin panel', reply_markup=InlineKeyboardMarkup(admin_keyboard, resize_keyboard=True))


def callback_admin_moderate_queue(update, context):  # NOT REFACTORED
    query = update.callback_query
    user_id = query.message.chat.id

    if db.aggregate_one('admins', {'user_id': user_id}) is None:
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
        short_teacher_name = ''.join(map(lambda x: x[0], teacher.split()[1::-1]))
        head_queue = db.aggregate_one('queues', {'teacher': teacher, 'place': 1})
        if head_queue:
            head_queue_name = db.aggregate_one('users', {'user_id': head_queue['user_id']})['name']
            head_queue_problem = head_queue['problem']
            text = f'На первом месте к {short_teacher_name}: {head_queue_name} ' \
                   f'\nна задачу {head_queue_problem}. Удалить?'
            cd = 'admin_moderate_queue_d_' + str(head_queue['user_id']) + '_' + str(head_queue['_id'])
            query.edit_message_text(text=text, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=InlineKeyboardMarkup(
                                        [[InlineKeyboardButton('удалить', callback_data=cd)]]))
    elif command_info[0] == 'd':
        command_info = command_info.split('_')
        head_queue = db.aggregate_one('queues',
                                      {'user_id': int(command_info[1]), '_id': bson.objectid.ObjectId(command_info[2])})
        if head_queue:
            print(head_queue)
            teacher = head_queue['teacher']
            db.aggregate_many('queues',
                              {'user_id': int(command_info[1]), '_id': bson.objectid.ObjectId(command_info[2])},
                              delete=True)
            queuebot.send_messages_to_top_queue(queuebot.recalculate_queue(teacher))
            queuebot.send_queue_updates(teacher)
            query.edit_message_text(text=f'Пользователь удален')
        else:
            queuebot.bot.send_message(text=f'Выбранный пользватель не найден')
