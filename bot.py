import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
from get_match import poll_for_new_match, initialize_database, on_new_match
import poros

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
RANK_EMBLEM_TEMPLATE = "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/images/ranked-emblem/emblem-{}.png"
PUUID = os.getenv("PUUID")

LOSS_STREAK_FACES = {
    #Add new faces if you want
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
        poros.ensure_open_next_game_market()

        if not self.poll_started:
            self.poll_started = True
            self.loop.create_task(poll_for_new_match(on_new_match=self.handle_new_match, puuid=PUUID))
        else:
            print("Polling already started")

    async def handle_new_match(self, match_id: str):
        channel = self.get_channel(int(CHANNEL_ID))
        result = await on_new_match(match_id)

        if result["status"] == "remake":
            await channel.send("🔁 Remake — no LP change.")
            await self._announce_poro_settlement(
                channel,
                poros.refund_market(match_id=match_id, reason="remake"),
            )
            return

        if result["status"] == "unknown":
            await channel.send("⚠️ Couldn't determine match result — check logs.")
            await self._announce_poro_settlement(
                channel,
                poros.refund_market(match_id=match_id, reason="unknown"),
            )
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
        await self._announce_poro_settlement(
            channel,
            poros.resolve_market("win" if win else "loss", match_id=match_id),
        )

    async def _announce_poro_settlement(self, channel, settlement: dict):
        text = poros.format_settlement(settlement)
        if text:
            await channel.send(text)

intents = discord.Intents.default()
intents.message_content = True

## BELOW IS SOME RANDOM CODE FOR FUTURE FEATURES
# 1. Instantiate YOUR custom MyBot class, not commands.Bot
bot = MyBot(command_prefix="!", intents=intents)

# 2. Register slash command to your custom bot instance
@bot.tree.command(name="ping", description="replies with pong")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")


def _fmt_multiplier(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}x"


class ResetConfirmView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Reset Poros", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This isn't your reset.", ephemeral=True)
            return

        try:
            result = poros.reset_wallet(self.user_id)
        except poros.PorosError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"Poro refill complete. You're back to **{result['balance']}** Poros.",
            view=self,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This isn't your reset.", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="Reset cancelled.", view=self)


poro = app_commands.Group(name="poro", description="Bet Poros on a.lin's next ranked game")


@poro.command(name="balance", description="Check your Poro balance")
async def poro_balance(interaction: discord.Interaction):
    view = poros.get_balance_view(str(interaction.user.id))
    embed = discord.Embed(
        title="Poro Wallet",
        color=discord.Color.gold(),
    )
    embed.add_field(name="Balance", value=f"{view['balance']} Poros", inline=True)
    rank = view["rank"]
    embed.add_field(
        name="Rich List",
        value=f"#{rank} of {view['wallet_count']}" if rank else "Unranked",
        inline=True,
    )
    embed.add_field(
        name="Bet Record",
        value=f"{view['bets_won']}W / {view['bets_lost']}L",
        inline=True,
    )
    embed.add_field(name="Total Won", value=str(view["total_won"]), inline=True)
    embed.add_field(name="Total Lost", value=str(view["total_lost"]), inline=True)
    embed.add_field(name="Total Wagered", value=str(view["total_wagered"]), inline=True)

    pending = view.get("pending")
    if pending:
        embed.add_field(
            name="Pending Bet",
            value=f"{pending['amount']} Poros on **{pending['prediction']}**",
            inline=False,
        )

    await interaction.response.send_message(embed=embed)


