import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    User
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
import random
import logging
import asyncio
from tasks import tasks

# --- GLOBALS --- #
game_state = False  # True - currently going, false - passive
night_state = False # True - night, false - day
registration_state = False  # True - currently going, false - passive
players: dict[int, "Player"] = dict()  # Key: ID of player, value: object of Player class
quantity = 0
roles: dict[str, int | list[int]] = dict()  # Key: role, value: ID of player
reg_message_id: None | int = None
game_chat_id: None | int = None
day_count = 0

# --- CONSTANTS --- #
from bot_token import BOT_TOKEN

REGISTRATION_TIME = 60  # In seconds
NIGHT_TIME = 60 # In seconds
DAY_TIME = 420 # In seconds
VOTING_TIME = 60 # In seconds
REQUIRED_PLAYERS = 4
LEADERS_INNOCENTS = ['detective']
SPECIAL_INNOCENTS = ['doctor', 'prostitute']
SPECIAL_MAFIOSI = ['godfather']
OTHERS = ['maniac']
REQUEST_MAX_TRIES = 3
'''
    QUANTITY_OF_ROLES
    It is a dictionary, keys of which are a number of players, the values are the quantities of roles:
    each value is a string, each of digits in which represents the quantity of each type of character, accordingly:
        1. Leaders of innocents. There are randomly selected from LEADERS_INNOCENTS.
        2. Simple innocents
        3. Special innocents. Randomly selected from SPECIAL_INNOCENTS
        4. Simple mafiosi
        5. Special mafiosi. Randomly selected from SPECIAL_MAFIOSI
        6. Individuals, such as maniac. Randomly selected from  OTHERS 
'''
QUANTITY_OF_ROLES = {1: '1 0 0 0 0 0', 2: '1 0 0 1 0 0', 3: '1 1 0 1 0 0', 4: '1 2 0 1 0 0', 5: '1 2 0 2 0 0',
                     6: '1 3 0 2 0 0', 7: '1 4 0 2 0 0', 8: '1 5 0 2 0 0', 9: '1 6 0 2 0 0', 10: '1 6 0 3 0 0',
                     11: '1 7 0 3 0 0', 12: '1 8 0 3 0 0', 13: '1 8 0 4 0 0', 14: '1 9 0 4 0 0', 15: '1 10 0 4 0 0',
                     16: '1 11 0 4 0 0'}
ROLE_GREETING = {
    "Detective": '\n'.join(["You are a Team-Leader Dylan Burns.",
                           "Your goal is to get rid of all QA-engineers in your town, while doing planned tasks",
                            "Your special ability is to check one's role in the company",
                            "Good luck, and let the justice prevail!"]),
    "Innocent": '\n'.join(["You are an Programmer. You don't have sleeping disorders, so at the night you always sleep.",
                           "Your goal is to get rid of all QA-engineers in your town, while doing planned tasks",
                           "Good luck, Programmer, and let the justice prevail!"]),
    "Mafioso": '\n'.join(["You are a QA-Engineer.",
                          "Your goal is to get rid of all Programmers and claim company to yourself",
                          "Your special ability is to increase one's tasks difficulty during the night.",
                          'Every text message from you in this chat will be sent to other QA-Engineers.',
                          "Good luck, and let the dark forces prevail!"])}

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("MafiaBot")


class Player:
    def __init__(self, user):
        if isinstance(user, User):
            self.ID = user.id
            self.name = user.first_name + (' ' + user.last_name if user.last_name else '')
            self.nick = user.username
        else:
            self.ID = 0
            self.name = user
            self.nick = user
        self.cf_name = None
        self.card = None
        self.is_alive = True
        self.is_abilities_active = True
        self.can_be_killed = True
        self.able_to_vote = True
        self.able_to_discuss = True
        self.chat_id = None
        self.difficulty = 800
        self.task = None
        self.voted_amount = 0


