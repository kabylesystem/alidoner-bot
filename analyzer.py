"""
AliDonerBot — Analyse et priorisation des news
Filtrage strict : on ne garde que ce qui compte vraiment.
"""
import re
from typing import List, Dict, Tuple, Set
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AnalyzedItem:
    original: Dict
    priority: str   # P0, P1, P2, P3
    category: str   # Model, Product, Infra, Security, Business, Other
    score: int
    reason: str


# Mots/patterns qui indiquent que c'est PAS une vraie actu IA
# (même si le titre matche des keywords P0/P1)
NOISE_PATTERNS = [
    # Startups random / levées non-IA
    r'sleeptech', r'wearable', r'fintech', r'edtech', r'healthtech',
    r'logistics', r'grocery', r'food delivery', r'eats',
    r'real estate', r'proptech', r'agritech', r'medtech',
    r'climate.ready', r'green skills', r'electric vehicle',
    r'payments? for', r'global payments', r'money platform',
    r'usd.*gbp.*eur', r'forex', r'remittance',
    # Contenu générique / clickbait
    r'how to build your', r'best practices for',
    r'tips for', r'\d+ ways to', r'\d+ reasons why',
    r'complete guide to', r'ultimate guide',
    # Régions hors scope (sauf si actu IA majeure)
    r'cricket', r'bollywood', r'ipl ', r'karnataka',
    r'bengaluru(?!.*ai)', r'mumbai(?!.*ai)',
    # News non-tech
    r'real estate', r'fashion', r'lifestyle', r'wellness',
    r'fitness', r'yoga', r'meditation',
]


