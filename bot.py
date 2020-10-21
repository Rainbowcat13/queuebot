from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, \
    InputTextMessageContent, ParseMode, CallbackQuery
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, InlineQueryHandler, CallbackQueryHandler
from pymongo.collection import Collection
import pymongo
import re

from start import update_homeworks

TELEGRAMTOKEN: str = open('config/token', 'r').read()
MONGODB_CLIENT: str = open('config/mongo', 'r').read()
TEACHERS = ['Корнеев Георгий Александрович', 'Савон Юлия Константиновна', 'Плотников Андрей Игоревич']
START_KEYBOARD = [[InlineKeyboardButton('Встать в очередь',
                                           switch_inline_query_current_chat='Начните писать номер или название ДЗ: ')],
                  [InlineKeyboardButton('Отозвать заявку',
                                           switch_inline_query_current_chat='Начните писать название заявки: ')]
                  ]


def start(update, context):
    user_id = update.message.chat.id
    login_keyboard = [[InlineKeyboardButton('Ввести данные',
                                       switch_inline_query_current_chat='Начните писать фамилию: ')]]

    if users.find_one({'user_id': user_id}) is None:
        update.message.reply_text(f'Здравствуйте! Введите, пожалуйста, ваши настоящие имя, фамилию и группу. '
                                  f'Это необходимо лишь в первый раз.',
                                  reply_markup=InlineKeyboardMarkup(login_keyboard, resize_keyboard=True))
    else:
        show_status(user_id)


def getElapsedTime(): # todo: return real time
    return 1337 % 55  # is negative time allowed?
    

def show_status(user_id):
    user_in_queues = queues.find({'user_id': user_id})
    
    shortName = ' '.join(users.find_one({'user_id': user_id})['name'].split()[:2])
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


def logout(update, context):
    user_id = update.message.chat.id
    if users.find_one({'user_id': user_id}):
        users.delete_one({'user_id': user_id})
        update.message.reply_text('Деавторизация успешна')


