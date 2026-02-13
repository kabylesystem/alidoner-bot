#!/usr/bin/env python3
"""
AliDonerBot 🥙 — Bot de Veille IA
Collecte, analyse, enrichit (Ollama), formate et envoie les news IA sur Telegram.
Chaque matin, ultra court, actionnable, pédagogique, zéro bruit.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from sources.rss_fetcher import RSSFetcher
from sources.hackernews import HackerNewsFetcher
from sources.reddit import RedditFetcher
from sources.github_trending import GitHubTrendingFetcher
from sources.twitter_fetcher import TwitterFetcher
from analyzer import NewsAnalyzer, AnalyzedItem
from telegram_formatter import TelegramFormatter
from telegram_sender import TelegramSender, get_sender_from_env
from subscribers import get_all_subscribers, add_subscriber
from history import filter_already_sent, mark_as_sent
from ollama_summarizer import OllamaSummarizer


class AliDonerBot:
    """
    Bot de veille IA — collecte multi-sources, priorise, enrichit par IA, formate, envoie.
    """

    def __init__(self):
        self.rss_fetcher = RSSFetcher()
        self.hn_fetcher = HackerNewsFetcher()
        self.reddit_fetcher = RedditFetcher()
        self.github_fetcher = GitHubTrendingFetcher()
        self.twitter_fetcher = TwitterFetcher()
        self.analyzer = NewsAnalyzer(config)
        self.summarizer = OllamaSummarizer()
        self.formatter = TelegramFormatter(
            max_top=config.MAX_TOP_ITEMS,
            max_radar=config.MAX_RADAR_ITEMS,
            max_rumors=config.MAX_RUMORS,
            max_actions=config.MAX_ACTIONS,
        )

    def run(
        self,
        days_back: int = None,
        output_file: str = None,
        send_telegram: bool = False,
        since_last_run: bool = False,
    ) -> str:
        """
        Pipeline complet : collect → analyze → enrich (IA) → format → save → send

        Args:
            days_back: Combien de jours en arrière (défaut: config)
            output_file: Fichier de sortie (optionnel)
            send_telegram: Envoyer sur Telegram
            since_last_run: Utiliser le timestamp du dernier run

        Returns:
            Message Telegram formaté
        """
        # Déterminer la fenêtre temporelle
        if since_last_run:
            last_run = config.get_last_run()
            if last_run:
                hours_diff = (datetime.now() - last_run).total_seconds() / 3600
                days_back = max(1, int(hours_diff / 24) + 1)
                window_str = f"depuis {last_run.strftime('%d/%m %Hh%M')}"
                print(f"⏰ Dernier run: {last_run.strftime('%Y-%m-%d %H:%M')}")
                print(f"   → Fenêtre: {hours_diff:.0f}h ({days_back} jour(s))")
            else:
                days_back = days_back or config.DAYS_BACK
                window_str = f"dernières {days_back * 24}h"
                print("⏰ Pas de run précédent, utilise la config par défaut")
        else:
            days_back = days_back or config.DAYS_BACK
            window_str = f"dernières {days_back * 24}h"

        print()
        print("=" * 60)
        print(f"🥙 {config.BOT_NAME} — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)
        print()

        # ═══════════════════════════════════════
        # 1. COLLECT
        # ═══════════════════════════════════════
        print("📥 PHASE 1 : COLLECTION DES SOURCES")
        print("-" * 40)

        all_items = []

        # RSS feeds
        print("\n1. RSS Feeds...")
        for source in config.RSS_SOURCES:
            items = self.rss_fetcher.fetch_feed(source.name, source.url, days_back)
            for item in items:
                item['source_category'] = source.category
                item['priority_boost'] = source.priority_boost
            all_items.extend(items)

        # Hacker News
        print("\n2. Hacker News...")
        hn_items = self.hn_fetcher.fetch_all(config.HACKERNEWS_QUERIES, days_back)
        all_items.extend(hn_items)

        # Reddit
        print("\n3. Reddit...")
        reddit_items = self.reddit_fetcher.fetch_all(config.REDDIT_SOURCES)
        all_items.extend(reddit_items)

        # GitHub Trending
        print("\n4. GitHub Trending...")
        gh_items = self.github_fetcher.fetch_all(config.GITHUB_TOPICS)
        all_items.extend(gh_items)

        # X / Twitter
        print("\n5. X / Twitter...")
        twitter_items = self.twitter_fetcher.fetch_all(days_back)
        all_items.extend(twitter_items)

        print()
        print(f"📊 Total collecté : {len(all_items)} items")

        # Filtrer les news déjà envoyées les jours précédents
        all_items = filter_already_sent(all_items)
        print(f"📊 Après filtre duplicatas : {len(all_items)} items nouveaux")
        print()

        if not all_items:
            msg = "⚠️  Aucun item collecté (ou tout déjà envoyé). Vérifie ta connexion internet."
            print(msg)
            if send_telegram:
                sender = get_sender_from_env()
                if sender:
                    sender.send(f"🥙 AliDonerBot — {msg}")
            return ""

        # ═══════════════════════════════════════
        # 2. ANALYZE
        # ═══════════════════════════════════════
        print("🧠 PHASE 2 : ANALYSE ET PRIORISATION")
        print("-" * 40)

        analyzed = self.analyzer.analyze(all_items)

        counts = {}
        for item in analyzed:
            counts[item.priority] = counts.get(item.priority, 0) + 1

        print(f"   P0 (Critique)    : {counts.get('P0', 0)}")
        print(f"   P1 (Important)   : {counts.get('P1', 0)}")
        print(f"   P2 (Intéressant) : {counts.get('P2', 0)}")
        print(f"   P3 (Bruit)       : {counts.get('P3', 0)}")
        print()

        # Deduplicate
        deduplicated = self.analyzer.deduplicate(analyzed)
        print(f"   Après déduplication : {len(deduplicated)} items uniques")
        print()

        # ═══════════════════════════════════════
        # 3. ENRICH (LLM IA)
        # ═══════════════════════════════════════
        daily_tip = None
        actionable_idea = None
        if self.summarizer.enabled:
            print("✨ PHASE 3 : ENRICHISSEMENT IA")
            print("-" * 40)

            # Enrichir exactement les items qui seront affichés (P0 + P1, max 10)
            p0 = [i for i in deduplicated if i.priority == 'P0']
            p1 = [i for i in deduplicated if i.priority == 'P1']
            top_analyzed = (p0 + p1)[:config.MAX_TOP_ITEMS]

            items_to_enrich = [item.original for item in top_analyzed]

            enriched_items = self.summarizer.enrich_items(items_to_enrich, max_items=len(items_to_enrich))

            # Remettre les items enrichis dans les AnalyzedItem
            for i, enriched in enumerate(enriched_items):
                if i < len(top_analyzed):
                    top_analyzed[i].original = enriched

            # Générer le "Concept du jour"
            print("    🎓 Génération du concept du jour...")
            daily_tip = self.summarizer.generate_daily_tip(items_to_enrich)
            if daily_tip:
                print(f"    ✅ Concept du jour ({len(daily_tip)} chars)")
            else:
                print("    ⚠️  Pas de concept du jour")

            # Générer "l'Idée à piquer"
            print("    💡 Génération de l'idée actionnable...")
            actionable_idea = self.summarizer.generate_actionable_idea(items_to_enrich)
            if actionable_idea:
                print(f"    ✅ Idée à piquer ({len(actionable_idea)} chars)")
            else:
                print("    ⚠️  Pas d'idée générée")
            print()
        else:
            print("⏭️  PHASE 3 : Enrichissement IA désactivé (pas de clé LLM)")
            print()

        # ═══════════════════════════════════════
        # 4. FORMAT
        # ═══════════════════════════════════════
        print("📱 PHASE 4 : FORMATAGE TELEGRAM")
        print("-" * 40)

        telegram_message = self.formatter.format(
            deduplicated,
            window=window_str,
            daily_tip=daily_tip,
            actionable_idea=actionable_idea,
        )

        print(f"   Message : {len(telegram_message)} caractères")
        print()

        # ═══════════════════════════════════════
        # 5. SAVE
        # ═══════════════════════════════════════
        if output_file:
            self._save_output(telegram_message, output_file)
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
            default_file = f"output/telegram_{date_str}.txt"
            self._save_output(telegram_message, default_file)

        # ═══════════════════════════════════════
        # 6. SEND TELEGRAM
        # ═══════════════════════════════════════
        if send_telegram:
            print("📤 PHASE 6 : ENVOI TELEGRAM")
            print("-" * 40)

            sender = get_sender_from_env()
            if sender:
                # S'assurer que le owner est abonné
                owner_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
                if owner_id:
                    add_subscriber(owner_id)

                subs = get_all_subscribers()
                if subs:
                    ok = sender.send_to_all(telegram_message, subs)
                    print(f"   ✅ Message envoyé à {ok}/{len(subs)} abonné(s) !")
                    # Marquer les news comme envoyées pour éviter les duplicatas demain
                    sent_items = [item.original for item in deduplicated[:config.MAX_TOP_ITEMS + 5]]
                    mark_as_sent(sent_items)
                    print(f"   📝 {len(sent_items)} news marquées dans l'historique")
                else:
                    print("   ⚠️  Aucun abonné. Envoi au owner uniquement.")
                    sender.send(telegram_message)
            else:
                print("   ⚠️  Pas de config Telegram — fichier uniquement")
                print("   💡 Lance: python setup_telegram.py")
            print()

        # Sauvegarder le timestamp du run
        config.save_last_run()

        # Afficher le message
        print("=" * 60)
        print("📤 MESSAGE TELEGRAM :")
        print("=" * 60)
        print()
        print(telegram_message)
        print()
        print("=" * 60)

        return telegram_message

    def _save_output(self, message: str, filepath: str):
        """Sauvegarde le message dans un fichier"""
        directory = os.path.dirname(filepath) if os.path.dirname(filepath) else "output"
        os.makedirs(directory, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(message)

        print(f"💾 Sauvegardé dans : {filepath}")
        print()


def main():
    """Point d'entrée CLI"""
    import argparse

    parser = argparse.ArgumentParser(
        description=f"🥙 {config.BOT_NAME} — Veille IA quotidienne sur Telegram"
    )
    parser.add_argument(
        "--days", "-d", type=int, default=None,
        help="Nombre de jours en arrière (défaut: 1)"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Fichier de sortie (défaut: output/telegram_YYYY-MM-DD.txt)"
    )
    parser.add_argument(
        "--send", "-S", action="store_true",
        help="Envoyer le recap sur Telegram"
    )
    parser.add_argument(
        "--since-last-run", "-L", action="store_true",
        help="Ne prendre que les news depuis le dernier run"
    )
    parser.add_argument(
        "--short", "-s", action="store_true",
        help="Format court (liens uniquement)"
    )
    parser.add_argument(
        "--schedule", type=str, default=None,
        help="Lancer en mode planifié (ex: '08:00' pour chaque jour à 8h)"
    )
    parser.add_argument(
        "--setup", action="store_true",
        help="Lancer la configuration Telegram interactive"
    )

    args = parser.parse_args()

    # Mode setup
    if args.setup:
        os.system(f'{sys.executable} "{os.path.join(os.path.dirname(__file__), "setup_telegram.py")}"')
        return

    # Mode planifié
    if args.schedule:
        _run_scheduled(args)
        return

    # Mode normal
    bot = AliDonerBot()

    try:
        message = bot.run(
            days_back=args.days,
            output_file=args.output,
            send_telegram=args.send,
            since_last_run=args.since_last_run,
        )

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def _run_scheduled(args):
    """Mode planifié — exécute le bot à une heure fixe chaque jour"""
    try:
        import schedule
        import time
    except ImportError:
        print("❌ Le module 'schedule' n'est pas installé.")
        print("   pip install schedule")
        sys.exit(1)

    schedule_time = args.schedule
    print(f"🥙 {config.BOT_NAME} — Mode planifié")
    print(f"   Exécution prévue chaque jour à {schedule_time}")
    print(f"   Ctrl+C pour arrêter")
    print()

    def job():
        print(f"\n⏰ Exécution planifiée — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        bot = AliDonerBot()
        bot.run(
            send_telegram=True,
            since_last_run=True,
        )

    schedule.every().day.at(schedule_time).do(job)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
