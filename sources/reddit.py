"""
AliDonerBot — Fetch AI discussions from Reddit
Utilise les flux RSS publics (plus fiable que le JSON API qui bloque)
"""
import requests
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import time
from dateutil import parser as date_parser


class RedditFetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'AliDonerBot/1.0 (AI News Monitoring)',
        }

    def fetch_subreddit(self, subreddit: str, url: str) -> List[Dict]:
        """Fetch hot posts via RSS feed (plus fiable que JSON API)"""
        try:
            # RSS endpoint (souvent pas bloqué contrairement au JSON)
            rss_url = f"https://www.reddit.com/r/{subreddit}/hot/.rss?limit=15"

            resp = requests.get(rss_url, headers=self.headers, timeout=8)

            if resp.status_code != 200:
                # Fallback: essayer old.reddit
                rss_url = f"https://old.reddit.com/r/{subreddit}/hot/.rss?limit=15"
                resp = requests.get(rss_url, headers=self.headers, timeout=8)

            if resp.status_code != 200:
                # Dernier fallback: JSON API
                return self._fetch_json(subreddit, url)

            feed = feedparser.parse(resp.text)
            if not feed.entries:
                return self._fetch_json(subreddit, url)

            entries = []
            for entry in feed.entries[:10]:
                title = entry.get('title', '').strip()
                link = entry.get('link', '')

                if not title:
                    continue

                # Parse date
                published = None
                if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    try:
                        published = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                    except Exception:
                        pass

                summary = entry.get('summary', '')[:200] if entry.get('summary') else ''

                entries.append({
                    'source': f'r/{subreddit}',
                    'title': title,
                    'link': link,
                    'summary': summary,
                    'published': published.isoformat() if published else None,
                    'type': 'reddit',
                    'score': 0,
                })

            time.sleep(0.3)
            return entries

        except Exception as e:
            print(f"    ✗ Error fetching r/{subreddit}: {e}")
            return []

    def _fetch_json(self, subreddit: str, url: str) -> List[Dict]:
        """Fallback: fetch via JSON API"""
        try:
            resp = requests.get(url, headers=self.headers, timeout=8)
            if resp.status_code != 200:
                return []

            data = resp.json()
            posts = data.get('data', {}).get('children', [])

            entries = []
            for post in posts:
                pdata = post.get('data', {})

                if pdata.get('stickied'):
                    continue

                title = pdata.get('title', '')
                url_post = pdata.get('url', '')
                permalink = f"https://reddit.com{pdata.get('permalink', '')}"
                score = pdata.get('score', 0)
                comments = pdata.get('num_comments', 0)
                created_utc = pdata.get('created_utc', 0)

                if score < 10 and comments < 5:
                    continue

                published = datetime.fromtimestamp(created_utc)

                entries.append({
                    'source': f'r/{subreddit}',
                    'title': title,
                    'link': url_post if not url_post.startswith('/r/') else permalink,
                    'summary': f"{score} upvotes, {comments} comments | {pdata.get('selftext', '')[:200]}",
                    'published': published.isoformat(),
                    'type': 'reddit',
                    'score': score,
                })

            return entries

        except Exception:
            return []

    def fetch_all(self, sources: List[Tuple[str, str, str]]) -> List[Dict]:
        """Fetch from multiple subreddits"""
        print("  📡 Fetching Reddit...")
        all_entries = []

        for name, url, _ in sources:
            entries = self.fetch_subreddit(name, url)
            all_entries.extend(entries)

        # Déduplique
        seen_urls = set()
        unique_entries = []
        for entry in all_entries:
            url = entry['link']
            if url not in seen_urls:
                seen_urls.add(url)
                unique_entries.append(entry)

        unique_entries.sort(key=lambda x: x.get('score', 0), reverse=True)
        print(f"    ✓ Got {len(unique_entries)} posts")
        return unique_entries[:20]
