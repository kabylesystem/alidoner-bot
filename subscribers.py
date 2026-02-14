"""
AliDonerBot — Gestion des abonnés + commandes Telegram
Commandes :
  /start   — S'abonner
  /stop    — Se désabonner
  /status  — Vérifier son abonnement
  /last    — Recevoir le dernier recap
  /heure HH:MM — Choisir l'heure d'envoi
  /focus   — Choisir ses thèmes (coding, business, all)
  /subs    — Liste des abonnés (admin only)
"""
import os
import json
import time
import glob
import threading
import requests
from typing import Set, Dict, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUBSCRIBERS_FILE = os.path.join(BASE_DIR, "subscribers.json")
TELEGRAM_API = "https://api.telegram.org"

# ══════════════════════════════════════
# Messages
# ══════════════════════════════════════

WELCOME_MSG = """🥙 Bienvenue sur AliDonerBot !

Chaque matin à 9h, tu reçois un recap IA :
- Les 10 news les plus importantes des dernières 24h
- Résumés complets en français (pas besoin de cliquer)
- "Pourquoi ça compte" pour chaque news
- Un concept du jour expliqué simplement
- Une idée concrète à implémenter

Commandes :
/start — S'abonner au recap
/stop — Se désabonner
/status — Vérifier son abonnement
/last — Recevoir le dernier recap
/heure 7:30 — Choisir l'heure d'envoi
/focus — Choisir tes thèmes

C'est gratuit pour l'instant, sans pub. Profite !"""

GOODBYE_MSG = """👋 Tu es désabonné d'AliDonerBot.

Tu ne recevras plus le recap quotidien.
Fais /start à tout moment pour te réabonner."""

ALREADY_SUB_MSG = "✅ Tu es déjà abonné ! Tu recevras le prochain recap demain matin. C'est gratuit pour l'instant !"
STATUS_NOT_SUB_MSG = "❌ Tu n'es pas abonné. Fais /start pour t'inscrire."

FOCUS_HELP = """🎯 Choisis tes thèmes :

/focus all — Tout recevoir (défaut)
/focus coding — Modèles, open source, outils dev, GitHub
/focus business — Levées, acquisitions, produits, régulation

Tu peux combiner : /focus coding business"""

FOCUS_THEMES = {
    "coding": ["Model", "Infra", "Other"],
    "business": ["Business", "Product", "Security"],
}

# ══════════════════════════════════════
# Data layer — subscribers.json
# Format: {"subscribers": {"chat_id": {"hour": "09:00", "focus": ["all"]}}}
# ══════════════════════════════════════

def _load_data() -> Dict:
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r") as f:
                data = json.load(f)
                # Migration: old format (list) → new format (dict)
                if isinstance(data.get("subscribers"), list):
                    old = data["subscribers"]
                    data["subscribers"] = {str(cid): {"hour": "09:00", "focus": ["all"]} for cid in old}
                    _save_data(data)
                return data
        except (json.JSONDecodeError, IOError):
            pass
    return {"subscribers": {}}


def _save_data(data: Dict):
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_subscribers() -> Set[str]:
    return set(_load_data().get("subscribers", {}).keys())


def save_subscribers(subs: Set[str]):
    """Legacy compat"""
    data = _load_data()
    existing = data.get("subscribers", {})
    for cid in subs:
        if cid not in existing:
            existing[cid] = {"hour": "09:00", "focus": ["all"]}
    # Remove unsubscribed
    for cid in list(existing.keys()):
        if cid not in subs:
            del existing[cid]
    data["subscribers"] = existing
    _save_data(data)


def add_subscriber(chat_id: str) -> bool:
    data = _load_data()
    chat_id = str(chat_id)
    subs = data.get("subscribers", {})
    if chat_id in subs:
        return False
    subs[chat_id] = {"hour": "09:00", "focus": ["all"]}
    data["subscribers"] = subs
    _save_data(data)
    return True


