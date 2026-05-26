#!/usr/bin/env python3
"""Static site + economic calendar API for the Institutional Trading sales page."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("TRADING_DATA_DIR", ROOT)).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
PARIS = ZoneInfo("Europe/Paris") if ZoneInfo else timezone(timedelta(hours=2))
TRADING_ECONOMICS_URL = "https://api.tradingeconomics.com/calendar/country/united%20states"
FOREX_FACTORY_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json",
]
CALENDAR_CACHE_SECONDS = 300
CALENDAR_CACHE: dict[str, Any] = {"expires_at": None, "payload": None}
ACCESS_REQUESTS_FILE = DATA_DIR / "access_requests.json"
PAYPAL_EVENTS_FILE = DATA_DIR / "paypal_events.json"
DONATIONS_FILE = DATA_DIR / "donations.json"
ANALYTICS_FILE = DATA_DIR / "analytics.json"
SITE_CONFIG_FILE = DATA_DIR / "site_config.json"
CHAT_MESSAGES_FILE = DATA_DIR / "chat_messages.json"
ACCESS_REQUESTS_LOCK = threading.Lock()
ADMIN_PASSWORD = os.environ.get("TRADING_ADMIN_PASSWORD", "ghostadmin")
ADMIN_ACCESS_KEY = os.environ.get("TRADING_ADMIN_KEY", "audin-private-2026")
PAYPAL_WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID", "")
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_API_BASE = os.environ.get("PAYPAL_API_BASE", "https://api-m.paypal.com")
PAYPAL_ALLOW_UNVERIFIED = os.environ.get("PAYPAL_WEBHOOK_ALLOW_UNVERIFIED", "").lower() in {"1", "true", "yes"}
PAYPAL_PRICE_EUR = 49.99
PAYPAL_PAYMENT_URL = os.environ.get("TRADING_PAYPAL_URL", "https://www.paypal.com/ncp/payment/DCVU8JTEY7GJ4")
PAYPAL_PAYMENT_URLS = {
    "gold": "https://www.paypal.com/ncp/payment/DCVU8JTEY7GJ4",
    "nasdaq": "https://www.paypal.com/ncp/payment/VMTBQ5G9EMWTU",
    "btc": "https://www.paypal.com/ncp/payment/SB6UU4KPJ974A",
}
PRODUCT_LABELS = {
    "btc": "BTC Institutional Setup - 49,99 EUR / mois",
    "gold": "Gold Institutional Setup - 49,99 EUR / mois",
    "nasdaq": "Nasdaq Institutional Setup - 49,99 EUR / mois",
}
DONATION_EMAIL = os.environ.get("TRADING_DONATION_EMAIL", "Mehdi.parisville@outlook.com")
DONATION_URL = os.environ.get(
    "TRADING_DONATION_URL",
    f"https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business={quote(DONATION_EMAIL)}&currency_code=EUR&item_name=Institutional%20Trading%20Donation&custom=donation",
)


def now_paris() -> datetime:
    return datetime.now(PARIS).replace(microsecond=0)


def format_date_label(value: datetime) -> str:
    weekdays = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    months = ["jan", "fev", "mar", "avr", "mai", "juin", "juil", "aout", "sep", "oct", "nov", "dec"]
    return f"{weekdays[value.weekday()]} {value.day:02d} {months[value.month - 1]}"


def parse_provider_date(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.startswith("/Date(") and text.endswith(")/"):
        try:
            millis = int(text[6:-2].split("+", 1)[0].split("-", 1)[0])
            return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).astimezone(PARIS)
        except ValueError:
            return None
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(PARIS)


def markets_for_event(title: str, category: str) -> list[str]:
    haystack = f"{title} {category}".lower()
    markets = {"macro"}
    if any(word in haystack for word in ["cpi", "inflation", "ppi", "pce", "fed", "fomc", "rate", "yields", "payroll", "unemployment", "claims"]):
        markets.add("gold")
    if any(word in haystack for word in ["cpi", "ppi", "pce", "fed", "fomc", "retail", "payroll", "unemployment", "claims", "sentiment"]):
        markets.add("btc")
    if any(word in haystack for word in ["retail", "industrial", "pmi", "ism", "gdp", "sentiment", "confidence", "fed", "fomc", "payroll", "claims"]):
        markets.add("indices")
    return sorted(markets)


def relevant_event(title: str, category: str) -> bool:
    haystack = f"{title} {category}".lower()
    keywords = [
        "cpi",
        "consumer price",
        "ppi",
        "producer price",
        "pce",
        "inflation",
        "fomc",
        "fed",
        "interest rate",
        "non farm",
        "payroll",
        "unemployment",
        "jobless",
        "retail sales",
        "industrial production",
        "ism",
        "pmi",
        "gdp",
        "consumer sentiment",
        "consumer confidence",
    ]
    return any(keyword in haystack for keyword in keywords)


def event_copy(title: str, markets: list[str]) -> tuple[str, str, str]:
    haystack = title.lower()
    if any(word in haystack for word in ["cpi", "inflation", "ppi", "pce"]):
        return (
            "Inflation = taux, dollar, volatilite",
            "Verifier le consensus puis la reaction DXY / US10Y. Gold et BTC peuvent partir vite si les taux reels bougent.",
            "Attendre la premiere impulsion, puis chercher reprise ou invalidation sur niveau propre.",
        )
    if any(word in haystack for word in ["fed", "fomc", "rate"]):
        return (
            "Fed = volatilite taux / dollar",
            "Le marche lit le ton hawkish ou dovish. Impact direct sur Gold, Nasdaq, BTC et rendements US.",
            "Ne pas courir la premiere bougie. Lire le deuxieme mouvement et la confirmation inter-marche.",
        )
    if any(word in haystack for word in ["payroll", "unemployment", "jobless"]):
        return (
            "Emploi US = gros catalyseur",
            "Comparer emploi, chomage et salaires. La reaction peut changer si les sous-composantes se contredisent.",
            "Surveiller dollar, rendements et Nasdaq avant de valider un signal BTC ou Gold.",
        )
    if any(word in haystack for word in ["retail", "sentiment", "confidence"]):
        return (
            "Consommation = regime de risque",
            "Les chiffres consommateurs donnent le ton risk-on / risk-off pour indices et BTC.",
            "Verifier si Nasdaq confirme le mouvement. Gold reste sensible au dollar et aux taux.",
        )
    return (
        "Catalyseur macro a surveiller",
        "Verifier consensus, chiffre publie, dollar, rendements US et reaction des indices.",
        "Attendre que la volatilite initiale se calme avant de prendre le signal.",
    )


def accent_for(markets: list[str], tag: str) -> str:
    if tag in {"High impact", "Impact fort"}:
        return "green"
    if "gold" in markets and "btc" not in markets:
        return "gold"
    if "btc" in markets and "gold" not in markets:
        return "blue"
    return "green"


def normalize_te_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    title = str(raw.get("Event") or raw.get("event") or raw.get("Category") or "Evenement marche").strip()
    category = str(raw.get("Category") or raw.get("category") or "").strip()
    date = parse_provider_date(raw.get("Date") or raw.get("date") or raw.get("LastUpdate"))
    if not date or not relevant_event(title, category):
        return None
    markets = markets_for_event(title, category)
    importance = str(raw.get("Importance") or raw.get("importance") or "")
    tag = "Impact fort" if importance == "3" or any(word in title.lower() for word in ["cpi", "fomc", "payroll", "pce"]) else "Macro"
    expected_title, expected, reaction = event_copy(title, markets)
    source_url = raw.get("URL") or raw.get("SourceURL") or "https://tradingeconomics.com/calendar"
    window = "Gold / BTC" if {"gold", "btc"}.issubset(markets) else "XAUUSD" if "gold" in markets else "BTC / Indices" if "btc" in markets else "Session US"
    return {
        "id": f"te-{raw.get('CalendarId') or raw.get('Ticker') or date.isoformat()}",
        "date": date.isoformat(),
        "dateLabel": format_date_label(date),
        "timeLabel": f"{date:%H:%M} Paris",
        "title": title,
        "copy": f"{category or 'Macro US'} : impact potentiel sur {', '.join(markets).replace('macro, ', '')}.",
        "source": source_url,
        "markets": markets,
        "window": window,
        "tag": tag,
        "accent": accent_for(markets, tag),
        "expectedTitle": expected_title,
        "expected": expected,
        "reaction": reaction,
    }


def normalize_ff_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    title = str(raw.get("title") or "Evenement marche").strip()
    country = str(raw.get("country") or "").strip().upper()
    impact = str(raw.get("impact") or "").strip()
    date = parse_provider_date(raw.get("date"))
    if country != "USD" or not date or impact not in {"High", "Medium"}:
        return None
    if not relevant_event(title, "USD"):
        return None

    markets = markets_for_event(title, "USD")
    tag = "Impact fort" if impact == "High" else "Macro"
    expected_title, expected, reaction = event_copy(title, markets)
    forecast = str(raw.get("forecast") or "").strip() or "n/a"
    previous = str(raw.get("previous") or "").strip() or "n/a"
    window = "Gold / BTC" if {"gold", "btc"}.issubset(markets) else "XAUUSD" if "gold" in markets else "BTC / Indices" if "btc" in markets else "Session US"
    return {
        "id": f"ff-{country}-{title}-{date.isoformat()}",
        "date": date.isoformat(),
        "dateLabel": format_date_label(date),
        "timeLabel": f"{date:%H:%M} Paris",
        "title": title,
        "copy": f"Forecast {forecast} / previous {previous}. Impact potentiel sur {', '.join(markets).replace('macro, ', '')}.",
        "source": "https://www.forexfactory.com/calendar",
        "markets": markets,
        "window": window,
        "tag": tag,
        "accent": accent_for(markets, tag),
        "expectedTitle": expected_title,
        "expected": expected,
        "reaction": reaction,
    }


def fetch_trading_economics() -> list[dict[str, Any]]:
    api_key = os.environ.get("TRADING_ECONOMICS_KEY", "guest:guest")
    url = f"{TRADING_ECONOMICS_URL}?c={quote(api_key, safe=':')}&importance=3"
    request = Request(url, headers={"User-Agent": "InstitutionalTradingCalendar/1.0"})
    with urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        return []
    start = now_paris() - timedelta(days=1)
    end = now_paris() + timedelta(days=45)
    events = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        event = normalize_te_event(raw)
        if not event:
            continue
        event_date = parse_provider_date(event["date"])
        if event_date and start <= event_date <= end:
            events.append(event)
    return sorted(events, key=lambda item: item["date"])[:18]


def fetch_forex_factory() -> list[dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) InstitutionalTradingCalendar/1.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.forexfactory.com/",
    }
    last_error: Exception | None = None
    payload: Any = []
    for url in FOREX_FACTORY_URLS:
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
            last_error = None
            break
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            last_error = error
    if last_error:
        raise last_error
    if not isinstance(payload, list):
        return []
    start = now_paris() - timedelta(hours=12)
    end = now_paris() + timedelta(days=14)
    events = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        event = normalize_ff_event(raw)
        if not event:
            continue
        event_date = parse_provider_date(event["date"])
        if event_date and start <= event_date <= end:
            events.append(event)
    return sorted(events, key=lambda item: item["date"])[:18]


def fallback_events() -> list[dict[str, Any]]:
    def next_weekday(weekday: int, hour: int, minute: int = 30, min_days: int = 0) -> datetime:
        base = now_paris()
        days = (weekday - base.weekday()) % 7
        if days < min_days:
            days += 7
        candidate = (base + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= base + timedelta(hours=2):
            candidate += timedelta(days=7)
        return candidate

    events = [
        (next_weekday(3, 14, 30), "Inscriptions chomage US", "Emploi US, dollar, rendements et reaction indices.", "https://www.dol.gov/ui/data.pdf", ["macro", "gold", "btc", "indices"], "Gold / BTC", "Impact fort", "green"),
        (next_weekday(2, 20, 0, 1), "Communication Fed", "Ton Fed, taux, dollar et risque de volatilite sur Gold, BTC et Nasdaq.", "https://www.federalreserve.gov/newsevents/calendar.htm", ["macro", "gold", "btc", "indices"], "Fed / taux", "Macro", "gold"),
        (next_weekday(4, 15, 45, 2), "PMI US / croissance", "Activite US et sentiment marche : surveiller indices, DXY et rendements.", "https://www.spglobal.com/marketintelligence/en/mi/products/pmi.html", ["macro", "gold", "indices"], "Session US", "Macro", "blue"),
        (next_weekday(1, 14, 30, 3), "Inflation US", "Inflation et taux reels : catalyseur majeur pour Gold, BTC et indices.", "https://www.bls.gov/schedule/news_release/cpi.htm", ["macro", "gold", "btc", "indices"], "Gold / BTC", "Impact fort", "green"),
    ]
    output = []
    for index, (date, title, copy, source, markets, window, tag, accent) in enumerate(events):
        expected_title, expected, reaction = event_copy(title, markets)
        output.append({
            "id": f"fallback-{index}",
            "date": date.isoformat(),
            "dateLabel": format_date_label(date),
            "timeLabel": f"{date:%H:%M} Paris",
            "title": title,
            "copy": copy,
            "source": source,
            "markets": markets,
            "window": window,
            "tag": tag,
            "accent": accent,
            "expectedTitle": expected_title,
            "expected": expected,
            "reaction": reaction,
        })
    return sorted(output, key=lambda item: item["date"])


def calendar_payload() -> dict[str, Any]:
    cached_payload = CALENDAR_CACHE.get("payload")
    cached_expires = CALENDAR_CACHE.get("expires_at")
    if isinstance(cached_payload, dict) and isinstance(cached_expires, datetime) and now_paris() < cached_expires:
        return cached_payload

    provider = "fallback"
    status = "local_fallback"
    events: list[dict[str, Any]] = []

    try:
        if os.environ.get("TRADING_ECONOMICS_KEY"):
            events = fetch_trading_economics()
            provider = "tradingeconomics"
            status = "live"
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        status = f"tradingeconomics_unavailable: {error.__class__.__name__}"

    if not events:
        try:
            events = fetch_forex_factory()
            if events:
                provider = "forexfactory"
                status = "live"
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            status = f"forexfactory_unavailable: {error.__class__.__name__}"

    if not events:
        events = fallback_events()

    payload = {
        "provider": provider,
        "status": status,
        "updated_at": now_paris().isoformat(),
        "timezone": "Europe/Paris",
        "events": events,
    }
    CALENDAR_CACHE["payload"] = payload
    CALENDAR_CACHE["expires_at"] = now_paris() + timedelta(seconds=CALENDAR_CACHE_SECONDS)
    return payload


def clean_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return " ".join(text.split())[:limit]


def clean_image_data(value: Any) -> str:
    text = str(value or "").strip()
    if not text.startswith("data:image/"):
        return ""
    header, separator, payload = text.partition(",")
    if separator != "," or ";base64" not in header:
        return ""
    if len(text) > 5_500_000:
        return ""
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    if not payload or any(char not in allowed for char in payload[:2000]):
        return ""
    return text


def load_access_requests() -> list[dict[str, Any]]:
    if not ACCESS_REQUESTS_FILE.exists():
        return []
    try:
        payload = json.loads(ACCESS_REQUESTS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def save_access_requests(requests: list[dict[str, Any]]) -> None:
    ACCESS_REQUESTS_FILE.write_text(json.dumps(requests, ensure_ascii=True, indent=2), encoding="utf-8")


def load_paypal_events() -> list[dict[str, Any]]:
    if not PAYPAL_EVENTS_FILE.exists():
        return []
    try:
        payload = json.loads(PAYPAL_EVENTS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def save_paypal_events(events: list[dict[str, Any]]) -> None:
    PAYPAL_EVENTS_FILE.write_text(json.dumps(events[:250], ensure_ascii=True, indent=2), encoding="utf-8")


def load_donations() -> list[dict[str, Any]]:
    if not DONATIONS_FILE.exists():
        return []
    try:
        payload = json.loads(DONATIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def save_donations(donations: list[dict[str, Any]]) -> None:
    DONATIONS_FILE.write_text(json.dumps(donations[:500], ensure_ascii=True, indent=2), encoding="utf-8")


def load_chat_messages() -> list[dict[str, Any]]:
    if not CHAT_MESSAGES_FILE.exists():
        return []
    try:
        payload = json.loads(CHAT_MESSAGES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def save_chat_messages(messages: list[dict[str, Any]]) -> None:
    CHAT_MESSAGES_FILE.write_text(json.dumps(messages[:500], ensure_ascii=True, indent=2), encoding="utf-8")


def create_chat_message(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    email = clean_text(data.get("email"), 180).lower()
    message = clean_text(data.get("message"), 1200)
    if not email or not message:
        return False, {"ok": False, "error": "missing_fields"}
    item = {
        "id": f"chat-{now_paris():%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
        "created_at": now_paris().isoformat(),
        "sender": "client",
        "status": "open",
        "name": clean_text(data.get("name"), 120),
        "email": email,
        "message": message,
    }
    with ACCESS_REQUESTS_LOCK:
        messages = load_chat_messages()
        messages.insert(0, item)
        save_chat_messages(messages)
    return True, {"ok": True, "message": item}


def reply_chat_message(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    email = clean_text(data.get("email"), 180).lower()
    message = clean_text(data.get("message"), 1200)
    if not email or not message:
        return False, {"ok": False, "error": "missing_fields"}
    item = {
        "id": f"chat-{now_paris():%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
        "created_at": now_paris().isoformat(),
        "sender": "admin",
        "status": "answered",
        "name": "Admin",
        "email": email,
        "message": message,
    }
    with ACCESS_REQUESTS_LOCK:
        messages = load_chat_messages()
        messages.insert(0, item)
        save_chat_messages(messages)
    return True, {"ok": True, "message": item}


def default_site_config() -> dict[str, Any]:
    return {
        "flash": {
            "active": False,
            "title": "",
            "copy": "",
            "cta": "Voir l'offre",
            "url": "#offers",
            "endsAt": "",
        }
    }


def load_site_config() -> dict[str, Any]:
    if not SITE_CONFIG_FILE.exists():
        return default_site_config()
    try:
        payload = json.loads(SITE_CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default_site_config()
    config = default_site_config()
    if isinstance(payload, dict):
        flash = payload.get("flash")
        if isinstance(flash, dict):
            config["flash"].update({key: flash.get(key, config["flash"][key]) for key in config["flash"]})
    return config


def save_site_config(config: dict[str, Any]) -> None:
    SITE_CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=True, indent=2), encoding="utf-8")


def parse_local_datetime(value: Any) -> datetime | None:
    text = clean_text(value, 80)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PARIS)
    return parsed.astimezone(PARIS)


def public_flash_payload() -> dict[str, Any]:
    flash = dict(load_site_config().get("flash", {}))
    ends_at = parse_local_datetime(flash.get("endsAt"))
    if not flash.get("active") or not clean_text(flash.get("title"), 90):
        flash["active"] = False
    if ends_at and ends_at <= now_paris():
        flash["active"] = False
    return flash


def load_analytics() -> dict[str, Any]:
    if not ANALYTICS_FILE.exists():
        return {"sessions": {}, "events": []}
    try:
        payload = json.loads(ANALYTICS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"sessions": {}, "events": []}
    if not isinstance(payload, dict):
        return {"sessions": {}, "events": []}
    sessions = payload.get("sessions") if isinstance(payload.get("sessions"), dict) else {}
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    return {"sessions": sessions, "events": events}


def save_analytics(payload: dict[str, Any]) -> None:
    sessions = payload.get("sessions") if isinstance(payload.get("sessions"), dict) else {}
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    ANALYTICS_FILE.write_text(json.dumps({"sessions": sessions, "events": events[:2500]}, ensure_ascii=True, indent=2), encoding="utf-8")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 120_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = encoded.split("$", 3)
        iterations = int(iterations_text)
    except (ValueError, AttributeError):
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), iterations).hex()
    return hmac.compare_digest(digest, expected)


def normalize_referral_code(value: Any) -> str:
    text = clean_text(value, 40).upper()
    return "".join(char for char in text if char.isalnum())[:18]


def make_referral_code(name: str, tradingview: str, requests: list[dict[str, Any]]) -> str:
    seed = normalize_referral_code(tradingview or name)[:8] or "TRADING"
    existing = {normalize_referral_code(item.get("referralCode")) for item in requests}
    candidate = f"TI{seed}"
    if candidate not in existing:
        return candidate
    for index in range(2, 1000):
        candidate = f"TI{seed}{index}"
        if candidate not in existing:
            return candidate
    return f"TI{uuid4().hex[:10].upper()}"


def referral_summary(requests: list[dict[str, Any]], item: dict[str, Any]) -> dict[str, Any]:
    code = normalize_referral_code(item.get("referralCode"))
    approved = [
        child for child in requests
        if normalize_referral_code(child.get("usedReferralCode")) == code and child.get("status") == "approved"
    ]
    pending = [
        child for child in requests
        if normalize_referral_code(child.get("usedReferralCode")) == code and child.get("status") == "pending"
    ]
    count = len(approved)
    if count >= 10:
        reward = "1 mois gratuit"
        next_target = 10
        remaining = 0
    elif count >= 5:
        reward = "Bot a -50%"
        next_target = 10
        remaining = 10 - count
    else:
        reward = "Aucun palier atteint"
        next_target = 5
        remaining = 5 - count
    return {
        "code": code,
        "approvedCount": count,
        "pendingCount": len(pending),
        "nextTarget": next_target,
        "remaining": remaining,
        "reward": reward,
        "rules": [
            {"target": 5, "reward": "Bot a -50%"},
            {"target": 10, "reward": "1 mois gratuit"},
        ],
    }


def default_subscription_end() -> str:
    return (now_paris() + timedelta(days=30)).replace(microsecond=0).isoformat()


def normalize_subscription_end(value: Any) -> str:
    text = clean_text(value, 60)
    if not text:
        return ""
    try:
        if len(text) == 10:
            parsed = datetime.fromisoformat(text).replace(hour=23, minute=59, second=59, tzinfo=PARIS)
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=PARIS)
            parsed = parsed.astimezone(PARIS)
        return parsed.replace(microsecond=0).isoformat()
    except ValueError:
        return ""


def days_remaining(subscription_end: str) -> int:
    parsed = parse_provider_date(subscription_end)
    if not parsed:
        return 0
    delta = parsed - now_paris()
    return max(0, int(delta.total_seconds() // 86400))


def extend_subscription(item: dict[str, Any], event: dict[str, Any], transaction_id: str) -> None:
    current_end = parse_provider_date(item.get("subscriptionEnd"))
    start_from = current_end if current_end and current_end > now_paris() else now_paris()
    new_end = (start_from + timedelta(days=30)).replace(microsecond=0)
    now = now_paris().isoformat()
    item["status"] = "approved"
    item["subscriptionStart"] = item.get("subscriptionStart") or now
    item["subscriptionEnd"] = new_end.isoformat()
    item["lastPaymentAt"] = now
    item["lastPayPalEventId"] = clean_text(event.get("id"), 120)
    item["lastPayPalTransactionId"] = clean_text(transaction_id, 120)
    item["updated_at"] = now
    history = item.get("paymentHistory")
    if not isinstance(history, list):
        history = []
    history.insert(0, {
        "at": now,
        "eventId": clean_text(event.get("id"), 120),
        "transactionId": clean_text(transaction_id, 120),
        "source": "paypal_webhook",
    })
    item["paymentHistory"] = history[:24]


def paypal_url_for_product(product: str) -> str:
    text = clean_text(product, 240).lower()
    if "+" in text or "par setup" in text or "setups" in text:
        return "#offers"
    if "nasdaq" in text:
        return PAYPAL_PAYMENT_URLS["nasdaq"]
    if "btc" in text:
        return PAYPAL_PAYMENT_URLS["btc"]
    if "gold" in text:
        return PAYPAL_PAYMENT_URLS["gold"]
    return PAYPAL_PAYMENT_URL


def normalize_products(data: dict[str, Any]) -> list[str]:
    raw_products = data.get("products")
    values: list[str] = []
    if isinstance(raw_products, list):
        values.extend(clean_text(item, 180) for item in raw_products)
    elif isinstance(raw_products, str):
        values.append(clean_text(raw_products, 320))
    values.append(clean_text(data.get("product"), 320))
    haystack = " ".join(values).lower()
    selected = [label for key, label in PRODUCT_LABELS.items() if key in haystack]
    if selected:
        return selected[:3]
    fallback = clean_text(data.get("product"), 320)
    return [fallback] if fallback else []


def product_summary(products: list[str]) -> str:
    if not products:
        return "Institutional Trading Setup - 49,99 EUR / mois"
    if len(products) == 1:
        return products[0]
    names = []
    for product in products:
        text = product.lower()
        if "btc" in text:
            names.append("BTC")
        elif "gold" in text:
            names.append("Gold")
        elif "nasdaq" in text:
            names.append("Nasdaq")
    if names:
        return f"{' + '.join(names)} Institutional Setups - 49,99 EUR / mois par setup"
    return clean_text(" + ".join(products), 320)


def public_client_payload(item: dict[str, Any]) -> dict[str, Any]:
    subscription_end = str(item.get("subscriptionEnd") or "")
    requests = load_access_requests()
    product = item.get("product", "Institutional Trading Setup - 49,99 EUR / mois")
    products = item.get("products") if isinstance(item.get("products"), list) else normalize_products({"product": product})
    return {
        "id": item.get("id"),
        "status": item.get("status", "pending"),
        "name": item.get("name", ""),
        "email": item.get("email", ""),
        "tradingview": item.get("tradingview", ""),
        "product": product,
        "products": products,
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
        "subscriptionStart": item.get("subscriptionStart", ""),
        "subscriptionEnd": subscription_end,
        "daysRemaining": days_remaining(subscription_end),
        "paypalUrl": paypal_url_for_product(product),
        "donationUrl": DONATION_URL,
        "referral": referral_summary(requests, item),
        "setups": [
            {"name": "BTC Institutional Setup", "market": "BTC", "session": "24/7", "wr": "85.3%", "pf": "2.98"},
            {"name": "Gold Institutional Setup", "market": "Gold", "session": "London / New York / Asia", "wr": "83.0%", "pf": "2.70"},
            {"name": "Nasdaq Institutional Setup", "market": "US100", "session": "London / New York / Asia", "wr": "81.3%", "pf": "3.40"},
        ],
    }


def create_access_request(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    required = {
        "name": clean_text(data.get("name"), 120),
        "email": clean_text(data.get("email"), 180),
        "tradingview": clean_text(data.get("tradingview"), 120),
        "paymentProof": clean_text(data.get("paymentProof"), 400),
        "clientPassword": clean_text(data.get("clientPassword"), 200),
    }
    missing = [label for label, value in required.items() if not value]
    if missing:
        return False, {"ok": False, "error": "missing_fields", "fields": missing}
    if len(required["clientPassword"]) < 6:
        return False, {"ok": False, "error": "password_too_short"}

    products = normalize_products(data)
    now = now_paris().isoformat()
    item = {
        "id": f"req-{now_paris():%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
        "created_at": now,
        "updated_at": now,
        "status": "pending",
        "name": required["name"],
        "email": required["email"],
        "tradingview": required["tradingview"],
        "paymentProof": required["paymentProof"],
        "paymentProofImage": clean_image_data(data.get("paymentProofImage")),
        "passwordHash": hash_password(required["clientPassword"]),
        "product": product_summary(products),
        "products": products,
        "message": clean_text(data.get("message"), 1200),
        "adminNote": "",
        "subscriptionStart": "",
        "subscriptionEnd": "",
    }
    with ACCESS_REQUESTS_LOCK:
        requests = load_access_requests()
        used_referral = normalize_referral_code(data.get("referralCode"))
        item["referralCode"] = make_referral_code(required["name"], required["tradingview"], requests)
        item["usedReferralCode"] = used_referral
        item["referrerId"] = ""
        if used_referral:
            for referrer in requests:
                if normalize_referral_code(referrer.get("referralCode")) == used_referral:
                    item["referrerId"] = clean_text(referrer.get("id"), 120)
                    break
        requests.insert(0, item)
        save_access_requests(requests)
    return True, {"ok": True, "request": item}


def create_donation(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    return False, {"ok": False, "error": "payment_required", "donationUrl": DONATION_URL}


def update_site_config(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    config = load_site_config()
    flash = config.get("flash") if isinstance(config.get("flash"), dict) else default_site_config()["flash"]
    flash["active"] = bool(data.get("active"))
    flash["title"] = clean_text(data.get("title"), 90)
    flash["copy"] = clean_text(data.get("copy"), 180)
    flash["cta"] = clean_text(data.get("cta"), 40) or "Profiter de l'offre"
    flash["url"] = clean_text(data.get("url"), 400) or "#offers"
    flash["endsAt"] = clean_text(data.get("endsAt"), 80)
    if not flash["active"]:
        flash["title"] = ""
        flash["copy"] = ""
        flash["endsAt"] = ""
    config["flash"] = flash
    save_site_config(config)
    return True, {"ok": True, "config": config}


def track_visit(data: dict[str, Any], headers: Any, client_ip: str) -> dict[str, Any]:
    session_id = clean_text(data.get("sessionId"), 80) or f"s-{uuid4().hex}"
    page = clean_text(data.get("page"), 180) or "/"
    now = now_paris()
    now_iso = now.isoformat()
    analytics = load_analytics()
    sessions = analytics["sessions"]
    current = sessions.get(session_id) if isinstance(sessions.get(session_id), dict) else {}
    sessions[session_id] = {
        "id": session_id,
        "firstSeen": current.get("firstSeen") or now_iso,
        "lastSeen": now_iso,
        "page": page,
        "ip": client_ip,
        "userAgent": clean_text(headers.get("User-Agent", ""), 240),
    }
    analytics["events"].insert(0, {"at": now_iso, "sessionId": session_id, "page": page})
    cutoff = now - timedelta(days=14)
    analytics["events"] = [
        event for event in analytics["events"][:2500]
        if (parse_provider_date(event.get("at")) or now) >= cutoff
    ]
    save_analytics(analytics)
    return {"ok": True, "sessionId": session_id}


def analytics_summary() -> dict[str, Any]:
    analytics = load_analytics()
    now = now_paris()
    online_cutoff = now - timedelta(minutes=5)
    today_key = now.strftime("%Y-%m-%d")
    sessions = list(analytics["sessions"].values())
    online = [
        item for item in sessions
        if (parse_provider_date(item.get("lastSeen")) or datetime.fromtimestamp(0, PARIS)) >= online_cutoff
    ]
    events_today = [
        item for item in analytics["events"]
        if (parse_provider_date(item.get("at")) or now).strftime("%Y-%m-%d") == today_key
    ]
    pages: dict[str, int] = {}
    for event in events_today:
        page = clean_text(event.get("page"), 180) or "/"
        pages[page] = pages.get(page, 0) + 1
    top_pages = [{"page": page, "views": views} for page, views in sorted(pages.items(), key=lambda item: item[1], reverse=True)[:8]]
    return {
        "ok": True,
        "online": len(online),
        "visitorsToday": len({clean_text(item.get("sessionId"), 80) for item in events_today}),
        "pageViewsToday": len(events_today),
        "totalVisitors": len(sessions),
        "topPages": top_pages,
        "onlineSessions": sorted(online, key=lambda item: item.get("lastSeen", ""), reverse=True)[:20],
        "updated_at": now.isoformat(),
    }


def update_donation_status(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    donation_id = clean_text(data.get("id"), 80)
    status = clean_text(data.get("status"), 40) or "pending"
    if status not in {"pending", "confirmed", "rejected"}:
        return False, {"ok": False, "error": "invalid_status"}
    with ACCESS_REQUESTS_LOCK:
        donations = load_donations()
        for item in donations:
            if item.get("id") == donation_id:
                item["status"] = status
                item["adminNote"] = clean_text(data.get("adminNote"), 800)
                item["updated_at"] = now_paris().isoformat()
                save_donations(donations)
                return True, {"ok": True, "donation": item}
    return False, {"ok": False, "error": "not_found"}


def update_access_request_status(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    request_id = clean_text(data.get("id"), 80)
    status = clean_text(data.get("status"), 40) or "pending"
    if status not in {"pending", "approved", "rejected"}:
        return False, {"ok": False, "error": "invalid_status"}
    with ACCESS_REQUESTS_LOCK:
        requests = load_access_requests()
        for item in requests:
            if item.get("id") == request_id:
                subscription_end = normalize_subscription_end(data.get("subscriptionEnd"))
                item["status"] = status
                item["adminNote"] = clean_text(data.get("adminNote"), 800)
                if subscription_end:
                    item["subscriptionEnd"] = subscription_end
                elif status == "approved" and not item.get("subscriptionEnd"):
                    item["subscriptionEnd"] = default_subscription_end()
                if status == "approved" and not item.get("subscriptionStart"):
                    item["subscriptionStart"] = now_paris().isoformat()
                item["updated_at"] = now_paris().isoformat()
                save_access_requests(requests)
                return True, {"ok": True, "request": item}
    return False, {"ok": False, "error": "not_found"}


def client_login(data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    email = clean_text(data.get("email"), 180).lower()
    password = clean_text(data.get("password"), 200)
    tradingview = clean_text(data.get("tradingview"), 120).lower()
    if not email or not (password or tradingview):
        return False, {"ok": False, "error": "missing_fields"}

    requests = load_access_requests()
    for item in requests:
        if clean_text(item.get("email"), 180).lower() != email:
            continue
        stored_password = clean_text(item.get("passwordHash"), 500)
        if stored_password:
            if verify_password(password, stored_password):
                return True, {"ok": True, "client": public_client_payload(item)}
        elif tradingview and clean_text(item.get("tradingview"), 120).lower() == tradingview:
            return True, {"ok": True, "client": public_client_payload(item)}
    return False, {"ok": False, "error": "not_found"}


def deep_find_email(value: Any) -> str:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in {"email", "email_address", "payer_email"}:
                text = clean_text(child, 180)
                if "@" in text:
                    return text
        for child in value.values():
            found = deep_find_email(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = deep_find_email(child)
            if found:
                return found
    return ""


def deep_find_amount(value: Any) -> tuple[str, float | None]:
    if isinstance(value, dict):
        currency = clean_text(value.get("currency_code") or value.get("currency"), 12).upper()
        raw_amount = value.get("value") or value.get("amount")
        if currency and raw_amount is not None:
            try:
                return currency, float(str(raw_amount).replace(",", "."))
            except ValueError:
                pass
        for child in value.values():
            found_currency, found_amount = deep_find_amount(child)
            if found_currency or found_amount is not None:
                return found_currency, found_amount
    if isinstance(value, list):
        for child in value:
            found_currency, found_amount = deep_find_amount(child)
            if found_currency or found_amount is not None:
                return found_currency, found_amount
    return "", None


def paypal_transaction_id(event: dict[str, Any]) -> str:
    resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
    candidates = [
        resource.get("id"),
        resource.get("sale_id"),
        resource.get("capture_id"),
        event.get("resource_id"),
        event.get("id"),
    ]
    for value in candidates:
        text = clean_text(value, 120)
        if text:
            return text
    return ""


def paypal_event_allowed(event_type: str, currency: str, amount: float | None) -> tuple[bool, str]:
    paid_events = {
        "PAYMENT.CAPTURE.COMPLETED",
        "PAYMENT.SALE.COMPLETED",
        "CHECKOUT.ORDER.COMPLETED",
        "BILLING.SUBSCRIPTION.PAYMENT.SUCCEEDED",
    }
    if event_type not in paid_events:
        return False, "event_not_payment_success"
    if currency and currency != "EUR":
        return False, "currency_not_eur"
    if amount is not None and amount <= 0:
        return False, "invalid_amount"
    return True, "ok"


def collect_paypal_text(value: Any) -> str:
    parts: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            if isinstance(child, (dict, list)):
                nested = collect_paypal_text(child)
                if nested:
                    parts.append(nested)
            elif isinstance(child, (str, int, float)):
                text = clean_text(child, 220)
                if text:
                    parts.append(text)
    elif isinstance(value, list):
        for child in value:
            nested = collect_paypal_text(child)
            if nested:
                parts.append(nested)
    return " ".join(parts)[:3000]


def paypal_payment_is_donation(event: dict[str, Any], amount: float | None) -> bool:
    text = collect_paypal_text(event).lower()
    markers = ("donation", "contribution", "soutien", "support_app", "site_support_app", "tip")
    return any(marker in text for marker in markers) or (amount is not None and amount + 0.01 < PAYPAL_PRICE_EUR)


def record_paypal_donation(
    donations: list[dict[str, Any]],
    event: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    transaction_id = clean_text(result.get("transaction_id"), 120)
    event_id = clean_text(result.get("id"), 120)
    for item in donations:
        if transaction_id and clean_text(item.get("transaction_id"), 120) == transaction_id:
            return item
        if event_id and clean_text(item.get("paypalEventId"), 120) == event_id:
            return item
    payer_email = clean_text(result.get("payer_email"), 180)
    amount = result.get("amount")
    now = now_paris().isoformat()
    item = {
        "id": f"don-{now_paris():%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
        "created_at": now,
        "updated_at": now,
        "status": "confirmed",
        "name": payer_email.split("@")[0] if payer_email else "PayPal",
        "email": payer_email,
        "amount": round(float(amount or 0), 2),
        "currency": clean_text(result.get("currency"), 12) or "EUR",
        "message": "Don confirme par PayPal",
        "transaction_id": transaction_id,
        "paypalEventId": event_id,
        "event_type": clean_text(result.get("event_type"), 120),
        "verified": bool(result.get("verified")),
        "verification_status": clean_text(result.get("verification_status"), 80),
        "source": "paypal_webhook",
    }
    donations.insert(0, item)
    return item


def paypal_oauth_token() -> str:
    token = base64.b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}".encode("utf-8")).decode("ascii")
    body = b"grant_type=client_credentials"
    request = Request(
        f"{PAYPAL_API_BASE}/v1/oauth2/token",
        data=body,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return clean_text(payload.get("access_token"), 500)


def verify_paypal_webhook(headers: Any, event: dict[str, Any]) -> tuple[bool, str]:
    if PAYPAL_ALLOW_UNVERIFIED:
        return True, "local_unverified_allowed"
    if not (PAYPAL_WEBHOOK_ID and PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET):
        return False, "verification_not_configured"
    token = paypal_oauth_token()
    verify_payload = {
        "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID", ""),
        "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME", ""),
        "cert_url": headers.get("PAYPAL-CERT-URL", ""),
        "auth_algo": headers.get("PAYPAL-AUTH-ALGO", ""),
        "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG", ""),
        "webhook_id": PAYPAL_WEBHOOK_ID,
        "webhook_event": event,
    }
    request = Request(
        f"{PAYPAL_API_BASE}/v1/notifications/verify-webhook-signature",
        data=json.dumps(verify_payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("verification_status") == "SUCCESS", clean_text(payload.get("verification_status"), 80)


def process_paypal_webhook(event: dict[str, Any], headers: Any) -> dict[str, Any]:
    event_id = clean_text(event.get("id"), 120)
    event_type = clean_text(event.get("event_type"), 120)
    resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
    payer_email = deep_find_email(resource or event).lower()
    currency, amount = deep_find_amount(resource or event)
    transaction_id = paypal_transaction_id(event)
    verified, verification_status = verify_paypal_webhook(headers, event)
    allowed, allow_reason = paypal_event_allowed(event_type, currency, amount)
    result = {
        "id": event_id or f"paypal-{now_paris():%Y%m%d%H%M%S}-{uuid4().hex[:8]}",
        "received_at": now_paris().isoformat(),
        "event_type": event_type,
        "transaction_id": transaction_id,
        "payer_email": payer_email,
        "currency": currency,
        "amount": amount,
        "verified": verified,
        "verification_status": verification_status,
        "matched_request_id": "",
        "matched_donation_id": "",
        "action": "logged",
        "reason": allow_reason,
    }

    with ACCESS_REQUESTS_LOCK:
        paypal_events = load_paypal_events()
        known_ids = {clean_text(item.get("id"), 120) for item in paypal_events}
        if result["id"] in known_ids:
            result["action"] = "duplicate_ignored"
            paypal_events.insert(0, result)
            save_paypal_events(paypal_events)
            return result

        if verified and allowed:
            requests = load_access_requests()
            is_donation = paypal_payment_is_donation(event, amount)
            if payer_email and not is_donation and (amount is None or amount + 0.01 >= PAYPAL_PRICE_EUR):
                for item in requests:
                    if clean_text(item.get("email"), 180).lower() == payer_email:
                        extend_subscription(item, event, transaction_id)
                        result["matched_request_id"] = clean_text(item.get("id"), 120)
                        result["action"] = "subscription_extended"
                        result["reason"] = "matched_by_paypal_email"
                        save_access_requests(requests)
                        break
            if not result["matched_request_id"]:
                if is_donation:
                    donations = load_donations()
                    donation = record_paypal_donation(donations, event, result)
                    save_donations(donations)
                    result["matched_donation_id"] = clean_text(donation.get("id"), 120)
                    result["action"] = "donation_recorded"
                    result["reason"] = "donation_payment"
                else:
                    result["action"] = "unmatched_payment"
                    result["reason"] = "paypal_email_not_found"
        elif not verified:
            result["reason"] = verification_status

        paypal_events.insert(0, result)
        save_paypal_events(paypal_events)
    return result


class InstitutionalTradingHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Password")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Password")
        self.end_headers()

    def is_admin(self) -> bool:
        return self.headers.get("X-Admin-Password", "") == ADMIN_PASSWORD

    def read_json_body(self) -> dict[str, Any]:
        raw = self.read_body_text()
        if not raw:
            return {}
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}

    def read_body_text(self) -> str:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 6_000_000:
            return ""
        return self.rfile.read(length).decode("utf-8")

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if path == "/admin.html":
            owner_key = parse_qs(parsed_url.query).get("owner", [""])[0]
            if owner_key != ADMIN_ACCESS_KEY:
                self.send_error(404)
                return
        if path == "/api/health":
            self.send_json({"ok": True, "updated_at": now_paris().isoformat()})
            return
        if path == "/api/calendar":
            self.send_json(calendar_payload())
            return
        if path == "/api/admin/access-requests":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            self.send_json({"ok": True, "requests": load_access_requests(), "updated_at": now_paris().isoformat()})
            return
        if path == "/api/admin/paypal-events":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            self.send_json({"ok": True, "events": load_paypal_events(), "updated_at": now_paris().isoformat()})
            return
        if path == "/api/admin/donations":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            donations = load_donations()
            total_confirmed = sum(float(item.get("amount") or 0) for item in donations if item.get("status") == "confirmed")
            self.send_json({"ok": True, "donations": donations, "totalConfirmed": round(total_confirmed, 2), "updated_at": now_paris().isoformat()})
            return
        if path == "/api/admin/analytics":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            self.send_json(analytics_summary())
            return
        if path == "/api/admin/site-config":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            self.send_json({"ok": True, "config": load_site_config(), "updated_at": now_paris().isoformat()})
            return
        if path == "/api/admin/chat":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            self.send_json({"ok": True, "messages": load_chat_messages(), "updated_at": now_paris().isoformat()})
            return
        if path == "/api/chat/thread":
            email = clean_text(parse_qs(parsed_url.query).get("email", [""])[0], 180).lower()
            messages = [item for item in load_chat_messages() if clean_text(item.get("email"), 180).lower() == email] if email else []
            self.send_json({"ok": True, "messages": list(reversed(messages[-60:]))})
            return
        if path == "/api/public-config":
            self.send_json({"ok": True, "paypalUrl": PAYPAL_PAYMENT_URL, "donationUrl": DONATION_URL, "donationEmail": DONATION_EMAIL, "flash": public_flash_payload()})
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/paypal/webhook":
            try:
                raw = self.read_body_text()
                event = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self.send_json({"ok": False, "error": "invalid_json"}, 400)
                return
            if not isinstance(event, dict):
                self.send_json({"ok": False, "error": "invalid_payload"}, 400)
                return
            try:
                result = process_paypal_webhook(event, self.headers)
            except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
                result = {"action": "verification_error", "reason": error.__class__.__name__}
            self.send_json({"ok": True, "result": result}, 202)
            return
        try:
            data = self.read_json_body()
        except json.JSONDecodeError:
            self.send_json({"ok": False, "error": "invalid_json"}, 400)
            return
        if path == "/api/access-requests":
            ok, payload = create_access_request(data)
            self.send_json(payload, 201 if ok else 400)
            return
        if path == "/api/donations":
            ok, payload = create_donation(data)
            self.send_json(payload, 201 if ok else 400)
            return
        if path == "/api/track":
            self.send_json(track_visit(data, self.headers, self.client_address[0]))
            return
        if path == "/api/chat/messages":
            ok, payload = create_chat_message(data)
            self.send_json(payload, 201 if ok else 400)
            return
        if path == "/api/admin/access-requests/status":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            ok, payload = update_access_request_status(data)
            self.send_json(payload, 200 if ok else 400)
            return
        if path == "/api/admin/donations/status":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            ok, payload = update_donation_status(data)
            self.send_json(payload, 200 if ok else 400)
            return
        if path == "/api/admin/site-config":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            ok, payload = update_site_config(data)
            self.send_json(payload, 200 if ok else 400)
            return
        if path == "/api/admin/chat/reply":
            if not self.is_admin():
                self.send_json({"ok": False, "error": "unauthorized"}, 401)
                return
            ok, payload = reply_chat_message(data)
            self.send_json(payload, 200 if ok else 400)
            return
        if path == "/api/client/login":
            ok, payload = client_login(data)
            self.send_json(payload, 200 if ok else 404)
            return
        self.send_json({"ok": False, "error": "not_found"}, 404)


def main() -> None:
    parser = argparse.ArgumentParser(description="Institutional Trading static site + calendar API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8795")))
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), InstitutionalTradingHandler)
    print(f"Institutional Trading API server: http://{args.host}:{args.port}/vente.html", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
