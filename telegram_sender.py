"""
AliDonerBot — Envoi de messages sur Telegram via Bot API HTTP
Utilise requests (synchrone, simple, pas de problème d'event loop)
"""
import os
import time
import requests
from typing import Optional, List

# Limite Telegram pour un message
MAX_MESSAGE_LENGTH = 4096
TELEGRAM_API = "https://api.telegram.org"


class TelegramSender:
    def __init__(self, token: str, chat_id: str):
        """
        Args:
            token: Token du bot BotFather
            chat_id: Chat ID du destinataire (user ou group)
        """
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"{TELEGRAM_API}/bot{token}"

    def send(self, message: str) -> bool:
        """
        Envoie un message Telegram (synchrone).
        Découpe automatiquement si le message dépasse 4096 chars.

        Returns:
            True si envoyé avec succès, False sinon
        """
        try:
            chunks = self._split_message(message)

            for i, chunk in enumerate(chunks):
                if i > 0:
                    time.sleep(0.5)

                resp = requests.post(
                    f"{self.api_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": chunk,
                        "disable_web_page_preview": True,
                    },
                    timeout=30,
                )

                if not resp.ok:
                    error = resp.json().get("description", resp.text)
                    print(f"    ❌ Erreur Telegram API: {error}")
                    return False

            return True

        except Exception as e:
            print(f"    ❌ Erreur envoi Telegram: {e}")
            return False

    def test_connection(self) -> bool:
        """Teste la connexion au bot (synchrone)"""
        try:
            resp = requests.get(f"{self.api_url}/getMe", timeout=10)
            if resp.ok:
                data = resp.json().get("result", {})
                print(f"    ✅ Bot connecté: @{data.get('username')} ({data.get('first_name')})")
                return True
            else:
                print(f"    ❌ Erreur: {resp.text}")
                return False
        except Exception as e:
            print(f"    ❌ Impossible de se connecter au bot: {e}")
            return False

    def get_updates(self) -> list:
        """Récupère les derniers messages envoyés au bot"""
        try:
            resp = requests.get(
                f"{self.api_url}/getUpdates",
                params={"timeout": 10},
                timeout=15,
            )
            if resp.ok:
                return resp.json().get("result", [])
            return []
        except Exception:
            return []

    @staticmethod
    def _split_message(message: str) -> List[str]:
        """
        Découpe intelligemment un message en morceaux <= 4096 chars.
        Coupe aux sauts de ligne plutôt qu'au milieu d'un mot.
        """
        if len(message) <= MAX_MESSAGE_LENGTH:
            return [message]

        chunks = []
        current = ""

        for line in message.split("\n"):
            if len(current) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                if current:
                    chunks.append(current.rstrip())
                current = line + "\n"
            else:
                current += line + "\n"

        if current.strip():
            chunks.append(current.rstrip())

        return chunks


def get_sender_from_env() -> Optional[TelegramSender]:
    """
    Crée un TelegramSender depuis les variables d'environnement.
    Retourne None si les variables ne sont pas définies.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token:
        print("    ⚠️  TELEGRAM_BOT_TOKEN non défini — pas d'envoi Telegram")
        print("    💡 Lance: python setup_telegram.py")
        return None

    if not chat_id:
        print("    ⚠️  TELEGRAM_CHAT_ID non défini — pas d'envoi Telegram")
        print("    💡 Lance: python setup_telegram.py")
        return None

    return TelegramSender(token=token, chat_id=chat_id)
