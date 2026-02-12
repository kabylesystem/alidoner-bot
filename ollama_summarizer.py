"""
AliDonerBot — Résumé intelligent via LLM Cloud
Stratégie multi-provider (tous gratuits) :
  1. Cerebras (1M tokens/jour gratuit, ultra rapide)
  2. Ollama Cloud (fallback si Cerebras down)
Génère :
  - Résumés AUTONOMES (pas besoin de cliquer le lien)
  - "Pourquoi t'en as quelque chose à foutre" concret
  - "Le saviez-vous" vulga
  - "Concept du jour" pédagogique
  - "Idée du jour" actionnable pour tes projets
"""
import os
import requests
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ═══ Providers ═══
PROVIDERS = [
    {
        "name": "Ollama Cloud (DeepSeek-V3.2)",
        "url": "https://ollama.com/api/chat",
        "key_env": "OLLAMA_API_KEY",
        "model": "deepseek-v3.2",
    },
    {
        "name": "Ollama Cloud (GLM-5)",
        "url": "https://ollama.com/api/chat",
        "key_env": "OLLAMA_API_KEY",
        "model": "glm-5",
    },
    {
        "name": "Cerebras",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "key_env": "CEREBRAS_API_KEY",
        "model": "gpt-oss-120b",
    },
    {
        "name": "Cerebras (fallback)",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "key_env": "CEREBRAS_API_KEY",
        "model": "llama-3.3-70b",
    },
]


