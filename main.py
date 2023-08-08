import os
from datetime import datetime
import pandas as pd
import telebot
from telebot import types
from config import TOKEN, replit

if replit:
    from background import keep_alive

bot = telebot.TeleBot(TOKEN)

TRAINING_DATA_COLUMNS = ['chat_id', 'date', 'group', 'exercise', 'run', 'weight', 'reps']
training_data = pd.DataFrame(columns=TRAINING_DATA_COLUMNS)
exercises = pd.read_csv('files/exercises.csv', sep=',')


def get_stats(chat_id):
    file_name = f'stats/{chat_id}_stats.csv'
    if os.path.exists(file_name):
        return pd.read_csv(file_name, sep=',')
    else:
        return pd.DataFrame(columns=TRAINING_DATA_COLUMNS)


def save_stats(chat_id, df):
    file_name = f'stats/{chat_id}_stats.csv'
    df.to_csv(file_name, index=False, sep=',')


def ask_question(chat_id, question, next_field, keyboard_type):
    bot.send_message(chat_id, question, reply_markup=keyboard_type)
    bot.register_next_step_handler_by_chat_id(chat_id, next_field)


def choose_group(message):
    chat_id = message.chat.id
    group = message.text
    training_data.loc[chat_id, ['chat_id', 'date', 'group']] = [chat_id, (datetime.now()).date(), group]
    ask_question(chat_id, "📋Выбери упражнение или впиши новое",
                 lambda msg: choose_exercise(msg, group), make_keyboard_exc(group))


def choose_exercise(message, group):
    chat_id = message.chat.id
    exercise = message.text
    df = get_stats(chat_id)
    df['date'] = pd.to_datetime(df['date'])
    selected_exercise = df[df['exercise'] == exercise]

    days_of_week_russian = {
        'Monday': 'пн',
        'Tuesday': 'вт',
        'Wednesday': 'ср',
        'Thursday': 'чт',
        'Friday': 'пт',
        'Saturday': 'сб',
        'Sunday': 'вс'
    }

    last_date = selected_exercise['date'].max()
    today = pd.Timestamp.today().normalize()  # Сегодняшняя дата без времени
    if last_date == today:
        last_date = selected_exercise[selected_exercise['date'] < today]['date'].max()
    result = selected_exercise[selected_exercise['date'] == last_date]
    if not result.empty:
        day_of_week = days_of_week_russian[last_date.strftime('%A')]
        message_rep = f"Подходы за {last_date.strftime('%d.%m')} ({day_of_week}):\n\n"
        for _i, row in result.iterrows():
            message_rep += f"{row['weight']:g} x {row['reps']:g}\n"
        sent_message = bot.send_message(chat_id, message_rep)
        bot.pin_chat_message(chat_id, sent_message.message_id)

    if exercise not in exercises['exercise'].values:
        exercises.loc[len(exercises)] = [group, exercise]
        exercises.to_csv('files/exercises.csv', index=False, sep=',')
    training_data.loc[chat_id, 'exercise'] = exercise
    ask_question(chat_id, "🏋🏻‍♂️Введи вес", choose_weight, make_keyboard_nums())


def choose_weight(message, prev_reps='', run=0):
    chat_id = message.chat.id

    try:
        weight = float(message.text.replace(',', '.'))
    except ValueError:
        weight = 0

    training_data.loc[chat_id, 'weight'] = weight
    run += 1
    training_data.loc[chat_id, 'run'] = run
    prev_reps = prev_reps + f'Подход {str(run)}: {weight:g}x'
    ask_question(chat_id, "🔢 Введи количество повторений",
                 lambda msg: choose_reps(msg, run=run, prev_reps=prev_reps), make_keyboard_nums())


