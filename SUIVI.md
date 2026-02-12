# SUIVI.md — AliDonerBot 🥙

## Ce qui a été fait (dans l'ordre)

### Session 1 : Création du bot de base

**Fichiers créés from scratch :**
- `bot.py` — Orchestrateur principal (collect → analyze → format → save)
- `config.py` — 25 sources RSS, 5 subreddits, 6 queries HN, 4 topics GitHub
- `analyzer.py` — Priorisation P0/P1/P2/P3 par mots-clés, scoring, dédup
- `telegram_formatter.py` — Formatage sections Top/Radar/Actions
- `sources/rss_fetcher.py` — Fetcher RSS avec feedparser
- `sources/hackernews.py` — API Algolia HN (gratuit)
- `sources/reddit.py` — Reddit JSON API
- `sources/github_trending.py` — Scraping GitHub trending

**Ce qui marchait :** Collecte multi-sources, priorisation, formatage, sauvegarde fichier.
**Ce qui manquait :** Pas d'envoi Telegram, pas de résumé IA, pas de X/Twitter.

---

### Session 2 : Upgrade AliDonerBot + Telegram + Ollama + X

#### 1. Envoi Telegram réel
- `telegram_sender.py` — Envoi via Bot API HTTP (requests, pas asyncio — plus fiable)
- `setup_telegram.py` — Script interactif pour config BotFather + chat_id
- `.env` — Token + chat_id + clé Ollama
- Fix du bug "event loop is closed" : remplacé python-telegram-bot async par appels HTTP directs

#### 2. Résumé intelligent via Ollama Cloud
- `ollama_summarizer.py` — Appelle Ollama Cloud API (`ollama.com/api/chat`)
- Modèle : `gemini-3-flash-preview` (le plus rapide dispo en cloud)
- Génère pour chaque item : résumé FR, "Pourquoi ça compte", "Le saviez-vous" (pédagogique)
- Génère un "Concept du jour" vulgarisé
- Fallback gracieux si quota épuisé (429) : skip instantané, pas de blocage

#### 3. X / Twitter via Nitter
- `sources/twitter_fetcher.py` — Fetch via instances Nitter RSS
- Détecte automatiquement l'instance qui marche (rotation entre 5)
- Comptes suivis : @sama, @OpenAI, @AnthropicAI, @GoogleAI, @MistralAI, @huggingface, @karpathy, @ylecun, @swyx, @bettercallmedhi, @TheRundownAI
- Limitation : Nitter est instable, certaines instances bloquent. Pas garanti 100%.

#### 4. Reddit amélioré
- Réécrit pour utiliser RSS d'abord (plus fiable que JSON API bloqué)
- Fallback JSON si RSS échoue

#### 5. Filtrage strict + dédup avancée
- `NOISE_PATTERNS` — Regex pour virer le bruit (fintech, edtech, clickbait, etc.)
- Sources YourStory et Inc42 retirées (trop de bruit non-IA)
- Dédup fuzzy : si 50% des termes-clés d'un article matchent un article déjà gardé → doublon éliminé
- Résultat : 49 items P3 (bruit) sur 105 collectés = 47% de filtrage

#### 6. Mise en page Telegram refaite
- Tout en français (date, sections, actions, pourquoi)
- Emojis par catégorie (🧠 Model, 💰 Business, 🔒 Security, 🛠 Product, ⚙️ Infra)
- Séparateurs visuels `━━━` pour les sections
- Titres nettoyés : plus de @handle:, plus de sauts de ligne, tronqués à 120 chars
- Résumés nettoyés : HTML viré, markdown viré, pas de doublon avec le titre
- 5 items TOP max + 3 Radar = message concis lisible en 90 secondes
- Actions concrètes et pertinentes

#### 7. Optimisation vitesse
- Queries HN réduites de 12 à 7
- Topics GitHub réduits de 10 à 4
- Sleep RSS réduit de 0.5s à 0.2s
- Twitter : trouve l'instance une seule fois puis l'utilise pour tous les comptes
- Résultat : ~60-80s au lieu de 5 min

---

## Architecture finale

```
bot veille/
├── bot.py                     # AliDonerBot — orchestrateur CLI
├── config.py                  # Sources + filtrage + limites
├── analyzer.py                # P0/P1/P2/P3 + scoring + dédup fuzzy
├── telegram_formatter.py      # Mise en page FR + emojis catégorie
├── telegram_sender.py         # Envoi HTTP Telegram (sync, fiable)
├── ollama_summarizer.py       # Résumé IA cloud (Ollama)
├── setup_telegram.py          # Setup interactif BotFather
├── .env                       # Secrets (token, chat_id, ollama key)
├── .last_run                  # Timestamp dernier run
├── sources/
│   ├── rss_fetcher.py         # 28 flux RSS
│   ├── hackernews.py          # API Algolia (7 queries)
│   ├── reddit.py              # RSS + JSON fallback (7 subs)
│   ├── github_trending.py     # Scraping (4 topics)
│   └── twitter_fetcher.py     # Nitter RSS (11 comptes)
├── output/                    # Fichiers de sortie
├── SUIVI.md                   # CE FICHIER
├── CLAUDE.md                  # Guide Claude AI
└── README.md                  # Doc projet
```

## Commandes

```bash
# Setup Telegram (une fois)
python setup_telegram.py

# Lancer la veille + envoyer
python bot.py --send

# Depuis le dernier run
python bot.py --since-last-run --send

# Mode planifié (tourne en continu)
python bot.py --schedule 08:00

# Cron quotidien
0 8 * * * cd "/home/user/future/perso projects/bot veille" && python bot.py --since-last-run --send
```

## Limitations connues

- **Ollama Cloud** : quota gratuit limité — quand épuisé, les résumés IA sont remplacés par des templates
- **X/Twitter** : Nitter est instable, les instances changent souvent. 0 tweets certains jours.
- **Reddit** : JSON API parfois bloqué (403), RSS fonctionne comme fallback
- **RSS** : Certains blogs ont des feeds cassés (Anthropic, Meta AI, etc.)
- **Pas de traduction** : Les titres restent en anglais (Ollama les traduirait quand le quota est dispo)