def add(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    user = users.find_one({'user_id': user_id})
    
    already_in_queue = queues.find_one({'user_id': user_id,
                                        'teacher': users.find_one({'user_id': user_id})['teacher']})
    if already_in_queue is not None:
        query.answer('Вы уже в очереди!')
        return
    
    new_place = queues.find({'teacher': user['teacher'],
                             'first_time': not user['was_in_queue']}).sort([('place', pymongo.ASCENDING)]).limit(1)
    new_place = list(new_place)
    
    if new_place:
        new_place = new_place[0]['place'] + 1
    else:
        new_place = 1
        
    if not user['was_in_queue']:
        size = queues.find({'teacher': user['teacher']}).count()
        for p in range(size, new_place - 1, -1):
            queues.find_one_and_update({'place': p, 'teacher': user['teacher']}, {'$set': {'place': p + 1}})
            
    queues.insert_one({'user_id': user_id, 'problem': user['problem'],
                       'teacher': user['teacher'], 'place': new_place,
                       'first_time': not user['was_in_queue']})
    
    users.find_one_and_update({'user_id': user_id}, {'$set': {'was_in_queue': True}})

    query = update.callback_query
    message_id = query.message.message_id
    bot.edit_message_text(chat_id=user_id, message_id=message_id,
                          text=f'Заявка создана!\nВаше место в очереди - {new_place}\n\nЗадача:\n{user["problem"]}\n\nПреподаватель:\n{user["teacher"]}')
    
    if new_place == 1:
        bot.send_message(chat_id=user_id, text='Идите сдавать. Удачи!')
    elif new_place <= 3:
        bot.send_message(chat_id=user_id, text='Приготовьтесь!')
        
    show_status(user_id)


def clear_queue(update, context):
    user_id = update.message.chat.id
    if admins.find_one({'user_id': user_id}) is None:
        update.message.reply_text('У вас недостаточно прав для очистки очереди')
        return
    for user in users.find():
        users.find_one_and_update({'user_id': user['user_id']}, {'$set': {'problem': '', 'teacher': '',
                                                                          'was_in_queue': False}})
    queues.remove()
    update.message.reply_text('Очередь очищена')


def delete(update, context):
    query = update.callback_query
    user_id = update.message.chat.id
    user = users.find_one({'user_id': user_id})
    teacher = user['teacher']
    
    queue_place = queues.find_one({'user_id': user_id, 'teacher': teacher})
    old_place = queue_place['place']
    
    queues.remove({'user_id': user_id, 'teacher': teacher})
    size = queues.find({'teacher': teacher}).count()
    
    for p in range(old_place + 1, size + 2):
        queues.find_one_and_update({'place': p, 'teacher': teacher}, {'$set': {'place': p - 1}})
        
    #print(size + 1)
    
    for p in range(1, min(4, size + 1)):
        user_id = queues.find_one({'place': p, 'teacher': teacher})['user_id']
        text = f'Ваше место в очереди — {p}. Преподаватель {teacher}. '
        if p == 1:
            text += 'Идите сдавать. Удачи!'
        else:
            text += 'Приготовьтесь!'
        bot.send_message(chat_id=user_id, text=text)


def inline_query(update, context):
    results = []
    query: str = update.inline_query.query
    cache_time=300
    is_personal = False
    if query.startswith('Начните писать фамилию: '):
        query = query.replace('Начните писать фамилию: ', '')
        regex = re.compile(re.escape(query), re.IGNORECASE)
            
        for student in students.find({'name': {'$regex': regex}}):
            s = f"{student['name']} {student['group']}"
            results.append(InlineQueryResultArticle(
                id=str(uuid4()),
                title=s,
                input_message_content=InputTextMessageContent("Студент: " + s)))
    elif query.startswith('Начните писать номер или название ДЗ: '):
        query = query.replace('Начните писать номер или название ДЗ: ', '').lower()
        for hw in homeworks.find():
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
        for request in queues.find({'user_id': user_id}):
            if query in request['problem'].lower():
                results.append(InlineQueryResultArticle(
                    id=str(uuid4()),
                    title=request['problem'],
                    input_message_content=InputTextMessageContent("Отозвать: " + request['problem'])))
    update.inline_query.answer(results[:20], cache_time=cache_time, is_personal=is_personal)


def add_student(update, context):
    user_id = update.message.chat.id
    text = update.message.text.replace('Студент: ', '')
    name, group = ' '.join(text.split()[:-1]), text.split()[-1]
    if users.find_one({'user_id': user_id}) is not None:
        return
    users.insert_one({'user_id': user_id, 'name': name, 'group': group,
                      'problem': '', 'teacher': '', 'was_in_queue': False})
    start(update, context)


def join_queue(update, context):
    keyboard1 = [[InlineKeyboardButton('Георгий Корнеев', callback_data='teacher_chosen0')],
                [InlineKeyboardButton('Юлия Савон', callback_data='teacher_chosen1')],
                [InlineKeyboardButton('Андрей Плотников', callback_data='teacher_chosen2')]]

    query = update.callback_query
    user_id = update.message.chat.id
    user = users.find_one({'user_id': user_id})
    
    hw = update.message.text.replace('ДЗ: ', '')
    users.find_one_and_update({'user_id': user_id}, {'$set': {'problem': hw}})
    
    update.message.reply_text(f'Текущая задача:\n{hw}\n\nВыберите преподавателя:',
                                  reply_markup=InlineKeyboardMarkup(keyboard1, resize_keyboard=True))


def teacher_chosen(update, context):
    query = update.callback_query
    teacher_name = TEACHERS[int(query.data[-1])]
    user_id = query.message.chat.id
    users.find_one_and_update({'user_id': user_id}, {'$set': {'teacher': teacher_name}})
    add(update, context)


def revoke(update, context):
    query = update.callback_query
    user_id = update.message.chat.id
    problem = update.message.text.replace('Отозвать: ', '')
    
    t = queues.find_one({'user_id': user_id, 'problem': problem})
    
    if not t:
        bot.send_message(chat_id=user_id, text='Ошибка!')
        return
    
    users.find_one_and_update({'user_id': user_id}, {'$set': {'teacher': t['teacher'], 'problem': problem}})
    delete(update, context)
    show_status(user_id)


if __name__ == '__main__':
    update_homeworks()
    mongo = pymongo.MongoClient(MONGODB_CLIENT)
    db = mongo['queue']
    users: Collection = db['users']
    students: Collection = db['students']
    homeworks: Collection = db['homeworks']
    admins: Collection = db['admins']
    queues: Collection = db['queues']
    updater = Updater(TELEGRAMTOKEN, use_context=True)
    
    # debug purposes
    # queues.delete_many({})

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    bot = updater.bot

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("restart", start))
    dp.add_handler(CommandHandler("logout", logout))
    
    # priveleged commands
    dp.add_handler(CommandHandler("clear_queue", clear_queue))

    # on callbacks
    dp.add_handler(CallbackQueryHandler(callback=add, pattern='^add$'))
    dp.add_handler(CallbackQueryHandler(callback=delete, pattern='^delete$'))
    dp.add_handler(CallbackQueryHandler(callback=teacher_chosen, pattern='^teacher_chosen.*$'))

    # messages and inline
    dp.add_handler(MessageHandler(Filters.regex('^Студент: .*$'), add_student))
    dp.add_handler(MessageHandler(Filters.regex('^ДЗ: .*$'), join_queue))
    dp.add_handler(MessageHandler(Filters.regex('^Отозвать: .*$'), revoke))
    dp.add_handler(InlineQueryHandler(inline_query))

    # Start the Bot
    updater.start_polling()
    print("Start polling")

    updater.idle()
