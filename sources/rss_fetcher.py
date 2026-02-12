"""
Fetch RSS feeds from AI blogs and news sources
"""
import feedparser
import html2text
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dateutil import parser as date_parser
import time

class RSSFetcher:
    def __init__(self):
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True

    def fetch_feed(self, source_name: str, url: str, days_back: int = 2) -> List[Dict]:
        """Fetch and parse a single RSS feed"""
        try:
            print(f"  📡 Fetching {source_name}...")
            feed = feedparser.parse(url)

            if feed.bozo and hasattr(feed, 'bozo_exception'):
                print(f"    ⚠️  Warning: {feed.bozo_exception}")

            entries = []
            cutoff_date = datetime.now() - timedelta(days=days_back)

            for entry in feed.entries[:20]:  # Limit to 20 most recent
                # Parse date
                published = self._get_date(entry)
                if published and published < cutoff_date:
                    continue  # Skip old entries

                # Extract content
                title = entry.get('title', '').strip()
                link = entry.get('link', '')
                summary = self._get_summary(entry)

                if not title or not link:
                    continue

                entries.append({
                    'source': source_name,
                    'title': title,
                    'link': link,
                    'summary': summary[:500] if summary else '',
                    'published': published.isoformat() if published else None,
                    'type': 'rss',
                })

            print(f"    ✓ Got {len(entries)} recent entries")
            time.sleep(0.2)  # Rate limiting (réduit pour la vitesse)
            return entries

        except Exception as e:
            print(f"    ✗ Error fetching {source_name}: {e}")
            return []

    def _get_date(self, entry) -> Optional[datetime]:
        """Extract date from entry"""
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed', 'date_parsed']

        for field in date_fields:
            if hasattr(entry, field) and getattr(entry, field):
                struct_time = getattr(entry, field)
                return datetime.fromtimestamp(time.mktime(struct_time))

        # Try string dates
        for field in ['published', 'updated', 'created', 'date']:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    return date_parser.parse(getattr(entry, field))
                except:
                    pass

        return None

    def _get_summary(self, entry) -> str:
        """Extract clean summary from entry"""
        content = ''

        # Try different content fields
        if hasattr(entry, 'summary'):
            content = entry.summary
        elif hasattr(entry, 'description'):
            content = entry.description
        elif hasattr(entry, 'content'):
            if isinstance(entry.content, list) and entry.content:
                content = entry.content[0].value
            else:
                content = str(entry.content)

        # Convert HTML to text
        if content:
            try:
                text = self.html_converter.handle(content)
                return text.strip()
            except:
                return content.strip()

        return ''