async def distribute_roles():
    global roles
    global players
    global QUANTITY_OF_ROLES
    global LEADERS_INNOCENTS
    global SPECIAL_MAFIOSI
    global SPECIAL_INNOCENTS
    global OTHERS
    global quantity

    logger.info('Distributing roles...')

    roles_q = list(map(int, QUANTITY_OF_ROLES[quantity].split(' ')))

    leaders_innocents = random.sample(LEADERS_INNOCENTS, roles_q[0])
    special_innocents = random.sample(SPECIAL_INNOCENTS, roles_q[2])
    special_mafiosi = random.sample(SPECIAL_MAFIOSI, roles_q[4])
    others = random.sample(OTHERS, roles_q[5])

    rand_players = [i.ID for i in players.values()]
    random.shuffle(rand_players)

    ind = 0
    for i in range(len(leaders_innocents)):
        players[rand_players[ind]].card = leaders_innocents[i].capitalize()
        roles[leaders_innocents[i].capitalize()] = rand_players[ind]
        ind += 1

    for i in range(len(special_innocents)):
        players[rand_players[ind]].card = special_innocents[i].capitalize()
        roles[special_innocents[i].capitalize()] = rand_players[ind]
        ind += 1

    for i in range(len(special_mafiosi)):
        players[rand_players[ind]].card = special_mafiosi[i].capitalize()
        roles[special_mafiosi[i].capitalize()] = rand_players[ind]
        ind += 1

    for i in range(len(others)):
        players[rand_players[ind]].card = others[i].capitalize()
        roles[others[i].capitalize()] = rand_players[ind]
        ind += 1

    roles['Innocent'] = []
    for i in range(roles_q[1]):
        players[rand_players[ind]].card = 'Innocent'
        roles['Innocent'].append(rand_players[ind])
        ind += 1

    roles['Mafioso'] = []
    for i in range(roles_q[3]):
        players[rand_players[ind]].card = 'Mafioso'
        roles['Mafioso'].append(rand_players[ind])
        ind += 1
    logger.info('Roles distribution finished:')
    for key, value in roles.items():
        if key == 'Mafioso':
            logger.info('Mafiosi: %s', ', '.join([players[i].name for i in value]))
        elif key == 'Innocent':
            logger.info('Innocents: %s', ', '.join([players[i].name for i in value]))
        else:
            logger.info('%s: %s', key, players[value].name)

    # These ifs are for debug, as situation with no mafiosi/innocents is prohibited by the rules
    # if not roles['Mafioso']:
    #     del roles['Mafioso']
    #
    # if not roles['Innocent']:
    #     del roles['Innocent']


async def send_roles(context: ContextTypes.DEFAULT_TYPE):
    global roles
    global players
    global ROLE_GREETING

    logger.info('Sending roles...')

    for role, player in roles.items():
        if role == 'Mafioso':
            for pl in player:
                await context.bot.send_message(chat_id=pl, text=ROLE_GREETING[role])
                if len(roles['Mafioso']) > 1:
                    await context.bot.send_message(
                        chat_id=pl,
                    text='Other QA-Engineers: \n{}'.format('\n'.join(players[i].name for i in roles['Mafioso'] if pl != i)),
                        parse_mode='Markdown'
                    )
        elif role == 'Innocent':
            for pl in player:
                await context.bot.send_message(chat_id=pl, text=ROLE_GREETING[role])
        else:
            await context.bot.send_message(chat_id=player, text=ROLE_GREETING[role])

    logger.info('Roles were sent successfully')

async def send_tasks(context: ContextTypes.DEFAULT_TYPE):
    logger.info('Sending tasks...')

    to_send = []
    for role, player in roles.items():
        if role == 'Innocent':
            for pl in player:
                to_send.append(pl)
        elif role != 'Mafioso':
            to_send.append(player)

    for pl in to_send:
        problem = random.choice(tasks[players[pl].difficulty])
        players[pl].task = str(problem["contestId"]) + '/' + problem["index"]
        await context.bot.send_message(chat_id=pl, text=f"Your new task:\nhttps://codeforces.com/problemset/problem/{players[pl].task}\nDeadline: today")

    logger.info('Tasks were sent successfully')

async def check_tasks(context: ContextTypes.DEFAULT_TYPE):
    to_check = []
    for role, player in roles.items():
        if role == 'Innocent':
            for pl in player:
                to_check.append(pl)
        elif role != 'Mafioso':
            to_check.append(player)

    for pl in to_check:
        solved = False
        try:
            r = dict()
            for i in range(REQUEST_MAX_TRIES):
                r = requests.get(f"https://codeforces.com/api/user.status?handle={players[pl].cf_name}&from=1&count=2").json()
                await asyncio.sleep(1)
                if r['status'] == 'OK':
                    break
            if r['status'] != 'OK':
                raise ConnectionError("Unable to connect")
            for solve_try in r['result']:
                problem = solve_try['problem']
                if "contestId" not in problem or "index" not in problem or "verdict" not in solve_try:
                    continue
                task = str(problem["contestId"]) + '/' + problem["index"]
                if task == players[pl].task and solve_try["verdict"] == 'OK':
                    solved = True
        except Exception as e:
            logger.error(f"Error checking tasks: {e}")
        if solved:
            await context.bot.send_message(chat_id=pl, text=f"Congratulation with solving your task!")
        else:
            await context.bot.send_message(chat_id=pl, text=f"You did not solve your task in time.")
            await kill_player(context, pl)

