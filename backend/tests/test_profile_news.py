from backend.app.modules.external_data.public_news import parse_feed


def test_news_preserves_publication_dates_and_deduplicates_safe_article_links():
    xml = """<rss><channel>
      <item><title>Undated</title><link>https://example.org/older</link></item>
      <item><title>Latest</title><link>https://example.org/latest</link>
        <pubDate>Tue, 17 Nov 2026 10:00:00 -0500</pubDate>
        <description><![CDATA[<p>First paragraph.</p>]]></description></item>
      <item><title>Duplicate</title><link>https://example.org/latest</link></item>
      <item><title>Bad link</title><link>javascript:void(0)</link></item>
    </channel></rss>"""
    latest, older = parse_feed(xml, "Test feed")["articles"]
    assert latest["title"] == "Latest"
    assert latest["published_at"] == "2026-11-17T15:00:00+00:00"
    assert latest["summary"] == "First paragraph."
    assert older["published_at"] is None
