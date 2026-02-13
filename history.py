"""
AliDonerBot — Historique des news envoyées
Évite les duplicatas d'un jour à l'autre en gardant un hash
de chaque news déjà envoyée (titre + lien).
Garde les 7 derniers jours pour rester léger.
"""
import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import Set, List, Dict

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".news_history.json")
HISTORY_DAYS = 7  # On garde l'historique 7 jours


def _make_key(item: Dict) -> str:
    """Crée une clé unique pour un item (hash du titre normalisé + lien)"""
    title = (item.get("title", "") or "").strip().lower()
    link = (item.get("link", "") or "").strip().lower()
    # Normaliser : retirer les espaces multiples, ponctuation mineure
    title = " ".join(title.split())
    raw = f"{title}|{link}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def load_history() -> Dict:
    """Charge l'historique depuis le fichier JSON"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"sent": {}}


def save_history(history: Dict):
    """Sauvegarde l'historique (et purge les entrées > 7 jours)"""
    cutoff = (datetime.now() - timedelta(days=HISTORY_DAYS)).isoformat()
    cleaned = {}
    for key, date_str in history.get("sent", {}).items():
        if date_str >= cutoff:
            cleaned[key] = date_str
    history["sent"] = cleaned
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def filter_already_sent(items: List[Dict]) -> List[Dict]:
    """
    Filtre les items déjà envoyés dans les derniers jours.
    Retourne uniquement les items NOUVEAUX.
    """
    history = load_history()
    sent_keys = set(history.get("sent", {}).keys())

    new_items = []
    dupes = 0
    for item in items:
        key = _make_key(item)
        if key in sent_keys:
            dupes += 1
        else:
            new_items.append(item)

    if dupes > 0:
        print(f"   🔄 {dupes} news déjà envoyées filtrées (duplicatas)")

    return new_items


def mark_as_sent(items: List[Dict]):
    """Enregistre les items comme envoyés"""
    history = load_history()
    now = datetime.now().isoformat()
    for item in items:
        key = _make_key(item)
        history["sent"][key] = now
    save_history(history)
