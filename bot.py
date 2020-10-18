from collections import deque
from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, \
    InputTextMessageContent, ParseMode, CallbackQuery
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, InlineQueryHandler, CallbackQueryHandler
from pymongo.collection import Collection
import pymongo

queue = deque()


def start(update, context):
    user_id = update.message.chat.id
    reply_keyboard = [[InlineKeyboardButton('Встать в очередь', callback_data='add')],
                      [InlineKeyboardButton('Уйти из очереди', callback_data='delete')],
                      [InlineKeyboardButton('Мое место в очереди', callback_data='check')],
                      [InlineKeyboardButton('Выбрать задачу', callback_data='choose_problem')]]

    keyboard2 = [[InlineKeyboardButton('Ввести данные',
                                       switch_inline_query_current_chat='Начните писать фамилию: ')]]

    if users.find_one({'user_id': user_id}) is None:
        update.message.reply_text(f'Здравствуйте! Введите, пожалуйста, ваши настоящие имя, фамилию и группу. '
                                  f'Это необходимо лишь в первый раз.', reply_markup=InlineKeyboardMarkup(keyboard2))
    else:
        name = users.find_one({'user_id': user_id})['name']
        update.message.reply_text(f'Здравствуйте! Что вы хотите сделать, {name}?',
                                  reply_markup=InlineKeyboardMarkup(reply_keyboard, resize_keyboard=True))


def add(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    if user_id in queue:
        query.answer('Да ты охуел? Ты уже в очереди. Иди в жопу')
    else:
        queue.append(user_id)
        query.answer('Хорошо, теперь ты в очереди.')


def delete(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    if user_id not in queue:
        query.answer('Да ты охуел? Тебя нет в очереди. Иди в жопу')
    else:
        for i in range(len(queue)):
            if queue[i] == user_id:
                del queue[i]
                break
        query.answer('Хорошо, теперь тебя нет в очереди.')


def check(update, context):
    query = update.callback_query
    user_id = query.message.chat.id
    if user_id not in queue:
        query.message.reply_text('Твое место у параши, а в очереди тебя нет. Иди в жопу')
        query.answer('Ответил')
    else:
        place = -1
        for i in range(len(queue)):
            if queue[i] == user_id:
                place = i + 1
                break
        query.message.reply_text(f'Твое место в очереди: {place}')
        query.answer('Ответил')


def choose_problem(update, context):
    pass


def find_student(update, context):
    results = []
    query: str = update.inline_query.query
    query = query.replace('Начните писать фамилию: ', '').lower()
    for student in students.find():
        if query in student['name'].lower():
            s = f"{student['name']} {student['group']}"
            results.append(InlineQueryResultArticle(
                            id=str(uuid4()),
                            title=s,
                            input_message_content=InputTextMessageContent("Студент: " + s)))
    update.inline_query.answer(results[:20])


def add_student(update, context):
    user_id = update.message.chat.id
    text = update.message.text.replace('Студент: ', '')
    name, group = ' '.join(text.split()[:-1]), text.split()[-1]
    if users.find_one({'user_id': user_id}) is not None:
        return
    users.insert_one({'user_id': user_id, 'name': name, 'group': group, 'place': -1})


if __name__ == '__main__':
    mongo = pymongo.MongoClient('mongodb://localhost:27017/')
    db = mongo['queue']
    users: Collection = db['users']
    students: Collection = db['students']

    updater = Updater(open('token', 'r').read(), use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("restart", start))

    # on callbacks
    dp.add_handler(CallbackQueryHandler(callback=add, pattern='^add$'))
    dp.add_handler(CallbackQueryHandler(callback=delete, pattern='^delete$'))
    dp.add_handler(CallbackQueryHandler(callback=check, pattern='^check$'))
    dp.add_handler(CallbackQueryHandler(callback=choose_problem, pattern='^choose_problem$'))

    dp.add_handler(MessageHandler(Filters.regex('^Студент: .*$'), add_student))
    dp.add_handler(InlineQueryHandler(find_student))

    # Start the Bot
    updater.start_polling()

    updater.idle()
