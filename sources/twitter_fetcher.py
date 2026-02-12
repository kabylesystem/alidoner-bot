"""
AliDonerBot — Fetch tweets IA depuis X/Twitter
Stratégie :
  1. X API v2 via OAuth 1.0a (lecture tweets, Free tier)
  2. Nitter RSS (fallback gratuit, instances multiples)
  3. RSSHub bridge (fallback secondaire)
"""
import os
import re
import requests
import feedparser
import time
import hmac
import hashlib
import base64
import urllib.parse
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dateutil import parser as date_parser
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

# ═══ Nitter / bridges RSS ═══
NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://xcancel.com",
    "https://nitter.privacyredirect.com",
    "https://nitter.net",
    "https://nitter.cz",
    "https://nitter.1d4.us",
]

RSSHUB_INSTANCES = [
    "https://rsshub.app",
    "https://rsshub.rssforever.com",
]

# Comptes X à suivre — IA, tech, builders
DEFAULT_ACCOUNTS = [
    # Tes favoris
    ("sama", "Sam Altman"),
    ("karpathy", "Andrej Karpathy"),
    ("BetterCallMedhi", "Mehdi"),
    # Labs officiels
    ("OpenAI", "OpenAI"),
    ("AnthropicAI", "Anthropic"),
    ("GoogleDeepMind", "Google DeepMind"),
    ("MistralAI", "Mistral AI"),
    ("xaboratory", "xAI"),
    # Builders / Voix clés
    ("huggingface", "Hugging Face"),
    ("ylecun", "Yann LeCun"),
    ("JimFan", "Jim Fan (NVIDIA)"),
    ("swyx", "swyx"),
    # Agrégateurs IA
    ("TheRundownAI", "The Rundown AI"),
    ("AISafetyMemes", "AI Safety Memes"),
]