def remove_subscriber(chat_id: str) -> bool:
    data = _load_data()
    chat_id = str(chat_id)
    subs = data.get("subscribers", {})
    if chat_id not in subs:
        return False
    del subs[chat_id]
    data["subscribers"] = subs
    _save_data(data)
    return True


def get_all_subscribers() -> Set[str]:
    return load_subscribers()


def get_subscriber_prefs(chat_id: str) -> Dict:
    data = _load_data()
    return data.get("subscribers", {}).get(str(chat_id), {"hour": "09:00", "focus": ["all"]})


def set_subscriber_hour(chat_id: str, hour: str):
    data = _load_data()
    chat_id = str(chat_id)
    if chat_id in data.get("subscribers", {}):
        data["subscribers"][chat_id]["hour"] = hour
        _save_data(data)


def set_subscriber_focus(chat_id: str, focus: list):
    data = _load_data()
    chat_id = str(chat_id)
    if chat_id in data.get("subscribers", {}):
        data["subscribers"][chat_id]["focus"] = focus
        _save_data(data)


def get_subscribers_for_hour(hour: str) -> Set[str]:
    """Retourne les abonnés qui doivent recevoir le recap à cette heure"""
    data = _load_data()
    result = set()
    for cid, prefs in data.get("subscribers", {}).items():
        if prefs.get("hour", "09:00") == hour:
            result.add(cid)
    return result


# ══════════════════════════════════════
# /last — Envoyer le dernier recap
# ══════════════════════════════════════

def get_last_recap() -> Optional[str]:
    """Récupère le dernier recap depuis output/"""
    output_dir = os.path.join(BASE_DIR, "output")
    if not os.path.exists(output_dir):
        return None
    files = sorted(glob.glob(os.path.join(output_dir, "telegram_*.txt")), reverse=True)
    if not files:
        return None
    try:
        with open(files[0], "r", encoding="utf-8") as f:
            return f.read()
    except IOError:
        return None


# ══════════════════════════════════════
# Telegram helpers
# ══════════════════════════════════════

def send_message(token: str, chat_id: str, text: str):
    try:
        # Split if too long
        chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
        for chunk in chunks:
            requests.post(
                f"{TELEGRAM_API}/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
                timeout=15,
            )
            if len(chunks) > 1:
                time.sleep(0.3)
    except Exception:
        pass


# ══════════════════════════════════════
# Command handler
# ══════════════════════════════════════

