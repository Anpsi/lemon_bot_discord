import asyncio
import json
import os
import threading
import traceback

import aiohttp

webhook_url = os.environ.get("ERROR_CHANNEL_WEBHOOK", None)

async def log_exception():
    err_str = traceback.format_exc()
    print("ERROR: {0}".format(err_str))
    if webhook_url is not None:
        await post_exception(err_str)


async def post_exception(err_str):
    data = {
        "username": "Errors",
        "icon_url": "https://rce.fi/error.png",
        "text": "```" + err_str + "```",
    }

    async with aiohttp.post(webhook_url + "/slack", data=json.dumps(data)) as r:
        if r.status != 200:
            print("util: unknown webhook response {0}".format(r))
            return

        print("util: posted error on channel")


# Run discord.py coroutines from antoher thread
def threadsafe(client, coroutine):
    return asyncio.run_coroutine_threadsafe(coroutine, client.loop).result()

# Start a coroutine task in new thread
def start_task_thread(coroutine):
    def thread_func(coroutine):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(coroutine)
    threading.Thread(target=thread_func, args=(coroutine,)).start()