def choose_reps(message, run, prev_reps):
    chat_id = message.chat.id
    df = get_stats(chat_id)
    try:
        reps = float(message.text.replace(',', '.'))
    except ValueError:
        reps = 0

    training_data.loc[chat_id, 'reps'] = reps
    df = pd.concat([df, training_data], ignore_index=False)
    save_stats(chat_id, df)
    prev_reps = prev_reps + f'{reps:g}\n'
    ask_question(chat_id, f"{prev_reps}\nПродолжаем?",
                 lambda msg: save_more_sets(msg, run=run, prev_reps=prev_reps), make_keyboard_choose())


def save_more_sets(message, run, prev_reps):
    chat_id = message.chat.id

    if message.text == '💪Да':
        ask_question(chat_id, "🏋🏻‍♂️Введи вес",
                     lambda msg: choose_weight(msg, prev_reps=prev_reps, run=run), make_keyboard_nums())
    else:
        try:
            bot.unpin_chat_message(chat_id)
        except Exception as e:
            print(f"Ошибка: {e}")
        finish_training(message)


def finish_training(message):
    bot.send_message(message.chat.id, "✅Запись подходов завершена\n\n"
                                      "Продолжить тренировку — /training\n\n",
                     reply_markup=hide_keyboard())


@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Начать тренировку — /training",
                     reply_markup=hide_keyboard())
    training_data.loc[chat_id, :] = ''
    get_stats(chat_id)


@bot.message_handler(commands=['training'])
def start_training(message):
    chat_id = message.chat.id
    ask_question(chat_id, "💪Выбери группу мышц", choose_group, make_keyboard_groups())


@bot.message_handler(commands=['stats'])
def show_stats(message):
    chat_id = message.chat.id
    df = get_stats(chat_id)
    bot.send_message(chat_id, "Вот история тренировок")
    data = df.to_string(index=False)
    bot.send_message(chat_id, data)


@bot.message_handler(commands=['send'])
def send_files(message):
    files = [f'stats/{message.chat.id}_stats.csv']
    for file in files:
        bot.send_document(message.chat.id, open(file, 'rb'))
    start(message)


@bot.message_handler(commands=['card'])
def send_card(message):
    bot.send_photo(message.chat.id, open('files/card.png', 'rb'))
    start(message)


def make_keyboard_groups():
    uniques = exercises['group'].unique().tolist()
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for n in range(0, len(uniques), 2):
        keyboard.add(*uniques[n:n + 2])
    return keyboard


def make_keyboard_exc(group):
    uniques = exercises.loc[exercises['group'] == group, 'exercise'].tolist()
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for n in range(0, len(uniques), 2):
        keyboard.add(*uniques[n:n + 2])
    return keyboard


def make_keyboard_nums():
    keyboard = types.ReplyKeyboardMarkup(row_width=6, resize_keyboard=True)
    nums = ['0', '1', '2', '3', '4',
            '5', '6', '7.5', '8', '9',
            '10', '11', '12', '15', '18',
            '20', '23', '25', '30', '35',
            '40', '45', '50', '55', '60',
            '65', '70', '75', '80', '85']
    keyboard.add(*nums)
    return keyboard


def make_keyboard_choose():
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add("💪Да", "🙅🏻‍♂️Нет, хватит")
    return keyboard


def hide_keyboard():
    hide_markup = types.ReplyKeyboardRemove()
    return hide_markup


@bot.message_handler(commands=['drop_stat'])
def drop_stat(message):
    df = get_stats(message.chat.id)
    df = df.drop(df.index[-1])
    save_stats(message.chat.id, df)
    bot.send_message(message.chat.id, '✖️Последний подход удален')
    start(message)


@bot.message_handler(commands=['drop_ex'])
def drop_ex(message):
    df = exercises
    df = df.drop(df.index[-1])
    df.to_csv('files/exercises.csv', index=False)
    bot.send_message(message.chat.id, '✖️Удалено последнее упражнение из списка')
    start(message)


if replit:
    keep_alive()

bot.infinity_polling(none_stop=True)
