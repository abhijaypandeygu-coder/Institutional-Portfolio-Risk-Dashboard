import React, { useEffect, useState } from 'react';
import { ArrowUpRight, Newspaper } from 'lucide-react';

type Story = { title: string; url: string; publisher: string; published_at?: string; summary?: string };
type Feed = { source: string; retrieved_at: string; articles: Story[] };
type BrokerStory = { heading: string; article_link: string; summary?: string; published_time?: number };
const dateTime = (value?: string) => value && Number.isFinite(Date.parse(value))
  ? new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : null;

function readable(story: Story) {
  try { return !!story.title?.trim() && ['https:', 'http:'].includes(new URL(story.url).protocol); }
  catch { return false; }
}

async function readNews(topic: string, operatorKey: string, signal: AbortSignal): Promise<Feed> {
  if (topic !== 'broker') {
    const query = topic === 'market' ? '' : '?symbol=' + encodeURIComponent(topic);
    const r = await fetch('/api/v1/external-data/news' + query, { signal });
    if (!r.ok) throw new Error('The publisher feed is temporarily unavailable.');
    const feed: Feed = await r.json();
    if (!Array.isArray(feed.articles)) throw new Error('The publisher returned an unreadable feed.');
    return { ...feed, articles: feed.articles.filter(readable) };
  }
  const r = await fetch('/api/v1/external-data/upstox_news/news', {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json', 'X-API-Key': operatorKey },
    body: JSON.stringify({ parameters: { category: 'holdings', page_number: 1, page_size: 12 } }),
  });
  if (!r.ok) throw new Error(r.status === 401 || r.status === 403 ? 'Access was denied. Check your operator key and broker authorization.' : 'Upstox news is unavailable. Check the broker connection in Data Feeds.');
  const body = await r.json(), groups = body.data?.data;
  if (!groups || typeof groups !== 'object') throw new Error('Upstox returned an unreadable feed.');
  const unique = new Map<string, Story>();
  for (const rows of Object.values(groups)) {
    if (!Array.isArray(rows)) continue;
    for (const item of rows as BrokerStory[]) {
      const stamp = new Date(item.published_time ?? NaN);
      const story = { title: item.heading, url: item.article_link, summary: item.summary, publisher: 'Upstox',
        published_at: Number.isFinite(stamp.getTime()) ? stamp.toISOString() : undefined };
      if (readable(story)) unique.set(story.url, story);
    }
  }
  return { source: 'Upstox', retrieved_at: body.retrieved_at,
    articles: [...unique.values()].sort((a, b) => (b.published_at || '').localeCompare(a.published_at || '')).slice(0, 12) };
}

function Stories({ topic }: { topic: string }) {
  const [feed, setFeed] = useState<Feed | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [key, setKey] = useState('');
  const [request, setRequest] = useState({ revision: 0, credential: '' });
  useEffect(() => {
    if (topic === 'broker' && !request.credential) return;
    const controller = new AbortController();
    setBusy(true); setError('');
    readNews(topic, request.credential, controller.signal)
      .then(result => { if (!controller.signal.aborted) setFeed(result); })
      .catch(err => { if (!controller.signal.aborted) setError(err.message || 'News is temporarily unavailable.'); })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [topic, request]);
  return <>
    <form className="mt-3 flex flex-wrap items-end gap-2 text-sm" onSubmit={e => {
      e.preventDefault(); setRequest(old => ({ revision: old.revision + 1, credential: topic === 'broker' ? key.trim() : '' }));
    }}>
      {topic === 'broker' && <label className="grid gap-1">Operator access key<input className="rounded-lg border border-line p-2" type="password" required autoComplete="off" value={key} onChange={e => setKey(e.target.value)} /></label>}
      <button className="rounded-lg border border-line px-3 py-1 text-brand" disabled={busy || (topic === 'broker' && !key.trim())}>{topic === 'broker' && !feed ? 'Load broker news' : 'Refresh news'}</button>
    </form>
    <p role="status" className="mt-3 text-xs text-muted">{busy ? 'Loading headlines…' : error || (feed && !feed.articles.length ? 'No articles returned for this selection.' : '')}</p>
    {feed && <><p className="mt-2 text-xs text-muted">{feed.source} · Last retrieved {dateTime(feed.retrieved_at) || 'at an unknown time'}</p>
      <ul className="mt-2 divide-y divide-line">{feed.articles.slice(0, expanded ? undefined : 4).map(article => <li key={article.url} className="py-3">
        <p className="mb-1 text-xs text-muted">{article.publisher} · {dateTime(article.published_at) || 'Publication time unavailable'}</p>
        <a href={article.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-brand hover:underline">{article.title} <ArrowUpRight aria-hidden="true" className="inline size-3.5" /></a>
        {article.summary && article.summary !== article.title && <p className="mt-1 text-sm text-secondary">{article.summary}</p>}
      </li>)}</ul>
      {feed.articles.length > 4 && <button className="text-sm font-medium text-brand" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
        {expanded ? 'Show fewer headlines' : 'Show all ' + feed.articles.length + ' headlines'}</button>}</>}
  </>;
}

export function ProfileNews({ symbols }: { symbols: string[] }) {
  const [selection, setSelection] = useState('market');
  const topic = selection === 'broker' || symbols.includes(selection) ? selection : 'market';
  return <section className="profile-card" aria-labelledby="profile-news-heading">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 id="profile-news-heading" className="flex items-center gap-2 text-lg font-semibold"><Newspaper size={19} aria-hidden="true" />Market news</h2>
      <label className="flex items-center gap-2 text-sm">Coverage<select value={topic} onChange={e => setSelection(e.target.value)} className="rounded-lg border border-line bg-surface px-2 py-1">
        <option value="market">Market headlines</option>
        {symbols.length > 0 && <optgroup label="Selected portfolio">{symbols.map(s => <option key={s} value={s}>{s}</option>)}</optgroup>}
        <option value="broker">Upstox broker holdings</option>
      </select></label></div>
    {topic === 'broker' && <p className="mt-2 text-sm text-muted">Coverage for the connected Upstox account. Your operator key stays in this view’s memory.</p>}
    <Stories key={topic} topic={topic} />
  </section>;
}