def poll_commands(token: str, stop_event: threading.Event = None):
    api = f"{TELEGRAM_API}/bot{token}"
    offset = 0
    owner_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    print("    👂 Écoute des commandes Telegram...")

    while True:
        if stop_event and stop_event.is_set():
            break

        try:
            resp = requests.get(
                f"{api}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35,
            )
            if not resp.ok:
                time.sleep(5)
                continue

            updates = resp.json().get("result", [])

            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "").strip()
                text_lower = text.lower()
                chat = msg.get("chat", {})
                chat_id = str(chat.get("id", ""))
                name = chat.get("first_name", "") or chat.get("title", "")

                if not chat_id or not text:
                    continue

                # /start
                if text_lower == "/start":
                    is_new = add_subscriber(chat_id)
                    if is_new:
                        send_message(token, chat_id, WELCOME_MSG)
                        subs = get_all_subscribers()
                        print(f"    ✅ Nouvel abonné : {name} ({chat_id}) — total: {len(subs)}")
                    else:
                        send_message(token, chat_id, ALREADY_SUB_MSG)

                # /stop
                elif text_lower == "/stop":
                    removed = remove_subscriber(chat_id)
                    if removed:
                        send_message(token, chat_id, GOODBYE_MSG)
                        subs = get_all_subscribers()
                        print(f"    👋 Désabonné : {name} ({chat_id}) — total: {len(subs)}")
                    else:
                        send_message(token, chat_id, STATUS_NOT_SUB_MSG)

                # /status
                elif text_lower == "/status":
                    subs = get_all_subscribers()
                    if chat_id in subs:
                        prefs = get_subscriber_prefs(chat_id)
                        hour = prefs.get("hour", "09:00")
                        focus = ", ".join(prefs.get("focus", ["all"]))
                        send_message(token, chat_id,
                            f"✅ Tu es abonné.\n"
                            f"⏰ Heure d'envoi : {hour}\n"
                            f"🎯 Thèmes : {focus}\n\n"
                            f"Commandes : /heure /focus /last /stop")
                    else:
                        send_message(token, chat_id, STATUS_NOT_SUB_MSG)

                # /last
                elif text_lower == "/last":
                    recap = get_last_recap()
                    if recap:
                        send_message(token, chat_id, recap)
                    else:
                        send_message(token, chat_id, "📭 Aucun recap disponible. Le premier arrivera demain matin !")

                # /heure HH:MM
                elif text_lower.startswith("/heure"):
                    parts = text.split()
                    if len(parts) < 2:
                        send_message(token, chat_id,
                            "⏰ Usage : /heure 7:30\n\n"
                            "Exemples :\n"
                            "/heure 7:00 — Recap à 7h\n"
                            "/heure 9:00 — Recap à 9h (défaut)\n"
                            "/heure 20:00 — Recap le soir")
                        continue
                    raw = parts[1].strip()
                    # Parse HH:MM or H:MM
                    try:
                        h, m = raw.split(":")
                        h, m = int(h), int(m)
                        if not (0 <= h <= 23 and 0 <= m <= 59):
                            raise ValueError
                        hour_str = f"{h:02d}:{m:02d}"
                        set_subscriber_hour(chat_id, hour_str)
                        send_message(token, chat_id,
                            f"✅ Recap programmé à {hour_str} chaque jour.")
                        print(f"    ⏰ {name} ({chat_id}) → heure: {hour_str}")
                    except (ValueError, AttributeError):
                        send_message(token, chat_id, "❌ Format invalide. Utilise : /heure 7:30")

                # /focus [theme]
                elif text_lower.startswith("/focus"):
                    parts = text_lower.split()[1:]
                    if not parts:
                        send_message(token, chat_id, FOCUS_HELP)
                        continue
                    valid = {"all", "coding", "business"}
                    chosen = [p for p in parts if p in valid]
                    if not chosen:
                        send_message(token, chat_id, FOCUS_HELP)
                        continue
                    if "all" in chosen:
                        chosen = ["all"]
                    set_subscriber_focus(chat_id, chosen)
                    send_message(token, chat_id,
                        f"✅ Thèmes mis à jour : {', '.join(chosen)}")
                    print(f"    🎯 {name} ({chat_id}) → focus: {chosen}")

                # /subs (admin only)
                elif text_lower == "/subs":
                    if chat_id == owner_id:
                        subs = get_all_subscribers()
                        data = _load_data()
                        lines = [f"📊 {len(subs)} abonné(s)\n"]
                        for cid in sorted(subs):
                            prefs = data["subscribers"].get(cid, {})
                            h = prefs.get("hour", "09:00")
                            f = ", ".join(prefs.get("focus", ["all"]))
                            lines.append(f"• {cid} — {h} — {f}")
                        send_message(token, chat_id, "\n".join(lines))
                    else:
                        send_message(token, chat_id, "🔒 Commande réservée à l'admin.")

        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            print(f"    ⚠️  Erreur polling: {e}")
            time.sleep(5)


def start_listener_thread(token: str) -> threading.Thread:
    stop_event = threading.Event()
    t = threading.Thread(target=poll_commands, args=(token, stop_event), daemon=True)
    t.start()
    return t


# ── Standalone ──
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN manquant dans .env")
        exit(1)

    owner_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if owner_id:
        add_subscriber(owner_id)
        print(f"    👑 Owner {owner_id} ajouté comme abonné")

    subs = get_all_subscribers()
    print(f"    📊 {len(subs)} abonné(s)")
    print("    Commandes : /start /stop /status /last /heure /focus /subs")
    print("    Ctrl+C pour arrêter\n")

    try:
        poll_commands(token)
    except KeyboardInterrupt:
        print("\n    Arrêté.")
