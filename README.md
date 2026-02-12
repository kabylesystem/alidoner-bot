# AliDonerBot 🥙

Bot Telegram qui envoie chaque matin un digest IA ultra-court, actionnable et pédagogique. 10-12 news max, priorisées P0/P1/P2, 100% en français, lisible en 90 secondes les yeux mi-clos.

## Ce que ça fait

- **Collecte** des news IA depuis 25+ sources (RSS, Hacker News, Reddit, GitHub Trending)
- **Priorise** automatiquement (P0 = breaking, P1 = important, P2 = intéressant)
- **Enrichit via LLM** (Cerebras, gratuit) : résumés autonomes, "Pourquoi ça compte", "Le saviez-vous"
- **Formate** un message Telegram mobile-friendly avec sections Top, Concept du jour, Idée à piquer
- **Envoie** automatiquement chaque matin via systemd

## Sources

| Type | Sources | API payante ? |
|------|---------|---------------|
| RSS | OpenAI, Anthropic, Google AI, Meta AI, TechCrunch, The Verge, Ars Technica, etc. | Non |
| Hacker News | Algolia API (queries IA) | Non |
| Reddit | r/MachineLearning, r/LocalLLaMA, r/artificial, etc. | Non |
| GitHub | Trending repos (Python, ML) | Non |
| X/Twitter | Karpathy, Sam Altman, etc. (via Nitter/RSSHub, limité) | Non* |

*Le Free tier de l'API X ne permet pas la lecture. Le bot fonctionne très bien sans.

## Installation

```bash
git clone https://github.com/ton-user/alidoner-bot.git
cd alidoner-bot
pip install -r requirements.txt
cp .env.example .env
# Remplir .env avec tes tokens (voir ci-dessous)
```

## Configuration

Crée un fichier `.env` à la racine :

```env
# Obligatoire — via @BotFather sur Telegram
TELEGRAM_BOT_TOKEN=ton_token
TELEGRAM_CHAT_ID=ton_chat_id

# Recommandé — Cerebras (gratuit, 1M tokens/jour)
# https://cloud.cerebras.ai
CEREBRAS_API_KEY=ta_cle

# Optionnel — Ollama Cloud (fallback)
OLLAMA_API_KEY=ta_cle
```

Pour obtenir ton `CHAT_ID` :
```bash
python setup_telegram.py
```

## Utilisation

```bash
# Lancer manuellement (dernières 24h, envoi sur Telegram)
python bot.py --days 1 --send

# Dernière semaine, sauvegarder en fichier
python bot.py --days 7 --output veille.txt

# Depuis le dernier run
python bot.py --send --since-last-run

# Lancer le listener (écoute /start, /stop, /status)
python subscribers.py
```

### Système d'abonnés

N'importe qui peut s'abonner au bot :
1. Ouvrir `t.me/TON_BOT` sur Telegram
2. Taper `/start`
3. C'est tout — le digest arrive chaque matin

Commandes disponibles :
- `/start` — S'abonner
- `/stop` — Se désabonner
- `/status` — Vérifier son abonnement

## Automatiser (systemd)

Deux services : le **listener** (écoute /start en permanence) et le **timer** (envoie le digest chaque matin).

```bash
# Copier les fichiers service/timer
cp alidoner.service ~/.config/systemd/user/
cp alidoner.timer ~/.config/systemd/user/
cp alidoner-listener.service ~/.config/systemd/user/

# Activer tout
systemctl --user daemon-reload
systemctl --user enable --now alidoner.timer
systemctl --user enable --now alidoner-listener.service
loginctl enable-linger $USER

# Vérifier
systemctl --user status alidoner.timer
systemctl --user status alidoner-listener.service
```

- **alidoner.timer** : envoie le digest chaque jour à 9h00 CET
- **alidoner-listener** : tourne 24/7, capte les /start /stop /status

## Structure

```
├── bot.py                  # Orchestrateur principal
├── config.py               # Sources, mots-clés, paramètres
├── analyzer.py             # Priorisation P0-P3, scoring, dédup
├── ollama_summarizer.py    # Enrichissement LLM (DeepSeek-V3.2 / Ollama Cloud)
├── telegram_formatter.py   # Mise en page Telegram
├── telegram_sender.py      # Envoi via Telegram Bot API
├── subscribers.py          # Gestion abonnés (/start, /stop, /status)
├── setup_telegram.py       # Assistant config Telegram
├── sources/
│   ├── rss_fetcher.py      # 25+ flux RSS
│   ├── hackernews.py       # HN via Algolia
│   ├── reddit.py           # Reddit JSON
│   ├── github_trending.py  # GitHub trending (scraping)
│   └── twitter_fetcher.py  # X/Twitter (Nitter/RSSHub)
├── .env.example            # Template de config
├── .gitignore              # Exclut .env, subscribers.json, output/
└── requirements.txt
```

## Exemple de message

```
🥙 AliDonerBot — 12 fév 2026
📅 dernières 24h

━━━━━━━━━━━━━━━━━━━━
🔥 L'ESSENTIEL
━━━━━━━━━━━━━━━━━━━━

1. 💰 Anthropic lève 30 Mds$ en Série G

  Lead Lightspeed + Spark Capital, valo 380 Mds$. L'argent finance Claude 4 et l'expansion Europe.
  👉 Les prix de l'API Claude vont baisser, Claude 4 arrive d'ici 6 mois.
  🎓 Une Series G c'est le top 0.1% des startups.
  ↗ https://...

2. 🧠 GPT-5 bat tous les benchmarks sur MMLU

  ...

━━━━━━━━━━━━━━━━━━━━
🎓 2 MIN POUR COMPRENDRE
━━━━━━━━━━━━━━━━━━━━

Concept du jour expliqué simplement...

━━━━━━━━━━━━━━━━━━━━
💡 IDÉE À PIQUER
━━━━━━━━━━━━━━━━━━━━

Idée concrète à implémenter basée sur l'actu du jour...

—
📊 10 news · Blogs · HN · Reddit · GitHub
```

## Coût

**0€.** Toutes les sources sont gratuites. Le LLM utilise le free tier Cerebras (1M tokens/jour, largement suffisant).

## Licence

MIT — Fais-en ce que tu veux.
