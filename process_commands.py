#!/usr/bin/env python3
"""
AliDonerBot — Traitement des commandes en batch
Tourne toutes les 5 min via GitHub Actions.
Récupère TOUTES les commandes en attente et les traite d'un coup.
"""
import os
import sys
import json
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from subscribers import (
    add_subscriber, remove_subscriber, get_all_subscribers,
    get_subscriber_prefs, set_subscriber_hour, set_subscriber_focus,
    send_message, _load_data,
    WELCOME_MSG, GOODBYE_MSG, ALREADY_SUB_MSG, STATUS_NOT_SUB_MSG, FOCUS_HELP,
)


def get_last_recap():
    """Récupère le dernier recap — cherche d'abord les fichiers, puis le secret."""
    base = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base, "output")

    # 1. Try real recap files
    if os.path.exists(output_dir):
        import glob as _glob
        files = sorted(_glob.glob(os.path.join(output_dir, "telegram_*.txt")), reverse=True)
        if files:
            try:
                with open(files[0], "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        return content
            except IOError:
                pass

    # 2. Try last_recap.txt (downloaded from secrets)
    fallback = os.path.join(output_dir, "last_recap.txt")
    if os.path.exists(fallback):
        try:
            with open(fallback, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except IOError:
            pass

    return None

TELEGRAM_API = "https://api.telegram.org"
OFFSET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".listener_offset")


def load_offset() -> int:
    # Try env var first (persisted via GitHub secrets)
    env_offset = os.getenv("LISTENER_OFFSET", "").strip()
    if env_offset:
        try:
            return int(env_offset)
        except ValueError:
            pass
    if os.path.exists(OFFSET_FILE):
        try:
            with open(OFFSET_FILE, "r") as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            pass
    return 0


def save_offset(offset: int):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))
    # Also try to save to GitHub secrets for persistence
    try:
        token = os.getenv("GH_TOKEN", "").strip()
        repo = os.getenv("GITHUB_REPOSITORY", "").strip()
        if token and repo:
            import subprocess
            subprocess.run(
                ["gh", "secret", "set", "LISTENER_OFFSET", "--body", str(offset), "--repo", repo],
                env={**os.environ, "GH_TOKEN": token},
                capture_output=True, timeout=10,
            )
    except Exception:
        pass


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    owner_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token:
        print("❌ TELEGRAM_BOT_TOKEN manquant")
        return

    # Ensure owner is subscribed
    if owner_id:
        add_subscriber(owner_id)

    api = f"{TELEGRAM_API}/bot{token}"
    offset = load_offset()

    print(f"📥 Récupération des commandes (offset: {offset})...")

    try:
        resp = requests.get(
            f"{api}/getUpdates",
            params={"offset": offset, "timeout": 5, "allowed_updates": json.dumps(["message"])},
            timeout=10,
        )
        if not resp.ok:
            print(f"   ❌ API error: {resp.status_code}")
            return

        updates = resp.json().get("result", [])
        print(f"   📬 {len(updates)} message(s) en attente")

        processed = 0
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

            processed += 1

            # /start
            if text_lower == "/start":
                is_new = add_subscriber(chat_id)
                if is_new:
                    send_message(token, chat_id, WELCOME_MSG)
                    print(f"   ✅ Nouvel abonné : {name} ({chat_id})")
                else:
                    send_message(token, chat_id, ALREADY_SUB_MSG)

            # /stop
            elif text_lower == "/stop":
                removed = remove_subscriber(chat_id)
                if removed:
                    send_message(token, chat_id, GOODBYE_MSG)
                    print(f"   👋 Désabonné : {name} ({chat_id})")
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
                        f"✅ Tu es abonné.\n⏰ Heure : {hour}\n🎯 Thèmes : {focus}\n\n/heure /focus /last /stop")
                else:
                    send_message(token, chat_id, STATUS_NOT_SUB_MSG)

            # /last
            elif text_lower == "/last":
                recap = get_last_recap()
                if recap:
                    send_message(token, chat_id, recap)
                else:
                    send_message(token, chat_id, "📭 Aucun recap dispo. Le premier arrive demain matin !")

            # /heure
            elif text_lower.startswith("/heure"):
                parts = text.split()
                if len(parts) < 2:
                    send_message(token, chat_id, "⏰ Usage : /heure 7:30\nExemples : /heure 7:00 / /heure 20:00")
                    continue
                try:
                    h, m = parts[1].strip().split(":")
                    h, m = int(h), int(m)
                    if not (0 <= h <= 23 and 0 <= m <= 59):
                        raise ValueError
                    hour_str = f"{h:02d}:{m:02d}"
                    set_subscriber_hour(chat_id, hour_str)
                    send_message(token, chat_id, f"✅ Recap programmé à {hour_str}.")
                    print(f"   ⏰ {name} → {hour_str}")
                except (ValueError, AttributeError):
                    send_message(token, chat_id, "❌ Format invalide. Utilise : /heure 7:30")

            # /focus
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
                send_message(token, chat_id, f"✅ Thèmes : {', '.join(chosen)}")
                print(f"   🎯 {name} → {chosen}")

            # /subs
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
                    send_message(token, chat_id, "🔒 Admin only.")

        save_offset(offset)
        subs = get_all_subscribers()
        print(f"\n   📊 {processed} commande(s) traitées — {len(subs)} abonné(s) total")

    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
