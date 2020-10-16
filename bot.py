from collections import deque


from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, \
    InputTextMessageContent, ParseMode, CallbackQuery
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, InlineQueryHandler, CallbackQueryHandler


queue = deque()


def start(update, context):
    user_id = update.message.chat.id
    reply_keyboard = [[InlineKeyboardButton('Встать в очередь', callback_data='add')],
                      [InlineKeyboardButton('Уйти из очереди', callback_data='delete')],
                      [InlineKeyboardButton('Мое место в очереди', callback_data='check')]]
    update.message.reply_text(f'Здравствуйте! Пожалуйста, пососите, уважаемый user{user_id}, '
                              f'потому что этот бот еще ничего не умеет',
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


if __name__ == '__main__':
    updater = Updater(open('token', 'r').read(), use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("restart", start))

    # # on callbacks
    dp.add_handler(CallbackQueryHandler(callback=add, pattern='^add$'))
    dp.add_handler(CallbackQueryHandler(callback=delete, pattern='^delete$'))
    dp.add_handler(CallbackQueryHandler(callback=check, pattern='^check$'))

    # Start the Bot
    updater.start_polling()

    updater.idle()