# Role functions
async def detective(context: ContextTypes.DEFAULT_TYPE):
    logger.info('Detective woke up')

    checklist = []
    for role, _id in roles.items():
        if role == 'Innocent' or role == 'Mafioso':
            for inn in _id:
                checklist.append([InlineKeyboardButton(players[inn].name, callback_data=f'doc_check:{inn}:{day_count}')])
        elif role != 'Detective':
            checklist.append([InlineKeyboardButton(players[_id].name, callback_data=f'doc_check:{_id}:{day_count}')])
    checklist.sort(key=lambda x: -int(x[0].callback_data.split(':')[1]))

    await context.bot.send_message(
        chat_id=roles['Detective'],
        text='Confirm your suspicions',
        reply_markup=InlineKeyboardMarkup(checklist)
    )

async def mafioso(context: ContextTypes.DEFAULT_TYPE):
    logger.info('Mafiosi woke up')

    shoot_list = []
    for role, _id in roles.items():
        if role == 'Innocent':
            for inn in _id:
                shoot_list.append([InlineKeyboardButton(players[inn].name, callback_data=f'maf_kill:{inn}:{day_count}')])
        elif role != 'Mafioso':
            shoot_list.append([InlineKeyboardButton(players[_id].name, callback_data=f'maf_kill:{_id}:{day_count}')])
    shoot_list.sort(key=lambda x: -int(x[0].callback_data.split(':')[1]))

    for i in roles['Mafioso']:
        await context.bot.send_message(
            chat_id=i,
            text='Choose a target properly',
            reply_markup=InlineKeyboardMarkup(shoot_list)
        )

# on maf_kill:x:y callback
async def mafioso_fire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, player_id, message_day = query.data.split(':')
    player_id = int(player_id)
    message_day = int(message_day)
    if message_day == day_count and night_state and game_state:
        players[player_id].difficulty += 100
        await query.edit_message_text(text=f"You send a massive bug report to {players[player_id].name}! \n"\
                                           f"His problems will be at {players[player_id].difficulty} difficulty")
    else:
        await query.edit_message_text(text="Too late!")

# on doc_check:x:y callback
async def detective_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, player_id, message_day = query.data.split(':')
    player_id = int(player_id)
    message_day = int(message_day)
    if message_day == day_count and night_state and game_state:
        role = players[player_id].card
        if role == 'Mafioso':
            await query.edit_message_text(text=f"{players[player_id].name} is a QA-Engineer!")
        else:
            await query.edit_message_text(text=f"{players[player_id].name} is a Programmer.")
    else:
        await query.edit_message_text(text="Too late!")

async def innocent(context):
    for i in roles['Innocent']:
        await context.bot.send_message(
            chat_id=i,
            text='Sleep tight!',
        )


async def night_cycle(context: ContextTypes.DEFAULT_TYPE, chat_id):
    global game_state
    global day_count
    global night_state
    night_state = True
    day_count += 1
    await joeover(context)
    if not game_state:
        return
    await context.bot.send_message(chat_id=chat_id, text=f'Working day ends. Night {day_count} starts')
    for i in roles.keys():
        i = i.lower()
        if i == 'detective':
            await detective(context)
        elif i == 'mafioso':
            await mafioso(context)
        elif i == 'innocent':
            await innocent(context)
        # other role functions here
    await asyncio.sleep(NIGHT_TIME)
    await day_cycle(context, chat_id)


async def voting(context: ContextTypes.DEFAULT_TYPE, chat_id):

    assert quantity >= 2, "Game must end with 1 or less players"
    for p in players.values():
        p.voted_amount = 0
    await context.bot.send_message(chat_id=chat_id, text=f'Voting starts!')
    checklist = []
    for p in players.values():
        checklist.append([InlineKeyboardButton(p.name, callback_data=f'vote:{p.ID}:{day_count}')])
    checklist.sort(key=lambda x: -int(x[0].callback_data.split(':')[1]))
    for p in players.values():
        if p.ID == 0:
            continue
        await context.bot.send_message(
            chat_id=p.ID,
            text='Voting',
            reply_markup=InlineKeyboardMarkup(checklist)
        )
    await asyncio.sleep(VOTING_TIME)
    order = sorted(players.values(), key=lambda x: -x.voted_amount)
    results = '\n'.join([str(x.name) + ": " + str(x.voted_amount) + " votes" for x in order])
    await context.bot.send_message(
        chat_id=chat_id,
        text=f'Voting results:\n{results}'
    )
    if order[0].voted_amount > order[1].voted_amount:
        if order[0].ID == 0:
            await context.bot.send_message(chat_id=chat_id, text=f'Office decided to not do anything')
        else:
            await context.bot.send_message(chat_id=chat_id, text=f'Office decided to make a denunciation about {order[0].name}!\n')
            await kill_player(context, order[0].ID)
    else:
        await context.bot.send_message(chat_id=chat_id, text=f'Office could not decide...')