class LLMSummarizer:
    def __init__(self):
        self.provider = None
        self.api_url = None
        self.api_key = None
        self.model = None
        self.enabled = False

        for p in PROVIDERS:
            key = os.getenv(p["key_env"], "").strip()
            if key:
                self.provider = p["name"]
                self.api_url = p["url"]
                self.api_key = key
                self.model = p["model"]
                self.enabled = True
                break

        if self.enabled:
            print(f"    🧠 LLM actif : {self.provider} ({self.model})")
        else:
            print("    ⚠️  Aucune clé LLM configurée — résumés basiques")

    def enrich_items(self, items: List[Dict], max_items: int = 15) -> List[Dict]:
        """Enrichit les items en plusieurs batches pour éviter les coupures"""
        if not self.enabled:
            return items

        print(f"    🧠 Enrichissement via {self.provider}...")

        top = items[:max_items]
        batch_size = 8  # gpt-oss-120b coupe au-delà de ~8 items

        for start in range(0, len(top), batch_size):
            batch = top[start:start + batch_size]
            enriched = self._batch_enrich(batch, start_idx=start)
            for i, item in enumerate(enriched):
                idx = start + i
                if idx < len(items):
                    items[idx] = item

        # Rattrapage : traduire les titres non enrichis en FR
        missing = [i for i, item in enumerate(top) if not item.get("ai_title")]
        if missing:
            print(f"    🔄 Traduction FR pour {len(missing)} titres manquants...")
            self._translate_missing_titles(top, missing)
            for i in missing:
                if i < len(items):
                    items[i] = top[i]

        return items

    def _translate_missing_titles(self, items: List[Dict], indices: List[int]):
        """Traduit en FR les titres des items non enrichis"""
        block = ""
        for idx in indices:
            title = items[idx].get("title", "")[:120]
            block += f"[{idx+1}] {title}\n"

        prompt = f"""Traduis ces titres d'articles en français. Court, naturel, max 60 caractères chacun.
Format EXACT : [N] titre en français

{block}
Pas de markdown. Pas d'explication. Juste les titres traduits."""

        response = self._call_llm(prompt, max_tokens=500)
        if not response:
            return

        import re
        response = response.strip().strip('"').strip("'")
        response = re.sub(r'\*\*', '', response)
        for line in response.strip().split("\n"):
            line = line.strip()
            match = re.match(r'^\[(\d+)\]\s*(.*)', line)
            if match:
                idx = int(match.group(1)) - 1
                val = match.group(2).strip()
                if 0 <= idx < len(items) and val and len(val) > 3:
                    items[idx]["ai_title"] = val

    def _batch_enrich(self, items: List[Dict], start_idx: int = 0) -> List[Dict]:
        """Appel LLM pour enrichir un batch d'items"""

        items_block = ""
        for i, item in enumerate(items):
            n = i + 1  # Numérotation locale au batch (toujours 1-based)
            title = item.get("title", "")[:200]
            summary = item.get("summary", "")[:400]
            source = item.get("source", "")
            link = item.get("link", "")[:120]
            items_block += f"\n[{n}] ({source}) {title}\n    Contexte: {summary}\n    Lien: {link}\n"

        prompt = f"""Briefing IA du matin pour un dev/entrepreneur français fatigué. Il ne cliquera AUCUN lien.

RÈGLES DE FORMAT STRICTES :
- PAS de markdown, PAS de gras, PAS de listes à puces, PAS de tirets
- 4 lignes par item, chaque ligne sur UNE SEULE ligne
- Labels EXACTS : TITRE, RESUME, WHY, LEARN
- TOUT EN FRANÇAIS, y compris le TITRE (traduis-le si l'original est en anglais)

RÈGLES DE CONTENU :
- TITRE = Titre COURT en français (max 60 caractères). Pas de traduction mot à mot, reformule pour que ce soit naturel.
- RESUME = 2 phrases avec TOUS les faits. Levée : montant + investisseurs + valo. Modèle : perf chiffrée vs avant. Produit : ce que ça fait + pour qui.
- WHY = 1 phrase, impact concret PRÉCIS. Pas "tu peux profiter" mais des vrais chiffres et conséquences.
- LEARN = 1 fun fact surprenant qui N'EST PAS déjà dans le résumé.

COPIE CE FORMAT EXACTEMENT :
[1] TITRE: Anthropic lève 30Mds$ en Série G
[1] RESUME: Anthropic lève 30Mds$ en Series G (lead: Lightspeed, Spark Capital), valo 380Mds$. L'argent finance l'entraînement de Claude 4 et l'expansion en Europe.
[1] WHY: Les prix de l'API Claude vont baisser sous la pression, et Claude 4 arrive d'ici 6 mois max.
[1] LEARN: Une Series G c'est le top 0.1% des startups. Anthropic a 3 ans et vaut déjà plus que SpaceX au même âge.

Items :
{items_block}

TOUT EN FRANÇAIS. Factuel. Détaillé. PAS DE MARKDOWN. UNE LIGNE PAR CHAMP."""

        response = self._call_llm(prompt, max_tokens=4000)
        if response:
            return self._parse_response(response, items)
        return items

    def generate_daily_tip(self, items: List[Dict]) -> Optional[str]:
        """Génère LE concept du jour — vulga et mémorable"""
        if not self.enabled:
            return None

        titles = "\n".join(f"- {item.get('title', '')[:100]}" for item in items[:5])

        prompt = f"""Actus IA du jour :
{titles}

Écris UN concept du jour. 3 phrases MAX. Règles :
- Prends UN concept tech de ces news
- Explique-le avec une analogie de la vie courante
- Le lecteur (pas dev) doit comprendre en 10 secondes
- Ton : comme un pote, pas Wikipedia
- INTERDICTION de commencer par "Le concept de X c'est comme"

Bon exemple : "Le fine-tuning c'est comme briefer un chef étoilé pour qu'il fasse des kebabs. Il sait déjà cuisiner, tu lui montres 50 recettes de döner et en 2 jours il est meilleur que toi. C'est pour ça que plus personne n'entraîne de modèle from scratch."

Mauvais exemple : "Le Codex, c'est comme avoir un traducteur universel. Imagine que tu as..."

Réponds UNIQUEMENT avec le paragraphe. Rien d'autre."""

        tip = self._call_llm(prompt, max_tokens=300)
        if tip:
            tip = tip.strip().strip('"').strip("'")
            if len(tip) > 500:
                cut = tip[:500]
                last_dot = cut.rfind(".")
                tip = cut[:last_dot + 1] if last_dot > 200 else cut + "…"
            return tip
        return None

    def generate_actionable_idea(self, items: List[Dict]) -> Optional[str]:
        """Génère UNE idée concrète à implémenter inspirée des actus du jour"""
        if not self.enabled:
            return None

        context = ""
        for item in items[:5]:
            title = item.get("title", "")[:100]
            summary = item.get("ai_summary", item.get("summary", ""))[:150]
            context += f"- {title}: {summary}\n"

        prompt = f"""Actus IA du jour :
{context}

Inspire-toi d'UNE de ces actus et propose UNE idée concrète. 2 phrases max.
- Side project faisable en 1 week-end
- OU automatisation utile pour un business
- OU truc malin à tester dans sa vie
- Sois ULTRA spécifique : quel outil, quelle API, combien de temps, quel résultat
- INTERDICTION de dire "il pourrait" — dis "Prends X, fais Y, résultat Z"
- INTERDICTION de dire "ce qui pourrait lui faire gagner du temps"

Bon : "Prends l'API Codex-Spark d'OpenAI, branche-la sur ton repo GitHub, et génère automatiquement les tests unitaires de ton code. Setup en 30 min, gratuit en preview."
Mauvais : "Il pourrait utiliser l'API pour accélérer la production de code de haute qualité."

Réponds UNIQUEMENT avec l'idée."""

        idea = self._call_llm(prompt, max_tokens=200)
        if idea:
            idea = idea.strip().strip('"').strip("'")
            if len(idea) > 400:
                cut = idea[:400]
                last_dot = cut.rfind(".")
                idea = cut[:last_dot + 1] if last_dot > 200 else cut + "…"
            return idea
        return None

    # ──────────────────────────────────────
    # Appel LLM (multi-provider)
    # ──────────────────────────────────────

    def _call_llm(self, prompt: str, max_tokens: int = 1500) -> Optional[str]:
        result = self._call_provider(self.api_url, self.api_key, self.model, prompt, max_tokens)
        if result:
            return result

        for p in PROVIDERS:
            if p["name"] == self.provider:
                continue
            key = os.getenv(p["key_env"], "").strip()
            if not key:
                continue
            print(f"    🔄 Fallback vers {p['name']}...")
            result = self._call_provider(p["url"], key, p["model"], prompt, max_tokens)
            if result:
                self.provider = p["name"]
                self.api_url = p["url"]
                self.api_key = key
                self.model = p["model"]
                return result

        return None

    def _call_provider(self, url: str, key: str, model: str, prompt: str, max_tokens: int) -> Optional[str]:
        try:
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.4,
            }

            if "ollama.com" in url:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                }

            timeout = 120 if "ollama.com" in url else 45
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                msg = data.get("message", {})
                if msg:
                    return msg.get("content", "")
                return None
            elif resp.status_code == 429:
                print(f"    ⚠️  {model} : quota épuisé (429)")
                return None
            else:
                err = resp.text[:120]
                print(f"    ⚠️  Erreur {resp.status_code}: {err}")
                return None

        except requests.exceptions.Timeout:
            print(f"    ⚠️  Timeout LLM — skip")
            return None
        except Exception as e:
            print(f"    ⚠️  Erreur LLM: {e}")
            return None

    def _parse_response(self, response: str, items: List[Dict]) -> List[Dict]:
        """Parse la réponse structurée du LLM — ultra robuste face aux variations"""
        import re
        import unicodedata

        def strip_accents(s):
            return ''.join(
                c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn'
            )

        # Nettoyer : guillemets, markdown bold, préambule
        response = response.strip().strip('"').strip("'")
        response = re.sub(r'\*\*', '', response)
        response = re.sub(r'^[-•]\s+', '', response, flags=re.MULTILINE)
        # Supprimer les blocs code markdown
        response = re.sub(r'```[a-z]*\n?', '', response)

        current_idx = 0

        for line in response.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # Pattern: [N] LABEL: contenu
            idx_match = re.match(r'^\[(\d+)\]\s*(.*)', line)
            if idx_match:
                current_idx = int(idx_match.group(1)) - 1
                rest = idx_match.group(2).strip()
            else:
                # Pattern alternatif: N. LABEL: contenu  ou  N) LABEL: contenu
                alt_match = re.match(r'^(\d+)[.)]\s*(.*)', line)
                if alt_match:
                    current_idx = int(alt_match.group(1)) - 1
                    rest = alt_match.group(2).strip()
                else:
                    rest = line

            if current_idx < 0 or current_idx >= len(items):
                continue

            # Normaliser : enlever tous les accents
            rest_norm = strip_accents(rest).upper()

            # Extraire le contenu après le label
            # Gère "LABEL: contenu", "LABEL : contenu", "LABEL contenu"
            val_match = re.match(r'^[A-Z][A-Z ]*\s*[:：]\s*(.+)', rest, re.IGNORECASE)
            if not val_match:
                # Essayer sans les deux-points (LABEL suivi d'espace + texte long)
                val_match = re.match(r'^[A-Z]{2,}[A-Z ]*\s+(.{10,})', rest, re.IGNORECASE)
            if not val_match:
                continue
            val = val_match.group(1).strip()
            # Nettoyer les restes de markdown
            val = re.sub(r'^\*+\s*', '', val)
            val = re.sub(r'\*+$', '', val)
            val = val.strip()
            if not val or len(val) < 5:
                continue

            if re.match(r'^TITRE', rest_norm):
                items[current_idx]["ai_title"] = val
            elif re.match(r'^RESUM', rest_norm):
                items[current_idx]["ai_summary"] = val
            elif re.match(r'^(WHY|POURQUOI|PQ|IMPACT)', rest_norm):
                items[current_idx]["ai_why"] = val
            elif re.match(r'^(LEARN|APPRENDRE|SAVIEZ|FUN|LE SAV)', rest_norm):
                items[current_idx]["ai_learn"] = val

        enriched = sum(1 for item in items if item.get("ai_summary"))
        print(f"    ✅ {enriched}/{len(items)} items enrichis")
        return items


# Alias
OllamaSummarizer = LLMSummarizer