class NewsAnalyzer:
    def __init__(self, config):
        self.config = config
        self._noise_re = re.compile('|'.join(NOISE_PATTERNS), re.IGNORECASE)

    def analyze(self, items: List[Dict]) -> List[AnalyzedItem]:
        """Analyse tous les items, assigne priorité + catégorie + score"""
        analyzed = []

        for item in items:
            a = self._analyze_single(item)
            analyzed.append(a)

        analyzed.sort(key=lambda x: x.score, reverse=True)
        return analyzed

    def _analyze_single(self, item: Dict) -> AnalyzedItem:
        """Analyse un item individuel"""
        title = item.get('title', '').lower()
        summary = item.get('summary', '').lower()
        source = item.get('source', '').lower()
        full_text = f"{title} {summary}"

        # ── Exclusions (marketing, spam) ──
        if self._is_excluded(full_text):
            return AnalyzedItem(item, 'P3', 'Other', 0, 'Exclu (bruit)')

        # ── Filtre bruit : articles non-IA qui matchent des keywords génériques ──
        if self._noise_re.search(full_text):
            return AnalyzedItem(item, 'P3', 'Other', 0, 'Exclu (hors scope IA)')

        # ── Priorité ──
        priority, priority_score = self._determine_priority(full_text)

        # ── Catégorie ──
        category = self._determine_category(full_text, source)

        # ── Boost source ──
        source_boost = item.get('priority_boost', 0)
        if source_boost == 0:
            if any(s in source for s in ['openai', 'anthropic', 'google', 'deepmind', 'meta ai', 'mistral']):
                source_boost = 3
            elif any(s in source for s in ['hn:', 'github', 'hugging face']):
                source_boost = 2
            elif any(s in source for s in ['x: @sama', 'x: @openai', 'x: @anthropicai', 'x: @karpathy']):
                source_boost = 2
            elif 'x: @' in source:
                source_boost = 1
            elif any(s in source for s in ['techcrunch', 'verge', 'wired', 'venturebeat']):
                source_boost = 1

        # ── Boost récence ──
        recency_boost = 0
        try:
            published = item.get('published')
            if published:
                pub_date = datetime.fromisoformat(published.replace('Z', '+00:00'))
                hours_ago = (datetime.now() - pub_date.replace(tzinfo=None)).total_seconds() / 3600
                if hours_ago < 6:
                    recency_boost = 2
                elif hours_ago < 12:
                    recency_boost = 1
        except Exception:
            pass

        # ── Engagement ──
        engagement = min(item.get('score', 0) // 100, 5)

        # ── Score final ──
        total = priority_score + source_boost + recency_boost + engagement

        # ── Raison (debug) ──
        reasons = []
        if priority_score > 0:
            reasons.append(f"{priority}")
        if source_boost:
            reasons.append("source majeure")
        if recency_boost:
            reasons.append("très récent")
        if engagement:
            reasons.append(f"engagement élevé ({item.get('score', 0)})")

        return AnalyzedItem(item, priority, category, total, '; '.join(reasons))

    def _is_excluded(self, text: str) -> bool:
        """Vérifie les exclusions (marketing, spam)"""
        for kw in self.config.EXCLUDE_KEYWORDS:
            if kw.lower() in text:
                return True
        for domain in self.config.EXCLUDE_DOMAINS:
            if domain.lower() in text:
                return True
        return False

    def _determine_priority(self, text: str) -> Tuple[str, int]:
        """Détermine la priorité P0/P1/P2/P3 par mots-clés"""
        t = text.lower()

        p0 = sum(1 for kw in self.config.PRIORITY_KEYWORDS['P0'] if kw.lower() in t)
        if p0 > 0:
            return 'P0', 10 + p0 * 2

        p1 = sum(1 for kw in self.config.PRIORITY_KEYWORDS['P1'] if kw.lower() in t)
        if p1 > 0:
            return 'P1', 6 + p1

        p2 = sum(1 for kw in self.config.PRIORITY_KEYWORDS['P2'] if kw.lower() in t)
        if p2 > 0:
            return 'P2', 3 + p2

        return 'P3', 1

    def _determine_category(self, text: str, source: str) -> str:
        """Catégorise la news"""
        t = text.lower()

        if any(kw in t for kw in ['security', 'vulnerability', 'exploit', 'jailbreak', 'attack', 'safety', 'red team', 'data breach']):
            return 'Security'
        if any(kw in t for kw in ['funding', 'million', 'billion', 'acquisition', 'acquired', 'ipo', 'investment', 'raised', 'startup', 'series']):
            return 'Business'
        if any(kw in t for kw in ['model', 'gpt', 'claude', 'llama', 'mistral', 'gemini', 'benchmark', 'paper', 'research', 'weights', 'parameters']):
            return 'Model'
        if any(kw in t for kw in ['launches', 'tool', 'app', 'feature', 'api', 'integration', 'product', 'plugin', 'extension']):
            return 'Product'
        if any(kw in t for kw in ['framework', 'library', 'cuda', 'gpu', 'training', 'inference', 'optimization', 'quantization', 'distillation', 'fine-tun']):
            return 'Infra'

        return 'Other'

    # ──────────────────────────────────────
    # Déduplication avancée
    # ──────────────────────────────────────

    def deduplicate(self, items: List[AnalyzedItem]) -> List[AnalyzedItem]:
        """Déduplication agressive — garde la meilleure version de chaque sujet"""
        unique = []
        seen_terms_list: List[Set[str]] = []

        for item in items:
            title = item.original.get('title', '').lower()
            summary = item.original.get('summary', '').lower()[:120]
            combined = f"{title} {summary}"

            terms = set(self._extract_key_terms(combined))

            if not terms:
                # Pas de termes exploitables → garder si P0/P1
                if item.priority in ('P0', 'P1'):
                    unique.append(item)
                continue

            # Vérifier le chevauchement avec les items déjà gardés
            is_dup = False
            for existing in seen_terms_list:
                if not existing:
                    continue
                overlap = len(terms & existing)
                smaller = min(len(terms), len(existing))
                # Seuil à 50% : si la moitié des termes sont communs → doublon
                if smaller > 0 and overlap / smaller >= 0.5:
                    is_dup = True
                    break

            if not is_dup:
                seen_terms_list.append(terms)
                unique.append(item)

        return unique

    def _extract_key_terms(self, text: str) -> List[str]:
        """Extrait les termes-clés discriminants pour la dédup"""
        stop = {
            # Anglais courant
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'to', 'of',
            'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
            'during', 'before', 'after', 'above', 'below', 'between', 'under',
            'and', 'but', 'or', 'yet', 'so', 'if', 'because', 'while', 'where',
            'when', 'that', 'which', 'who', 'whom', 'what', 'this', 'these', 'those',
            'not', 'no', 'nor', 'very', 'too', 'also', 'than', 'then', 'there',
            'here', 'its', 'our', 'your', 'their', 'his', 'her', 'my',
            # Verbes / mots génériques dans les titres tech
            'new', 'just', 'now', 'get', 'got', 'use', 'using', 'used',
            'launches', 'launched', 'launch', 'launching',
            'announces', 'announced', 'announcing', 'announce',
            'releases', 'released', 'release', 'releasing',
            'introduces', 'introducing', 'introduce',
            'shows', 'show', 'showing', 'showed',
            'says', 'said', 'says', 'telling', 'told',
            'makes', 'made', 'making', 'make',
            'gives', 'gave', 'giving', 'give',
            'first', 'like', 'think', 'going', 'love',
            'more', 'about', 'some', 'getting', 'today',
            # Handles / noms de plateformes
            'https', 'http', 'com', 'www', 'pic', 'video',
            'twitter', 'nitter', 'reddit', 'github',
            'sama', 'openai', 'therundownai', 'anthropicai', 'googleai',
        }

        words = re.findall(r'\b[a-zA-Z0-9][a-zA-Z0-9\-\.]+\b', text.lower())
        terms = [w for w in words if w not in stop and len(w) > 2]
        return terms[:7]
