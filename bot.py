import bson
import math
import re

from time import strftime, time
from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, \
    InputTextMessageContent, ParseMode, CallbackQuery
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, InlineQueryHandler, CallbackQueryHandler

from callbacks import *
from db import DBConnector
from lesson_settings import lesson_settings


class QueueBot:
    TOKEN: str = open('config/token', 'r').read()
    START_KEYBOARD = [[InlineKeyboardButton('Обновить',
                                            callback_data='callback_refresh_statistics')],
                      [InlineKeyboardButton('Встать в очередь',
                                            switch_inline_query_current_chat='Начните писать номер или название ДЗ: ')],
                      [InlineKeyboardButton('Отозвать заявку',
                                            switch_inline_query_current_chat='Начните писать название заявки: ')]
                      ]

    def __init__(self):
        self.db: DBConnector = DBConnector()
        self.updater = Updater(QueueBot.TOKEN, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.bot = self.updater.bot

    def _set_admins(self):
        self.db.add_many('admins', {'user_id': [316671439, 487574745, 333728707]})

    def _register_handlers(self):
        # command handlers
        #     commands for all users
        self.dispatcher.add_handler(CommandHandler("start", callback_start))
        self.dispatcher.add_handler(CommandHandler("restart", callback_start))
        self.dispatcher.add_handler(CommandHandler("logout", callback_logout))

        #     commands for admins
        self.dispatcher.add_handler(CommandHandler("admin", callback_admin))
        self.dispatcher.add_handler(CommandHandler("start_broadcast_table", callback_start_broadcast_table))
        self.dispatcher.add_handler(CommandHandler("stop_broadcast_table", callback_stop_broadcast_table))

        # callback handlers
        #     usual callbacks
        self.dispatcher.add_handler(CallbackQueryHandler(callback=callback_add, pattern='^add$'))
        self.dispatcher.add_handler(CallbackQueryHandler(callback=callback_delete, pattern='^delete$'))
        self.dispatcher.add_handler(CallbackQueryHandler(callback=callback_teacher_chosen,
                                                         pattern='^teacher_chosen.*$'))
        self.dispatcher.add_handler(CallbackQueryHandler(callback=callback_refresh_statistics,
                                                         pattern='^self.callback_refresh_statistics$'))

        #     callbacks from admin panel
        self.dispatcher.add_handler(CallbackQueryHandler(callback=callback_admin_clear_queue,
                                                         pattern='^admin_clear_queue$'))
        self.dispatcher.add_handler(CallbackQueryHandler(callback=callback_admin_moderate_queue,
                                                         pattern='^admin_moderate_queue.*$'))
        # message handlers
        self.dispatcher.add_handler(MessageHandler(Filters.regex('^Студент: .*$'), callback_reg_student))
        self.dispatcher.add_handler(MessageHandler(Filters.regex('^ДЗ: .*$'), callback_join_queue))
        self.dispatcher.add_handler(MessageHandler(Filters.regex('^Отозвать: .*$'), callback_revoke))

        # inline handlers !INLINE QUERIES MUST BE ENABLED FOR YOUR BOT!
        # (you can enable them in https://t.me/BotFather by /setinline command)
        self.dispatcher.add_handler(InlineQueryHandler(callback_inline_query))

    def show_status(self, user_id):
        self.bot.send_message(chat_id=user_id, text=self.get_status(user_id),
                              reply_markup=InlineKeyboardMarkup(QueueBot.START_KEYBOARD, resize_keyboard=True))

    def get_status(self, user_id):  # NOT REFACTORED
        user_in_queues = self.db.aggregate_many('queues', {'user_id': user_id})

        short_name = ' '.join(db.aggregate_one('users', {'user_id': user_id})['name'].split()[:2])
        text = f'Студент: {short_name}\nВремя до конца практики: {get_elapsed_time()}\n\n'

        if not user_in_queues.count():
            text += 'У Вас нет активных заявок'
        else:
            text += 'Активные заявки:\n'
            for u in user_in_queues:
                short_teacher_name = ''.join(map(lambda x: x[0], u["teacher"].split()[1::-1]))
                text += f'{u["problem"]} — {u["place"]} место ({short_teacher_name})\n'
        return text

    def recalculate_queue(self, teacher):  # NOT REFACTORED
        priority = lesson_settings['problems_priority']
        old_queue = self.db.aggregate_many('queues', {'teacher': teacher})
        if old_queue is not None:
            old_places = {}
            new_places = []
            with_changes = []
            old_queue = list(old_queue)
            old_queue.sort(key=lambda x: (  # Here must be good comparator with lots of priorities
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
                    self.db.aggregate_one('queues', {'_id': bson.objectid.ObjectId(n_pl['_id'])}, update={'place': i})
            return with_changes
        return []

    def send_queue_updates(self, teacher):  # NOT REFACTORED
        if teacher in TEACHERS:
            db['queues'].create_index('place')
            full_queue = db.aggregate_many('queues', {'teacher': teacher, 'place': {'$gt': 0}}).sort('place')
            text = '*' + teacher + '*\n'
            free_queue = True
            for st in full_queue:
                free_queue = False
                user_name = db.aggregate_one('users', {'user_id': st['user_id']})['name']
                text += str(st['place']) + ': ' + user_name + '\n'
            if free_queue:
                text += '_в очереди никого нет_\n'
            text += 'Время обновления: ' + strftime("%H:%M:%S")
            for chat in db['chats_with_broadcast'].find():
                messages_ids = chat['messages_id']
                try:
                    if teacher not in messages_ids:
                        msg = queuebot.bot.send_message(chat_id=chat['chat_id'], parse_mode=ParseMode.MARKDOWN_V2,
                                                        text=text)
                        messages_ids[teacher] = msg['message_id']
                        db.aggregate_one('chats_with_broadcast', {'chat_id': chat['chat_id']},
                                         {'$set': {'messages_id': messages_ids}})
                    else:
                        queuebot.bot.edit_message_text(chat_id=chat['chat_id'], message_id=messages_ids[teacher],
                                                       parse_mode=ParseMode.MARKDOWN, text=text)
                except:
                    print(f'Can not send queue updates in chat {chat}')

    def run(self):
        self._set_admins()
        self._register_handlers()

        self.updater.start_polling()
        print("Start polling")

        self.updater.idle()


queuebot = QueueBot()
queuebot.run()
