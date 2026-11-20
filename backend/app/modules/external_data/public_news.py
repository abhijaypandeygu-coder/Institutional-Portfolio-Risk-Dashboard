"""Public publisher feeds for the local portfolio profile."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import re
from time import monotonic
from urllib.parse import urlsplit
from xml.etree import ElementTree

import httpx
from fastapi import HTTPException


_cache = {}


def _text(value):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value or "")).split())


def parse_feed(xml, source):
    channel = ElementTree.fromstring(xml).find("channel")
    if channel is None:
        raise ValueError("Missing feed channel")
    articles = {}
    for item in channel.findall("item"):
        url = (item.findtext("link") or "").strip()
        title = _text(item.findtext("title"))
        parts = urlsplit(url)
        if not title or parts.scheme not in ("https", "http") or not parts.hostname or url in articles:
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "").astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError):
            published = None
        articles[url] = dict(title=title, url=url, publisher=_text(item.findtext("source")) or parts.hostname.removeprefix("www."),
                             published_at=published, summary=_text(item.findtext("description"))[:360])
    return dict(source=source, retrieved_at=datetime.now(timezone.utc).isoformat(),
                articles=sorted(articles.values(), key=lambda a: a["published_at"] or "", reverse=True)[:12])


async def public_news(symbol):
    key = symbol.upper() if symbol else ""
    cached = _cache.get(key)
    if cached and monotonic() - cached[0] < 300:
        return cached[1]
    url = "https://feeds.finance.yahoo.com/rss/2.0/headline" if key else "https://feeds.content.dowjones.io/public/rss/mw_topstories"
    params = {"s": key, "region": "US", "lang": "en-US"} if key else {}
    try:
        async with httpx.AsyncClient(timeout=7, headers={"User-Agent": "FinSight/1.0"}, follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        result = parse_feed(response.content, "Yahoo Finance" if key else "MarketWatch")
    except (httpx.HTTPError, ElementTree.ParseError, ValueError) as exc:
        raise HTTPException(503, "Publisher feed temporarily unavailable") from exc
    if len(_cache) >= 128:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (monotonic(), result)
    return result
