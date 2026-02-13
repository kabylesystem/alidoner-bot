"""
AliDonerBot — Formatage du recap Telegram
Objectif : message AUTONOME lisible en 90 secondes le matin,
cerveau fatigué, pas besoin de cliquer un seul lien.
100% français, zéro bruit, beau sur mobile Telegram.
"""
import re
from datetime import datetime
from typing import List, Optional
from analyzer import AnalyzedItem

# Emojis par catégorie
CATEGORY_EMOJI = {
    'Model': '🧠',
    'Product': '🛠',
    'Infra': '⚙️',
    'Security': '🔒',
    'Business': '💰',
    'Other': '📌',
}

# Mois en français
MOIS_FR = {
    1: 'janv', 2: 'fév', 3: 'mars', 4: 'avr', 5: 'mai', 6: 'juin',
    7: 'juil', 8: 'août', 9: 'sept', 10: 'oct', 11: 'nov', 12: 'déc',
}

# (plus d'emoji pour les numéros, on reste simple)


class TelegramFormatter:
    def __init__(self, max_top=5, max_radar=3, max_rumors=2, max_actions=3):
        self.max_top = max_top
        self.max_radar = max_radar
        self.max_rumors = max_rumors
        self.max_actions = max_actions

    def format(
        self,
        items: List[AnalyzedItem],
        date_str: str = None,
        window: str = "dernières 24h",
        daily_tip: str = None,
        actionable_idea: str = None,
    ) -> str:
        """Message Telegram complet — lisible en 90s, cerveau fatigué OK"""
        now = datetime.now()
        if not date_str:
            date_str = f"{now.day} {MOIS_FR[now.month]} {now.year}"

        # ━━━ Header ━━━
        lines = [
            f"🥙 AliDonerBot — {date_str}",
            f"📅 {window}",
            "",
        ]

        # Séparer par priorité
        p0_items = [i for i in items if i.priority == 'P0']
        p1_items = [i for i in items if i.priority == 'P1']

        # ━━━ L'ESSENTIEL (P0 + top P1) ━━━
        top_items = (p0_items + p1_items)[:self.max_top]

        if top_items:
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("🔥 L'ESSENTIEL")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("")

            for i, item in enumerate(top_items):
                lines.extend(self._format_news_item(item, i))
                lines.append("")

        # ━━━ CONCEPT DU JOUR ━━━
        if daily_tip:
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("🎓 2 MIN POUR COMPRENDRE")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("")
            lines.append(daily_tip)
            lines.append("")

        # ━━━ IDÉE À PIQUER ━━━
        if actionable_idea:
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("💡 IDÉE À PIQUER")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("")
            lines.append(actionable_idea)
            lines.append("")

        # ━━━ Footer ━━━
        total = len(top_items)
        sources_used = set()
        for item in items[:50]:
            t = item.original.get('type', '')
            sources_used.add({
                'rss': 'Blogs', 'hackernews': 'HN', 'reddit': 'Reddit',
                'github': 'GitHub', 'twitter': 'X',
            }.get(t, ''))
        sources_used.discard('')
        src_str = " · ".join(sorted(sources_used)) or "Multi-sources"
        lines.append(f"—\n📊 {total} news · {src_str}")

        return "\n".join(lines)

    # ──────────────────────────────────────
    # Formatage d'un item
    # ──────────────────────────────────────

    def _format_news_item(self, item: AnalyzedItem, index: int) -> List[str]:
        """
        Format optimisé cerveau du matin :
        - Numéro + emoji catégorie + titre court
        - Résumé complet (autonome, pas besoin de cliquer)
        - Pourquoi t'en as qqch à foutre
        - Le saviez-vous (si dispo)
        - Lien tout petit en bas (optionnel, discret)
        """
        original = item.original
        emoji = CATEGORY_EMOJI.get(item.category, '📌')
        num = f"{index + 1}."

        # Titre : FR (via IA) si dispo, sinon original nettoyé
        ai_title = original.get('ai_title', '')
        if ai_title and len(ai_title) > 5:
            title = ai_title
        else:
            title = self._clean_title(original.get('title', ''), original.get('source', ''))

        lines = [
            f"{num} {emoji} {title}",
            "",  # saut de ligne entre titre et texte
        ]

        # Résumé complet — c'est LE contenu principal
        ai_summary = original.get('ai_summary', '')
        if ai_summary:
            lines.append(f"  {ai_summary}")
        else:
            raw = original.get('summary', '')
            summary = self._clean_summary(raw, title)
            if summary:
                lines.append(f"  {summary}")

        # Pourquoi ça compte — concret
        ai_why = original.get('ai_why', '')
        if ai_why:
            lines.append(f"  👉 {ai_why}")

        # Le saviez-vous — pédagogique
        ai_learn = original.get('ai_learn', '')
        if ai_learn:
            lines.append(f"  🎓 {ai_learn}")

        # Lien discret
        link = original.get('link', '')
        if link:
            lines.append(f"  ↗ {link}")

        return lines

    # ──────────────────────────────────────
    # Nettoyage de texte
    # ──────────────────────────────────────

    @staticmethod
    def _clean_title(title: str, source: str = '') -> str:
        title = re.sub(r'^@\w+:\s*', '', title)
        title = title.replace('\n', ' ').replace('\r', ' ')
        title = re.sub(r'\s+', ' ', title).strip()
        if len(title) > 90:
            cut = title[:87]
            last_space = cut.rfind(' ')
            if last_space > 50:
                title = cut[:last_space] + "…"
            else:
                title = cut + "…"
        return title

    @staticmethod
    def _clean_summary(raw: str, title: str) -> str:
        if not raw or len(raw) < 15:
            return ''
        summary = re.sub(r'<[^>]+>', ' ', raw)
        summary = re.sub(r'\*\*?\[?', '', summary)
        summary = re.sub(r'\]\([^)]*\)', '', summary)
        summary = summary.replace('\n', ' ').replace('\r', ' ')
        summary = re.sub(r'\s+', ' ', summary).strip()
        if summary.startswith(('http', 'www', '<', '![')):
            return ''
        if summary.lower()[:50] == title.lower()[:50]:
            return ''
        if re.match(r'^\d+ (upvotes|points)', summary):
            return ''
        if len(summary) > 200:
            cut = summary[:200]
            last_dot = cut.rfind('.')
            if last_dot > 80:
                summary = cut[:last_dot + 1]
            else:
                last_space = cut.rfind(' ')
                summary = cut[:last_space] + "…" if last_space > 100 else cut + "…"
        return summary

    # Legacy — gardé au cas où mais plus utilisé dans le format principal
    @staticmethod
    def _generate_why(item: AnalyzedItem) -> str:
        return "Signal à suivre"

    def _generate_actions(self, items: List[AnalyzedItem]) -> List[str]:
        return []

    @staticmethod
    def _extract_product_name(title: str) -> str:
        title = re.sub(r'^@\w+:\s*', '', title)
        names = re.findall(r'[A-Z][a-zA-Z0-9\-\.]+(?:\s+[A-Z0-9][a-zA-Z0-9\-\.]*)*', title)
        if names:
            return names[0][:40]
        words = title.split()[:3]
        return " ".join(words) if words else title[:30]
