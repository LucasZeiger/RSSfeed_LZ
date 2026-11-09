import Ajv2020 from 'ajv/dist/2020'
import schema from './dataset.schema.json'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { Article, Dataset, Leaning, Market, Status, Story } from './types'
import { leanings } from './types'
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Check,
  ChevronDown,
  Clock3,
  ExternalLink,
  Globe2,
  Layers3,
  Menu,
  Newspaper,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  TrendingUp,
  X,
} from 'lucide-react'
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const validateDataset = new Ajv2020({ strict: false, validateFormats: false }).compile<Dataset>(
  schema,
)

const countries: Record<string, string> = {
  US: 'United States',
  UK: 'United Kingdom',
  AT: 'Austria',
}
const navigation = [
  'All news',
  'Politics',
  'World',
  'Business',
  'Technology',
  'Markets',
  'Watchlist',
]
const formatter = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
})
function date(value: string) {
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? 'Unknown' : formatter.format(d)
}
function ago(value: string, reference = Date.now()) {
  const hours = Math.max(0, Math.floor((reference - Date.parse(value)) / 3600000))
  return hours < 1 ? 'Just now' : hours < 24 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago`
}
function priceStale(market: Market, reference = Date.now()) {
  return reference - Date.parse(market.prices.at(-1)!.date) > 5 * 86400000
}
function safeLink(url: string) {
  try {
    const parsed = new URL(url)
    return ['http:', 'https:'].includes(parsed.protocol) ? url : undefined
  } catch {
    return undefined
  }
}
function readPrefs() {
  try {
    return JSON.parse(localStorage.getItem('newslens-preferences') || '{}')
  } catch {
    return {}
  }
}

function Coverage({
  counts,
  compact = false,
}: {
  counts: Record<Leaning, number>
  compact?: boolean
}) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0)
  return (
    <div className={`coverage ${compact ? 'compact' : ''}`}>
      <div
        className="coverage-bar"
        role="img"
        aria-label={leanings.map((l) => `${l}: ${counts[l] || 0}`).join(', ')}
      >
        {leanings.map(
          (l) =>
            counts[l] > 0 && (
              <span key={l} className={l} style={{ flex: counts[l] / Math.max(total, 1) }} />
            ),
        )}
      </div>
      {!compact && (
        <div className="coverage-labels">
          {leanings.map((l) => (
            <span key={l}>
              <i className={l} />
              {l} <b>{counts[l] || 0}</b>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function Sparkline({ market, large = false }: { market: Market; large?: boolean }) {
  return (
    <div
      className={large ? 'chart-large' : 'sparkline'}
      aria-label={`${market.symbol} ${market.source} closing prices`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={market.prices} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient
              id={`gradient-${market.symbol.replace(/\W/g, '')}-${large}`}
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop offset="0%" stopColor="#a6c69e" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#a6c69e" stopOpacity={0} />
            </linearGradient>
          </defs>
          {large && (
            <>
              <XAxis
                dataKey="date"
                tick={{ fill: '#8e939c', fontSize: 11 }}
                minTickGap={70}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={['auto', 'auto']}
                tick={{ fill: '#8e939c', fontSize: 11 }}
                width={48}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: '#202329',
                  border: '1px solid #454951',
                  borderRadius: 8,
                  color: '#eee',
                }}
                formatter={(value) => [Number(value).toFixed(2), `${market.currency} close`]}
              />
            </>
          )}
          <Area
            type="monotone"
            dataKey="close"
            stroke="#a6c69e"
            strokeWidth={large ? 2 : 1.5}
            fill={`url(#gradient-${market.symbol.replace(/\W/g, '')}-${large})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function StoryDetail({ story, data, close }: { story: Story; data: Dataset; close: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [metric, setMetric] = useState<'articles' | 'publishers'>('articles')
  const articles = data.articles.filter((a) => story.article_ids.includes(a.id))
  const sources = Object.fromEntries(data.sources.map((s) => [s.id, s]))
  useEffect(() => {
    const dialog = dialogRef.current
    dialog?.showModal()
    return () => dialog?.close()
  }, [])
  function Evidence({ ids }: { ids: string[] }) {
    return (
      <div className="evidence">
        {ids.map((id, i) => {
          const a = articles.find((a) => a.id === id)
          return (
            a && (
              <a key={id} href={safeLink(a.url)} target="_blank" rel="noopener noreferrer">
                Source {i + 1} <ExternalLink size={11} />
              </a>
            )
          )
        })}
      </div>
    )
  }
  return (
    <dialog
      ref={dialogRef}
      onCancel={close}
      onClick={(e) => {
        if (e.target === e.currentTarget) close()
      }}
      className="story-dialog"
      aria-labelledby="detail-title"
    >
      <div className="dialog-content">
        <button className="icon-button dialog-close" onClick={close} aria-label="Close story">
          <X size={22} />
        </button>
        <div className="eyebrow">
          {story.category} <span> / </span>{' '}
          {story.countries.map((c) => countries[c] || c).join(' · ')}
        </div>
        <h1 id="detail-title">{story.title}</h1>
        <div className="meta">
          <Clock3 size={13} /> First reported {date(story.first_published)} <span>·</span>{' '}
          {story.publisher_count} publishers <span>·</span> {articles.length} articles
        </div>
        <section>
          <h2>What happened</h2>
          <p>
            {story.ai?.summary ||
              story.overview ||
              'No excerpt was available. Read the original sources below.'}
          </p>
          <p className="fine">
            {story.ai
              ? `AI interpretation · ${story.ai.provider} · ${date(story.ai.generated_at)}`
              : data.mode === 'demo'
                ? 'Synthetic event and excerpts for demonstration.'
                : 'Headline and excerpt from a source, not an independently verified neutral summary.'}
          </p>
        </section>
        <section>
          <div className="section-heading">
            <h2>Coverage, in perspective</h2>
            <div className="segmented">
              <button
                className={metric === 'articles' ? 'active' : ''}
                onClick={() => setMetric('articles')}
              >
                Articles
              </button>
              <button
                className={metric === 'publishers' ? 'active' : ''}
                onClick={() => setMetric('publishers')}
              >
                Publishers
              </button>
            </div>
          </div>
          <Coverage
            counts={metric === 'articles' ? story.article_counts : story.publisher_counts}
          />
          <p className="fine">
            Counts reflect configured sources only. Unknown does not mean centre. Political
            categories have different meanings across countries.
          </p>
          <div className="perspectives">
            {leanings.map((leaning) => (
              <div key={leaning} className="perspective">
                <h3>
                  <i className={leaning} />
                  {leaning}
                </h3>
                {articles
                  .filter((a) => sources[a.source_id]?.political_leaning === leaning)
                  .map((a) => (
                    <article key={a.id}>
                      <a
                        href={safeLink(a.url)}
                        target="_blank"
                        rel="noopener noreferrer"
                        lang={a.language}
                      >
                        {a.title} <ExternalLink size={12} />
                      </a>
                      <p className="source-name">{sources[a.source_id].name}</p>
                      <p lang={a.language}>{a.summary}</p>
                      <p className="fine">
                        {date(a.published_at)}
                        {a.date_estimated ? ' · estimated time' : ''}
                      </p>
                      <details>
                        <summary>Classification provenance</summary>
                        <p className="fine">
                          {sources[a.source_id].classification
                            ? `${sources[a.source_id].classification?.methodology} Reviewer: ${sources[a.source_id].classification?.reviewer}. Date: ${sources[a.source_id].classification?.reviewed_at}.`
                            : 'Unrated publisher; no political classification assigned.'}
                        </p>
                      </details>
                    </article>
                  ))}
                {!articles.some((a) => sources[a.source_id]?.political_leaning === leaning) && (
                  <p className="fine">No coverage found in configured sources.</p>
                )}
              </div>
            ))}
          </div>
        </section>
        <section>
          <h2>Agreements & differences</h2>
          {story.limitations.map((l) => (
            <p key={l} className="notice">
              {l}
            </p>
          ))}
          {story.ai ? (
            <>
              <h3>Model-identified common facts</h3>
              {story.ai.common_facts.map((f) => (
                <p key={f}>{f}</p>
              ))}
              <h3>Framing and unresolved disagreements</h3>
              {[...story.ai.framing, ...story.ai.disagreements].map((f) => (
                <p key={f}>{f}</p>
              ))}
              <Evidence ids={story.ai.article_ids} />
            </>
          ) : (
            <>
              <p>
                Compare the original wording above. Automated factual agreement, omissions and
                disagreements have not been established.
              </p>
              {story.common_terms.length > 0 && (
                <p className="fine">
                  Repeated headline terms: {story.common_terms.join(', ')}. Shared wording is not
                  proof of factual agreement.
                </p>
              )}
            </>
          )}
        </section>
        {story.exposures.length > 0 && (
          <section>
            <h2>Possible economic consequences</h2>
            <p className="fine">
              Rule-based scenarios, not price predictions or investment advice.
            </p>
            {story.exposures.map((e) => (
              <div className="exposure-panel" key={e.category}>
                <div className="eyebrow">
                  {e.category} · {e.sector}
                </div>
                <h3>{e.mechanism}</h3>
                <div className="scenario-grid">
                  <div>
                    <span className="scenario-label">Possible benefit</span>
                    <p>{e.positive}</p>
                  </div>
                  <div>
                    <span className="scenario-label">Possible pressure</span>
                    <p>{e.negative}</p>
                  </div>
                </div>
                <p className="fine">
                  {e.horizon}. {e.uncertainty}
                </p>
                {Object.entries(e.matches).map(([symbol, reason]) => (
                  <p className="fine" key={symbol}>
                    <b>{symbol}</b> — {reason}
                  </p>
                ))}
                <Evidence ids={e.article_ids} />
              </div>
            ))}
          </section>
        )}
        <section>
          <h2>Related instruments & price context</h2>
          {[...new Set(story.exposures.flatMap((e) => e.symbols))].map((symbol) => {
            const m = data.markets.find((m) => m.symbol === symbol)
            const instrument = data.instruments.find((i) => i.symbol === symbol)
            return (
              <div className="instrument-detail" key={symbol}>
                <h3>
                  {symbol} <span>{instrument?.name}</span>
                </h3>
                {m ? (
                  <>
                    <p>
                      {data.mode === 'demo' ? 'SIMULATED · ' : ''}
                      {m.prices.at(-1)?.close.toFixed(2)} {m.currency} · close{' '}
                      {m.prices.at(-1)?.date}
                    </p>
                    {priceStale(
                      m,
                      data.mode === 'demo' ? Date.parse(data.generated_at) : Date.now(),
                    ) && (
                      <p className="notice">
                        Stale price context: latest close is over five calendar days old.
                      </p>
                    )}
                    <Sparkline market={m} large />
                    <p className="fine">
                      {m.source} ·{' '}
                      {m.adjusted
                        ? 'Adjusted'
                        : 'Unadjusted: splits and distributions can distort returns.'}
                    </p>
                    {m.excess_return_pct !== null && (
                      <p className="fine">
                        Return minus {instrument?.benchmark}: {m.excess_return_pct.toFixed(2)}{' '}
                        percentage points, {m.comparison_dates.join(' to ')}.
                      </p>
                    )}
                  </>
                ) : (
                  <p className="fine">
                    Market price data not configured or unavailable for this instrument.
                  </p>
                )}
              </div>
            )
          })}
          {!story.exposures.some((e) => e.symbols.length) && (
            <p className="fine">No watchlist instrument has sufficient matching evidence.</p>
          )}
          <p className="notice">
            A price change near a news event does not establish that the event caused it.
          </p>
        </section>
      </div>
    </dialog>
  )
}

function StoryCard({
  story,
  data,
  open,
  featured = false,
}: {
  story: Story
  data: Dataset
  open: () => void
  featured?: boolean
}) {
  const reference = data.mode === 'demo' ? Date.parse(data.generated_at) : Date.now()
  const initials = [
    ...new Map(
      data.articles
        .filter((a) => story.article_ids.includes(a.id))
        .map((a) => {
          const source = data.sources.find((s) => s.id === a.source_id)
          return [source?.publisher_id || a.source_id, source?.name || '?'] as const
        }),
    ).values(),
  ]
  return (
    <article className={`story-card ${featured ? 'featured' : ''}`}>
      <div className="card-top">
        <span className={`category-tag ${story.category.toLowerCase()}`}>{story.category}</span>
        <span className="region-code">
          {story.countries.join(' / ')} <span>·</span> {ago(story.updated_at, reference)}
        </span>
      </div>
      <button className="story-link" onClick={open}>
        <h2 lang={story.language}>{story.title}</h2>
      </button>
      <p className="story-excerpt" lang={story.language}>
        {story.overview || 'Explore the original headlines and available source coverage.'}
      </p>
      {story.exposures.length > 0 && (
        <div className="exposure-chip">
          <TrendingUp size={13} />
          <span>{story.exposures[0].sector} exposure</span>
          {story.exposures[0].symbols.slice(0, 3).map((s) => (
            <b key={s}>{s}</b>
          ))}
        </div>
      )}
      <div className="card-bottom">
        <div className="publisher-info">
          <div className="publisher-avatars" aria-hidden="true">
            {initials.slice(0, 3).map((s, i) => (
              <span key={s} className={`avatar av-${i}`}>
                {s.replace(/^The /, '')[0]}
              </span>
            ))}
          </div>
          <span>
            {story.publisher_count} {story.publisher_count === 1 ? 'publisher' : 'publishers'}{' '}
            <span className="muted">· {story.article_ids.length} articles</span>
          </span>
        </div>
        <button className="arrow-button" onClick={open} aria-label={`Read ${story.title}`}>
          <ArrowRight size={17} />
        </button>
      </div>
      <Coverage counts={story.article_counts} compact />
    </article>
  )
}

export default function App() {
  const prefs = useMemo(readPrefs, [])
  const initialMode = new URLSearchParams(location.search).get('data')
  const [mode, setMode] = useState<'demo' | 'live'>(
    initialMode === 'live'
      ? 'live'
      : initialMode === 'demo'
        ? 'demo'
        : prefs.mode === 'live'
          ? 'live'
          : prefs.mode === 'demo'
            ? 'demo'
            : import.meta.env.VITE_DATA_MODE === 'live'
              ? 'live'
              : 'demo',
  )
  const [nav, setNav] = useState<string>(prefs.nav || 'All news')
  const [region, setRegion] = useState<string>(prefs.region || 'all')
  const [query, setQuery] = useState<string>(prefs.query || '')
  const [leaning, setLeaning] = useState<string>(prefs.leaning || 'all')
  const [publisher, setPublisher] = useState<string>(prefs.publisher || 'all')
  const [windowHours, setWindowHours] = useState<string>(prefs.windowHours || '168')
  const [financial, setFinancial] = useState<boolean>(prefs.financial === true)
  const [data, setData] = useState<Dataset | null>(null)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [reload, setReload] = useState(0)
  const refreshMinutes = useRef(60)
  const [selected, setSelected] = useState<Story | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [sidebar, setSidebar] = useState(false)
  const [metric, setMetric] = useState<'articles' | 'publishers'>('articles')
  const [status, setStatus] = useState<Status | null>(null)
  useEffect(() => {
    try {
      localStorage.setItem(
        'newslens-preferences',
        JSON.stringify({ mode, nav, region, query, leaning, publisher, windowHours, financial }),
      )
    } catch {
      /* Storage may be disabled. */
    }
  }, [mode, nav, region, query, leaning, publisher, windowHours, financial])
  useEffect(() => {
    setData(null)
    setStatus(null)
    setSelected(null)
  }, [mode])
  useEffect(() => {
    let disposed = false
    const controller = new AbortController()
    setError('')
    async function load() {
      if (document.hidden) return
      setRefreshing(true)
      try {
        const response = await fetch(
          `${import.meta.env.BASE_URL}data/${mode === 'demo' ? 'demo' : 'latest'}.json`,
          { cache: 'no-store', signal: controller.signal },
        )
        if (!response.ok && response.status !== 404)
          throw new Error(
            `Published data request failed (HTTP ${response.status}). Previous valid information is retained.`,
          )
        if (!response.ok)
          throw new Error(
            mode === 'live'
              ? 'No real dataset has been published yet. Run the collector, then refresh. Demo mode remains a separate option.'
              : 'Demo dataset is unavailable. Generate it with python -m backend.cli demo.',
          )
        const payload: unknown = await response.json()
        if (!validateDataset(payload) || payload.mode !== mode)
          throw new Error('Unsupported or invalid dataset. Previous valid information is retained.')
        if (!disposed) {
          refreshMinutes.current = Math.max(5, payload.refresh_minutes)
          setData(payload)
          setError('')
        }
      } catch (err) {
        if (!disposed && !controller.signal.aborted)
          setError(
            err instanceof Error
              ? err.message
              : 'Unable to refresh data; previous valid information is retained.',
          )
      }
      if (mode === 'live')
        try {
          const response = await fetch(`${import.meta.env.BASE_URL}data/status.json`, {
            cache: 'no-store',
            signal: controller.signal,
          })
          if (response.ok) {
            const run = (await response.json()) as Status
            if (!disposed && run.attempted_at) setStatus(run)
          }
        } catch {
          /* Dataset status remains available. */
        }
      if (!disposed) setRefreshing(false)
    }
    let timer: ReturnType<typeof setTimeout>
    async function tick() {
      await load()
      if (!disposed) timer = setTimeout(() => void tick(), refreshMinutes.current * 60 * 1000)
    }
    void tick()
    return () => {
      disposed = true
      controller.abort()
      clearTimeout(timer)
    }
  }, [mode, reload])
  const sources = useMemo(
    () => Object.fromEntries((data?.sources || []).map((s) => [s.id, s])),
    [data],
  )
  const reference = data?.mode === 'demo' ? Date.parse(data.generated_at) : Date.now()
  const stories = useMemo(() => {
    if (!data) return []
    const articleMap = Object.fromEntries(data.articles.map((a) => [a.id, a]))
    return data.stories
      .filter((s) => {
        const articles = s.article_ids.map((id) => articleMap[id]).filter((a): a is Article => !!a)
        return (
          (region === 'all' || s.countries.includes(region)) &&
          (!['Politics', 'World', 'Business', 'Technology'].includes(nav) || s.category === nav) &&
          (!['Markets', 'Watchlist'].includes(nav) || s.exposures.length > 0) &&
          (!financial || s.exposures.length > 0) &&
          (leaning === 'all' ||
            articles.some((a) => sources[a.source_id]?.political_leaning === leaning)) &&
          (publisher === 'all' || articles.some((a) => a.source_id === publisher)) &&
          reference - Date.parse(s.updated_at) <= Number(windowHours) * 3600000 &&
          (!query ||
            `${s.title} ${s.overview} ${s.exposures.flatMap((e) => e.symbols).join(' ')} ${articles.map((a) => a.title).join(' ')}`
              .toLowerCase()
              .includes(query.toLowerCase()))
        )
      })
      .sort(
        (a, b) =>
          Date.parse(b.updated_at) - Date.parse(a.updated_at) ||
          b.publisher_count - a.publisher_count,
      )
  }, [data, region, nav, financial, leaning, publisher, reference, windowHours, query, sources])
  const counts = useMemo(() => {
    const articles = (data?.articles || []).filter((a) =>
      stories.some((s) => s.article_ids.includes(a.id)),
    )
    return Object.fromEntries(
      leanings.map((l) => [
        l,
        metric === 'articles'
          ? articles.filter((a) => sources[a.source_id]?.political_leaning === l).length
          : new Set(
              articles
                .filter((a) => sources[a.source_id]?.political_leaning === l)
                .map((a) => sources[a.source_id]?.publisher_id || a.source_id),
            ).size,
      ]),
    ) as Record<Leaning, number>
  }, [data, stories, sources, metric])
  const runStatus = status || data?.status
  const stale = data?.mode === 'live' && Date.now() - Date.parse(data.generated_at) > 3 * 3600000
  const marketView = ['Markets', 'Watchlist'].includes(nav)
  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebar ? 'mobile-open' : ''}`}>
        <a className="brand" href="./" aria-label="NewsLens home">
          <span className="brand-mark">
            <Layers3 size={24} />
          </span>
          <span>
            news<span className="brand-light">lens</span>
            <i />
          </span>
        </a>
        <div className="sidebar-caption">YOUR DAILY PERSPECTIVE</div>
        <nav aria-label="Main navigation">
          {navigation.map((item, index) => {
            const Icon =
              index === 0 ? Newspaper : index === 5 ? BarChart3 : index === 6 ? Activity : Globe2
            return (
              <button
                key={item}
                className={nav === item ? 'selected' : ''}
                onClick={() => {
                  setNav(item)
                  setSidebar(false)
                }}
              >
                <Icon size={18} />
                {item}
                {item === 'All news' && data && (
                  <span className="nav-count">{data.stories.length}</span>
                )}
              </button>
            )
          })}
        </nav>
        <div className="sidebar-rule" />
        <div className="sidebar-caption">YOUR REGIONS</div>
        <div className="regions">
          {Object.entries(countries).map(([code, name]) => (
            <button
              className={region === code ? 'selected-region' : ''}
              key={code}
              onClick={() => setRegion(region === code ? 'all' : code)}
            >
              <span className="country-dot">
                {code === 'US' ? '🇺🇸' : code === 'UK' ? '🇬🇧' : '🇦🇹'}
              </span>
              {name}
              {region === code && <Check size={14} />}
            </button>
          ))}
        </div>
        <div className="sidebar-bottom">
          <div className="principles">
            <ShieldCheck size={19} />
            <b>Context over noise.</b>
            <p>
              Different perspectives.
              <br />A clearer picture.
            </p>
          </div>
          <button className="settings-link" onClick={() => setShowSettings(!showSettings)}>
            <Settings2 size={17} />
            Display & data settings
          </button>
          <div className="version">
            NEWSLENS <span>V0.1 · OPEN SOURCE</span>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              onClick={() => setSidebar(!sidebar)}
              aria-label="Toggle navigation"
            >
              <Menu size={20} />
            </button>
            <Globe2 size={15} />
            <span>Your briefing</span>
            <span className="slash">/</span>
            <b>{nav}</b>
          </div>
          <div className="topbar-right">
            <span className="today">
              {new Intl.DateTimeFormat('en-GB', {
                weekday: 'short',
                day: 'numeric',
                month: 'long',
                year: 'numeric',
              }).format(new Date())}
            </span>
            <button
              className={`refresh-button ${refreshing ? 'refreshing' : ''}`}
              onClick={() => setReload((v) => v + 1)}
              disabled={refreshing}
            >
              <RefreshCw size={14} />
              <span>{refreshing ? 'Refreshing' : 'Refresh'}</span>
            </button>
          </div>
        </header>
        {mode === 'demo' && (
          <div className="demo-banner">
            <span className="demo-pill">DEMO</span>
            <span>
              You’re exploring a synthetic dataset. All stories, publishers and prices are
              fictional.
            </span>
            <button onClick={() => setMode('live')}>
              Switch to real news <ArrowRight size={14} />
            </button>
          </div>
        )}
        {showSettings && (
          <div className="settings-panel">
            <div>
              <h2>Display & data</h2>
              <p>Sources are managed in version-controlled YAML. No browser write access.</p>
            </div>
            <label>
              Dataset
              <select value={mode} onChange={(e) => setMode(e.target.value as 'demo' | 'live')}>
                <option value="demo">Synthetic demo</option>
                <option value="live">Real RSS data</option>
              </select>
            </label>
            <p className="fine">
              Display preferences stay on this device. Published data refreshes at the configured
              interval while this tab is visible.
            </p>
            <button
              className="icon-button"
              aria-label="Close settings"
              onClick={() => setShowSettings(false)}
            >
              <X size={18} />
            </button>
          </div>
        )}
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="live-dot" />
                {mode === 'demo'
                  ? 'A DIFFERENT LENS ON THE NEWS'
                  : 'YOUR SOURCE-LINKED NEWS BRIEFING'}
              </div>
              <h1>{marketView ? 'The market context.' : 'See the whole story.'}</h1>
              <p>
                {marketView
                  ? 'Possible exposure. Observed movement. A clear distinction.'
                  : 'What happened. How it’s framed. What it could mean.'}
              </p>
            </div>
            <div className="freshness">
              <span
                className={`status-dot ${stale || runStatus?.state === 'failed' ? 'warning' : ''}`}
              />
              <div>
                {mode === 'demo'
                  ? 'Synthetic demo'
                  : stale
                    ? 'Dataset is stale'
                    : 'Published dataset'}
                <small>{data ? `Updated ${date(data.generated_at)}` : 'Awaiting data'}</small>
              </div>
            </div>
          </div>
          {error && (
            <div role="alert" className="error-box">
              <strong>Data update unavailable</strong>
              <p>{error}</p>
              <button onClick={() => setReload((v) => v + 1)}>Try again</button>
            </div>
          )}
          {runStatus && (runStatus.errors.length > 0 || runStatus.state === 'failed') && (
            <details className="run-status">
              <summary>
                Pipeline {runStatus.state} · attempted {date(runStatus.attempted_at)} ·{' '}
                {runStatus.errors.length} issue(s)
              </summary>
              {runStatus.errors.map((e) => (
                <p key={e}>{e}</p>
              ))}
              <p>
                Last completely successful news update:{' '}
                {runStatus.last_success_at ? date(runStatus.last_success_at) : 'not yet recorded'}.
                Healthy sources continue; previous valid output is retained on total failure.
              </p>
            </details>
          )}
          <div className="filter-row">
            <label className="search-box">
              <Search size={17} />
              <input
                aria-label="Search stories"
                placeholder="Search stories, topics, or tickers…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <kbd>/</kbd>
            </label>
            <div className="filter-controls">
              <label>
                <Globe2 size={14} />
                <select
                  aria-label="Region"
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                >
                  <option value="all">All regions</option>
                  {Object.entries(countries).map(([c, n]) => (
                    <option key={c} value={c}>
                      {n}
                    </option>
                  ))}
                </select>
                <ChevronDown size={12} />
              </label>
              <label>
                <Clock3 size={14} />
                <select
                  aria-label="Time window"
                  value={windowHours}
                  onChange={(e) => setWindowHours(e.target.value)}
                >
                  <option value="24">Last 24 hours</option>
                  <option value="72">Last 3 days</option>
                  <option value="168">Last 7 days</option>
                </select>
                <ChevronDown size={12} />
              </label>
              <label className={`financial-toggle ${financial ? 'enabled' : ''}`}>
                <input
                  type="checkbox"
                  checked={financial}
                  onChange={(e) => setFinancial(e.target.checked)}
                />
                <SlidersHorizontal size={14} />
                Financial relevance
              </label>
            </div>
          </div>
          <div className="secondary-filters">
            <label>
              Perspective
              <select
                aria-label="Political leaning"
                value={leaning}
                onChange={(e) => setLeaning(e.target.value)}
              >
                <option value="all">All perspectives</option>
                {leanings.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Publisher
              <select
                aria-label="Publisher"
                value={publisher}
                onChange={(e) => setPublisher(e.target.value)}
              >
                <option value="all">All publishers</option>
                {data?.sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            {(region !== 'all' ||
              query ||
              leaning !== 'all' ||
              publisher !== 'all' ||
              financial) && (
              <button
                onClick={() => {
                  setRegion('all')
                  setQuery('')
                  setLeaning('all')
                  setPublisher('all')
                  setFinancial(false)
                }}
              >
                Clear filters <X size={12} />
              </button>
            )}
          </div>
          {data ? (
            <div className="content-grid">
              <div className="news-column">
                {marketView && (
                  <section className="markets-grid">
                    {data.instruments.map((i) => {
                      const m = data.markets.find((m) => m.symbol === i.symbol)
                      return (
                        <article className="market-tile" key={i.symbol}>
                          <div className="section-heading">
                            <h3>{i.symbol}</h3>
                            <span className="fine">{i.exchange}</span>
                          </div>
                          <p>{i.name}</p>
                          {m ? (
                            <>
                              <strong>
                                {m.prices.at(-1)?.close.toFixed(2)} <small>{m.currency}</small>
                              </strong>
                              <Sparkline market={m} />
                              <p className="fine">
                                Close {m.prices.at(-1)?.date}
                                {priceStale(m, reference) ? ' · stale' : ''} ·{' '}
                                {mode === 'demo' ? 'SIMULATED' : m.source}
                              </p>
                            </>
                          ) : (
                            <p className="fine">Market price data not configured or unavailable.</p>
                          )}
                          <p className="fine">
                            {
                              data.stories.filter((s) =>
                                s.exposures.some((e) => e.symbols.includes(i.symbol)),
                              ).length
                            }{' '}
                            linked stories
                          </p>
                        </article>
                      )
                    })}
                  </section>
                )}
                <div className="section-heading news-heading">
                  <h2>
                    {marketView ? 'Financially relevant stories' : 'The latest briefing'}{' '}
                    <span>{stories.length}</span>
                  </h2>
                  <span className="sort-label">
                    Newest first <ChevronDown size={12} />
                  </span>
                </div>
                <div className="story-grid">
                  {stories.map((story, i) => (
                    <StoryCard
                      key={story.id}
                      story={story}
                      data={data}
                      featured={i === 0 && !marketView}
                      open={() => setSelected(story)}
                    />
                  ))}
                </div>
                {stories.length === 0 && (
                  <div className="empty-state">
                    <Search size={30} />
                    <h2>No stories match these filters</h2>
                    <p>Try a wider time window, another region or fewer filters.</p>
                  </div>
                )}
                <div className="end-note">
                  <Check size={14} />
                  {stories.length
                    ? 'You’re up to date with this selection.'
                    : 'Your briefing will appear here.'}
                  <span>More perspectives. Better context.</span>
                </div>
              </div>
              <aside className="context-column">
                <section className="context-panel">
                  <div className="section-heading">
                    <h2>Your coverage lens</h2>
                    <Layers3 size={17} />
                  </div>
                  <p>A snapshot of the stories in your view.</p>
                  <div className="segmented full">
                    <button
                      className={metric === 'articles' ? 'active' : ''}
                      onClick={() => setMetric('articles')}
                    >
                      Articles
                    </button>
                    <button
                      className={metric === 'publishers' ? 'active' : ''}
                      onClick={() => setMetric('publishers')}
                    >
                      Publishers
                    </button>
                  </div>
                  <div className="coverage-total">
                    {Object.values(counts).reduce((a, b) => a + b, 0)}
                    <span>
                      {metric === 'articles' ? 'collected articles' : 'distinct publishers'}
                    </span>
                  </div>
                  <Coverage counts={counts} />
                  <p className="panel-footnote">
                    Your configured sources, not the entire media landscape. Labels reflect a
                    publisher’s political context, not factual accuracy.
                  </p>
                </section>
                <section className="context-panel">
                  <div className="section-heading">
                    <h2>Market watch</h2>
                    <TrendingUp size={17} />
                  </div>
                  <p>
                    {mode === 'demo'
                      ? 'Simulated prices · not real market data'
                      : 'Daily closes · not real-time prices'}
                  </p>
                  {data.markets.length ? (
                    data.markets.slice(0, 3).map((m) => (
                      <div className="watch-row" key={m.symbol}>
                        <div>
                          <b>{m.symbol}</b>
                          <span>
                            {m.prices.at(-1)?.date}
                            {priceStale(m, reference) ? ' · stale' : ''}
                          </span>
                        </div>
                        <Sparkline market={m} />
                        <div className="watch-price">
                          <b>{m.prices.at(-1)?.close.toFixed(2)}</b>
                          <span className={(m.change_pct || 0) >= 0 ? 'positive' : 'negative'}>
                            {(m.change_pct || 0) >= 0 ? (
                              <ArrowUpRight size={12} />
                            ) : (
                              <ArrowDownRight size={12} />
                            )}
                            {m.change_pct !== null
                              ? `${m.change_pct > 0 ? '+' : ''}${m.change_pct.toFixed(2)}%`
                              : '—'}
                          </span>
                          <small>{m.currency}</small>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="notice">Market price data not configured.</p>
                  )}
                  <button className="text-button" onClick={() => setNav('Markets')}>
                    Explore market context <ArrowRight size={14} />
                  </button>
                </section>
                <section className="lens-note">
                  <div className="eyebrow">
                    <ShieldCheck size={15} /> THE NEWSLENS APPROACH
                  </div>
                  <h3>Perspective isn’t prediction.</h3>
                  <p>
                    Understand the reporting. Explore possible financial exposure. Keep observed
                    prices separate from explanations.
                  </p>
                  <div className="note-rule" />
                  <span>Always trace the story back to its sources.</span>
                </section>
              </aside>
            </div>
          ) : (
            !error && (
              <div className="empty-state" role="status">
                <RefreshCw size={26} />
                <h2>Preparing your briefing…</h2>
              </div>
            )
          )}
          <footer>
            <span className="footer-brand">
              newslens<span> · See the whole story.</span>
            </span>
            <span>Source-linked. Powered by Horizon. Independently hosted.</span>
          </footer>
        </main>
      </div>
      {selected && data && (
        <StoryDetail
          key={selected.id}
          story={selected}
          data={data}
          close={() => setSelected(null)}
        />
      )}
    </div>
  )
}
