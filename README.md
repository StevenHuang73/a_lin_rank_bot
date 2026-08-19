# a.lin Rank Bot

Discord bot that posts **Aaron Lin** ranked Solo/Duo updates and runs a virtual betting game called **Poros**.

## Rank updates

The bot polls the Riot API about every 30 seconds for a new ranked Solo/Duo game (`queue 420`). When one finishes, it posts an embed to the configured channel:

- Victory or defeat, with LP gained or lost
- Current rank (tier, division, LP) and rank emblem
- Season record and winrate
- Daily record (resets at 6:00 AM America/Vancouver)
- Loss streak (on losses only)

Remakes are announced with no LP change. If the result cannot be determined, the bot posts a warning instead of a rank embed.

LP change is computed from Iron through Diamond. Master and above are not supported yet.

## Poros

Poros is the in-bot currency. Anyone in the server can bet on whether a.lin wins or loses the **next** ranked game. Balances are global (one wallet per Discord user).

### Commands

| Command | What it does |
|---|---|
| `/bet` | Wager Poros on **win** or **loss** |
| `/undo` | Cancel your pending bet and refund the stake |
| `/balance` | Wallet, bet record, Rich List rank, and any pending bet |
| `/leaderboard` | Poro Rich List (top balances) |
| `/poro reset` | Refill to the starting amount if you are broke |
| `/poro help` | Rules, odds, and reset policy |

`/ping` is also available and replies `Pong!`.

### How betting works

1. There is always one open market: **next ranked game, win or loss**.
2. You pick a side and a wager. The stake is taken from your wallet immediately.
3. Same-side adds are allowed and stack into one position. There is no max bet besides your balance.
4. You cannot hedge. If you already bet **win**, you cannot also bet **loss** on the same game (and vice versa).
5. `/undo` cancels your pending bet and returns the full stake, as long as the market is still open.
6. When the match resolves, winners are paid `floor(stake × multiplier)` back into their wallet. Losers keep the loss of their stake.
7. Remakes and unresolved matches refund every pending bet, then a new market opens.

Default odds are **1.8x** on both sides. Example: bet 100 Poros on win, a.lin wins → you receive 180 Poros (net +80).

### Starting balance and reset

New players start with **1000** Poros (configurable).

`/poro reset` is only available when:

- your wallet is at **0** Poros
- you have **no pending bet**
- your reset cooldown has elapsed (default **24 hours**)

Reset asks for a button confirmation. It restores the starting balance and cannot be undone.

### Persistence

Wallets, the open market, pending bets, and recent settlement history live in `poros_database.json`. State survives bot restarts.

## Setup

1. Copy `example.env` to `.env` and fill in tokens.
2. Install dependencies: `pip install -r requirements.txt`
3. Run `python bot.py`.

On first ready, the bot snapshots a.lin’s current rank into `rank_database.json` and opens a Poros market if one is not already open. Slash commands sync on startup.

## Running locally (for developers)

Do **not** use the production bot token. Two processes with the same token will disconnect each other, and local code would post into the live channel.

Each developer creates their **own** Discord application and runs that bot against a test server. Production can stay down; you still test on your machine.

### 1. Create a Discord application

1. Open [Discord Developer Portal](https://discord.com/developers/applications) and sign in.
2. **New Application** → name it something like `a.lin rank bot (yourname)`.
3. Open **Bot**:
   - **Reset Token** / **Copy** the token. This is `DISCORD_TOKEN`.
   - Enable **Message Content Intent**.
4. Open **OAuth2 → URL Generator**:
   - Scopes: `bot` and `applications.commands`
   - Bot permissions: `Send Messages`, `Embed Links`, `Attach Files`, `Use Slash Commands`
   - Copy the URL, open it, and invite the bot into a **test server** (not the live community server, unless you are sure).

### 2. Copy IDs from Discord

In Discord: **User Settings → Advanced → Developer Mode** (on).

Then:

- Right-click the **test server icon** → **Copy Server ID**. This is `DISCORD_GUILD_ID`.
- Right-click the **test channel** → **Copy Channel ID**. This is `CHANNEL_ID`.

### 3. Local `.env`

From the repo root:

```
copy example.env .env
```

Edit `.env` so it looks like this (your values, not prod):

```
BOT_ENV=dev
DISCORD_TOKEN=paste-your-personal-bot-token
DISCORD_GUILD_ID=paste-test-server-id
CHANNEL_ID=paste-test-channel-id
SKIP_RIOT=true
DATABASE=rank_database.dev.json
POROS_DATABASE=poros_database.dev.json

POROS_STARTING_BALANCE=1000
POROS_WIN_MULTIPLIER=1.8
POROS_LOSS_MULTIPLIER=1.8
POROS_RESET_COOLDOWN_HOURS=24
POROS_LEADERBOARD_SIZE=10
```

Leave `RIOT_API` empty while `SKIP_RIOT=true`. You do not need a live ranked game to test Poros.

### 4. Run

```
python bot.py
```

The bot should go **Do Not Disturb** with status `DEV · local`. In the test server, `/bet`, `/undo`, `/balance`, `/leaderboard`, `/poro`, and `/dev` should appear within a few seconds.

If commands are missing: kick the bot, re-invite with `applications.commands`, restart `bot.py`.

### 5. Test Poros without a real match

1. `/balance` — you should get the starting wallet.
2. `/bet` — pick win or loss and an amount.
3. `/dev resolve` — pick **Win**, **Loss**, **Remake**, or **Unknown**.
4. Check `/balance` and `/leaderboard`.

`/dev resolve` is only registered when `BOT_ENV=dev`.

### Rules

- Never paste the production `DISCORD_TOKEN` into your `.env`.
- Use `*.dev.json` database files so you do not overwrite live rank/Poro state if you share a machine.
- Several people can test at once only if **each person has their own Discord application/token**.
- Set `SKIP_RIOT=false` and a `RIOT_API` key only if you specifically want local Riot polling.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `DISCORD_TOKEN` | Bot token | — |
| `CHANNEL_ID` | Channel for rank posts and Poro settlements | — |
| `DISCORD_GUILD_ID` | Test server ID; guild-syncs slash commands in `BOT_ENV=dev` | — |
| `BOT_ENV` | `prod` or `dev` | `prod` |
| `SKIP_RIOT` | Skip Riot snapshot and polling (`true` by default in dev) | `false` (prod) / `true` (dev) |
| `RIOT_API` | Riot Games API key | — |
| `PUUID` | Tracked account PUUID | — |
| `DATABASE` | Rank snapshot file | `rank_database.json` |
| `POROS_DATABASE` | Poros store file | `poros_database.json` |
| `POROS_STARTING_BALANCE` | New-wallet / reset amount | `1000` |
| `POROS_WIN_MULTIPLIER` | Payout on a correct win bet | `1.8` |
| `POROS_LOSS_MULTIPLIER` | Payout on a correct loss bet | `1.8` |
| `POROS_RESET_COOLDOWN_HOURS` | Hours between resets | `24` |
| `POROS_LEADERBOARD_SIZE` | Rich List length | `10` |