# on vote:x:y callback
async def vote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, player_id, message_day = query.data.split(':')
    player_id = int(player_id)
    message_day = int(message_day)
    if message_day == day_count and (not night_state) and game_state:
        players[player_id].voted_amount += 1
        await query.edit_message_text(text=f"You voted for {players[player_id].name}")
    else:
        await query.edit_message_text(text="Too late!")


async def day_cycle(context: ContextTypes.DEFAULT_TYPE, chat_id):
    global game_state
    global night_state
    night_state = False
    await joeover(context)
    if not game_state:
        return
    await context.bot.send_message(chat_id=chat_id, text=f'Day {day_count} starts')
    await context.bot.send_message(chat_id=chat_id, text=f'{quantity} souls remain...')
    await send_tasks(context)
    await asyncio.sleep(DAY_TIME)

    await check_tasks(context)
    await voting(context, chat_id)
    await night_cycle(context, chat_id)


async def kill_player(context: ContextTypes.DEFAULT_TYPE, player_id):
    global quantity
    if player_id in players:
        card = players[player_id].card
        if card == 'Mafioso' or card == 'Innocent':
            roles[card].remove(player_id)
        else:
            del roles[card]
        quantity -= 1
        await context.bot.send_message(chat_id=game_chat_id, text=f"RIP {players[player_id].name}")
        del players[player_id]


async def joeover(context: ContextTypes.DEFAULT_TYPE):
    global game_state
    global registration_state
    global quantity
    if len(roles['Mafioso']) * 2 >= quantity:
        await context.bot.send_message(chat_id=game_chat_id, text='QA-Engineers claimed the company!')
        await stop(context)
        return
    if len(roles['Mafioso']) == 0:
        await context.bot.send_message(chat_id=game_chat_id, text='Programmers secured the company!')
        await stop(context)
        return

# Mainloop
async def game(context: ContextTypes.DEFAULT_TYPE, chat_id):
    global game_state
    global day_count
    day_count = 1
    game_state = True
    logger.info('Game started')
    await context.bot.send_message(chat_id=chat_id, text='Game is started.')
    intro = '\n'.join([
        'Hello, players! Today you will become workers in <redacted>!',
        'This small company is thriving with such wonderful programmers.',
        'But, unfortunately, the CEO have changed recently,',
        'And the first thing they did in the office was to layoff a part of you and replace with QA-Engineers!',
        'Their only goal is to get all of Programmers fired,',
        'And to do so they will file bug reports on some of you to make your job harder!',
        'You all work remotely, and have no way to determine who is hiding behind the nickname.',
        '',
        'However, not all hope is lost: your Team-Leader has a backdoor to check one\'s side once per night',
        'In daylight, besides mandatory tasks, you will have a secret group chat to discuss current situation.',
        'After discussion, if the majority of programmers agree to eliminate someone,',
        'Your boss will receive a denunciation about this person and fire him immediately.',
        '',
        'Good luck, and may the mind game begin.'
        ])
    await context.bot.send_message(chat_id=chat_id, text=intro)
    await asyncio.sleep(15)

    await distribute_roles()
    await send_roles(context)

    players[0] = Player('skip')

    await night_cycle(context, chat_id)

# Starts on '/game'
async def registration_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_state
    global quantity
    global registration_state
    global reg_message_id
    global game_chat_id

    if not (game_state or registration_state):
        await update.message.reply_text('And may the odds be ever in your favor')
        registration_state = True

        keyboard = [[InlineKeyboardButton('Register!', url="https://t.me/cf_mafia_bot?start=Register")]]
        msg_markup = InlineKeyboardMarkup(keyboard)

        reg_message_id = update.message.message_id + 2
        game_chat_id = update.message.chat_id
        sent_msg = await update.message.reply_text(
            '*Registration is active!*',
            parse_mode="Markdown",
            reply_markup=msg_markup
        )

        await context.bot.pin_chat_message(
            chat_id=update.message.chat_id,
            message_id=sent_msg.message_id,
            disable_notification=True
        )
    else:
        await update.message.reply_text('Currently running')