class TwitterFetcher:
    def __init__(self, accounts: List[tuple] = None):
        self.accounts = accounts or DEFAULT_ACCOUNTS
        self._working_nitter = None
        self._working_rsshub = None

        # OAuth 1.0a credentials (X API v2 Free tier — lecture)
        self.consumer_key = os.getenv("X_CONSUMER_KEY", "").strip()
        self.consumer_secret = os.getenv("X_CONSUMER_SECRET", "").strip()
        self.access_token = os.getenv("X_ACCESS_TOKEN", "").strip()
        self.access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET", "").strip()

        self.use_api = all([
            self.consumer_key, self.consumer_secret,
            self.access_token, self.access_token_secret,
        ])

    def fetch_all(self, days_back: int = 2) -> List[Dict]:
        """Fetch tweets, multi-stratégie"""
        print("  📡 Fetching X/Twitter...")
        entries = []

        # Stratégie 1 : X API v2 via OAuth 1.0a (nécessite Basic tier $100/mois)
        if self.use_api:
            print("    📍 Tentative X API v2 (OAuth 1.0a)...")
            entries = self._fetch_via_api(days_back)
            if entries:
                print(f"    ✓ API : {len(entries)} tweets")

        # Stratégie 2 : Nitter RSS (public instances)
        if len(entries) < 3:
            nitter_entries = self._fetch_via_nitter(days_back)
            if nitter_entries:
                print(f"    📍 Nitter : {len(nitter_entries)} tweets")
                entries.extend(nitter_entries)

        # Stratégie 3 : RSSHub bridge
        if len(entries) < 3:
            rsshub_entries = self._fetch_via_rsshub(days_back)
            if rsshub_entries:
                print(f"    📍 RSSHub : {len(rsshub_entries)} tweets")
                entries.extend(rsshub_entries)

        if not entries:
            print("    ⚠️  Aucune source X dispo — skip")
            return []

        # Déduplique par titre
        seen_titles = set()
        unique = []
        for e in entries:
            key = e.get("title", "").lower().strip()[:60]
            if key and key not in seen_titles:
                seen_titles.add(key)
                unique.append(e)

        unique.sort(key=lambda x: x.get("published", ""), reverse=True)
        print(f"    ✓ {len(unique)} tweets uniques")
        return unique[:15]

    # ──────────────────────────────────────
    # Méthode 1 : X API v2 via OAuth 1.0a
    # ──────────────────────────────────────

    def _fetch_via_api(self, days_back: int) -> List[Dict]:
        """Fetch via X API v2 avec signature OAuth 1.0a"""
        all_entries = []

        for username, display_name in self.accounts:
            try:
                # Récupérer le user_id
                url = f"https://api.x.com/2/users/by/username/{username}"
                resp = self._oauth_get(url)
                if resp.status_code == 429:
                    print("    ⚠️  Rate limit X API — arrêt")
                    break
                if resp.status_code != 200:
                    continue

                user_id = resp.json().get("data", {}).get("id")
                if not user_id:
                    continue

                # Récupérer les tweets récents
                since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
                tweets_url = f"https://api.x.com/2/users/{user_id}/tweets"
                params = {
                    "max_results": "5",
                    "start_time": since,
                    "tweet.fields": "created_at,public_metrics,text",
                }

                resp = self._oauth_get(tweets_url, params)
                if resp.status_code == 429:
                    print("    ⚠️  Rate limit X API — arrêt")
                    break
                if resp.status_code != 200:
                    continue

                tweets = resp.json().get("data", [])
                if not tweets:
                    continue

                for tweet in tweets:
                    text = tweet.get("text", "")
                    tweet_id = tweet.get("id", "")
                    created = tweet.get("created_at", "")
                    metrics = tweet.get("public_metrics", {})

                    if text.startswith("RT @"):
                        continue
                    if len(text) < 30:
                        continue

                    title = self._clean_tweet_text(text)
                    if len(title) > 140:
                        title = title[:137] + "…"

                    all_entries.append({
                        "source": f"X: @{username}",
                        "title": title,
                        "link": f"https://x.com/{username}/status/{tweet_id}",
                        "summary": text[:300],
                        "published": created,
                        "type": "twitter",
                        "score": metrics.get("like_count", 0) + metrics.get("retweet_count", 0) * 3,
                    })

                time.sleep(0.3)

            except Exception:
                continue

        return all_entries

    def _oauth_get(self, url: str, params: dict = None) -> requests.Response:
        """GET request avec signature OAuth 1.0a (HMAC-SHA1)"""
        params = params or {}
        oauth_params = {
            "oauth_consumer_key": self.consumer_key,
            "oauth_nonce": uuid.uuid4().hex,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": self.access_token,
            "oauth_version": "1.0",
        }

        # Tous les params combinés pour la signature
        all_params = {**params, **oauth_params}
        sorted_params = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
            for k, v in sorted(all_params.items())
        )

        base_string = f"GET&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(sorted_params, safe='')}"
        signing_key = f"{urllib.parse.quote(self.consumer_secret, safe='')}&{urllib.parse.quote(self.access_token_secret, safe='')}"

        signature = base64.b64encode(
            hmac.new(
                signing_key.encode("utf-8"),
                base_string.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        oauth_params["oauth_signature"] = signature

        auth_header = "OAuth " + ", ".join(
            f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
            for k, v in sorted(oauth_params.items())
        )

        headers = {"Authorization": auth_header}
        return requests.get(url, params=params, headers=headers, timeout=10)

    # ──────────────────────────────────────
    # Méthode 2 : Nitter RSS
    # ──────────────────────────────────────

    def _fetch_via_nitter(self, days_back: int) -> List[Dict]:
        if not self._working_nitter:
            self._working_nitter = self._find_working_instance(
                NITTER_INSTANCES, "/{username}/rss"
            )
        if not self._working_nitter:
            return []
        return self._fetch_rss_entries(self._working_nitter, "/{username}/rss", days_back)

    # ──────────────────────────────────────
    # Méthode 3 : RSSHub bridge
    # ──────────────────────────────────────

    def _fetch_via_rsshub(self, days_back: int) -> List[Dict]:
        if not self._working_rsshub:
            self._working_rsshub = self._find_working_instance(
                RSSHUB_INSTANCES, "/twitter/user/{username}"
            )
        if not self._working_rsshub:
            return []
        return self._fetch_rss_entries(self._working_rsshub, "/twitter/user/{username}", days_back)

    # ──────────────────────────────────────
    # Logique commune RSS
    # ──────────────────────────────────────

    def _fetch_rss_entries(self, base_url: str, path_tpl: str, days_back: int) -> List[Dict]:
        all_entries = []
        cutoff = datetime.now() - timedelta(days=days_back)

        for username, display_name in self.accounts:
            try:
                path = path_tpl.replace("{username}", username)
                url = f"{base_url}{path}"
                resp = requests.get(
                    url, timeout=6,
                    headers={"User-Agent": "Mozilla/5.0 (AliDonerBot/1.0)"}
                )
                if resp.status_code != 200:
                    continue
                if "<rss" not in resp.text[:500] and "<feed" not in resp.text[:500]:
                    continue

                feed = feedparser.parse(resp.text)

                for entry in feed.entries[:3]:
                    published = self._parse_date(entry)
                    if published and published < cutoff:
                        continue

                    raw_title = entry.get("title", "")
                    title = self._clean_tweet_text(raw_title)
                    if not title or len(title) < 20:
                        continue
                    if len(title) > 140:
                        title = title[:137] + "…"

                    link = entry.get("link", f"https://x.com/{username}")
                    if "nitter" in link or "xcancel" in link or "rsshub" in link:
                        link = f"https://x.com/{username}"

                    all_entries.append({
                        "source": f"X: @{username}",
                        "title": title,
                        "link": link,
                        "summary": title,
                        "published": published.isoformat() if published else None,
                        "type": "twitter",
                        "score": 0,
                    })

                time.sleep(0.15)
            except Exception:
                continue

        return all_entries

    def _find_working_instance(self, instances: list, path_tpl: str) -> Optional[str]:
        test_user = "sama"
        for inst in instances:
            try:
                path = path_tpl.replace("{username}", test_user)
                url = f"{inst}{path}"
                resp = requests.get(
                    url, timeout=5,
                    headers={"User-Agent": "Mozilla/5.0 (AliDonerBot/1.0)"}
                )
                if resp.status_code == 200 and (
                    "<item" in resp.text or "<entry" in resp.text
                ):
                    print(f"    ✓ Instance active : {inst}")
                    return inst
            except Exception:
                continue
        return None

    # ──────────────────────────────────────
    # Utilitaires
    # ──────────────────────────────────────

    @staticmethod
    def _clean_tweet_text(text: str) -> str:
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'@\w+', '', text)
        text = re.sub(r'#(\w+)', r'\1', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        for field in ['published_parsed', 'updated_parsed']:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    return datetime.fromtimestamp(time.mktime(getattr(entry, field)))
                except Exception:
                    pass
        for field in ['published', 'updated']:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    dt = date_parser.parse(getattr(entry, field))
                    return dt.replace(tzinfo=None) if dt.tzinfo else dt
                except Exception:
                    pass
        return None