@poro.command(name="bet", description="Bet Poros on a.lin's next ranked game")
@app_commands.describe(
    prediction="Will a.lin win or lose the next ranked game?",
    amount="How many Poros to wager",
)
@app_commands.choices(
    prediction=[
        app_commands.Choice(name="Win", value="win"),
        app_commands.Choice(name="Loss", value="loss"),
    ]
)
async def poro_bet(
    interaction: discord.Interaction,
    prediction: app_commands.Choice[str],
    amount: int,
):
    try:
        result = poros.place_bet(str(interaction.user.id), prediction.value, amount)
    except poros.PorosError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return

    action = "added to" if result["aggregated"] else "placed"
    embed = discord.Embed(
        title="Poro Bet",
        description=(
            f"{interaction.user.mention} {action} **{result['added']}** Poros on "
            f"**{result['prediction']}**."
        ),
        color=discord.Color.gold(),
    )
    embed.add_field(name="Position", value=f"{result['amount']} on {result['prediction']}", inline=True)
    embed.add_field(name="Odds", value=_fmt_multiplier(result["multiplier"]), inline=True)
    embed.add_field(name="Pays", value=f"{result['potential_payout']} Poros", inline=True)
    embed.add_field(name="Remaining", value=f"{result['balance']} Poros", inline=True)
    await interaction.response.send_message(embed=embed)


@poro.command(name="leaderboard", description="Poro Rich List")
async def poro_leaderboard(interaction: discord.Interaction):
    rows = poros.leaderboard()
    embed = discord.Embed(
        title="Poro Rich List",
        color=discord.Color.gold(),
    )
    if not rows:
        embed.description = "No wallets yet. Use `/poro balance` to get started."
        await interaction.response.send_message(embed=embed)
        return

    lines = []
    for row in rows:
        lines.append(
            f"**{row['rank']}.** <@{row['user_id']}> — {row['balance']} Poros "
            f"({row['bets_won']}W/{row['bets_lost']}L)"
        )
    embed.description = "\n".join(lines)
    await interaction.response.send_message(embed=embed)


@poro.command(name="reset", description="Reset to starting Poros if you're broke")
async def poro_reset(interaction: discord.Interaction):
    eligibility = poros.reset_eligibility(str(interaction.user.id))
    if not eligibility["ok"]:
        await interaction.response.send_message(
            "\n".join(eligibility["reasons"]),
            ephemeral=True,
        )
        return

    view = ResetConfirmView(str(interaction.user.id))
    await interaction.response.send_message(
        f"Reset your wallet to **{eligibility['starting_balance']}** Poros? This cannot be undone.",
        view=view,
        ephemeral=True,
    )


@poro.command(name="help", description="How Poro betting works")
async def poro_help(interaction: discord.Interaction):
    market = poros.get_market_info()
    win_odds = _fmt_multiplier(market["multiplier_win"] if market else poros.WIN_MULTIPLIER)
    loss_odds = _fmt_multiplier(market["multiplier_loss"] if market else poros.LOSS_MULTIPLIER)
    embed = discord.Embed(
        title="Poro Betting",
        description="Bet Poros on a.lin's next ranked Solo/Duo game.",
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Commands",
        value=(
            "`/poro balance` — wallet and record\n"
            "`/poro bet` — wager on win or loss\n"
            "`/poro leaderboard` — Poro Rich List\n"
            "`/poro reset` — refill at 0 Poros"
        ),
        inline=False,
    )
    embed.add_field(
        name="Odds",
        value=f"Win pays {win_odds}. Loss pays {loss_odds}. Payouts round down.",
        inline=False,
    )
    embed.add_field(
        name="Rules",
        value=(
            f"New players start with **{poros.STARTING_BALANCE}** Poros.\n"
            "You can add more on the same side, but you cannot hedge both win and loss.\n"
            "Stake is taken when you bet. Winners get stake × odds back.\n"
            "Remakes and unresolved matches refund bets.\n"
            f"Reset is only at 0 Poros, once every **{int(poros.RESET_COOLDOWN_HOURS)}** hours."
        ),
        inline=False,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.tree.add_command(poro)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.lower() == "ping":
        channel = bot.get_channel(int(CHANNEL_ID))
        
        win = False
        rank = ['PLATINUM', "II", 23]
        wins = 120
        losses = 10000
        lp_change = 30
        daily_wins = 5
        daily_losses = 10
        loss_streak = 7


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

    # Required so prefix commands (if you add any with command_prefix="!") still work
    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)