import asyncio
from threading import Thread
import traceback

import discord
import parsedatetime
import pytz

import emoji
import database as db
import util

def register(client):
    print("reminder: registering")
    Thread(target=thread_func, args=(client,)).start()
    return {
        "remind": cmd_reminder,
        "remindme": cmd_reminder,
        "todo": cmd_reminder,
    }

async def cmd_reminder(client, message, text):
    reminder = parse_reminder(text)
    if reminder is None:
        reply = "Sorry {message.author.mention}, I couldn't figure out the time for your reminder.".format(message=message)
        await client.send_message(message.channel, reply)
        await client.add_reaction(message, emoji.CROSS_MARK)
        return

    await add_reminder(message.author.id, reminder.time, reminder.text, reminder.original_text)

    reply = "\n".join([
        "Hello, {message.author.mention}!",
        "I'll remind you about `{reminder.text}` at time `{reminder.time_text}`!",
        "I interpreted that as `{reminder.time}`.",
    ]).format(message=message, reminder=reminder)
    await client.send_message(message.channel, reply)
    await client.add_reaction(message, emoji.WHITE_HEAVY_CHECK_MARK)

async def add_reminder(user_id, time, text, original_text):
    async with db.connect() as c:
        await c.execute("""
            INSERT INTO reminder(user_id, ts, text, original_text)
            VALUES (%s, %s, %s, %s)
        """, [user_id, time, text, original_text])

def thread_func(client):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(task(client))

async def task(client):
    # Wait until the client is ready
    util.threadsafe(client, client.wait_until_ready())

    while True:
        await asyncio.sleep(1)
        try:
            await process_next_reminder(client)
        except Exception as e:
            print("ERROR: {0}".format(e))
            traceback.print_exc()

async def process_next_reminder(client):
    async with db.connect() as c:
        await c.execute("""
            SELECT reminder_id, user_id, text
            FROM reminder
            WHERE ts < current_timestamp AND reminded = false
            ORDER BY ts ASC
        """)
        reminders = await c.fetchall()
        if len(reminders) == 0:
            return

        print("reminder: sending {0} reminders".format(c.rowcount))

        for id, user_id, text in reminders:
            msg = "Hello! I'm here to remind you about `{0}`".format(text)
            user = util.threadsafe(client, client.get_user_info(user_id))
            util.threadsafe(client, client.send_message(user, msg))

            await c.execute("""
                UPDATE reminder
                SET reminded = true
                WHERE reminder_id = %s
            """, [id])

def parse_reminder(text):
    cal = parsedatetime.Calendar()
    time_expressions = cal.nlp(text)
    time_expressions = time_expressions if time_expressions else []

    reminders = map(lambda p: Reminder(text, p), time_expressions)
    reminders_in_priority_order = sorted(reminders, key=lambda r: r.priorty)
    return next(iter(reminders_in_priority_order), None)

class Reminder:
    def __init__(self, original_text, time_expression):
        time, flags, start, end, time_text = time_expression

        self.original_text = original_text
        self.time_text = time_text
        self.time = self.utc_to_local(time)

        self.text = self.strip_middle(original_text, start, end)

        prefix = start == 0
        postfix = end == len(original_text)
        self.priorty = 1 if postfix else (2 if prefix else 3)

    def strip_middle(self, text, start, end):
        return text[:start].strip() + " " + text[end:].strip()

    def utc_to_local(self, dt, tz = pytz.timezone('Europe/Helsinki')):
        return tz.normalize(pytz.utc.localize(dt).astimezone(tz=tz))
