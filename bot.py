import discord
from dotenv import load_dotenv
import os
from get_match import poll_for_new_match, initialize_database, on_new_match

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
PUUID = os.getenv("PUUID")

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.poll_started = False

    async def on_ready(self):
        print('Logged on as', self.user)
        initialize_database()

        if not self.poll_started:
            self.poll_started = True
            self.loop.create_task(poll_for_new_match(on_new_match=self.handle_new_match, puuid=PUUID))

    async def handle_new_match(self, match_id: str):
        channel = self.get_channel(int(CHANNEL_ID))
        print(f"channel resolved: {channel}")
        result = await on_new_match(match_id)
        print(f"result: {result!r}")
        
        if result == "REMAKE":
            await channel.send(result)
            return

        await channel.send(result)
intents = discord.Intents.default()
intents.message_content = True
client = MyClient(intents=intents)
client.run(DISCORD_TOKEN)