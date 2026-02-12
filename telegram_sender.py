"""
AliDonerBot — Envoi de messages sur Telegram via Bot API HTTP
Utilise requests (synchrone, simple, pas de problème d'event loop)
Supporte l'envoi à tous les abonnés via subscribers.json
"""
import os
import time
import requests
from typing import Optional, List, Set

# Limite Telegram pour un message
MAX_MESSAGE_LENGTH = 4096
TELEGRAM_API = "https://api.telegram.org"


class TelegramSender:
    def __init__(self, token: str, chat_id: str = ""):
        """
        Args:
            token: Token du bot BotFather
            chat_id: Chat ID du destinataire (legacy, optionnel)
        """
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"{TELEGRAM_API}/bot{token}"

    def send(self, message: str, chat_id: str = None) -> bool:
        """
        Envoie un message Telegram à un destinataire.

        Returns:
            True si envoyé avec succès, False sinon
        """
        target = chat_id or self.chat_id
        if not target:
            print("    ❌ Pas de chat_id spécifié")
            return False

        try:
            chunks = self._split_message(message)

            for i, chunk in enumerate(chunks):
                if i > 0:
                    time.sleep(0.5)

                resp = requests.post(
                    f"{self.api_url}/sendMessage",
                    json={
                        "chat_id": target,
                        "text": chunk,
                        "disable_web_page_preview": True,
                    },
                    timeout=30,
                )

                if not resp.ok:
                    error = resp.json().get("description", resp.text)
                    print(f"    ❌ Erreur Telegram ({target}): {error}")
                    return False

            return True

        except Exception as e:
            print(f"    ❌ Erreur envoi Telegram: {e}")
            return False

    def send_to_all(self, message: str, subscriber_ids: Set[str]) -> int:
        """
        Envoie le message à tous les abonnés.
        Retourne le nombre d'envois réussis.
        """
        if not subscriber_ids:
            print("    ⚠️  Aucun abonné")
            return 0

        success = 0
        failed = 0
        for cid in subscriber_ids:
            ok = self.send(message, chat_id=cid)
            if ok:
                success += 1
            else:
                failed += 1
            time.sleep(0.3)  # Rate limiting Telegram

        return success

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
