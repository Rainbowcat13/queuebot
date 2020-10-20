from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, \
    InputTextMessageContent, ParseMode, CallbackQuery
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, InlineQueryHandler, CallbackQueryHandler
from pymongo.collection import Collection
import pymongo

from start import update_homeworks

TELEGRAMTOKEN: str = open('config/token', 'r').read()
MONGODB_CLIENT: str = open('config/mongo', 'r').read()
TEACHERS = ['Корнеев Георгий Александрович', 'Савон Юлия Константиновна', 'Плотников Андрей Игоревич']
START_KEYBOARD = [[InlineKeyboardButton('Выбрать задачу',
                                        switch_inline_query_current_chat='Начните писать номер или название ДЗ: ')],
                  [InlineKeyboardButton('Выбрать преподавателя', callback_data='choose_teacher')],
                  [InlineKeyboardButton('Встать в очередь', callback_data='add')],
                  [InlineKeyboardButton('Уйти из очереди', callback_data='delete')],
                  [InlineKeyboardButton('Узнать место в очереди', callback_data='check')]
                  ]


def start(update, context):
    user_id = update.message.chat.id
    keyboard2 = [[InlineKeyboardButton('Ввести данные',
                                       switch_inline_query_current_chat='Начните писать фамилию: ')]]

    if users.find_one({'user_id': user_id}) is None:
        update.message.reply_text(f'Здравствуйте! Введите, пожалуйста, ваши настоящие имя, фамилию и группу. '
                                  f'Это необходимо лишь в первый раз.',
                                  reply_markup=InlineKeyboardMarkup(keyboard2, resize_keyboard=True))
    else:
        name = users.find_one({'user_id': user_id})['name']
        update.message.reply_text(f'Вы — {name}. Что хотите сделать?',
                                  reply_markup=InlineKeyboardMarkup(START_KEYBOARD, resize_keyboard=True))


