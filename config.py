"""
Configuration du Bot AliDonerBot — Veille IA
Sources RSS, API gratuites, scraping léger, envoi Telegram
"""

import os
import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Charger .env si présent
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# === TELEGRAM ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
BOT_NAME = "AliDonerBot"

# === OLLAMA (Cloud API pour résumés IA) ===
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")

# === LAST RUN TRACKING ===
LAST_RUN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_run")


def get_last_run() -> Optional[datetime]:
    """Récupère le timestamp du dernier run"""
    try:
        if os.path.exists(LAST_RUN_FILE):
            with open(LAST_RUN_FILE, "r") as f:
                ts = f.read().strip()
                return datetime.fromisoformat(ts)
    except Exception:
        pass
    return None


def save_last_run():
    """Sauvegarde le timestamp du run actuel"""
    with open(LAST_RUN_FILE, "w") as f:
        f.write(datetime.now().isoformat())


# === SOURCES ===

@dataclass
class Source:
    name: str
    url: str
    type: str  # 'rss', 'hackernews', 'reddit', 'github', 'scraping'
    category: str  # 'labs', 'media', 'india', 'opensource', 'community', 'research'
    priority_boost: int = 0  # Boost de priorité pour certaines sources


# === SOURCES RSS ===
RSS_SOURCES = [
    # --- Labs et entreprises AI (signaux forts) ---
    Source("OpenAI Blog", "https://openai.com/blog/rss.xml", "rss", "labs", 2),
    Source("Anthropic News", "https://www.anthropic.com/rss.xml", "rss", "labs", 2),
    Source("Google AI Blog", "http://ai.googleblog.com/feeds/posts/default", "rss", "labs", 2),
    Source("DeepMind Blog", "https://deepmind.google/blog/rss/", "rss", "labs", 2),
    Source("Meta AI Blog", "https://ai.meta.com/blog/rss/", "rss", "labs", 2),
    Source("Mistral AI", "https://mistral.ai/rss.xml", "rss", "labs", 2),
    Source("Cohere Blog", "https://cohere.com/rss.xml", "rss", "labs", 1),
    Source("Stability AI", "https://stability.ai/blog/rss.xml", "rss", "labs", 1),
    Source("xAI Blog", "https://x.ai/blog/rss.xml", "rss", "labs", 2),

    # --- Médias tech internationaux ---
    Source("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "rss", "media", 1),
    Source("The Verge AI", "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml", "rss", "media", 1),
    Source("Wired AI", "https://www.wired.com/tag/artificial-intelligence/feed/", "rss", "media", 1),
    Source("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", "rss", "media", 1),
    Source("Ars Technica AI", "https://arstechnica.com/tag/artificial-intelligence/feed/", "rss", "media", 1),
    Source("The Information", "https://www.theinformation.com/feed", "rss", "media", 1),

    # --- Inde et émergents (uniquement les feeds IA, pas les généralistes) ---
    Source("Analytics India Mag", "https://analyticsindiamag.com/feed/", "rss", "india", 1),
    # YourStory et Inc42 retirés — trop de bruit non-IA (fintech, edtech, etc.)

    # --- Open source et dev (signaux builders) ---
    Source("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "rss", "opensource", 2),
    Source("LangChain Blog", "https://blog.langchain.dev/rss/", "rss", "opensource", 1),
    Source("Pytorch Blog", "https://pytorch.org/blog/atom.xml", "rss", "opensource", 1),
    Source("TensorFlow Blog", "https://blog.tensorflow.org/feeds/posts/default", "rss", "opensource", 1),
    Source("Ollama Blog", "https://ollama.com/blog/rss", "rss", "opensource", 2),
    Source("Simon Willison", "https://simonwillison.net/atom/everything/", "rss", "opensource", 1),

    # --- Recherche ---
    Source("Papers with Code", "https://paperswithcode.com/rss", "rss", "research", 1),
    Source("MIT AI News", "http://news.mit.edu/rss/topic/artificial-intelligence2", "rss", "research", 1),
    Source("BAIR Blog", "http://bair.berkeley.edu/blog/feed.xml", "rss", "research", 1),

    # --- Newsletters / Agrégateurs IA (quand ils ont un RSS) ---
    Source("Ben's Bites", "https://www.bensbites.com/feed", "rss", "media", 1),
    Source("The Rundown AI", "https://www.therundown.ai/feed", "rss", "media", 1),
]

# === SOURCES REDDIT ===
REDDIT_SOURCES = [
    ("LocalLLaMA", "https://www.reddit.com/r/LocalLLaMA/hot.json?limit=15", "community"),
    ("MachineLearning", "https://www.reddit.com/r/MachineLearning/hot.json?limit=10", "research"),
    ("OpenAI", "https://www.reddit.com/r/OpenAI/hot.json?limit=10", "community"),
    ("ClaudeAI", "https://www.reddit.com/r/ClaudeAI/hot.json?limit=10", "community"),
    ("singularity", "https://www.reddit.com/r/singularity/hot.json?limit=10", "community"),
    ("selfhosted", "https://www.reddit.com/r/selfhosted/hot.json?limit=10", "community"),
    ("StableDiffusion", "https://www.reddit.com/r/StableDiffusion/hot.json?limit=10", "community"),
]

# === HACKER NEWS QUERIES ===
# Réduit pour la vitesse — les grosses queries capturent déjà tout
HACKERNEWS_QUERIES = [
    "LLM",
    "OpenAI",
    "Claude AI",
    "open source AI",
    "Show HN AI",
    "AI startup",
    "AI regulation",
]

# === GITHUB TOPICS ===
# Réduit aux topics les plus pertinents
GITHUB_TOPICS = [
    "llm",
    "ai",
    "langchain",
    "ai-agents",
]

# === FILTRAGE ===
PRIORITY_KEYWORDS = {
    "P0": [  # Critique - doit être signalé immédiatement
        # Annonces majeures
        "announces", "released", "launch", "launched", "launches",
        "breakthrough", "GPT-5", "GPT-4o", "Claude 4", "Claude 3.5",
        "Gemini 2", "AGI",
        # Business / Marché
        "funding", "acquisition", "acquired", "IPO", "billion", "raised",
        "partnership", "merger",
        # Régulation / Incidents
        "regulation", "banned", "ban", "lawsuit", "sued", "shutdown",
        "outage", "down", "incident",
        # Sécurité
        "vulnerability", "security flaw", "exploit", "jailbreak",
        "data breach", "leak",
    ],
    "P1": [  # Important - à lire
        # Modèles / Recherche
        "new model", "update", "major", "significant", "benchmark",
        "SOTA", "state of the art", "paper", "research",
        # Produit / Outils
        "integration", "API", "open source", "released",
        "demo", "preview", "beta",
        # Builders / Indie dev
        "trending", "Show HN", "self-hosted", "local AI",
        "open weight", "fine-tune", "fine-tuning",
        # Business secondaire
        "partnership", "investment", "series",
    ],
    "P2": [  # Intéressant - sur le radar
        "tool", "feature", "tutorial", "guide", "how to",
        "comparison", "benchmark", "local", "self-hosted",
        "workflow", "automation", "agent", "RAG",
        "inference", "quantization", "distillation",
    ]
}

# === EXCLUSIONS (bruit) ===
EXCLUDE_KEYWORDS = [
    "click here", "limited time", "exclusive offer", "sponsored",
    "webinar", "register now", "early bird", "discount", "promo",
    "marketing", "sales", "whitepaper", "course", "bootcamp",
    "certificate", "enroll now", "free trial",
]

EXCLUDE_DOMAINS = [
    "spam", "clickbank", "affiliate",
]

# === CONFIGURATION SORTIE ===
MAX_TOP_ITEMS = 10     # Les 10-12 news les plus importantes
MAX_RADAR_ITEMS = 0    # Radar désactivé (remplacé par "Idée à piquer")
MAX_RUMORS = 0         # Rumeurs désactivées
MAX_ACTIONS = 0        # Actions désactivées (remplacé par "Idée à piquer")

DAYS_BACK = 1  # Par défaut : dernières 24h (changé de 2 à 1)
