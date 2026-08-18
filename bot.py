import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
from get_match import poll_for_new_match, initialize_database, on_new_match

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
RANK_EMBLEM_TEMPLATE = "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/images/ranked-emblem/emblem-{}.png"
PUUID = os.getenv("PUUID")

LOSS_STREAK_FACES = {
    1: "😕",
    2: "😔",
    3: "😞",
    4: "😢",
    5: "😭",
    6: "💀",
    7: "🪦",
}


from PIL import Image
import requests
import io

def get_cropped_emblem(url: str) -> io.BytesIO:
    response = requests.get(url)
    img = Image.open(io.BytesIO(response.content)).convert("RGBA")

    # getbbox() finds the bounding box of non-transparent pixels
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
def get_rank_emblem_url(tier: str) -> str:
    return RANK_EMBLEM_TEMPLATE.format(tier.lower())

def get_loss_streak_face(streak: int) -> str:
    if streak <= 0:
        return ""

    # too lazy to add more faces
    return LOSS_STREAK_FACES.get(
        min(streak, max(LOSS_STREAK_FACES))
    )

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.poll_started = False
        
    async def setup_hook(self):
        # Sync slash commands with Discord on startup
        await self.tree.sync()
        
    async def on_ready(self):
        print('Logged on as', self.user)
        initialize_database()

        if not self.poll_started:
            self.poll_started = True
            self.loop.create_task(poll_for_new_match(on_new_match=self.handle_new_match, puuid=PUUID))

    async def handle_new_match(self, match_id: str):
        channel = self.get_channel(int(CHANNEL_ID))
        result = await on_new_match(match_id)

        if result["status"] == "remake":
            await channel.send("🔁 Remake — no LP change.")
            return

        if result["status"] == "unknown":
            await channel.send("⚠️ Couldn't determine match result — check logs.")
            return

        win = result["win"]
        rank = result["rank"]
        wins = result["wins"]
        losses = result["losses"]
        lp_change = result["lp_change"]
        daily_wins = result["daily_wins"]
        daily_losses = result["daily_losses"]
        loss_streak = result["loss_streak"]


        total_games = wins + losses
        winrate = (wins / total_games * 100) if total_games > 0 else 0.0

        embed = discord.Embed(
            title="VICTORY! 🟢" if win else "DEFEAT 🔴",
            description=f"{'+' if win else '-'}{abs(lp_change)} LP",
            color=discord.Color.green() if win else discord.Color.red(),
        )
        buf = get_cropped_emblem(get_rank_emblem_url(rank[0]))
        file = discord.File(buf, filename="emblem.png")
        embed.set_thumbnail(url="attachment://emblem.png")
        embed.add_field(name="Rank", value=f"{rank[0]} {rank[1]}, {rank[2]} LP", inline=False)
        embed.add_field(name="Record", value=f"{wins}W / {losses}L", inline=True)
        embed.add_field(name="Winrate", value=f"{winrate:.2f}%", inline=True)
        embed.add_field(name="Today", value=f"{daily_wins}W / {daily_losses}L", inline=True)
        if not win: embed.add_field(name="Loss Streak", value=f"{loss_streak} {get_loss_streak_face(loss_streak)}", inline=True)
        embed.set_footer(text="Aaron Lin Rank Updates")

        await channel.send(embed=embed, file=file)

intents = discord.Intents.default()
intents.message_content = True

## BELOW IS SOME RANDOM CODE FOR FUTURE FEATURES
# 1. Instantiate YOUR custom MyBot class, not commands.Bot
bot = MyBot(command_prefix="!", intents=intents)

# 2. Register slash command to your custom bot instance
@bot.tree.command(name="ping", description="replies with pong")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.lower() == "ping":
        channel = bot.get_channel(int(CHANNEL_ID))
        win = True
        rank = ['PLATINUM', "II", 23]
        wins = 120
        losses = 10000
        lp_change = 30

        total_games = wins + losses
        winrate = (wins / total_games * 100) if total_games > 0 else 0.0

        embed = discord.Embed(
            title="VICTORY!" if win else "DEFEAT",
            description=f"{'+' if win else '-'}{abs(lp_change)} LP",
            color=discord.Color.green() if win else discord.Color.red(),
        )
        buf = get_cropped_emblem(get_rank_emblem_url(rank[0]))
        file = discord.File(buf, filename="emblem.png")
        embed.set_thumbnail(url="attachment://emblem.png")
        embed.add_field(name="Rank", value=f"{rank[0]} {rank[1]}, {rank[2]} LP", inline=False)
        embed.add_field(name="Record", value=f"{wins}W / {losses}L", inline=True)
        embed.add_field(name="Winrate", value=f"{winrate:.2f}%", inline=True)
        embed.set_footer(text="Aaron Lin")

        await channel.send(embed=embed, file=file)

    # Required so prefix commands (if you add any with command_prefix="!") still work
    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)