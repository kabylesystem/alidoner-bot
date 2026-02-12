"""
AliDonerBot — Gestion des abonnés Telegram
Quand quelqu'un fait /start → il est enregistré et reçoit le digest chaque matin.
Quand quelqu'un fait /stop → il est désinscrit.
Les abonnés sont stockés dans subscribers.json (persistant).
"""
import os
import json
import time
import threading
import requests
from typing import Set

SUBSCRIBERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscribers.json")
TELEGRAM_API = "https://api.telegram.org"

WELCOME_MSG = """🥙 Bienvenue sur AliDonerBot !

Chaque matin à 9h, tu reçois un digest IA :
- Les 10 news les plus importantes des dernières 24h
- Résumés complets en français (pas besoin de cliquer)
- "Pourquoi ça compte" pour chaque news
- Un concept du jour expliqué simplement
- Une idée concrète à implémenter

Commandes :
/start — S'abonner au digest
/stop — Se désabonner
/status — Vérifier son abonnement

C'est gratuit, sans pub, open source.
Code : github.com/kabylesystem/alidoner-bot"""

GOODBYE_MSG = """👋 Tu es désabonné d'AliDonerBot.

Tu ne recevras plus le digest quotidien.
Fais /start à tout moment pour te réabonner."""

ALREADY_SUB_MSG = "✅ Tu es déjà abonné ! Tu recevras le prochain digest demain matin à 9h."
STATUS_SUB_MSG = "✅ Tu es abonné. Prochain digest demain matin à 9h."
STATUS_NOT_SUB_MSG = "❌ Tu n'es pas abonné. Fais /start pour t'inscrire."


def load_subscribers() -> Set[str]:
    """Charge les abonnés depuis le fichier JSON"""
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r") as f:
                data = json.load(f)
                return set(str(cid) for cid in data.get("subscribers", []))
        except (json.JSONDecodeError, IOError):
            pass
    return set()


def save_subscribers(subs: Set[str]):
    """Sauvegarde les abonnés dans le fichier JSON"""
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump({"subscribers": sorted(subs)}, f, indent=2)


def add_subscriber(chat_id: str) -> bool:
    """Ajoute un abonné. Retourne True si nouveau, False si déjà inscrit."""
    subs = load_subscribers()
    chat_id = str(chat_id)
    if chat_id in subs:
        return False
    subs.add(chat_id)
    save_subscribers(subs)
    return True


def remove_subscriber(chat_id: str) -> bool:
    """Retire un abonné. Retourne True si retiré, False si pas inscrit."""
    subs = load_subscribers()
    chat_id = str(chat_id)
    if chat_id not in subs:
        return False
    subs.discard(chat_id)
    save_subscribers(subs)
    return True


def get_all_subscribers() -> Set[str]:
    """Retourne tous les chat_ids abonnés"""
    return load_subscribers()


def send_message(token: str, chat_id: str, text: str):
    """Envoie un message à un chat_id"""
    try:
        requests.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=15,
        )
    except Exception:
        pass


def poll_commands(token: str, stop_event: threading.Event = None):
    """
    Écoute les commandes /start, /stop, /status en boucle (long polling).
    Tourne en background thread ou en standalone.
    """
    api = f"{TELEGRAM_API}/bot{token}"
    offset = 0

    print("    👂 Écoute des commandes Telegram (/start, /stop, /status)...")

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
                text = msg.get("text", "").strip().lower()
                chat = msg.get("chat", {})
                chat_id = str(chat.get("id", ""))
                name = chat.get("first_name", "") or chat.get("title", "")

                if not chat_id or not text:
                    continue

                if text == "/start":
                    is_new = add_subscriber(chat_id)
                    if is_new:
                        send_message(token, chat_id, WELCOME_MSG)
                        subs = get_all_subscribers()
                        print(f"    ✅ Nouvel abonné : {name} ({chat_id}) — total: {len(subs)}")
                    else:
                        send_message(token, chat_id, ALREADY_SUB_MSG)

                elif text == "/stop":
                    removed = remove_subscriber(chat_id)
                    if removed:
                        send_message(token, chat_id, GOODBYE_MSG)
                        subs = get_all_subscribers()
                        print(f"    👋 Désabonné : {name} ({chat_id}) — total: {len(subs)}")
                    else:
                        send_message(token, chat_id, STATUS_NOT_SUB_MSG)

                elif text == "/status":
                    subs = get_all_subscribers()
                    if chat_id in subs:
                        send_message(token, chat_id, STATUS_SUB_MSG)
                    else:
                        send_message(token, chat_id, STATUS_NOT_SUB_MSG)

        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            print(f"    ⚠️  Erreur polling: {e}")
            time.sleep(5)


def start_listener_thread(token: str) -> threading.Thread:
    """Lance le listener en background thread (non-bloquant)"""
    stop_event = threading.Event()
    t = threading.Thread(target=poll_commands, args=(token, stop_event), daemon=True)
    t.start()
    return t


# ── Standalone : python subscribers.py pour écouter en continu ──
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN manquant dans .env")
        exit(1)

    # Ajouter le chat_id du .env comme abonné fondateur
    owner_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if owner_id:
        add_subscriber(owner_id)
        print(f"    👑 Owner {owner_id} ajouté comme abonné")

    subs = get_all_subscribers()
    print(f"    📊 {len(subs)} abonné(s) actuellement")
    print()
    print("    En attente de /start, /stop, /status...")
    print("    Ctrl+C pour arrêter")
    print()

    try:
        poll_commands(token)
    except KeyboardInterrupt:
        print("\n    Arrêté.")
