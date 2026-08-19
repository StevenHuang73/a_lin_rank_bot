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
| `/poro help` | Rules, odds, and reset policy |
| `/poro balance` | Wallet, bet record, Rich List rank, and any pending bet |
| `/poro bet` | Wager Poros on **win** or **loss** |
| `/poro leaderboard` | Poro Rich List (top balances) |
| `/poro reset` | Refill to the starting amount if you are broke |

`/ping` is also available and replies `Pong!`.

### How betting works

1. There is always one open market: **next ranked game, win or loss**.
2. You pick a side and a wager. The stake is taken from your wallet immediately.
3. Same-side adds are allowed and stack into one position. There is no max bet besides your balance.
4. You cannot hedge. If you already bet **win**, you cannot also bet **loss** on the same game (and vice versa).
5. When the match resolves, winners are paid `floor(stake × multiplier)` back into their wallet. Losers keep the loss of their stake.
6. Remakes and unresolved matches refund every pending bet, then a new market opens.

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
2. Install dependencies (`discord.py`, `python-dotenv`, `Pillow`, `requests`).
3. Run `python bot.py`.

On first ready, the bot snapshots a.lin’s current rank into `rank_database.json` and opens a Poros market if one is not already open. Slash commands sync on startup.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `DISCORD_TOKEN` | Bot token | — |
| `CHANNEL_ID` | Channel for rank posts and Poro settlements | — |
| `RIOT_API` | Riot Games API key | — |
| `PUUID` | Tracked account PUUID | — |
| `DATABASE` | Rank snapshot file | `rank_database.json` |
| `POROS_DATABASE` | Poros store file | `poros_database.json` |
| `POROS_STARTING_BALANCE` | New-wallet / reset amount | `1000` |
| `POROS_WIN_MULTIPLIER` | Payout on a correct win bet | `1.8` |
| `POROS_LOSS_MULTIPLIER` | Payout on a correct loss bet | `1.8` |
| `POROS_RESET_COOLDOWN_HOURS` | Hours between resets | `24` |
| `POROS_LEADERBOARD_SIZE` | Rich List length | `10` |
