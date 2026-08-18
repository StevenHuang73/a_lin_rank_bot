from dotenv import load_dotenv
import os
import requests
import json
import asyncio

load_dotenv()

RIOT_API = os.getenv("RIOT_API")
PUUID = os.getenv("PUUID")
DATABASE_PATH = os.getenv("DATABASE")

headers = {"X-Riot-Token": RIOT_API}

last_match_id: str | None = None
POLL_INTERVAL_SECONDS = 30


# Ranked Solo/Duo queue ID
RANKED_SOLO_QUEUE_ID = 420


# Used to turn ranks into a continuous LP number.
# This handles Iron through Diamond.
TIER_ORDER = {
    "IRON": 0,
    "BRONZE": 1,
    "SILVER": 2,
    "GOLD": 3,
    "PLATINUM": 4,
    "EMERALD": 5,
    "DIAMOND": 6,
}

DIVISION_ORDER = {
    "IV": 0,
    "III": 1,
    "II": 2,
    "I": 3,
}


def get_account_info(puuid=PUUID):
    platform_host = "na1"

    league_v4_url = (
        f"https://{platform_host}.api.riotgames.com/"
        f"lol/league/v4/entries/by-puuid/{puuid}"
    )

    response = requests.get(league_v4_url, headers=headers)
    response.raise_for_status()

    lv4_response = response.json()

    solo_queue = next(
        (
            entry
            for entry in lv4_response
            if entry["queueType"] == "RANKED_SOLO_5x5"
        ),
        None
    )

    if solo_queue is None:
        raise ValueError(
            "No RANKED_SOLO_5x5 entry found for this account."
        )

    latest_match_id = get_latest_match_id(puuid)

    return solo_queue, latest_match_id


def get_latest_match_id(puuid=PUUID):
    """
    Gets the most recent Ranked Solo/Duo match only.
    """

    matches_url = (
        "https://americas.api.riotgames.com/"
        f"lol/match/v5/matches/by-puuid/{puuid}/ids"
        f"?queue={RANKED_SOLO_QUEUE_ID}&count=1"
    )

    response = requests.get(matches_url, headers=headers)
    response.raise_for_status()

    matches = response.json()

    if not matches:
        return None

    return matches[0]


def initialize_database(database=DATABASE_PATH):
    ranked_data, latest_match_id = get_account_info()

    data = {
        "tier": ranked_data["tier"],
        "rank": ranked_data["rank"],
        "leaguePoints": ranked_data["leaguePoints"],
        "wins": ranked_data["wins"],
        "losses": ranked_data["losses"],
        "hotStreak": ranked_data["hotStreak"],
        "last_match_id": latest_match_id
    }

    with open(database, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)

    print(f"Database initialized and saved to {database}")


def update_database(database=DATABASE_PATH):
    ranked_data, latest_match_id = get_account_info()

    data = {
        "tier": ranked_data["tier"],
        "rank": ranked_data["rank"],
        "leaguePoints": ranked_data["leaguePoints"],
        "wins": ranked_data["wins"],
        "losses": ranked_data["losses"],
        "hotStreak": ranked_data["hotStreak"],
        "last_match_id": latest_match_id
    }

    with open(database, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)

    rank, wins, losses = get_rank(data)

    return rank, wins, losses


def get_rank(data):
    rank = [
        data["tier"],
        data["rank"],
        data["leaguePoints"]
    ]

    wins = data["wins"]
    losses = data["losses"]

    return rank, wins, losses


def rank_to_absolute_lp(rank):
    """
    Converts ranks from Iron IV through Diamond I into a continuous
    LP number.

    Example:
        SILVER II 90 LP
        SILVER I 14 LP

    can then be directly subtracted.
    """

    tier, division, lp = rank

    if tier not in TIER_ORDER:
        raise ValueError(
            f"Unsupported tier for LP calculation: {tier}. "
            "This implementation currently supports Iron through Diamond."
        )

    if division not in DIVISION_ORDER:
        raise ValueError(
            f"Unsupported division: {division}"
        )

    tier_base = TIER_ORDER[tier] * 400
    division_base = DIVISION_ORDER[division] * 100

    return tier_base + division_base + lp


