"""
Fetch trending AI repositories from GitHub (HTML scraping)
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
import time

class GitHubTrendingFetcher:
    def __init__(self):
        self.base_url = "https://github.com/trending"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        }

    def fetch_trending(self, topic: str = None, since: str = "daily") -> List[Dict]:
        """Fetch trending repos for a topic"""
        try:
            if topic:
                url = f"{self.base_url}/{topic}?since={since}"
            else:
                url = f"{self.base_url}?since={since}"

            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.find_all('article', class_='Box-row')

            entries = []
            for article in articles[:10]:  # Top 10
                # Get repo name
                h2 = article.find('h2')
                if not h2:
                    continue

                a_tag = h2.find('a')
                if not a_tag:
                    continue

                repo_path = a_tag.get('href', '').strip('/')
                if not repo_path:
                    continue

                # Get description
                p = article.find('p', class_='col-9')
                description = p.get_text(strip=True) if p else ""

                # Get language
                lang_span = article.find('span', itemprop='programmingLanguage')
                language = lang_span.get_text(strip=True) if lang_span else "Unknown"

                # Get stars
                stars_link = article.find('a', class_='Link--muted')
                stars = "0"
                if stars_link:
                    stars = stars_link.get_text(strip=True).replace(',', '')

                entries.append({
                    'source': f'GitHub Trending {topic or ""}',
                    'title': f"{repo_path} ({language}, ⭐{stars})",
                    'link': f"https://github.com/{repo_path}",
                    'summary': description[:200],
                    'published': datetime.now().isoformat(),
                    'type': 'github',
                    'score': int(stars.replace('k', '000').replace('.', '')) if stars else 0,
                })

            time.sleep(0.5)
            return entries

        except Exception as e:
            print(f"    ✗ Error fetching GitHub trending: {e}")
            return []

    def fetch_all(self, topics: List[str]) -> List[Dict]:
        """Fetch trending repos for multiple topics"""
        print("  📡 Fetching GitHub Trending...")
        all_entries = []

        for topic in topics:
            entries = self.fetch_trending(topic)
            all_entries.extend(entries)

        # Also fetch general trending
        general = self.fetch_trending()
        all_entries.extend(general)

        # Remove duplicates
        seen = set()
        unique = []
        for entry in all_entries:
            link = entry['link']
            if link not in seen:
                seen.add(link)
                unique.append(entry)

        # Sort by score
        unique.sort(key=lambda x: x.get('score', 0), reverse=True)

        print(f"    ✓ Got {len(unique)} trending repos")
        return unique[:15]