async def stop(context: ContextTypes.DEFAULT_TYPE):
    global game_state
    global registration_state
    global quantity
    global reg_message_id
    global game_chat_id

    if game_state or registration_state:

        if registration_state:
            try:
                await context.bot.delete_message(chat_id=game_chat_id, message_id=reg_message_id)
                await context.bot.delete_message(chat_id=game_chat_id, message_id=reg_message_id - 1)
            except Exception as e:
                logger.error(f"Error deleting messages: {e}")

        game_state = False
        registration_state = False

        quantity = 0
        players.clear()
        roles.clear()
        await context.bot.send_message(chat_id=game_chat_id, text='Game aborted successfully.')
        reg_message_id = None
        game_chat_id = None

# On '/stop'
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await context.bot.get_chat_member(update.message.chat_id, update.message.from_user.id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text('Sorry, only admins are able to stop the game.')
        return
    await stop(context)

# On text messages
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    if registration_state and user_id == chat_id and user_id in players:
        if players[user_id].cf_name is None:
            await update.message.reply_text(f"Handle {update.message.text} added!")
        else:
            await update.message.reply_text(f"Handle changed to {update.message.text}! Previous handle: {players[user_id].cf_name}")
        players[user_id].cf_name = update.message.text
    elif game_state and user_id == chat_id and user_id in players and players[user_id].card == 'Mafioso':
        s = f'{players[user_id].name}: *{update.message.text}*'
        for pl in roles['Mafioso']:
            if pl != user_id:
                await context.bot.send_message(chat_id=pl, text=s)


# On '/start'
async def reg_player_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global registration_state
    global quantity
    global reg_message_id
    global game_chat_id

    if registration_state:
        new_user = Player(update.message.from_user)

        if new_user.ID in players:
            await update.message.reply_text('You are already registered. Please wait for other players :)')
            return

        players[new_user.ID] = new_user
        quantity += 1

        logger.info('Player %s: %s, %s', quantity, new_user.name, new_user.ID)

        keyboard = [[InlineKeyboardButton('Register!', url="https://t.me/cf_mafia_bot?start=Register")]]
        msg_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text('Successful registration. Please send your handle on codeforces.com in the next message')

        await context.bot.edit_message_text(
            chat_id=game_chat_id,
            message_id=reg_message_id,
            text='Registration is active!\n\n*Registered players:* \n{}\n\nTotal: *{}*'.format(
                ', '.join(['[' + i.name + ']' + '(tg://user?id=' + str(i.ID) + ')' for _, i in players.items()]),
                str(quantity)),
            parse_mode="Markdown",
            reply_markup=msg_markup
        )
        await context.bot.send_message(chat_id=game_chat_id, text=f"Hello {new_user.name}!")
    else:
        await update.message.reply_text(
            'Registration is not active right now. Please call "/game" to start registration'
        )



async def default_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    logger.warning("Unexpected query: %s", query.data)

# On '/begin'
async def begin_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global quantity
    global registration_state
    global game_state
    global REQUIRED_PLAYERS
    global reg_message_id

    member = await context.bot.get_chat_member(update.message.chat_id, update.message.from_user.id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text('Sorry, only admins are able to begin the game.')
        return
    if game_state:
        await update.message.reply_text('Game is already running!')
        return
    if not registration_state:
        await update.message.reply_text('Please call "/game" to begin the registration.')
        return
    if quantity < REQUIRED_PLAYERS:
        await update.message.reply_text(
            '\n'.join(['Too small amount of players :(',
                      'Current amount of players: {}'.format(quantity),
                      'Amount of players required: {}.'.format(REQUIRED_PLAYERS)])
        )
        return
    without_cf_name = list(map(lambda p: p.name, filter(lambda p: p.cf_name is None, players.values())))
    if len(without_cf_name):
        await update.message.reply_text(', '.join(without_cf_name) + " must submit their handle(s)!")
        return

    await update.message.reply_text('Registration was successful! Game is starting...')
    registration_state = False
    try:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=reg_message_id)
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=reg_message_id - 1)
    except Exception as e:
        logger.error(f"Error deleting messages: {e}")
    asyncio.create_task(game(context, update.message.chat_id))

def main() -> None:
    """Run the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("game", registration_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("start", reg_player_command))
    application.add_handler(CommandHandler("begin", begin_game_command))
    application.add_handler(CallbackQueryHandler(mafioso_fire, pattern=r"^maf_kill:\d+:\d+$"))
    application.add_handler(CallbackQueryHandler(detective_check, pattern=r"^doc_check:\d+:\d+$"))
    application.add_handler(CallbackQueryHandler(vote_handler, pattern=r"^vote:\d+:\d+$"))
    application.add_handler(CallbackQueryHandler(default_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    application.run_polling()


if __name__ == "__main__":
    main()