#!/usr/bin/env python3
"""
AliDonerBot — Alertes trending
Tourne toutes les 4h. Si une news P0 majeure est détectée
(score très élevé), envoie une alerte immédiate aux abonnés.
"""
import os
import sys
import json
import hashlib
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from sources.rss_fetcher import RSSFetcher
from sources.hackernews import HackerNewsFetcher
from analyzer import NewsAnalyzer
from telegram_sender import TelegramSender, get_sender_from_env
from subscribers import get_all_subscribers, add_subscriber
from ollama_summarizer import OllamaSummarizer

ALERTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".alerts_history.json")


def load_alerts():
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"sent": {}}


def save_alerts(data):
    # Keep last 3 days only
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=3)).isoformat()
    cleaned = {k: v for k, v in data.get("sent", {}).items() if v >= cutoff}
    data["sent"] = cleaned
    with open(ALERTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def item_hash(item):
    title = (item.get("title", "") or "").strip().lower()[:80]
    return hashlib.md5(title.encode()).hexdigest()[:10]


def main():
    print("🚨 AliDonerBot — Vérification des alertes trending")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    # Collect (rapide : RSS + HN seulement)
    rss = RSSFetcher()
    hn = HackerNewsFetcher()
    items = []

    print("   📡 RSS (labs uniquement)...")
    lab_sources = [s for s in config.RSS_SOURCES if s.category == "labs"]
    for source in lab_sources:
        fetched = rss.fetch_feed(source.name, source.url, 1)
        for item in fetched:
            item['source_category'] = source.category
            item['priority_boost'] = source.priority_boost
        items.extend(fetched)

    print("   📡 Hacker News...")
    hn_items = hn.fetch_all(config.HACKERNEWS_QUERIES[:3], 1)
    items.extend(hn_items)

    print(f"   📊 {len(items)} items collectés")

    if not items:
        print("   Rien de nouveau.")
        return

    # Analyze
    analyzer = NewsAnalyzer(config)
    analyzed = analyzer.analyze(items)

    # Only P0 with high score
    p0_items = [i for i in analyzed if i.priority == "P0" and i.score >= 8]

    if not p0_items:
        print("   Pas de news P0 majeure. Rien à alerter.")
        return

    # Check history
    alerts = load_alerts()
    new_alerts = []
    for item in p0_items:
        h = item_hash(item.original)
        if h not in alerts["sent"]:
            new_alerts.append(item)
            alerts["sent"][h] = datetime.now().isoformat()

    if not new_alerts:
        print("   Alertes déjà envoyées. Rien de nouveau.")
        save_alerts(alerts)
        return

    print(f"   🚨 {len(new_alerts)} alerte(s) à envoyer !")

    # Enrich with LLM (just title + 1 line)
    summarizer = OllamaSummarizer()
    alert_items = [item.original for item in new_alerts[:3]]

    if summarizer.enabled:
        enriched = summarizer.enrich_items(alert_items, max_items=3)
    else:
        enriched = alert_items

    # Format alert
    lines = ["🚨 ALERTE IA — Breaking news", ""]
    for i, item in enumerate(new_alerts[:3]):
        original = item.original
        title = original.get("ai_title", "") or original.get("title", "")
        summary = original.get("ai_summary", "") or original.get("summary", "")[:150]
        link = original.get("link", "")

        lines.append(f"{i+1}. {title}")
        if summary:
            lines.append(f"   {summary}")
        if link:
            lines.append(f"   ↗ {link}")
        lines.append("")

    lines.append("—\n📡 Alerte automatique AliDonerBot")
    message = "\n".join(lines)

    print()
    print(message)
    print()

    # Send
    sender = get_sender_from_env()
    if sender:
        owner_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if owner_id:
            add_subscriber(owner_id)
        subs = get_all_subscribers()
        if subs:
            ok = sender.send_to_all(message, subs)
            print(f"   ✅ Alerte envoyée à {ok}/{len(subs)} abonné(s)")

    save_alerts(alerts)


if __name__ == "__main__":
    main()