def add(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    user = users.find_one({'user_id': user_id})
    if user['place']:
        query.answer('Вы уже в очереди!')
    elif user['problem']:
        if not user['teacher']:
            bot.send_message(chat_id=user_id, text=f'Вы не выбрали преподавателя, которому хотите сдать!')
            return
        new_place = users.find({'teacher': user['teacher']}).sort([('place', pymongo.ASCENDING)]).limit(1)
        new_place = list(new_place)[0]['place'] + 1
        users.find_one_and_update({'user_id': user_id}, {'$set': {'place': new_place}})

        if new_place == 1:
            bot.send_message(chat_id=user_id, text=f'Ваше место в очереди — {new_place}. Идите сдавать. Удачи!')
        elif new_place <= 3:
            bot.send_message(chat_id=user_id, text=f'Ваше место в очереди — {new_place}. Приготовьтесь!')
        query.answer('Хорошо, теперь вы в очереди.')
    else:
        bot.send_message(chat_id=user_id, text=f'Вы не выбрали задачу, которую хотите сдать!')


def clear(update, context):
    user_id = update.message.chat.id
    if admins.find_one({'user_id': user_id}) is None:
        update.message.reply_text('У вас недостаточно прав для выполнения операции очистки.')
        return
    for user in users.find():
        users.find_one_and_update({'user_id': user['user_id']}, {'$set': {'place': 0, 'problem': '', 'teacher': ''}})
    update.message.reply_text('Очередь очищена')


def delete(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    user = users.find_one({'user_id': user_id})
    if not user['place']:
        query.answer('Вас нет в очереди!')
    elif user['problem']:
        old_place = user['place']
        users.find_one_and_update({'user_id': user_id}, {'$set': {'place': 0}})
        teacher = user['teacher']
        size = users.find({'teacher': teacher}).count() - users.find({'teacher': teacher, 'place': 0}).count()
        for p in range(old_place + 1, size + 2):
            users.find_one_and_update({'place': p, 'teacher': teacher}, {'$set': {'place': p - 1}})
        print(size + 1)
        for p in range(1, min(4, size + 1)):
            user_id = users.find_one({'place': p, 'teacher': teacher})['user_id']
            text = f'Ваше место в очереди — {p}. '
            if p == 1:
                text += 'Идите сдавать. Удачи!'
            else:
                text += 'Приготовьтесь!'
            bot.send_message(chat_id=user_id, text=text)
        query.answer('Хорошо, теперь вас нет в очереди.')
    else:
        bot.send_message(chat_id=user_id, text=f'Вы не выбрали задачу, которую хотите сдавать')


def check(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    user = users.find_one({'user_id': user_id})
    if not user['place']:
        query.message.reply_text('Вас нет в очереди!')
    else:
        query.message.reply_text(f'Ваше место в очереди: {user["place"]}')
    query.answer('Ответ в сообщении')


def inline_query(update, context):
    results = []
    query: str = update.inline_query.query
    if query.startswith('Начните писать фамилию: '):
        query = query.replace('Начните писать фамилию: ', '').lower()
        for student in students.find():
            if query in student['name'].lower():
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
    update.inline_query.answer(results[:20])


def add_student(update, context):
    user_id = update.message.chat.id
    text = update.message.text.replace('Студент: ', '')
    name, group = ' '.join(text.split()[:-1]), text.split()[-1]
    if users.find_one({'user_id': user_id}) is not None:
        return
    users.insert_one({'user_id': user_id, 'name': name, 'group': group, 'problem': '', 'teacher': '', 'place': 0})
    start(update, context)


def change_problem(update, context):
    user_id = update.message.chat.id
    hw = update.message.text.replace('ДЗ: ', '')
    users.find_one_and_update({'user_id': user_id}, {'$set': {'problem': hw}})
    start(update, context)


def choose_teacher(update, context):
    keyboard = [[InlineKeyboardButton('Георгий Корнеев', callback_data='teacher_chosen0')],
                [InlineKeyboardButton('Юлия Савон', callback_data='teacher_chosen1')],
                [InlineKeyboardButton('Андрей Плотников', callback_data='teacher_chosen2')]]
    query = update.callback_query
    message_id = query.message.message_id
    user_id = query.message.chat.id
    bot.edit_message_text(chat_id=user_id, message_id=message_id, text='Выберите преподавателя: ',
                          reply_markup=InlineKeyboardMarkup(keyboard, resize_keyboard=True))


def teacher_chosen(update, context):
    query = update.callback_query
    teacher_name = TEACHERS[int(query.data[-1])]
    user_id = query.message.chat.id
    users.find_one_and_update({'user_id': user_id}, {'$set': {'teacher': teacher_name}})
    name = users.find_one({'user_id': user_id})['name']
    bot.edit_message_text(chat_id=user_id, message_id=query.message.message_id,
                          text=f'Вы — {name}. Что хотите сделать?',
                          reply_markup=InlineKeyboardMarkup(START_KEYBOARD, resize_keyboard=True))
    query.answer('Преподаватель выбран')


if __name__ == '__main__':
    update_homeworks()
    mongo = pymongo.MongoClient(MONGODB_CLIENT)
    db = mongo['queue']
    users: Collection = db['users']
    students: Collection = db['students']
    homeworks: Collection = db['homeworks']
    admins: Collection = db['admins']

    updater = Updater(TELEGRAMTOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    bot = updater.bot

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("restart", start))
    dp.add_handler(CommandHandler("clear_queue", clear))

    # on callbacks
    dp.add_handler(CallbackQueryHandler(callback=add, pattern='^add$'))
    dp.add_handler(CallbackQueryHandler(callback=delete, pattern='^delete$'))
    dp.add_handler(CallbackQueryHandler(callback=check, pattern='^check$'))
    dp.add_handler(CallbackQueryHandler(callback=choose_teacher, pattern='^choose_teacher$'))
    dp.add_handler(CallbackQueryHandler(callback=teacher_chosen, pattern='^teacher_chosen.*$'))

    # messages and inline
    dp.add_handler(MessageHandler(Filters.regex('^Студент: .*$'), add_student))
    dp.add_handler(MessageHandler(Filters.regex('^ДЗ: .*$'), change_problem))
    dp.add_handler(InlineQueryHandler(inline_query))

    # Start the Bot
    updater.start_polling()

    updater.idle()
