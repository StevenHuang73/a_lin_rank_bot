# Changelog

Env file versions match the `# Version` comment in `example.env`. Copy any new keys into your local `.env` when you upgrade.

## 1.2.0 — 2026-08-19

Local development mode so each person can run their own bot without the production token.

### Env file

Add these for local testing (commented examples are in `example.env`):

```
BOT_ENV=dev
DISCORD_GUILD_ID=
SKIP_RIOT=true
DATABASE=rank_database.dev.json
POROS_DATABASE=poros_database.dev.json
```

| Key | Purpose |
|---|---|
| `BOT_ENV` | `dev` or `prod`. `dev` enables `/dev resolve`, guild command sync, and `DEV · local` presence. Default is `prod`. |
| `DISCORD_GUILD_ID` | Test server ID. Required in `dev` so slash commands sync immediately. |
| `SKIP_RIOT` | Skip Riot snapshot and polling. Defaults to `true` when `BOT_ENV=dev`. |
| `DATABASE` / `POROS_DATABASE` | Use `*.dev.json` locally so you do not overwrite production JSON. |

Production `.env` can stay on 1.1.0 keys. Leave `BOT_ENV` unset (or `prod`) and keep the live `DISCORD_TOKEN`.

## 1.1.0

Poros betting.

### Env file

Added:

```
POROS_DATABASE=poros_database.json
POROS_STARTING_BALANCE=1000
POROS_WIN_MULTIPLIER=1.8
POROS_LOSS_MULTIPLIER=1.8
POROS_RESET_COOLDOWN_HOURS=24
POROS_LEADERBOARD_SIZE=10
```

| Key | Purpose |
|---|---|
| `POROS_DATABASE` | Poros wallet / market JSON file |
| `POROS_STARTING_BALANCE` | New wallet and reset amount |
| `POROS_WIN_MULTIPLIER` | Payout on a correct next-game **win** bet |
| `POROS_LOSS_MULTIPLIER` | Payout on a correct next-game **loss** bet |
| `POROS_RESET_COOLDOWN_HOURS` | Hours between `/poro reset` uses |
| `POROS_LEADERBOARD_SIZE` | `/poro leaderboard` length |

## 1.0.0

Initial rank-update bot.

### Env file

```
DISCORD_TOKEN=
CHANNEL_ID=
RIOT_API=
PUUID=
DATABASE=rank_database.json
```