def compute_lp_diff(initial_rank, final_rank, wl):
    """
    Computes LP gained/lost.

    'wl' is intentionally kept in the function signature so this remains
    compatible with existing code that calls:

        compute_lp_diff(initial_rank, final_rank, wl)

    It is no longer needed to calculate LP change.
    """

    initial_lp = rank_to_absolute_lp(initial_rank)
    final_lp = rank_to_absolute_lp(final_rank)

    return final_lp - initial_lp


def output_string(rank, wins, losses, wl, rank_difference):
    total_games = wins + losses

    winrate = (
        wins / total_games * 100
        if total_games > 0
        else 0.0
    )

    lp_change = abs(rank_difference)

    if wl:
        status_line = (
            f"Aaron Lin WON his last game! "
            f"He gained {lp_change} LP!"
        )
    else:
        status_line = (
            f"Aaron Lin LOST his last game. "
            f"He lost {lp_change} LP."
        )

    return (
        f"{status_line}\n\n"
        f"Aaron Lin's new rank is "
        f"{rank[0]} {rank[1]}, {rank[2]} LP\n"
        f"WINS: {wins} | LOSSES: {losses}\n"
        f"WINRATE: {winrate:.2f}%"
    )


async def on_new_match(match_id: str, database=DATABASE_PATH):
    print(f"on_new_match called with {match_id}")

    # Read the OLD ranked state before updating it.
    with open(database, "r", encoding="utf-8") as file:
        data = json.load(file)

    db_rank, db_wins, db_losses = get_rank(data)

    # Fetch and store the NEW ranked state.
    new_rank, new_wins, new_losses = update_database(database)

    wins_diff = new_wins - db_wins
    losses_diff = new_losses - db_losses

    print(
        f"Rank change: {db_rank} -> {new_rank}\n"
        f"Wins change: {db_wins} -> {new_wins}\n"
        f"Losses change: {db_losses} -> {new_losses}"
    )

    # Determine win/loss from the ranked W/L counters.
    if wins_diff == 1 and losses_diff == 0:
        wl = True

    elif wins_diff == 0 and losses_diff == 1:
        wl = False

    elif wins_diff == 0 and losses_diff == 0:
        # Ranked match appeared in Match-V5, but ranked record didn't change.
        # Most likely remake / non-counting game.
        print("No ranked W/L change detected. Treating as REMAKE.")
        return "REMAKE"

    else:
        # This means more than one ranked result happened between polls,
        # or Riot's API state changed in an unexpected way.
        print(
            "Unexpected ranked record change. "
            f"wins_diff={wins_diff}, losses_diff={losses_diff}"
        )

        return "UNKNOWN"

    rank_difference = compute_lp_diff(
        db_rank,
        new_rank,
        wl=wl
    )

    output = output_string(
        new_rank,
        new_wins,
        new_losses,
        wl,
        rank_difference=rank_difference
    )

    print(output)

    return output


def get_stored_match_id(database=DATABASE_PATH):
    """
    Loads the last processed match ID from the JSON database.
    """

    try:
        with open(database, "r", encoding="utf-8") as file:
            data = json.load(file)

        return data.get("last_match_id")

    except FileNotFoundError:
        return None

    except json.JSONDecodeError:
        return None


async def poll_for_new_match(puuid: str, on_new_match):
    """
    Continuously polls for the latest Ranked Solo/Duo match ID.

    Calls:

        await on_new_match(match_id)

    whenever a new ranked match is detected.
    """

    global last_match_id

    # On program restart, restore the previously processed match.
    if last_match_id is None:
        last_match_id = get_stored_match_id()

    print(f"Starting poller. Stored match ID: {last_match_id}")

    while True:
        print("POLLING")

        try:
            latest_id = get_latest_match_id(puuid)

            print(
                f"latest_id={latest_id}, "
                f"last_match_id={last_match_id}"
            )

            if latest_id is not None:

                if last_match_id is None:
                    # No database/baseline yet.
                    # Establish current match without treating it as new.
                    last_match_id = latest_id

                elif latest_id != last_match_id:
                    print(f"New ranked match detected: {latest_id}")

                    # Important:
                    # Process the match before changing our in-memory baseline.
                    result = await on_new_match(latest_id)

                    # Once processing succeeds, remember this as the latest match.
                    last_match_id = latest_id

                    print(f"Match processing result: {result}")

        except Exception as e:
            # Network errors, expired Riot key, rate limits, etc.
            # should not kill the polling loop.
            print(f"Polling error: {e}")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)