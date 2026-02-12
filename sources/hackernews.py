"""
Fetch AI-related stories from Hacker News via Algolia API (free, no key needed)
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict
import time

class HackerNewsFetcher:
    def __init__(self):
        self.base_url = "https://hn.algolia.com/api/v1/search"

    def search(self, query: str, days_back: int = 2, hits_per_page: int = 10) -> List[Dict]:
        """Search HN for a specific query"""
        try:
            # Calculate timestamp for filtering
            cutoff = datetime.now() - timedelta(days=days_back)
            timestamp = int(cutoff.timestamp())

            params = {
                'query': query,
                'tags': 'story',
                'numericFilters': f'created_at_i>{timestamp}',
                'hitsPerPage': hits_per_page,
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            hits = data.get('hits', [])

            entries = []
            for hit in hits:
                created_at = datetime.fromtimestamp(hit.get('created_at_i', 0))

                entries.append({
                    'source': f'HN: {query}',
                    'title': hit.get('title', ''),
                    'link': hit.get('url') or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    'summary': f"{hit.get('points', 0)} points, {hit.get('num_comments', 0)} comments",
                    'published': created_at.isoformat(),
                    'type': 'hackernews',
                    'score': hit.get('points', 0),
                })

            time.sleep(0.3)  # Rate limiting
            return entries

        except Exception as e:
            print(f"    ✗ Error searching HN for '{query}': {e}")
            return []

    def fetch_all(self, queries: List[str], days_back: int = 2) -> List[Dict]:
        """Fetch stories for multiple queries"""
        print("  📡 Fetching Hacker News...")
        all_entries = []

        for query in queries:
            entries = self.search(query, days_back)
            all_entries.extend(entries)

        # Remove duplicates (same URL)
        seen_urls = set()
        unique_entries = []
        for entry in all_entries:
            url = entry['link']
            if url not in seen_urls:
                seen_urls.add(url)
                unique_entries.append(entry)

        # Sort by score
        unique_entries.sort(key=lambda x: x.get('score', 0), reverse=True)

        print(f"    ✓ Got {len(unique_entries)} unique stories")
        return unique_entries[:20]  # Top 20
