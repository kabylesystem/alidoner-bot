#!/usr/bin/env python3
"""
AliDonerBot — Setup interactif pour configurer Telegram
Guide pas à pas pour obtenir le token et le chat_id
Utilise requests directement (pas d'asyncio, pas de problème d'event loop)
"""
import os
import sys
import requests

TELEGRAM_API = "https://api.telegram.org"


def main():
    print()
    print("=" * 60)
    print("🥙 AliDonerBot — Configuration Telegram")
    print("=" * 60)
    print()

    # Étape 1 : Token BotFather
    print("📋 ÉTAPE 1 : Créer ton bot Telegram")
    print("-" * 40)
    print()
    print("1. Ouvre Telegram et cherche @BotFather")
    print("2. Envoie /newbot")
    print("3. Choisis un nom : AliDonerBot")
    print("4. Choisis un username : AliDonerBot (ou alidoner_bot)")
    print("5. BotFather te donne un token du style :")
    print("   123456789:ABCdefGHIjklMNOpqrSTUvwxYZ")
    print()

    token = input("📝 Colle ton token BotFather ici : ").strip()
    if not token or ":" not in token:
        print("❌ Token invalide. Il doit contenir ':'")
        print("   Exemple: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ")
        sys.exit(1)

    api_url = f"{TELEGRAM_API}/bot{token}"

    # Test connexion
    print()
    print("🔄 Test de connexion au bot...")
    try:
        resp = requests.get(f"{api_url}/getMe", timeout=10)
        if resp.ok:
            me = resp.json().get("result", {})
            username = me.get("username", "unknown")
            first_name = me.get("first_name", "Bot")
            print(f"✅ Bot connecté : @{username} ({first_name})")
        else:
            print(f"❌ Erreur : {resp.json().get('description', resp.text)}")
            print("   Vérifie ton token et réessaie.")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur : {e}")
        print("   Vérifie ton token et réessaie.")
        sys.exit(1)

    # Étape 2 : Obtenir le chat_id
    print()
    print("📋 ÉTAPE 2 : Obtenir ton Chat ID")
    print("-" * 40)
    print()
    print(f"1. Ouvre Telegram et envoie /start à ton bot @{username}")
    print("2. Envoie n'importe quel message (ex: 'hello')")
    print()
    input("📝 Appuie sur Entrée quand c'est fait...")

    print()
    print("🔄 Récupération du chat_id...")

    chat_id = None
    try:
        resp = requests.get(f"{api_url}/getUpdates", params={"timeout": 10}, timeout=15)
        if resp.ok:
            updates = resp.json().get("result", [])
            if updates:
                # Prend le dernier message
                last = updates[-1]
                msg = last.get("message", {})
                chat = msg.get("chat", {})
                chat_id = str(chat.get("id", ""))
                chat_name = chat.get("first_name", "Unknown")
                print(f"✅ Chat ID trouvé : {chat_id} ({chat_name})")
            else:
                print("⚠️  Pas de messages trouvés.")
    except Exception as e:
        print(f"⚠️  Erreur : {e}")

    if not chat_id:
        print("   Entre ton chat_id manuellement.")
        print("   (Envoie un message à @userinfobot sur Telegram pour l'obtenir)")
        chat_id = input("📝 Chat ID : ").strip()

    if not chat_id:
        print("❌ Chat ID vide, impossible de continuer.")
        sys.exit(1)

    # Étape 3 : Sauvegarder dans .env
    print()
    print("📋 ÉTAPE 3 : Sauvegarde de la configuration")
    print("-" * 40)

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    # Lire le .env existant pour préserver d'autres variables
    existing_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    existing_vars[key.strip()] = val.strip()

    existing_vars["TELEGRAM_BOT_TOKEN"] = token
    existing_vars["TELEGRAM_CHAT_ID"] = chat_id

    env_lines = ["# AliDonerBot — Configuration", "# Généré par setup_telegram.py", ""]
    for key, val in existing_vars.items():
        env_lines.append(f"{key}={val}")
    env_lines.append("")

    with open(env_path, "w") as f:
        f.write("\n".join(env_lines))

    print(f"✅ Configuration sauvegardée dans : {env_path}")
    print()

    # Étape 4 : Test d'envoi
    print("📋 ÉTAPE 4 : Test d'envoi")
    print("-" * 40)
    print()

    try:
        test_msg = "🥙 AliDonerBot est configuré et prêt !\n\nLance `python bot.py --send` pour recevoir ta veille IA."
        resp = requests.post(
            f"{api_url}/sendMessage",
            json={"chat_id": chat_id, "text": test_msg},
            timeout=10,
        )
        if resp.ok:
            print("✅ Message de test envoyé ! Vérifie ton Telegram.")
        else:
            error = resp.json().get("description", resp.text)
            print(f"❌ Erreur envoi test : {error}")
            print("   Vérifie que tu as bien envoyé /start au bot.")
    except Exception as e:
        print(f"❌ Erreur envoi test : {e}")
        print("   Vérifie que tu as bien envoyé /start au bot.")

    print()
    print("=" * 60)
    print("🎉 Setup terminé !")
    print()
    print("Pour lancer ta veille IA :")
    print("  python bot.py --send")
    print()
    print("Pour automatiser chaque matin à 8h :")
    print('  0 8 * * * cd "/home/user/future/perso projects/bot veille" && python bot.py --since-last-run --send')
    print("=" * 60)


if __name__ == "__main__":
    main()
