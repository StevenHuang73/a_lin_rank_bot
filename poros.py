import json
import math
import os
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

STARTING_BALANCE = int(os.getenv("POROS_STARTING_BALANCE", "1000"))
WIN_MULTIPLIER = float(os.getenv("POROS_WIN_MULTIPLIER", "1.8"))
LOSS_MULTIPLIER = float(os.getenv("POROS_LOSS_MULTIPLIER", "1.8"))
RESET_COOLDOWN_HOURS = float(os.getenv("POROS_RESET_COOLDOWN_HOURS", "24"))
DATABASE_PATH = os.getenv("POROS_DATABASE", "poros_database.json")
LEADERBOARD_SIZE = int(os.getenv("POROS_LEADERBOARD_SIZE", "10"))
HISTORY_CAP = 20

_lock = threading.Lock()


class PorosError(Exception):
    """User-facing Poros error."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _empty_store() -> dict:
    return {
        "wallets": {},
        "current_market": None,
        "bets": [],
        "history": [],
    }


def _new_wallet() -> dict:
    return {
        "balance": STARTING_BALANCE,
        "total_wagered": 0,
        "total_won": 0,
        "total_lost": 0,
        "bets_won": 0,
        "bets_lost": 0,
        "reset_count": 0,
        "last_reset_at": None,
        "created_at": _now_iso(),
    }


def _new_market() -> dict:
    return {
        "market_id": str(uuid.uuid4()),
        "type": "next_game_wl",
        "status": "open",
        "created_at": _now_iso(),
        "multiplier_win": WIN_MULTIPLIER,
        "multiplier_loss": LOSS_MULTIPLIER,
        "match_id": None,
        "resolution": None,
        "resolved_at": None,
    }


def _load() -> dict:
    try:
        with open(DATABASE_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return _empty_store()

    data.setdefault("wallets", {})
    data.setdefault("current_market", None)
    data.setdefault("bets", [])
    data.setdefault("history", [])
    return data


def _save(data: dict) -> None:
    directory = os.path.dirname(os.path.abspath(DATABASE_PATH)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp", prefix="poros_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
        os.replace(tmp_path, DATABASE_PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _ensure_wallet(data: dict, user_id: str) -> dict:
    wallets = data["wallets"]
    if user_id not in wallets:
        wallets[user_id] = _new_wallet()
    return wallets[user_id]


def _open_new_market(data: dict) -> dict:
    data["current_market"] = _new_market()
    data["bets"] = []
    return data["current_market"]


def _pending_bet_for_user(data: dict, user_id: str, market_id: str) -> dict | None:
    for bet in data["bets"]:
        if (
            bet["user_id"] == user_id
            and bet["market_id"] == market_id
            and bet["status"] == "pending"
        ):
            return bet
    return None


def _archive_market(data: dict, reason: str) -> None:
    market = data.get("current_market")
    if market is None:
        return

    data["history"].append(
        {
            "market": market,
            "bets": data.get("bets", []),
            "reason": reason,
            "settled_at": _now_iso(),
        }
    )
    data["history"] = data["history"][-HISTORY_CAP:]


def _multiplier_for(market: dict, prediction: str) -> float:
    if prediction == "win":
        return float(market["multiplier_win"])
    return float(market["multiplier_loss"])


def _payout_amount(stake: int, multiplier: float) -> int:
    return math.floor(stake * multiplier)


def _sorted_wallets(data: dict) -> list[tuple[str, dict]]:
    return sorted(
        data["wallets"].items(),
        key=lambda item: (
            -item[1].get("balance", 0),
            -item[1].get("total_won", 0),
            item[1].get("created_at") or "",
        ),
    )


def _rank_for(data: dict, user_id: str) -> int | None:
    for index, (uid, _) in enumerate(_sorted_wallets(data), start=1):
        if uid == user_id:
            return index
    return None


def _empty_settlement(status: str, outcome: str | None = None) -> dict:
    return {
        "status": status,
        "outcome": outcome,
        "paid": 0,
        "lost": 0,
        "refunded": 0,
        "results": [],
        "market_id": None,
    }


def ensure_open_next_game_market() -> dict:
    with _lock:
        data = _load()
        market = data.get("current_market")
        if market is None or market.get("status") != "open":
            market = _open_new_market(data)
            _save(data)
        return dict(market)


def get_or_create_wallet(user_id: str) -> dict:
    with _lock:
        data = _load()
        wallet = _ensure_wallet(data, user_id)
        _save(data)
        return dict(wallet)


def get_balance_view(user_id: str) -> dict:
    with _lock:
        data = _load()
        wallet = _ensure_wallet(data, user_id)
        _save(data)

        market = data.get("current_market")
        pending = None
        if market and market.get("status") == "open":
            pending = _pending_bet_for_user(data, user_id, market["market_id"])

        return {
            "balance": wallet["balance"],
            "total_wagered": wallet["total_wagered"],
            "total_won": wallet["total_won"],
            "total_lost": wallet["total_lost"],
            "bets_won": wallet["bets_won"],
            "bets_lost": wallet["bets_lost"],
            "reset_count": wallet["reset_count"],
            "rank": _rank_for(data, user_id),
            "wallet_count": len(data["wallets"]),
            "pending": dict(pending) if pending else None,
            "market": dict(market) if market else None,
        }


def get_market_info() -> dict | None:
    with _lock:
        data = _load()
        market = data.get("current_market")
        if market is None:
            return None
        pending_count = sum(1 for bet in data["bets"] if bet["status"] == "pending")
        total_staked = sum(bet["amount"] for bet in data["bets"] if bet["status"] == "pending")
        info = dict(market)
        info["pending_bets"] = pending_count
        info["total_staked"] = total_staked
        return info


def place_bet(user_id: str, prediction: str, amount: int) -> dict:
    prediction = prediction.lower()
    if prediction not in {"win", "loss"}:
        raise PorosError("Prediction must be win or loss.")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise PorosError("Wager must be a positive whole number of Poros.")

    with _lock:
        data = _load()
        market = data.get("current_market")
        if market is None or market.get("status") != "open":
            market = _open_new_market(data)

        wallet = _ensure_wallet(data, user_id)
        if amount > wallet["balance"]:
            raise PorosError(
                f"Not enough Poros. You have {wallet['balance']}."
            )

        existing = _pending_bet_for_user(data, user_id, market["market_id"])
        if existing and existing["prediction"] != prediction:
            raise PorosError(
                "Opposite-side bets are not allowed on the same game. "
                f"You already have {existing['amount']} Poros on "
                f"**{existing['prediction']}**. Use `/undo` to cancel that bet first."
            )

        wallet["balance"] -= amount
        wallet["total_wagered"] += amount

        aggregated = False
        if existing:
            existing["amount"] += amount
            bet = existing
            aggregated = True
        else:
            bet = {
                "bet_id": str(uuid.uuid4()),
                "market_id": market["market_id"],
                "user_id": user_id,
                "prediction": prediction,
                "amount": amount,
                "status": "pending",
                "payout": 0,
                "placed_at": _now_iso(),
                "resolved_at": None,
            }
            data["bets"].append(bet)

        _save(data)

        multiplier = _multiplier_for(market, prediction)
        return {
            "amount": bet["amount"],
            "added": amount,
            "prediction": prediction,
            "balance": wallet["balance"],
            "multiplier": multiplier,
            "potential_payout": _payout_amount(bet["amount"], multiplier),
            "aggregated": aggregated,
            "market_id": market["market_id"],
        }


def undo_bet(user_id: str) -> dict:
    with _lock:
        data = _load()
        market = data.get("current_market")
        if market is None or market.get("status") != "open":
            raise PorosError("No open market to undo a bet on.")

        existing = _pending_bet_for_user(data, user_id, market["market_id"])
        if existing is None:
            raise PorosError("You don't have a pending bet on the next game.")

        wallet = _ensure_wallet(data, user_id)
        refund = existing["amount"]
        wallet["balance"] += refund
        wallet["total_wagered"] = max(0, wallet["total_wagered"] - refund)

        data["bets"] = [
            bet
            for bet in data["bets"]
            if bet.get("bet_id") != existing["bet_id"]
        ]
        _save(data)

        return {
            "refunded": refund,
            "prediction": existing["prediction"],
            "balance": wallet["balance"],
        }


def leaderboard(limit: int | None = None) -> list[dict]:
    size = limit if limit is not None else LEADERBOARD_SIZE
    with _lock:
        data = _load()
        rows = []
        for rank, (user_id, wallet) in enumerate(_sorted_wallets(data), start=1):
            if rank > size:
                break
            rows.append(
                {
                    "rank": rank,
                    "user_id": user_id,
                    "balance": wallet.get("balance", 0),
                    "bets_won": wallet.get("bets_won", 0),
                    "bets_lost": wallet.get("bets_lost", 0),
                    "total_won": wallet.get("total_won", 0),
                }
            )
        return rows


def reset_eligibility(user_id: str) -> dict:
    with _lock:
        data = _load()
        wallet = _ensure_wallet(data, user_id)
        _save(data)

        market = data.get("current_market")
        pending = None
        if market:
            pending = _pending_bet_for_user(data, user_id, market["market_id"])

        cooldown_until = None
        last_reset = _parse_iso(wallet.get("last_reset_at"))
        if last_reset is not None:
            cooldown_until = last_reset + timedelta(hours=RESET_COOLDOWN_HOURS)

        now = datetime.now(timezone.utc)
        on_cooldown = cooldown_until is not None and now < cooldown_until

        reasons = []
        if wallet["balance"] != 0:
            reasons.append(f"Reset is only available at 0 Poros. You have {wallet['balance']}.")
        if pending is not None:
            reasons.append("You still have a pending bet. Wait for it to resolve.")
        if on_cooldown:
            remaining = cooldown_until - now
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            reasons.append(f"Reset cooldown: {hours}h {minutes}m remaining.")

        return {
            "ok": len(reasons) == 0,
            "reasons": reasons,
            "balance": wallet["balance"],
            "starting_balance": STARTING_BALANCE,
        }


def reset_wallet(user_id: str) -> dict:
    with _lock:
        data = _load()
        wallet = _ensure_wallet(data, user_id)

        market = data.get("current_market")
        pending = None
        if market:
            pending = _pending_bet_for_user(data, user_id, market["market_id"])

        if wallet["balance"] != 0:
            raise PorosError(
                f"Reset is only available at 0 Poros. You have {wallet['balance']}."
            )
        if pending is not None:
            raise PorosError("You still have a pending bet. Wait for it to resolve.")

        last_reset = _parse_iso(wallet.get("last_reset_at"))
        if last_reset is not None:
            cooldown_until = last_reset + timedelta(hours=RESET_COOLDOWN_HOURS)
            now = datetime.now(timezone.utc)
            if now < cooldown_until:
                remaining = cooldown_until - now
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                raise PorosError(f"Reset cooldown: {hours}h {minutes}m remaining.")

        wallet["balance"] = STARTING_BALANCE
        wallet["reset_count"] = wallet.get("reset_count", 0) + 1
        wallet["last_reset_at"] = _now_iso()
        _save(data)

        return {
            "balance": wallet["balance"],
            "reset_count": wallet["reset_count"],
        }


def resolve_market(outcome: str, match_id: str | None = None) -> dict:
    outcome = outcome.lower()
    if outcome not in {"win", "loss"}:
        raise PorosError("Outcome must be win or loss.")

    with _lock:
        data = _load()
        market = data.get("current_market")
        if market is None or market.get("status") != "open":
            return _empty_settlement("no_market", outcome)

        now = _now_iso()
        results = []
        paid = 0
        lost = 0

        for bet in data["bets"]:
            if bet["status"] != "pending" or bet["market_id"] != market["market_id"]:
                continue

            wallet = _ensure_wallet(data, bet["user_id"])
            won = bet["prediction"] == outcome
            if won:
                multiplier = _multiplier_for(market, bet["prediction"])
                payout = _payout_amount(bet["amount"], multiplier)
                bet["status"] = "won"
                bet["payout"] = payout
                wallet["balance"] += payout
                wallet["total_won"] += payout
                wallet["bets_won"] += 1
                paid += 1
            else:
                payout = 0
                bet["status"] = "lost"
                bet["payout"] = 0
                wallet["total_lost"] += bet["amount"]
                wallet["bets_lost"] += 1
                lost += 1

            bet["resolved_at"] = now
            results.append(
                {
                    "user_id": bet["user_id"],
                    "prediction": bet["prediction"],
                    "amount": bet["amount"],
                    "status": bet["status"],
                    "payout": payout,
                    "balance": wallet["balance"],
                }
            )

        market["status"] = "resolved"
        market["match_id"] = match_id
        market["resolution"] = outcome
        market["resolved_at"] = now
        _archive_market(data, reason=outcome)
        _open_new_market(data)
        _save(data)

        return {
            "status": "resolved",
            "outcome": outcome,
            "paid": paid,
            "lost": lost,
            "refunded": 0,
            "results": results,
            "market_id": market["market_id"],
        }


def refund_market(match_id: str | None = None, reason: str = "refund") -> dict:
    with _lock:
        data = _load()
        market = data.get("current_market")
        if market is None or market.get("status") != "open":
            return _empty_settlement("no_market")

        now = _now_iso()
        results = []
        refunded = 0

        for bet in data["bets"]:
            if bet["status"] != "pending" or bet["market_id"] != market["market_id"]:
                continue

            wallet = _ensure_wallet(data, bet["user_id"])
            wallet["balance"] += bet["amount"]
            wallet["total_wagered"] = max(0, wallet["total_wagered"] - bet["amount"])
            bet["status"] = "refunded"
            bet["payout"] = bet["amount"]
            bet["resolved_at"] = now
            refunded += 1
            results.append(
                {
                    "user_id": bet["user_id"],
                    "prediction": bet["prediction"],
                    "amount": bet["amount"],
                    "status": "refunded",
                    "payout": bet["amount"],
                    "balance": wallet["balance"],
                }
            )

        market["status"] = "cancelled"
        market["match_id"] = match_id
        market["resolution"] = reason
        market["resolved_at"] = now
        _archive_market(data, reason=reason)
        _open_new_market(data)
        _save(data)

        return {
            "status": "refunded",
            "outcome": reason,
            "paid": 0,
            "lost": 0,
            "refunded": refunded,
            "results": results,
            "market_id": market["market_id"],
        }


def format_settlement(settlement: dict) -> str | None:
    status = settlement.get("status")
    results = settlement.get("results") or []

    if status == "no_market":
        return None

    if status == "refunded":
        reason = settlement.get("outcome") or "cancelled"
        label = "Remake" if reason == "remake" else "Unresolved match"
        if not results:
            return f"Poro bets refunded ({label.lower()}). No bets were in."
        lines = [f"Poro bets refunded ({label.lower()})."]
        for row in results:
            lines.append(
                f"<@{row['user_id']}> +{row['payout']} Poros returned"
            )
        return "\n".join(lines)

    outcome = settlement.get("outcome")
    title = "a.lin WON" if outcome == "win" else "a.lin LOST"
    if not results:
        return f"Poro settlement: {title}. No bets were in."

    lines = [
        f"Poro settlement: {title} — {settlement['paid']} paid, {settlement['lost']} lost"
    ]
    for row in results:
        if row["status"] == "won":
            profit = row["payout"] - row["amount"]
            lines.append(
                f"<@{row['user_id']}> +{row['payout']} Poros (bet {row['amount']} on {row['prediction']}, {profit:+d} net)"
            )
        else:
            lines.append(
                f"<@{row['user_id']}> lost {row['amount']} Poros (bet on {row['prediction']})"
            )
    return "\n".join(lines)
