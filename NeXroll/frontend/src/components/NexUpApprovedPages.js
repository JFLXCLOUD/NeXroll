import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, CalendarDays, Check, ChevronLeft, ChevronRight, Download,
  Film, FolderOpen, Loader2, Play, Plus, RefreshCw, Search,
  ImageOff, LayoutGrid, Rows3,
  Sparkles, ToggleLeft, ToggleRight, Trash2, Tv, Upload, Video, X
} from 'lucide-react';
import NeXUpGeneratorStudio from './NeXUpGeneratorStudio';

const formatDate = value => {
  if (!value) return 'Date unknown';
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  const date = match
    ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
    : new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
};

const formatTimeAgo = value => {
  if (!value) return 'Not yet';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return formatDate(value);
  const minutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60000));
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return formatDate(value);
};

const formatSize = trailer => {
  if (Number.isFinite(Number(trailer?.file_size_mb))) return `${Number(trailer.file_size_mb).toFixed(1)} MB`;
  if (Number.isFinite(Number(trailer?.size_bytes))) return `${(Number(trailer.size_bytes) / 1048576).toFixed(1)} MB`;
  return '—';
};

const formatDuration = trailer => {
  const seconds = Number(trailer?.duration_seconds || trailer?.duration || 0);
  if (!seconds) return '—';
  return `${Math.floor(seconds / 60)}:${String(Math.round(seconds % 60)).padStart(2, '0')}`;
};

const titleForTrailer = trailer => trailer?.title || trailer?.movie_title || trailer?.series_title || trailer?.filename || 'Untitled trailer';

// Poster artwork comes from Radarr/Sonarr as a remote TMDB URL. A title can
// legitimately have none, and a URL can fail to load, so both cases fall back to
// a labelled placeholder rather than a broken image.
function Poster({ url, title, children }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className="nx-ap-poster-art">
      {url && !failed
        ? <img src={url} alt="" loading="lazy" onError={() => setFailed(true)} />
        : <div className="nx-ap-poster-fallback"><ImageOff size={22} /><span>{title}</span></div>}
      {children}
    </div>
  );
}

function Badge({ tone = '', children }) {
  return <span className={`nx-ap-badge${tone ? ` ${tone}` : ''}`}>{children}</span>;
}

function Switch({ checked, onChange, label }) {
  return (
    <button type="button" className={`nx-ap-switch${checked ? ' on' : ''}`} role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}>
      <i />
    </button>
  );
}

function Stats({ items, five = false }) {
  return (
    <div className={`nx-route-summary nx-ap-stats${five ? ' five' : ''}`}>
      {items.map(item => <div key={item.label} className={item.tone || ''}><span>{item.label}</span><strong>{item.value}</strong></div>)}
    </div>
  );
}

function EmptyState({ icon: Icon, title, copy, action, actionLabel }) {
  return (
    <div className="nx-ap-empty">
      <Icon size={25} />
      <strong>{title}</strong>
      <span>{copy}</span>
      {action && <button type="button" className="nx-ap-btn amber" onClick={action}>{actionLabel}</button>}
    </div>
  );
}

function ConnectionsPage(props) {
  const {
    settings, storage, upcomingMovies, upcomingShows, movieTrailers, tvTrailers,
    loading, syncProgress, onFullSync, onUpdateSettings,
    radarrUrl, setRadarrUrl, radarrKey, setRadarrKey, onConnectRadarr, onDisconnectRadarr,
    sonarrUrl, setSonarrUrl, sonarrKey, setSonarrKey, onConnectSonarr, onDisconnectSonarr,
    onRefreshMovies, onRefreshShows, onSyncMovies, onSyncShows,
  } = props;
  const connectedCount = Number(Boolean(settings.radarr_connected)) + Number(Boolean(settings.sonarr_connected));
  const enabled = Boolean(settings.enabled || settings.sonarr_enabled);
  const nextSync = settings.next_sync || settings.next_sonarr_sync;
  const todayKey = new Date().toDateString();
  const downloadedToday = [...movieTrailers, ...tvTrailers].filter(trailer => {
    const value = trailer.downloaded_at || trailer.created_at;
    const date = value ? new Date(value) : null;
    return date && !Number.isNaN(date.getTime()) && date.toDateString() === todayKey;
  }).length;
  const connectionCard = ({ kind, connected, url, value, setValue, keyValue, setKeyValue, connect, disconnect, refresh, sync, enabledKey }) => {
    const isSonarr = kind === 'Sonarr';
    return (
      <article className={`nx-ap-service-card${isSonarr ? ' sonarr' : ''}`}>
        <header>
          <i>{isSonarr ? 'S' : 'R'}</i>
          <div><h3>{kind}</h3><p>{isSonarr ? 'Upcoming television and trailers' : 'Upcoming movies and trailers'}</p></div>
          <Badge tone={connected ? 'live' : 'muted'}>{connected ? 'Connected' : 'Not connected'}</Badge>
        </header>
        {connected ? (
          <div className="nx-ap-service-body">
            <dl className="nx-ap-info-list">
              <div><dt>Server</dt><dd>{url || 'Connected server'}</dd></div>
              <div><dt>Upcoming</dt><dd>{isSonarr ? upcomingShows.length : upcomingMovies.length} monitored</dd></div>
              <div><dt>Trailers</dt><dd>{isSonarr ? tvTrailers.length : movieTrailers.length} stored</dd></div>
              <div><dt>Last refresh</dt><dd>{formatTimeAgo(isSonarr ? settings.last_sonarr_sync : settings.last_sync)}</dd></div>
            </dl>
            <div className="nx-ap-status-line">
              <i className={Boolean(settings[enabledKey]) ? 'on' : 'off'}>{Boolean(settings[enabledKey]) ? 'ON' : 'OFF'}</i><div><strong>Automatic trailer downloads</strong><span>Fetch eligible missing trailers during sync.</span></div>
              <Switch checked={Boolean(settings[enabledKey])} onChange={checked => onUpdateSettings({ [enabledKey]: checked })} label={`${kind} automatic trailer downloads`} />
            </div>
            <footer><button type="button" className="nx-ap-btn" onClick={refresh}>Refresh {isSonarr ? 'shows' : 'movies'}</button><button type="button" className={`nx-ap-btn ${isSonarr ? 'blue' : 'amber'}`} onClick={sync}>Auto-download</button><button type="button" className="nx-ap-btn danger" onClick={disconnect}>Disconnect</button></footer>
          </div>
        ) : (
          <div className="nx-ap-service-body nx-ap-connect-form">
            <p>Connect your {kind} server to discover upcoming {isSonarr ? 'shows and season trailers' : 'movies and trailers'}.</p>
            <label><span>{kind} URL</span><input value={value} onChange={event => setValue(event.target.value)} placeholder={`http://localhost:${isSonarr ? '8989' : '7878'}`} /></label>
            <label><span>API key</span><input type="password" value={keyValue} onChange={event => setKeyValue(event.target.value)} placeholder={`Enter your ${kind} API key`} /></label>
            <button type="button" className={`nx-ap-btn wide${isSonarr ? ' blue' : ' amber'}`} disabled={loading || !value.trim() || !keyValue.trim()} onClick={connect}>{loading ? <Loader2 size={12} className="spin" /> : null} Connect to {kind}</button>
          </div>
        )}
      </article>
    );
  };

  return (
    <div className="nx-ap-page nx-ap-connections" data-nexup-page="connections">
      <Stats items={[
        { label: 'Automation', value: enabled ? 'On' : 'Off', tone: 'warn' },
        { label: 'Last sync', value: formatTimeAgo(settings.last_sync || settings.last_sonarr_sync), tone: 'good' },
        { label: 'Trailers stored', value: movieTrailers.length + tvTrailers.length },
        { label: 'Downloaded today', value: downloadedToday, tone: 'violet' },
      ]} />
      {connectedCount > 0 && (
        <section className="nx-ap-sync-banner">
          <div><h3>{connectedCount === 2 ? 'Radarr and Sonarr are ready' : `${settings.radarr_connected ? 'Radarr' : 'Sonarr'} is ready`}</h3><p>{enabled ? `Automatic syncing is on.${nextSync ? ` Next refresh ${formatTimeAgo(nextSync)}.` : ''}` : 'Automation is paused. Manual sync remains available.'}</p></div>
          <div><Badge tone={syncProgress?.phase === 'error' ? 'danger' : 'live'}>{syncProgress?.status || 'Healthy'}</Badge><button type="button" className="nx-ap-btn amber" disabled={syncProgress?.phase === 'init'} onClick={onFullSync}>{syncProgress?.phase === 'init' ? <Loader2 size={12} className="spin" /> : <RefreshCw size={12} />} Sync now</button></div>
        </section>
      )}
      <div className="nx-ap-service-grid">
        {connectionCard({ kind: 'Radarr', connected: settings.radarr_connected, url: settings.radarr_url, value: radarrUrl, setValue: setRadarrUrl, keyValue: radarrKey, setKeyValue: setRadarrKey, connect: onConnectRadarr, disconnect: onDisconnectRadarr, refresh: onRefreshMovies, sync: onSyncMovies, enabledKey: 'enabled' })}
        {connectionCard({ kind: 'Sonarr', connected: settings.sonarr_connected, url: settings.sonarr_url, value: sonarrUrl, setValue: setSonarrUrl, keyValue: sonarrKey, setKeyValue: setSonarrKey, connect: onConnectSonarr, disconnect: onDisconnectSonarr, refresh: onRefreshShows, sync: onSyncShows, enabledKey: 'sonarr_enabled' })}
      </div>
      <div className="nx-ap-notice"><i>i</i><div><strong>Sync behavior</strong><span>NeX-Up refreshes monitored media, downloads eligible missing trailers, and can regenerate Coming Soon lists after a successful sync. Current storage: {Number(storage?.total_size_gb || 0).toFixed(1)} GB.</span></div></div>
    </div>
  );
}

function UpcomingPage(props) {
  const {
    settings, upcomingMovies, upcomingShows, upcomingTab, setUpcomingTab,
    calendarMonth, setCalendarMonth, downloadingId,
    onRefreshMovies, onRefreshShows, onDownloadMovie, onDownloadShow,
    onToggleExclude, onNavigate, movieTrailers, tvTrailers, onPlayTrailer,
  } = props;
  const [source, setSource] = useState(upcomingTab === 'shows' ? 'shows' : 'movies');
  const [view, setView] = useState(() => {
    try {
      const saved = localStorage.getItem('nexupUpcomingView');
      if (saved === 'posters') return 'posters';
    } catch (_) { /* storage unavailable; fall through to the tab */ }
    return upcomingTab === 'calendar' ? 'calendar' : 'list';
  });
  const [search, setSearch] = useState('');
  const [windowDays, setWindowDays] = useState('90');
  const [trailerState, setTrailerState] = useState('all');
  const [listState, setListState] = useState('included');
  const [selectedDay, setSelectedDay] = useState(null);
  const dateKey = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  const itemDateKey = item => String(item.release_date || item.air_date || '').slice(0, 10);
  const items = source === 'movies' ? upcomingMovies : upcomingShows;
  const connected = source === 'movies' ? settings.radarr_connected : settings.sonarr_connected;
  const filtered = useMemo(() => items.filter(item => {
    const title = String(item.title || '').toLowerCase();
    const release = item.release_date || item.air_date;
    const releaseDate = release ? new Date(release) : null;
    const inWindow = windowDays === 'all' || !releaseDate || Number.isNaN(releaseDate.getTime()) || releaseDate <= new Date(Date.now() + Number(windowDays) * 86400000);
    const state = item.downloaded ? 'ready' : item.trailer_url || source === 'shows' ? 'missing' : 'unavailable';
    const listMatches = listState === 'all' || (listState === 'excluded' ? item.excluded_from_list : !item.excluded_from_list);
    const dayMatches = !selectedDay || itemDateKey(item) === selectedDay;
    return title.includes(search.trim().toLowerCase()) && inWindow && listMatches && dayMatches && (trailerState === 'all' || state === trailerState);
  }), [items, listState, search, source, trailerState, windowDays, selectedDay]);
  const selectSource = next => {
    setSource(next);
    setUpcomingTab(next);
    setSelectedDay(null);
    if (next === 'movies') onRefreshMovies(); else onRefreshShows();
  };
  const selectView = next => {
    setView(next);
    try { localStorage.setItem('nexupUpcomingView', next); } catch (_) { /* not fatal */ }
    if (next === 'calendar') setUpcomingTab('calendar'); else setUpcomingTab(source);
  };
  const today = new Date();
  const monday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - ((today.getDay() + 6) % 7));
  const weekDays = Array.from({ length: 7 }, (_, index) => new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + index));
  // Every comparison here has to reject undefined on both sides. The previous
  // version OR'd all three id checks unguarded, so on the Movies tab
  // `trailer.sonarr_series_id === item.sonarr_id` compared undefined to
  // undefined, matched the first trailer in the collection, and every Preview
  // played that same one. Season number matters too: a series can have a
  // separate trailer per season.
  const sameId = (a, b) => a != null && b != null && a === b;
  const playFor = item => {
    const isMovies = source === 'movies';
    const collection = isMovies ? movieTrailers : tvTrailers;
    const match = collection.find(trailer => {
      if (sameId(trailer.id, item.trailer_db_id)) return true;
      if (isMovies) return sameId(trailer.radarr_movie_id, item.radarr_id);
      if (!sameId(trailer.sonarr_series_id, item.sonarr_id)) return false;
      return item.season_number == null || trailer.season_number === item.season_number;
    });
    if (match) onPlayTrailer({ type: isMovies ? 'movie' : 'tv', trailer: match });
  };
  const downloadFor = item => source === 'movies'
    ? onDownloadMovie(item.radarr_id, item.title)
    : onDownloadShow(item.sonarr_id, item.season_number, item.title);

  const calendarGrid = () => {
    const year = calendarMonth.getFullYear();
    const month = calendarMonth.getMonth();
    const first = new Date(year, month, 1);
    const gridStart = new Date(year, month, 1 - ((first.getDay() + 6) % 7));
    const days = Array.from({ length: 42 }, (_, index) => new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + index));
    const allItems = [...upcomingMovies.map(item => ({ ...item, _source: 'movie' })), ...upcomingShows.map(item => ({ ...item, _source: 'show' }))];
    return (
      <div className="nx-ap-release-month" data-upcoming-view="calendar">
        <div className="nx-ap-month-nav"><button type="button" onClick={() => setCalendarMonth(new Date(year, month - 1, 1))}><ChevronLeft size={13} /></button><strong>{calendarMonth.toLocaleDateString([], { month: 'long', year: 'numeric' })}</strong><button type="button" onClick={() => setCalendarMonth(new Date(year, month + 1, 1))}><ChevronRight size={13} /></button></div>
        <div className="nx-ap-month-grid">{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => <b key={day}>{day}</b>)}{days.map(day => {
          const dayItems = allItems.filter(item => itemDateKey(item) === dateKey(day));
          return <div key={dateKey(day)} className={`${day.getMonth() !== month ? 'outside' : ''}${dateKey(day) === dateKey(today) ? ' today' : ''}`}><time>{day.getDate()}</time>{dayItems.slice(0, 3).map((item, index) => <span key={`${item._source}-${item.id || item.radarr_id || item.sonarr_id}-${index}`} className={item._source}>{item.title}</span>)}{dayItems.length > 3 && <small>+{dayItems.length - 3} more</small>}</div>;
        })}</div>
      </div>
    );
  };

  return (
    <div className="nx-ap-page nx-ap-upcoming" data-nexup-page="upcoming">
      <section className="nx-ap-panel">
        <header className="nx-ap-panel-head"><div><strong>Release calendar</strong><span>{formatDate(weekDays[0])} - {formatDate(weekDays[6])}</span></div><div><div className="nx-ap-segmented"><button type="button" className={source === 'movies' ? 'active' : ''} onClick={() => selectSource('movies')}>Movies ({upcomingMovies.length})</button><button type="button" className={source === 'shows' ? 'active blue' : ''} onClick={() => selectSource('shows')}>TV shows ({upcomingShows.length})</button></div><div className="nx-ap-segmented"><button type="button" className={view === 'list' ? 'active' : ''} onClick={() => selectView('list')}>List</button><button type="button" className={view === 'posters' ? 'active' : ''} onClick={() => selectView('posters')}>Posters</button><button type="button" className={view === 'calendar' ? 'active' : ''} onClick={() => selectView('calendar')}>Calendar</button></div></div></header>
        {view === 'calendar' ? calendarGrid() : view === 'posters' ? (
          <div className="nx-ap-panel-body" data-upcoming-view="posters">
            <div className="nx-ap-command"><label><Search size={13} /><input aria-label="Search upcoming" value={search} onChange={event => setSearch(event.target.value)} placeholder={`Search upcoming ${source === 'movies' ? 'movies' : 'shows'}...`} /></label><select aria-label="Release window" value={windowDays} onChange={event => setWindowDays(event.target.value)}><option value="30">Next 30 days</option><option value="90">Next 90 days</option><option value="365">This year</option><option value="all">All dates</option></select><select aria-label="Trailer state" value={trailerState} onChange={event => setTrailerState(event.target.value)}><option value="all">All trailer states</option><option value="ready">Ready</option><option value="missing">Missing</option><option value="unavailable">Unavailable</option></select><select aria-label="List state" value={listState} onChange={event => setListState(event.target.value)}><option value="included">In list only</option><option value="excluded">Excluded only</option><option value="all">All items</option></select></div>
            {!connected
              ? <EmptyState icon={source === 'movies' ? Video : Tv} title={`${source === 'movies' ? 'Radarr' : 'Sonarr'} is not connected`} copy="Connect this service before loading upcoming releases." action={() => onNavigate('nexup')} actionLabel="Go to Connections" />
              : filtered.length === 0
                ? <EmptyState icon={CalendarDays} title="No upcoming releases found" copy="Try another filter or refresh the connected service." />
                : <div className="nx-ap-poster-grid">{filtered.map((item, index) => {
                    const downloaded = Boolean(item.downloaded);
                    const sourceId = source === 'movies' ? item.radarr_id : `${item.sonarr_id}-${item.season_number || 1}`;
                    const isDownloading = downloadingId === sourceId || downloadingId === `tv_${sourceId}`;
                    const state = downloaded ? 'Ready' : item.trailer_url || source === 'shows' ? 'Missing' : 'Unavailable';
                    return (
                      <article key={sourceId || index} className={`nx-ap-poster-card${item.excluded_from_list ? ' excluded' : ''}`}>
                        <Poster url={item.poster_url} title={item.title || 'Untitled'}>
                          <span className={`nx-ap-poster-state is-${state.toLowerCase()}`}>{state}</span>
                          {downloaded && <button type="button" className="nx-ap-poster-play" onClick={() => playFor(item)} aria-label={`Preview ${item.title || 'trailer'}`}><Play size={17} /></button>}
                        </Poster>
                        <div className="nx-ap-poster-meta">
                          <strong title={item.title || 'Untitled'}>{item.title || 'Untitled'}</strong>
                          <span>{formatDate(item.release_date || item.air_date).replace(/, \d{4}$/, '')}{source === 'shows' ? ` / Season ${item.season_number || 1}` : ''}</span>
                        </div>
                        <div className="nx-ap-poster-actions">
                          {downloaded
                            ? <button type="button" className="nx-ap-btn" onClick={() => playFor(item)}>Preview</button>
                            : <button type="button" className="nx-ap-btn" disabled={isDownloading || (!item.trailer_url && source === 'movies')} onClick={() => downloadFor(item)}>{isDownloading ? <Loader2 size={11} className="spin" /> : <Download size={11} />} Download</button>}
                          {item.trailer_db_id && <button type="button" className={`nx-ap-btn square toggle${item.excluded_from_list ? '' : ' on'}`} title={item.excluded_from_list ? 'Include in list' : 'Exclude from list'} aria-pressed={!item.excluded_from_list} onClick={() => onToggleExclude(item, source === 'movies' ? 'movie' : 'show')}>{item.excluded_from_list ? <ToggleLeft size={15} /> : <ToggleRight size={15} />}</button>}
                        </div>
                      </article>
                    );
                  })}</div>}
          </div>
        ) : (
          <div className="nx-ap-panel-body" data-upcoming-view="list">
            <div className="nx-ap-week-strip">{weekDays.map(day => {
              const key = dateKey(day);
              const isSelected = selectedDay === key;
              return <button type="button" key={key} aria-pressed={isSelected} className={`${dateKey(today) === key ? 'active' : ''}${items.some(item => itemDateKey(item) === key) ? ' has' : ''}${isSelected ? ' selected' : ''}`} onClick={() => setSelectedDay(isSelected ? null : key)}><span>{day.toLocaleDateString([], { weekday: 'short' })}</span><strong>{day.getDate()}</strong></button>;
            })}</div>
            {selectedDay && <div className="nx-ap-day-filter"><span>Showing releases for {formatDate(selectedDay)}</span><button type="button" className="nx-ap-btn square" onClick={() => setSelectedDay(null)} title="Clear day filter"><X size={12} /></button></div>}
            <div className="nx-ap-command"><label><Search size={13} /><input aria-label="Search upcoming" value={search} onChange={event => setSearch(event.target.value)} placeholder={`Search upcoming ${source === 'movies' ? 'movies' : 'shows'}...`} /></label><select aria-label="Release window" value={windowDays} onChange={event => setWindowDays(event.target.value)}><option value="30">Next 30 days</option><option value="90">Next 90 days</option><option value="365">This year</option><option value="all">All dates</option></select><select aria-label="Trailer state" value={trailerState} onChange={event => setTrailerState(event.target.value)}><option value="all">All trailer states</option><option value="ready">Ready</option><option value="missing">Missing</option><option value="unavailable">Unavailable</option></select><select aria-label="List state" value={listState} onChange={event => setListState(event.target.value)}><option value="included">In list only</option><option value="excluded">Excluded only</option><option value="all">All items</option></select></div>
            {!connected ? <EmptyState icon={source === 'movies' ? Video : Tv} title={`${source === 'movies' ? 'Radarr' : 'Sonarr'} is not connected`} copy="Connect this service before loading upcoming releases." action={() => onNavigate('nexup')} actionLabel="Go to Connections" /> : filtered.length === 0 ? <EmptyState icon={CalendarDays} title="No upcoming releases found" copy="Try another filter or refresh the connected service." /> : <div className="nx-ap-upcoming-list">{filtered.map((item, index) => {
              const downloaded = Boolean(item.downloaded);
              const sourceId = source === 'movies' ? item.radarr_id : `${item.sonarr_id}-${item.season_number || 1}`;
              const isDownloading = downloadingId === sourceId || downloadingId === `tv_${sourceId}`;
              return <article key={sourceId || index} className={item.excluded_from_list ? 'excluded' : ''}><div className="nx-ap-release"><i className={source === 'shows' ? 'blue' : ''}>{source === 'movies' ? 'R' : 'S'}</i><time>{formatDate(item.release_date || item.air_date).replace(/, \d{4}$/, '')}</time></div><div className="nx-ap-upcoming-title"><strong>{item.title || 'Untitled'}</strong><span>{source === 'shows' ? `Season ${item.season_number || 1}${item.network ? ` / ${item.network}` : ''}` : [item.release_type, item.genres?.join?.(', ')].filter(Boolean).join(' / ') || 'Upcoming movie'}</span></div><Badge tone={downloaded ? 'live' : item.trailer_url || source === 'shows' ? 'warn' : 'muted'}>Trailer {downloaded ? 'Ready' : item.trailer_url || source === 'shows' ? 'Missing' : 'Unavailable'}</Badge><Badge>{item.monitored === false ? 'Unmonitored' : 'Monitored'}</Badge><span className="nx-ap-list-state">{item.excluded_from_list ? 'Excluded' : 'In list'}</span><div className="nx-ap-row-actions">{downloaded ? <button type="button" className="nx-ap-btn" onClick={() => playFor(item)}>Preview</button> : <button type="button" className="nx-ap-btn" disabled={isDownloading || (!item.trailer_url && source === 'movies')} onClick={() => downloadFor(item)}>{isDownloading ? <Loader2 size={11} className="spin" /> : <Download size={11} />} Download</button>}{item.trailer_db_id && <button type="button" className={`nx-ap-btn square toggle${item.excluded_from_list ? '' : ' on'}`} title={item.excluded_from_list ? 'Include in list' : 'Exclude from list'} aria-pressed={!item.excluded_from_list} onClick={() => onToggleExclude(item, source === 'movies' ? 'movie' : 'show')}>{item.excluded_from_list ? <ToggleLeft size={15} /> : <ToggleRight size={15} />}</button>}</div></article>;
            })}</div>}
          </div>
        )}
      </section>
    </div>
  );
}

function TrailersPage(props) {
  const {
    settings, storage, movieTrailers, tvTrailers,
    trailerViewMode, setTrailerViewMode, onPlayTrailer, onToggleMovie, onToggleTv,
    onDeleteMovie, onDeleteTv, onSync, onManual, onNavigate,
  } = props;
  const [search, setSearch] = useState('');
  const [kind, setKind] = useState('all');
  const [usage, setUsage] = useState('all');
  const [sort, setSort] = useState('recent');
  const combined = useMemo(() => [
    ...movieTrailers.map(trailer => ({ ...trailer, _kind: 'movie' })),
    ...tvTrailers.map(trailer => ({ ...trailer, _kind: 'tv' })),
  ], [movieTrailers, tvTrailers]);
  const filtered = useMemo(() => combined.filter(trailer => {
    const enabled = trailer.is_enabled !== false;
    return titleForTrailer(trailer).toLowerCase().includes(search.trim().toLowerCase()) && (kind === 'all' || trailer._kind === kind) && (usage === 'all' || (usage === 'used') === enabled);
  }).sort((a, b) => {
    if (sort === 'title') return titleForTrailer(a).localeCompare(titleForTrailer(b));
    if (sort === 'largest') return Number(b.size_bytes || b.file_size_mb || 0) - Number(a.size_bytes || a.file_size_mb || 0);
    return Number(b.created_at || b.downloaded_at || 0) - Number(a.created_at || a.downloaded_at || 0);
  }), [combined, kind, search, sort, usage]);
  const [layout, setLayout] = useState(() => {
    try { return localStorage.getItem('nexupTrailerLayout') === 'posters' ? 'posters' : 'table'; } catch (_) { return 'table'; }
  });
  const selectLayout = next => {
    setLayout(next);
    try { localStorage.setItem('nexupTrailerLayout', next); } catch (_) { /* not fatal */ }
  };
  const [selectedKey, setSelectedKey] = useState(null);
  useEffect(() => {
    if (!filtered.length) setSelectedKey(null);
    else if (!filtered.some(trailer => `${trailer._kind}-${trailer.id}` === selectedKey)) setSelectedKey(`${filtered[0]._kind}-${filtered[0].id}`);
  }, [filtered, selectedKey]);
  const selected = filtered.find(trailer => `${trailer._kind}-${trailer.id}` === selectedKey) || null;
  const previewOn = trailerViewMode === 'detailed';
  const usedCount = combined.filter(trailer => trailer.is_enabled !== false).length;
  const toggleSelected = trailer => trailer._kind === 'movie' ? onToggleMovie(trailer.id) : onToggleTv(trailer.id);
  const deleteSelected = trailer => trailer._kind === 'movie' ? onDeleteMovie(trailer.id, titleForTrailer(trailer)) : onDeleteTv(trailer.id);
  return (
    <div className="nx-ap-page nx-ap-trailers" data-nexup-page="trailers">
      <Stats five items={[
        { label: 'Total trailers', value: combined.length, tone: 'warn' },
        { label: 'Movie trailers', value: movieTrailers.length },
        { label: 'TV trailers', value: tvTrailers.length, tone: 'blue' },
        { label: 'Used', value: usedCount, tone: 'good' },
        { label: 'Storage', value: `${Number(storage?.total_size_gb || storage?.used_gb || 0).toFixed(1)} GB`, tone: 'violet' },
      ]} />
      <div className="nx-ap-command"><label><Search size={13} /><input aria-label="Search downloaded trailers" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search downloaded trailers..." /></label><select aria-label="Trailer type" value={kind} onChange={event => setKind(event.target.value)}><option value="all">Movies and TV</option><option value="movie">Movies</option><option value="tv">TV shows</option></select><select aria-label="Trailer usage" value={usage} onChange={event => setUsage(event.target.value)}><option value="all">All usage</option><option value="used">Used</option><option value="unused">Unused</option></select><select aria-label="Trailer sort" value={sort} onChange={event => setSort(event.target.value)}><option value="recent">Recently downloaded</option><option value="title">Title</option><option value="largest">Largest files</option></select><div className="nx-ap-segmented"><button type="button" className={layout === 'table' ? 'active' : ''} onClick={() => selectLayout('table')} title="Table view"><Rows3 size={12} /> Table</button><button type="button" className={layout === 'posters' ? 'active' : ''} onClick={() => selectLayout('posters')} title="Poster view"><LayoutGrid size={12} /> Posters</button></div><button type="button" className={`nx-ap-btn${previewOn ? ' active' : ''}`} onClick={() => setTrailerViewMode(previewOn ? 'list' : 'detailed')}>Preview {previewOn ? 'on' : 'off'}</button></div>
      <div className={`nx-ap-trailer-layout${previewOn ? ' has-preview' : ''}`}>
        <section className="nx-ap-panel nx-ap-trailer-table">
          {combined.length === 0 ? <EmptyState icon={Film} title="No downloaded trailers" copy="Connect Radarr or Sonarr, then sync eligible trailers." action={settings.radarr_connected || settings.sonarr_connected ? onSync : () => onNavigate('nexup')} actionLabel={settings.radarr_connected || settings.sonarr_connected ? 'Sync trailers' : 'Go to Connections'} /> : <>
            {layout === 'posters' ? <div className="nx-ap-poster-grid">{filtered.map(trailer => {
              const key = `${trailer._kind}-${trailer.id}`;
              const used = trailer.is_enabled !== false;
              return (
                <article key={key} className={`nx-ap-poster-card${selectedKey === key ? ' selected' : ''}${used ? '' : ' disabled'}`} onClick={() => setSelectedKey(key)}>
                  <Poster url={trailer.poster_url} title={titleForTrailer(trailer)}>
                    <span className={`nx-ap-poster-state is-${used ? 'ready' : 'unavailable'}`}>{used ? 'Used' : 'Unused'}</span>
                    <button type="button" className="nx-ap-poster-play" onClick={event => { event.stopPropagation(); onPlayTrailer({ type: trailer._kind, trailer }); }} aria-label={`Play ${titleForTrailer(trailer)}`}><Play size={17} /></button>
                  </Poster>
                  <div className="nx-ap-poster-meta">
                    <strong title={titleForTrailer(trailer)}>{titleForTrailer(trailer)}</strong>
                    <span>{trailer._kind === 'movie' ? 'Radarr' : 'Sonarr'} / {formatDuration(trailer)} / {formatSize(trailer)}</span>
                  </div>
                  <div className="nx-ap-poster-actions">
                    <button type="button" className={`nx-ap-btn square toggle${used ? ' on' : ''}`} onClick={event => { event.stopPropagation(); toggleSelected(trailer); }} title={used ? 'Disable trailer' : 'Enable trailer'} aria-pressed={used}>{used ? <ToggleRight size={15} /> : <ToggleLeft size={15} />}</button>
                    <button type="button" className="nx-ap-btn danger square" onClick={event => { event.stopPropagation(); deleteSelected(trailer); }} title={`Delete ${titleForTrailer(trailer)}`}><Trash2 size={12} /></button>
                  </div>
                </article>
              );
            })}</div> : <>
            <div className="nx-ap-trailer-head"><span>Trailer</span><span>Duration</span><span>Size</span><span>Usage</span><span>Deletes on</span><span /></div>
            {filtered.map(trailer => <article key={`${trailer._kind}-${trailer.id}`} className={`${selectedKey === `${trailer._kind}-${trailer.id}` ? 'selected' : ''}${trailer.is_enabled === false ? ' disabled' : ''}`} onClick={() => setSelectedKey(`${trailer._kind}-${trailer.id}`)}><div className="nx-ap-table-media"><button type="button" onClick={event => { event.stopPropagation(); onPlayTrailer({ type: trailer._kind, trailer }); }} aria-label={`Play ${titleForTrailer(trailer)}`}><Play size={12} /></button><div><strong>{titleForTrailer(trailer)}</strong><span>{trailer._kind === 'movie' ? 'Radarr' : 'Sonarr'} / {formatDate(trailer.downloaded_at || trailer.created_at || trailer.release_date)}</span></div></div><span>{formatDuration(trailer)}</span><span>{formatSize(trailer)}</span><Badge tone={trailer.is_enabled !== false ? 'live' : ''}>{trailer.is_enabled !== false ? 'Used' : 'Unused'}</Badge><span>{trailer.removal_date ? formatDate(trailer.removal_date) : 'Not scheduled'}</span><div className="nx-ap-row-actions"><button type="button" className="nx-ap-btn" onClick={event => { event.stopPropagation(); onPlayTrailer({ type: trailer._kind, trailer }); }}>Play</button><button type="button" className={`nx-ap-btn square toggle${trailer.is_enabled !== false ? ' on' : ''}`} onClick={event => { event.stopPropagation(); toggleSelected(trailer); }} title={trailer.is_enabled !== false ? 'Disable trailer' : 'Enable trailer'} aria-pressed={trailer.is_enabled !== false}>{trailer.is_enabled !== false ? <ToggleRight size={15} /> : <ToggleLeft size={15} />}</button></div></article>)}
            </>}
            <footer><span>Trailers are automatically removed when media enters your library or reaches its retention limit.</span><button type="button" className="nx-ap-btn" onClick={onManual}><Plus size={11} /> Add manual</button></footer>
          </>}
        </section>
        {previewOn && <aside className="nx-ap-panel nx-ap-preview-rail">{selected ? <><button type="button" className="nx-ap-video-preview" onClick={() => onPlayTrailer({ type: selected._kind, trailer: selected })}><Play size={19} /><span><strong>{titleForTrailer(selected)}</strong><small>{formatDuration(selected)}</small></span></button><div className="nx-ap-preview-body"><Badge tone={selected.is_enabled !== false ? 'live' : ''}>{selected.is_enabled !== false ? 'Used in rotation' : 'Not in rotation'}</Badge><h3>{titleForTrailer(selected)}</h3><p>{selected._kind === 'movie' ? 'Radarr movie trailer' : 'Sonarr television trailer'} / {formatDate(selected.release_date)}</p><dl className="nx-ap-info-list"><div><dt>Duration</dt><dd>{formatDuration(selected)}</dd></div><div><dt>File size</dt><dd>{formatSize(selected)}</dd></div><div><dt>Deletes on</dt><dd>{selected.removal_date ? formatDate(selected.removal_date) : 'Not scheduled'}</dd></div></dl><div><button type="button" className="nx-ap-btn amber" onClick={() => toggleSelected(selected)}>{selected.is_enabled !== false ? 'Remove from rotation' : 'Use as preroll'}</button><button type="button" className="nx-ap-btn danger" onClick={() => deleteSelected(selected)}><Trash2 size={11} /> Delete</button></div></div></> : <EmptyState icon={Film} title="Select a trailer" copy="Choose a row to inspect and preview it." />}</aside>}
      </div>
    </div>
  );
}

const LIBRARY_RECENT = [[0, 'Any time'], [30, 'Last 30 days'], [60, 'Last 60 days'], [90, 'Last 90 days'], [180, 'Last 6 months'], [365, 'Last year']];
const LIBRARY_MAX_DOWNLOADS = [[10, '10 trailers'], [25, '25 trailers'], [50, '50 trailers'], [100, '100 trailers'], [0, 'None (use only files next to movies)']];
const LIBRARY_MAX_GB = [[2, '2 GB'], [5, '5 GB'], [10, '10 GB'], [25, '25 GB']];
const LIBRARY_IMDB = [[0, 'Any score'], [6, '6.0 or higher'], [7, '7.0 or higher'], [7.5, '7.5 or higher'], [8, '8.0 or higher']];
const LIBRARY_RT = [[0, 'Any score'], [60, '60% or higher'], [75, '75% or higher'], [85, '85% or higher'], [90, '90% or higher']];
const LIBRARY_PRIORITY = [
  ['newest', 'Newest in your library', 'Movies you added most recently get trailers first.'],
  ['rating', 'Highest rated', 'Best IMDb scores first.'],
  ['popular', 'Most popular', 'What is popular on TMDB right now first.'],
  ['random', 'Random', 'A different mix every time the selection refreshes.'],
];
// The movie filters, and what "no filter" means for each. Presets start from these.
const LIBRARY_FILTER_DEFAULTS = {
  genres: [], exclude_genres: [], certifications: [], languages: [], tags: [],
  year_from: 0, year_to: 0, min_imdb: 0, min_rt: 0, recent_days: 0,
};
const LIBRARY_PRESETS = [
  { id: 'everything', label: 'Everything', copy: 'Every movie in your library', filters: {} },
  { id: 'family', label: 'Family night', copy: 'G and PG only', filters: { certifications: ['G', 'PG'] } },
  { id: 'acclaimed', label: 'Critically acclaimed', copy: '85%+ on Rotten Tomatoes', filters: { min_rt: 85 } },
  { id: 'horror', label: 'Horror night', copy: 'Horror and thrillers', filters: { genres: ['Horror', 'Thriller'] } },
  { id: 'classics', label: 'Classics', copy: 'Before 1990, rated 7+', filters: { year_to: 1989, min_imdb: 7 } },
  { id: 'new', label: 'New arrivals', copy: 'Added in the last 60 days', filters: { recent_days: 60 } },
];
const SYNC_STEPS = [['read', 'Read your library'], ['local', 'Check your folders'], ['download', 'Download trailers'], ['done', 'Finished']];
const SYNC_STEP_OF = { read: 0, local: 1, tidy: 2, download: 2, done: 3, error: 3 };

const libraryJson = async (url, options) => {
  const res = await fetch(url, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
};

// The backend writes UTC timestamps without a zone; read them as UTC.
const utcDate = value => (value ? new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`) : null);
const sinceText = (value, now) => {
  const date = utcDate(value);
  if (!date) return '';
  const seconds = Math.max(0, Math.round((now - date.getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return formatTimeAgo(date.toISOString());
};
const elapsedText = (from, to) => {
  const start = utcDate(from);
  if (!start) return '';
  const seconds = Math.max(0, Math.round(((to ? utcDate(to).getTime() : Date.now()) - start.getTime()) / 1000));
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s`;
};

const SYNC_EVENT = {
  found: { icon: FolderOpen, label: 'Found next to movie', tone: 'good' },
  downloaded: { icon: Download, label: 'Downloaded', tone: 'good' },
  failed: { icon: AlertTriangle, label: 'No trailer found', tone: 'warn' },
  rotated: { icon: RefreshCw, label: 'Rotated out', tone: '' },
  replaced: { icon: RefreshCw, label: 'Replaced to make room', tone: '' },
  removed: { icon: Trash2, label: 'Removed', tone: '' },
};

function LibrarySyncCard({ sync, onHide }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!sync?.running) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [sync?.running]);
  const running = Boolean(sync?.running);
  const failed = Boolean(sync?.error) && !running;
  const step = failed ? -1 : (SYNC_STEP_OF[sync?.stage] ?? 0);
  const counts = sync?.counts || sync?.result || {};
  const toDownload = Number(sync?.to_download || 0);
  const done = Number(sync?.download_done || 0);
  const percent = toDownload ? Math.round((done / toDownload) * 100) : (step >= 3 ? 100 : 0);
  const log = sync?.log || [];

  return (
    <section className={`nx-ap-panel nx-lt-sync${running ? ' running' : ''}${failed ? ' failed' : ''}`} aria-live="polite">
      <header className="nx-lt-sync-head">
        <div className="nx-lt-sync-title">
          <span className="nx-lt-sync-icon">{running ? <Loader2 size={16} className="spin" /> : failed ? <AlertTriangle size={16} /> : <Check size={16} />}</span>
          <div>
            <strong>{running ? 'Syncing library trailers' : failed ? 'Sync stopped' : 'Sync finished'}</strong>
            <span>{failed ? sync.error : sync?.status}{sync?.started_at ? ` / ${elapsedText(sync.started_at, running ? null : sync.finished_at)}` : ''}</span>
          </div>
        </div>
        {!running && <button type="button" className="nx-ap-btn" onClick={onHide}><X size={11} /> Hide</button>}
      </header>

      <ol className="nx-lt-steps">
        {SYNC_STEPS.map(([key, label], index) => {
          const state = failed ? (index < (SYNC_STEP_OF[sync?.stage] ?? 0) ? 'done' : 'todo') : index < step || (index === step && step === 3) ? 'done' : index === step ? 'active' : 'todo';
          return (
            <li key={key} className={state}>
              <span className="dot">{state === 'done' ? <Check size={11} /> : index + 1}</span>
              <span className="label">{label}</span>
            </li>
          );
        })}
      </ol>

      <div className="nx-lt-sync-body">
        <div className="nx-lt-sync-main">
          {toDownload > 0 && (
            <div className="nx-lt-progress">
              <div className="nx-lt-progress-bar"><span style={{ width: `${percent}%` }} /></div>
              <span>{done} of {toDownload} trailer{toDownload === 1 ? '' : 's'}</span>
            </div>
          )}
          {running && sync?.current && (
            <div className="nx-lt-current">
              <div className="nx-lt-current-poster">{sync.current.poster_url ? <img src={sync.current.poster_url} alt="" /> : <Film size={18} />}</div>
              <div><span>Downloading now</span><strong>{sync.current.title}{sync.current.year ? ` (${sync.current.year})` : ''}</strong></div>
            </div>
          )}
          {running && sync?.stage === 'local' && (
            <p className="nx-lt-muted">Checked {sync.scanned || 0} of {sync.candidates || 0} movie folders for trailer files...</p>
          )}
          <div className="nx-lt-counters">
            <div><span>Matching movies</span><strong>{counts.candidates ?? sync?.candidates ?? 0}</strong></div>
            <div className="good"><span>Found next to movies</span><strong>{counts.local_found || 0}</strong></div>
            <div className="good"><span>Downloaded</span><strong>{counts.downloaded || 0}</strong></div>
            <div className={counts.failed ? 'warn' : ''}><span>No trailer found</span><strong>{counts.failed || 0}</strong></div>
            <div><span>Removed or rotated</span><strong>{(counts.removed || 0) + (counts.rotated || 0)}</strong></div>
          </div>
        </div>
        <div className="nx-lt-feed">
          <span className="nx-lt-feed-title">Activity</span>
          {log.length === 0
            ? <p className="nx-lt-muted">{running ? 'Waiting for the first result...' : 'Nothing changed in this sync.'}</p>
            : (
              <ul>
                {log.slice(0, 12).map((entry, i) => {
                  const kind = SYNC_EVENT[entry.kind] || SYNC_EVENT.removed;
                  const Icon = kind.icon;
                  return (
                    <li key={`${entry.at}-${i}`} className={kind.tone}>
                      <span className="thumb">{entry.poster_url ? <img src={entry.poster_url} alt="" loading="lazy" /> : <Icon size={12} />}</span>
                      <span className="what"><strong>{entry.title}</strong><small><Icon size={10} /> {kind.label}</small></span>
                      <time>{sinceText(entry.at, now)}</time>
                    </li>
                  );
                })}
              </ul>
            )}
        </div>
      </div>
    </section>
  );
}

const BROWSE_PAGE = 60;
const BROWSE_SORTS = [['title', 'Title'], ['added', 'Newest in library'], ['rating', 'Highest rated'], ['year', 'Newest release']];
const TRAILER_STATE = {
  local: ['Next to movie', 'good'],
  download: ['Downloaded', 'good'],
  error: ['No trailer found', 'warn'],
};

// Hand-pick mode: browse the Radarr library and choose the movies to keep
// trailers for. Selection lives in config.picked, owned by the page.
function LibraryMovieBrowser({ picked, onChange, genres, maxDownloads, download }) {
  const [q, setQ] = useState('');
  const [genre, setGenre] = useState('');
  const [sort, setSort] = useState('title');
  const [show, setShow] = useState('all');
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const pickedSet = useMemo(() => new Set(picked), [picked]);
  // In the Selected / Not selected views the list depends on the picks, so a
  // change refetches; in All it only changes the ticks.
  const pickedKey = show === 'all' ? '' : picked.join(',');

  const load = useCallback(async (offset, append) => {
    setLoading(true);
    try {
      const body = await libraryJson('/nexup/library/browse', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ q, genre, sort, show, picked, offset, limit: BROWSE_PAGE }),
      });
      setItems(previous => (append ? [...previous, ...body.movies] : body.movies));
      setTotal(body.total);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, genre, sort, show, pickedKey]);
  useEffect(() => {
    const timer = setTimeout(() => load(0, false), q ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, q]);

  const toggle = id => onChange(pickedSet.has(id) ? picked.filter(x => x !== id) : [...picked, id]);
  const selectShown = () => onChange([...picked, ...items.map(m => m.id).filter(id => !pickedSet.has(id))]);
  const clearAll = () => {
    if (picked.length > 10 && !window.confirm(`Clear all ${picked.length} picked movies? Trailers you already have are kept.`)) return;
    onChange([]);
  };
  const over = download && maxDownloads > 0 && picked.length > maxDownloads;

  return (
    <div className="nx-lt-browser">
      <div className="nx-lt-browser-bar">
        <label className="nx-lt-browser-search"><Search size={13} /><input aria-label="Search your library" value={q} onChange={event => setQ(event.target.value)} placeholder="Search your library by title..." /></label>
        <select aria-label="Genre" value={genre} onChange={event => setGenre(event.target.value)}>
          <option value="">All genres</option>
          {(genres || []).map(g => <option key={g.name} value={g.name}>{g.name} ({g.count})</option>)}
        </select>
        <select aria-label="Sort by" value={sort} onChange={event => setSort(event.target.value)}>{BROWSE_SORTS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>
        <div className="nx-ap-segmented">
          <button type="button" className={show === 'all' ? 'active' : ''} onClick={() => setShow('all')}>All</button>
          <button type="button" className={show === 'picked' ? 'active' : ''} onClick={() => setShow('picked')}>Picked ({picked.length})</button>
          <button type="button" className={show === 'unpicked' ? 'active' : ''} onClick={() => setShow('unpicked')}>Not picked</button>
        </div>
      </div>

      <div className="nx-lt-browser-actions">
        <span>{loading && !items.length ? 'Loading your library...' : `${total} ${total === 1 ? 'movie' : 'movies'}${q || genre ? ' found' : ''}`}</span>
        <div>
          <button type="button" className="nx-ap-btn" disabled={!items.length} onClick={selectShown}><Check size={11} /> Pick all shown</button>
          <button type="button" className="nx-ap-btn ghost" disabled={!picked.length} onClick={clearAll}><X size={11} /> Clear picks</button>
        </div>
      </div>

      {over && (
        <div className="nx-lt-outside-row" role="status">
          <span><strong>You&apos;ve picked {picked.length} movies, and your download limit is {maxDownloads}.</strong> Trailers next to your movies don&apos;t count toward it. For the rest, raise Maximum downloaded trailers, or the first {maxDownloads} by Download first are fetched.</span>
        </div>
      )}
      {error && <p className="nx-ap-library-progress warn">{error}</p>}

      <div className="nx-lt-browser-grid">
        {items.map(m => {
          const on = pickedSet.has(m.id);
          const state = TRAILER_STATE[m.trailer] || (m.has_trailer_link ? null : ['No trailer link', 'muted']);
          return (
            <button type="button" key={m.id} className={`nx-lt-pick${on ? ' on' : ''}`} aria-pressed={on} onClick={() => toggle(m.id)} title={`${m.title}${m.year ? ` (${m.year})` : ''}${on ? ' - picked' : ''}`}>
              <span className="art">
                {m.poster_url ? <img src={m.poster_url} alt="" loading="lazy" /> : <span className="fallback"><Film size={16} /><small>{m.title}</small></span>}
                <span className="tick">{on ? <Check size={13} /> : <Plus size={13} />}</span>
                {state && <span className={`state ${state[1]}`}>{state[0]}</span>}
              </span>
              <strong>{m.title}</strong>
              <small>{[m.year, m.certification !== 'Unrated' ? m.certification : null, m.imdb ? `IMDb ${m.imdb}` : null].filter(Boolean).join(' / ')}</small>
            </button>
          );
        })}
      </div>
      {!loading && items.length === 0 && <p className="nx-ap-library-muted">{show === 'picked' ? 'No movies picked yet. Switch to All and click posters to pick them.' : 'No movies match.'}</p>}
      {items.length < total && (
        <div className="nx-lt-browser-more">
          <button type="button" className="nx-ap-btn" disabled={loading} onClick={() => load(items.length, true)}>{loading ? <Loader2 size={11} className="spin" /> : null} Show more ({total - items.length} left)</button>
        </div>
      )}
    </div>
  );
}

function LibraryChip({ on, off, count, onClick, children, title }) {
  return (
    <button type="button" className={`nx-lt-chip${on ? ' on' : ''}${off ? ' off' : ''}`} aria-pressed={on || off} title={title} onClick={onClick}>
      {off && <X size={10} />}{children}{count != null && <small>{count}</small>}
    </button>
  );
}

// Library Trailers: trailers for movies already in the library. Deliberately
// its own page with its own settings - Coming Soon removes a trailer once its
// movie arrives, and nothing here should be caught by that.
function LibraryTrailersPage({ onNavigate }) {
  const [info, setInfo] = useState(null);
  const [config, setConfig] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);
  const [preview, setPreview] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewError, setPreviewError] = useState(null);
  const [trailers, setTrailers] = useState([]);
  const [sync, setSync] = useState(null);
  const [showSync, setShowSync] = useState(false);
  const [search, setSearch] = useState('');
  const [source, setSource] = useState('all');
  const [playing, setPlaying] = useState(null);
  const [movieQuery, setMovieQuery] = useState('');
  const [movieResults, setMovieResults] = useState([]);
  const [pinnedInfo, setPinnedInfo] = useState({});

  const loadTrailers = useCallback(async () => {
    try { setTrailers((await libraryJson('/nexup/library/trailers')).trailers || []); } catch (_) { /* shown as empty */ }
  }, []);
  const loadSettings = useCallback(async () => {
    try {
      const body = await libraryJson('/nexup/library/settings');
      setInfo(body);
      setConfig(body.config);
      setSync(body.sync);
      if (body.sync?.running) setShowSync(true);
      setDirty(false);
    } catch (error) {
      setNotice({ tone: 'warn', text: error.message });
    }
  }, []);
  useEffect(() => { loadSettings(); loadTrailers(); }, [loadSettings, loadTrailers]);

  // What the current choices cover, before anything is saved.
  const selectionKey = config ? JSON.stringify(['mode', 'picked', 'genres', 'exclude_genres', 'certifications', 'languages', 'tags', 'year_from', 'year_to', 'min_imdb', 'min_rt', 'recent_days', 'always_include', 'never_include', 'priority'].map(k => config[k])) : '';
  useEffect(() => {
    if (!config || !info?.radarr_connected) return undefined;
    setPreviewing(true);
    const timer = setTimeout(async () => {
      try {
        const body = await libraryJson('/nexup/library/preview', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config),
        });
        setPreview(body);
        setPinnedInfo(previous => {
          const next = { ...previous };
          [...(body.pinned?.always || []), ...(body.pinned?.never || [])].forEach(m => { next[m.id] = m; });
          return next;
        });
        setPreviewError(null);
      } catch (error) {
        setPreviewError(error.message);
      } finally {
        setPreviewing(false);
      }
    }, 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectionKey, info?.radarr_connected]);

  // Follow a running sync, then refresh the list once it finishes.
  useEffect(() => {
    if (!sync?.running) return undefined;
    const timer = setInterval(async () => {
      try {
        const status = await libraryJson('/nexup/library/sync/status');
        setSync(status);
        if (!status.running) { loadTrailers(); loadSettings(); }
      } catch (_) { /* keep polling */ }
    }, 1500);
    return () => clearInterval(timer);
  }, [sync?.running, loadTrailers, loadSettings]);

  useEffect(() => {
    const q = movieQuery.trim();
    if (q.length < 2 || !info?.radarr_connected) { setMovieResults([]); return undefined; }
    const timer = setTimeout(async () => {
      try { setMovieResults((await libraryJson(`/nexup/library/movies?q=${encodeURIComponent(q)}`)).movies || []); } catch (_) { setMovieResults([]); }
    }, 250);
    return () => clearTimeout(timer);
  }, [movieQuery, info?.radarr_connected]);

  const change = patch => { setConfig(previous => ({ ...previous, ...patch })); setDirty(true); };
  const save = async () => {
    setSaving(true);
    try {
      const body = await libraryJson('/nexup/library/settings', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config),
      });
      setConfig(body.config);
      setDirty(false);
      setNotice({ tone: 'live', text: 'Saved. Sync to apply the new selection now, or it applies at the next NeX-Up refresh.' });
      return true;
    } catch (error) {
      setNotice({ tone: 'warn', text: error.message });
      return false;
    } finally {
      setSaving(false);
    }
  };
  const startSync = async () => {
    if (dirty && !(await save())) return;
    try {
      await libraryJson('/nexup/library/sync', { method: 'POST' });
      setSync({ running: true, stage: 'read', status: 'Starting...', log: [], started_at: new Date().toISOString() });
      setShowSync(true);
      setNotice(null);
    } catch (error) {
      setNotice({ tone: 'warn', text: error.message });
    }
  };
  const cleanupOutside = async () => {
    const count = info?.summary?.outside || 0;
    if (!window.confirm(`Remove ${count} trailer${count === 1 ? '' : 's'} outside your filters? Downloaded files are deleted; trailer files next to your movies are left alone.`)) return;
    try {
      const body = await libraryJson('/nexup/library/cleanup', { method: 'POST' });
      setNotice({ tone: 'live', text: `Removed ${body.removed} trailer${body.removed === 1 ? '' : 's'} outside your filters.` });
      loadTrailers();
      loadSettings();
    } catch (error) {
      setNotice({ tone: 'warn', text: error.message });
    }
  };
  const toggleTrailer = async trailer => {
    try {
      const row = await libraryJson(`/nexup/library/trailers/${trailer.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ is_enabled: !trailer.is_enabled }),
      });
      setTrailers(list => list.map(t => (t.id === row.id ? row : t)));
    } catch (error) {
      setNotice({ tone: 'warn', text: error.message });
    }
  };

  const has = (list, name) => (list || []).some(x => String(x).toLowerCase() === String(name).toLowerCase());
  const without = (list, name) => (list || []).filter(x => String(x).toLowerCase() !== String(name).toLowerCase());
  // Genres cycle: not used -> included -> excluded -> not used.
  const cycleGenre = name => {
    if (has(config.genres, name)) change({ genres: without(config.genres, name), exclude_genres: [...without(config.exclude_genres, name), name] });
    else if (has(config.exclude_genres, name)) change({ exclude_genres: without(config.exclude_genres, name) });
    else change({ genres: [...config.genres, name] });
  };
  const toggleIn = (key, value) => change({ [key]: has(config[key], value) ? without(config[key], value) : [...config[key], value] });
  const toggleTag = id => change({ tags: config.tags.includes(id) ? config.tags.filter(t => t !== id) : [...config.tags, id] });
  const pin = (movie, list) => {
    const other = list === 'always_include' ? 'never_include' : 'always_include';
    setPinnedInfo(previous => ({ ...previous, [movie.id]: movie }));
    change({ [list]: config[list].includes(movie.id) ? config[list] : [...config[list], movie.id], [other]: config[other].filter(id => id !== movie.id) });
  };
  const unpin = (id, list) => change({ [list]: config[list].filter(x => x !== id) });
  const applyPreset = preset => change({ ...LIBRARY_FILTER_DEFAULTS, ...preset.filters });
  const activePreset = LIBRARY_PRESETS.find(preset => Object.keys(LIBRARY_FILTER_DEFAULTS).every(key => {
    const want = preset.filters[key] ?? LIBRARY_FILTER_DEFAULTS[key];
    const have = config?.[key];
    return Array.isArray(want) ? JSON.stringify([...want].sort()) === JSON.stringify([...(have || [])].sort()) : Number(want) === Number(have);
  }));
  const filtersUsed = config ? Object.keys(LIBRARY_FILTER_DEFAULTS).some(key => {
    const value = config[key];
    return Array.isArray(value) ? value.length > 0 : Number(value) > 0;
  }) : false;

  const visible = useMemo(() => trailers.filter(t => (
    (source === 'all'
      || (source === 'error' ? t.status === 'error'
        : source === 'outside' ? t.status === 'available' && t.in_selection === false
          : t.source === source && t.status === 'available'))
    && `${t.title} ${(t.genres || []).join(' ')}`.toLowerCase().includes(search.trim().toLowerCase())
  )), [trailers, source, search]);

  if (!config) {
    return <div className="nx-ap-page"><EmptyState icon={Film} title="Loading Library Trailers" copy={notice?.text || 'Reading your settings...'} /></div>;
  }
  const summary = info?.summary || {};
  const running = Boolean(sync?.running);
  const facets = preview?.facets;
  const years = facets?.year_min && facets?.year_max ? [facets.year_min, facets.year_max] : null;
  const priority = LIBRARY_PRIORITY.find(p => p[0] === config.priority) || LIBRARY_PRIORITY[0];

  return (
    <div className="nx-ap-page nx-ap-library" data-nexup-page="library">
      <Stats five items={[
        { label: 'Ready to play', value: (summary.local || 0) + (summary.downloaded || 0), tone: 'good' },
        { label: 'Next to your movies', value: summary.local || 0 },
        { label: 'Downloaded', value: summary.downloaded || 0, tone: 'blue' },
        { label: 'Download storage', value: `${Number(summary.downloaded_gb || 0).toFixed(1)} / ${Number(config.max_gb).toFixed(0)} GB`, tone: 'violet' },
        { label: summary.outside ? 'Outside filters' : 'Not found', value: summary.outside || summary.errors || 0, tone: summary.outside || summary.errors ? 'warn' : '' },
      ]} />

      <div className="nx-ap-notice nx-ap-library-intro">
        <div>
          <strong>Trailers for movies you already own.</strong>
          <span>
            Separate from Coming Soon: nothing here is removed when a movie arrives, and Coming Soon&apos;s settings don&apos;t apply.
            Play them with a <em>Library trailers</em> block in the Sequence Builder, on Plex, Jellyfin and Emby. On Jellyfin and Emby the block can also pick trailers in the same genre as the movie that&apos;s starting.
          </span>
        </div>
      </div>

      {notice && <div className={`nx-ap-library-message ${notice.tone}`} role="status">{notice.text}</div>}
      {showSync && sync && <LibrarySyncCard sync={sync} onHide={() => setShowSync(false)} />}

      <div className="nx-ap-settings-grid">
        <section className="nx-ap-panel">
          <header className="nx-ap-panel-head"><div><strong>Library Trailers</strong><span>Turn on, then sync</span></div><Badge tone={config.enabled ? 'live' : ''}>{config.enabled ? 'On' : 'Off'}</Badge></header>
          <div className="nx-ap-panel-body">
            <div className="nx-ap-status-line no-icon"><div><strong>Keep trailers for movies in my library</strong><span>{info?.auto_refresh_hours ? `Refreshes with NeX-Up's automatic refresh, every ${info.auto_refresh_hours} hours.` : "NeX-Up's automatic refresh is off, so sync here when you want an update."}</span></div><Switch checked={config.enabled} onChange={checked => change({ enabled: checked })} label="Library Trailers" /></div>
            <div className="nx-ap-status-line no-icon"><div><strong>Radarr</strong><span>{info?.radarr_connected ? `Connected. ${preview ? `${preview.in_library} movies in your library.` : 'Your library is read from Radarr.'}` : 'Not connected.'}</span></div>{info?.radarr_connected ? <Badge tone="live">Connected</Badge> : <button type="button" className="nx-ap-btn" onClick={() => onNavigate('nexup')}>Connect</button>}</div>
            <div className="nx-ap-library-actions">
              <button type="button" className="nx-ap-btn amber" disabled={!dirty || saving} onClick={save}>{saving ? <Loader2 size={11} className="spin" /> : <Check size={11} />} Save changes</button>
              <button type="button" className="nx-ap-btn" disabled={running || !config.enabled || !info?.radarr_connected} onClick={startSync}>{running ? <Loader2 size={11} className="spin" /> : <RefreshCw size={11} />} {running ? 'Syncing...' : 'Sync now'}</button>
              {!showSync && sync?.finished_at && !running && <button type="button" className="nx-ap-btn ghost" onClick={() => setShowSync(true)}>Last sync</button>}
            </div>
          </div>
        </section>

        <section className="nx-ap-panel">
          <header className="nx-ap-panel-head"><div><strong>Where trailers come from</strong><span>Files you already have first</span></div></header>
          <div className="nx-ap-panel-body">
            <div className="nx-ap-status-line no-icon"><div><strong>Use trailers next to my movies</strong><span>Files like &quot;Movie-trailer.mp4&quot; or a &quot;Trailers&quot; folder. NeXroll only reads these, never deletes them.</span></div><Switch checked={config.use_local} onChange={checked => change({ use_local: checked })} label="Use trailers next to my movies" /></div>
            {config.use_local && (
              <div className="nx-ap-library-mappings">
                <span className="nx-ap-library-muted">If NeXroll sees your movie folders under a different path than Radarr does (Docker, a network share), map it here:</span>
                {config.path_mappings.map((m, i) => (
                  <div className="nx-ap-library-mapping" key={i}>
                    <input aria-label="Folder as Radarr sees it" placeholder="Radarr: /movies" value={m.radarr} onChange={event => change({ path_mappings: config.path_mappings.map((x, j) => (j === i ? { ...x, radarr: event.target.value } : x)) })} />
                    <span className="nx-ap-library-arrow" aria-hidden="true">&rarr;</span>
                    <input aria-label="Folder as NeXroll sees it" placeholder="NeXroll: D:\Movies" value={m.local} onChange={event => change({ path_mappings: config.path_mappings.map((x, j) => (j === i ? { ...x, local: event.target.value } : x)) })} />
                    <button type="button" className="nx-ap-btn danger square" aria-label="Remove folder mapping" onClick={() => change({ path_mappings: config.path_mappings.filter((_, j) => j !== i) })}><X size={11} /></button>
                  </div>
                ))}
                <button type="button" className="nx-ap-btn" onClick={() => change({ path_mappings: [...config.path_mappings, { radarr: '', local: '' }] })}><Plus size={11} /> Add folder mapping</button>
              </div>
            )}
            <div className="nx-ap-status-line no-icon"><div><strong>Download the rest from YouTube</strong><span>Uses Radarr&apos;s trailer link and NeX-Up&apos;s quality and YouTube settings.</span></div><Switch checked={config.download} onChange={checked => change({ download: checked })} label="Download the rest from YouTube" /></div>
          </div>
        </section>

        <section className="nx-ap-panel nx-lt-filters">
          <header className="nx-ap-panel-head">
            <div><strong>Which movies</strong><span>{config.mode === 'picked' ? 'Only the movies you pick get trailers' : 'Every filter is optional; together they narrow your library down'}</span></div>
            <div className="nx-lt-filter-head-actions">
              {previewing && <Loader2 size={13} className="spin" />}
              {config.mode === 'picked'
                ? <Badge tone="violet">{config.picked.length} picked</Badge>
                : preview && <Badge tone="violet">{preview.matching} of {preview.in_library} movies</Badge>}
              {config.mode !== 'picked' && filtersUsed && <button type="button" className="nx-ap-btn ghost" onClick={() => change(LIBRARY_FILTER_DEFAULTS)}>Clear filters</button>}
            </div>
          </header>
          <div className="nx-ap-panel-body">
            {!info?.radarr_connected ? <p className="nx-ap-library-muted">Connect Radarr under NeX-Up &gt; Connections to choose movies from your library.</p> : <>
              <div className="nx-lt-mode">
                <div className="nx-ap-segmented" role="group" aria-label="How to choose movies">
                  <button type="button" className={config.mode !== 'picked' ? 'active' : ''} onClick={() => change({ mode: 'filters' })}>Use filters</button>
                  <button type="button" className={config.mode === 'picked' ? 'active' : ''} onClick={() => change({ mode: 'picked' })}>Hand-pick movies</button>
                </div>
                <span>{config.mode === 'picked'
                  ? 'Browse your library and click posters to pick them. Picked trailers stay until you unpick them.'
                  : 'Describe the movies you want; new matches are picked up on every sync.'} Your filters and your picks are both kept when you switch.</span>
              </div>
              {config.mode === 'picked' ? (
                <LibraryMovieBrowser picked={config.picked} onChange={ids => change({ picked: ids })} genres={facets?.genres} maxDownloads={config.max_downloads} download={config.download} />
              ) : <>
              <div className="nx-lt-presets">
                {LIBRARY_PRESETS.map(preset => (
                  <button type="button" key={preset.id} className={`nx-lt-preset${activePreset?.id === preset.id ? ' on' : ''}`} onClick={() => applyPreset(preset)}>
                    <strong>{preset.label}</strong><span>{preset.copy}</span>
                  </button>
                ))}
              </div>

              <div className="nx-lt-filter-grid">
                <div className="nx-lt-filter wide">
                  <div className="nx-lt-filter-label"><strong>Genres</strong><span>Click once to include, twice to exclude, again to clear</span></div>
                  <div className="nx-lt-chips">
                    {(facets?.genres || []).map(g => (
                      <LibraryChip key={g.name} on={has(config.genres, g.name)} off={has(config.exclude_genres, g.name)} count={g.count} onClick={() => cycleGenre(g.name)}
                        title={has(config.genres, g.name) ? 'Included - click to exclude' : has(config.exclude_genres, g.name) ? 'Excluded - click to clear' : 'Click to include'}>{g.name}</LibraryChip>
                    ))}
                    {!facets && <span className="nx-ap-library-muted">Loading your library...</span>}
                  </div>
                </div>

                <div className="nx-lt-filter">
                  <div className="nx-lt-filter-label"><strong>Age ratings</strong><span>None chosen means every rating</span></div>
                  <div className="nx-lt-chips">
                    {(facets?.certifications || []).map(c => <LibraryChip key={c.name} on={has(config.certifications, c.name)} count={c.count} onClick={() => toggleIn('certifications', c.name)}>{c.name}</LibraryChip>)}
                  </div>
                </div>

                <div className="nx-lt-filter">
                  <div className="nx-lt-filter-label"><strong>Original language</strong><span>None chosen means any language</span></div>
                  <div className="nx-lt-chips">
                    {(facets?.languages || []).slice(0, 10).map(l => <LibraryChip key={l.name} on={has(config.languages, l.name)} count={l.count} onClick={() => toggleIn('languages', l.name)}>{l.name}</LibraryChip>)}
                  </div>
                </div>

                <div className="nx-lt-filter">
                  <div className="nx-lt-filter-label"><strong>Release years</strong><span>{years ? `Your library spans ${years[0]} to ${years[1]}` : 'Leave blank for any year'}</span></div>
                  <div className="nx-lt-range">
                    <input type="number" aria-label="From year" placeholder={years ? String(years[0]) : 'From'} value={config.year_from || ''} onChange={event => change({ year_from: Number(event.target.value) || 0 })} />
                    <span>to</span>
                    <input type="number" aria-label="To year" placeholder={years ? String(years[1]) : 'To'} value={config.year_to || ''} onChange={event => change({ year_to: Number(event.target.value) || 0 })} />
                  </div>
                </div>

                <div className="nx-lt-filter">
                  <div className="nx-lt-filter-label"><strong>Minimum scores</strong><span>Movies without a score are left out when set</span></div>
                  <div className="nx-lt-range">
                    <label><small>IMDb</small><select aria-label="Minimum IMDb score" value={config.min_imdb} onChange={event => change({ min_imdb: Number(event.target.value) })}>{LIBRARY_IMDB.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>
                    <label><small>Rotten Tomatoes</small><select aria-label="Minimum Rotten Tomatoes score" value={config.min_rt} onChange={event => change({ min_rt: Number(event.target.value) })}>{LIBRARY_RT.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>
                  </div>
                </div>

                <div className="nx-lt-filter">
                  <div className="nx-lt-filter-label"><strong>Recently added</strong><span>Only movies added within this time</span></div>
                  <select aria-label="Recently added" value={config.recent_days} onChange={event => change({ recent_days: Number(event.target.value) })}>{LIBRARY_RECENT.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>
                </div>

                {facets?.tags?.length > 0 && (
                  <div className="nx-lt-filter">
                    <div className="nx-lt-filter-label"><strong>Radarr tags</strong><span>Movies with any of these tags</span></div>
                    <div className="nx-lt-chips">{facets.tags.map(t => <LibraryChip key={t.id} on={config.tags.includes(t.id)} onClick={() => toggleTag(t.id)}>{t.label}</LibraryChip>)}</div>
                  </div>
                )}

                <div className="nx-lt-filter wide">
                  <div className="nx-lt-filter-label"><strong>Specific movies</strong><span>Always include or never include a movie, whatever the filters say</span></div>
                  <div className="nx-lt-movie-search">
                    <label><Search size={13} /><input aria-label="Search your library" value={movieQuery} onChange={event => setMovieQuery(event.target.value)} placeholder="Search your library by title..." /></label>
                    {movieResults.length > 0 && (
                      <ul className="nx-lt-movie-results">
                        {movieResults.map(m => (
                          <li key={m.id}>
                            <span className="thumb">{m.poster_url ? <img src={m.poster_url} alt="" loading="lazy" /> : <Film size={12} />}</span>
                            <span className="what"><strong>{m.title}</strong><small>{[m.year, m.certification, m.imdb ? `IMDb ${m.imdb}` : null].filter(Boolean).join(' / ')}</small></span>
                            <button type="button" className={`nx-ap-btn${config.always_include.includes(m.id) ? ' active' : ''}`} onClick={() => pin(m, 'always_include')}><Check size={11} /> Always</button>
                            <button type="button" className={`nx-ap-btn${config.never_include.includes(m.id) ? ' danger' : ''}`} onClick={() => pin(m, 'never_include')}><X size={11} /> Never</button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  {(config.always_include.length > 0 || config.never_include.length > 0) && (
                    <div className="nx-lt-pins">
                      {config.always_include.map(id => <span key={`a${id}`} className="nx-lt-pin always"><Check size={10} /> {pinnedInfo[id]?.title || `Movie ${id}`}<button type="button" aria-label="Remove from always include" onClick={() => unpin(id, 'always_include')}><X size={10} /></button></span>)}
                      {config.never_include.map(id => <span key={`n${id}`} className="nx-lt-pin never"><X size={10} /> {pinnedInfo[id]?.title || `Movie ${id}`}<button type="button" aria-label="Remove from never include" onClick={() => unpin(id, 'never_include')}><X size={10} /></button></span>)}
                    </div>
                  )}
                </div>
              </div>

              </>}
              {previewError && <p className="nx-ap-library-progress warn">{previewError}</p>}
              {preview && config.mode !== 'picked' && (
                <div className="nx-lt-result">
                  <div className="nx-lt-result-text">
                    {preview.matching === 0
                      ? <strong>No movies in your library match these filters.</strong>
                      : <><strong>{preview.matching} {preview.matching === 1 ? 'movie matches' : 'movies match'}</strong><span>{preview.with_trailer_link} have a trailer link in Radarr. {config.download && config.max_downloads ? `Up to ${config.max_downloads} will be downloaded, ${priority[1].toLowerCase()} first; trailers next to your movies are always included.` : 'Only trailers next to your movies will be used.'}</span></>}
                    {/* Replacement only ever affects downloads, and only when a
                        download limit is full. Saying "first replaced" with no
                        qualifier read as a contradiction of "never deletes",
                        and was simply wrong with downloads off, where nothing
                        is ever swapped out. */}
                    <span className="nx-lt-keep-note">Changing filters never deletes trailers you already have. Ones that no longer match are kept and still play, marked <strong>Outside filters</strong>.{config.download
                      ? ' They are the first to give way if a download limit later needs the room; trailers next to your movies are never removed.'
                      : ' With downloads off, nothing is ever swapped out.'}</span>
                  </div>
                  {preview.examples?.length > 0 && (
                    <div className="nx-lt-strip" aria-label="First movies in the selection">
                      {preview.examples.slice(0, 10).map(m => (
                        <figure key={m.id} title={`${m.title}${m.year ? ` (${m.year})` : ''}`}>
                          {m.poster_url ? <img src={m.poster_url} alt="" loading="lazy" /> : <div className="nx-lt-strip-fallback"><Film size={14} /></div>}
                          <figcaption>{m.title}</figcaption>
                        </figure>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>}
          </div>
        </section>

        <section className="nx-ap-panel">
          <header className="nx-ap-panel-head"><div><strong>Download limits</strong><span>Only downloads count toward these</span></div></header>
          <div className="nx-ap-panel-body">
            <div className="nx-ap-control-row"><div><strong>Maximum downloaded trailers</strong><span>Trailers next to your movies are always included on top of this.</span></div><select aria-label="Maximum downloaded trailers" value={config.max_downloads} disabled={!config.download} onChange={event => change({ max_downloads: Number(event.target.value) })}>{LIBRARY_MAX_DOWNLOADS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></div>
            <div className="nx-ap-control-row"><div><strong>Maximum download storage</strong><span>Kept in a Library folder inside NeX-Up storage.</span></div><select aria-label="Maximum download storage" value={config.max_gb} disabled={!config.download} onChange={event => change({ max_gb: Number(event.target.value) })}>{LIBRARY_MAX_GB.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></div>
            <div className="nx-ap-control-row"><div><strong>Download first</strong><span>{priority[2]} Movies you always include come first.</span></div><select aria-label="Download first" value={config.priority} disabled={!config.download} onChange={event => change({ priority: event.target.value })}>{LIBRARY_PRIORITY.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></div>
            <p className="nx-ap-library-muted">When a limit is reached, trailers outside your filters make room first. After that, each sync swaps up to three downloads that have played for at least a week for movies that don&apos;t have a trailer yet, so the selection keeps changing.</p>
            {(summary.outside || 0) > 0 && (
              <div className="nx-lt-outside-row">
                <span><strong>{summary.outside} trailer{summary.outside === 1 ? ' is' : 's are'} outside your filters.</strong> {summary.outside === 1 ? 'It still plays' : 'They still play'} until room is needed.</span>
                <button type="button" className="nx-ap-btn danger" disabled={running} onClick={cleanupOutside}><Trash2 size={11} /> Remove them</button>
              </div>
            )}
          </div>
        </section>
      </div>

      <div className="nx-ap-command">
        <label><Search size={13} /><input aria-label="Search library trailers" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search by title or genre..." /></label>
        <select aria-label="Trailer source" value={source} onChange={event => setSource(event.target.value)}>
          <option value="all">Every trailer</option><option value="local">Next to movies</option><option value="download">Downloaded</option><option value="outside">Outside your filters</option><option value="error">Not found</option>
        </select>
      </div>

      <div className={`nx-ap-trailer-layout${playing ? ' has-preview' : ''}`}>
        <section className="nx-ap-panel nx-ap-trailer-table">
          {trailers.length === 0
            ? <EmptyState icon={Film} title="No library trailers yet" copy={!config.enabled ? 'Turn Library Trailers on, choose your movies, then sync.' : config.download ? 'Sync to find trailers next to your movies and download the rest.' : 'Sync to find trailers next to your movies.'} action={config.enabled && info?.radarr_connected && !running ? startSync : null} actionLabel="Sync now" />
            : (
              <div className="nx-ap-poster-grid">
                {visible.map(t => {
                  const ready = t.status === 'available';
                  return (
                    <article key={t.id} className={`nx-ap-poster-card${playing?.id === t.id ? ' selected' : ''}${ready && t.is_enabled ? '' : ' disabled'}`}>
                      <Poster url={t.poster_url} title={t.title}>
                        <span className={`nx-ap-poster-state is-${ready && t.is_enabled ? 'ready' : 'unavailable'}`}>{!ready ? 'Not found' : t.source === 'local' ? 'Next to movie' : 'Downloaded'}</span>
                        {ready && t.in_selection === false && <span className="nx-lt-outside" title="This movie no longer matches your filters. The trailer is kept and still plays; it is replaced first when room is needed.">Outside filters</span>}
                        {ready && <button type="button" className="nx-ap-poster-play" onClick={() => setPlaying(t)} aria-label={`Play ${t.title}`}><Play size={17} /></button>}
                      </Poster>
                      <div className="nx-ap-poster-meta">
                        <strong title={t.title}>{t.title}{t.year ? ` (${t.year})` : ''}</strong>
                        <span title={ready ? (t.genres || []).join(', ') : t.error_message || ''}>{ready ? ((t.genres || []).slice(0, 3).join(', ') || 'No genres') : 'Retried in a few days'}</span>
                      </div>
                      {ready && (
                        <div className="nx-ap-poster-actions">
                          <button type="button" className={`nx-ap-btn square toggle${t.is_enabled ? ' on' : ''}`} onClick={() => toggleTrailer(t)} title={t.is_enabled ? 'Stop playing this trailer' : 'Play this trailer'} aria-pressed={t.is_enabled}>{t.is_enabled ? <ToggleRight size={15} /> : <ToggleLeft size={15} />}</button>
                        </div>
                      )}
                    </article>
                  );
                })}
                {visible.length === 0 && <EmptyState icon={Search} title="Nothing matches" copy="Try a different search or source." />}
              </div>
            )}
        </section>
        {playing && (
          <aside className="nx-ap-panel nx-ap-preview-rail">
            <video key={playing.id} className="nx-ap-library-video" src={playing.video_url} controls autoPlay />
            <div className="nx-ap-preview-body">
              <Badge tone={playing.is_enabled ? 'live' : ''}>{playing.source === 'local' ? 'Next to your movie' : 'Downloaded'}</Badge>
              <h3>{playing.title}{playing.year ? ` (${playing.year})` : ''}</h3>
              <p>{(playing.genres || []).join(', ') || 'No genres'}</p>
              <dl className="nx-ap-info-list">
                <div><dt>Added to library</dt><dd>{formatDate(playing.added_to_library)}</dd></div>
                <div><dt>Size</dt><dd>{playing.source === 'local' ? 'Your file' : formatSize(playing)}</dd></div>
              </dl>
              <div><button type="button" className="nx-ap-btn" onClick={() => setPlaying(null)}><X size={11} /> Close</button></div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}

// Retained temporarily as a parity reference while Generator Studio ships.
// eslint-disable-next-line no-unused-vars
function GeneratorPage(props) {
  const {
    settings, generatorTab, setGeneratorTab,
    dynamicSettings, setDynamicSettings, templates, colorThemes, ffmpegAvailable,
    dynamicGenerating, generatedPrerolls, onGenerateDynamic, onPreviewDynamic, onDeleteDynamic,
    previewRef, onUploadAsset, onRemoveAsset,
    comingSettings, setComingSettings, comingGenerating, generatedComingLists,
    onGenerateComing, onPreviewComing, onDeleteComing, onNavigate, onSaveDynamic, onSaveComing,
  } = props;
  const templateOptions = templates.length ? templates.slice(0, 3) : [
    { id: 'coming_soon', name: 'Cinematic glow', description: 'A polished Coming Soon identity.' },
    { id: 'feature_presentation', name: 'Feature presentation', description: 'A classic theater presentation.' },
    { id: 'now_showing', name: 'Now showing', description: 'A bright contemporary title.' },
  ];
  const selectedTemplate = templateOptions.find(item => item.id === dynamicSettings.template) || templateOptions[0];
  const themeEntries = Object.entries(colorThemes || {});
  const selectedTheme = colorThemes?.[dynamicSettings.theme] || {};
  const connected = settings.radarr_connected || settings.sonarr_connected;
  const updateComing = updates => setComingSettings(previous => ({ ...previous, ...updates }));
  const recent = generatorTab === 'dynamic' ? generatedPrerolls : generatedComingLists;
  return (
    <div className="nx-ap-page nx-ap-generator" data-nexup-page="generator">
      {!connected && <div className="nx-ap-notice warning"><AlertTriangle size={14} /><div><strong>Connect Radarr or Sonarr to populate media-driven generator content.</strong><span>You can still configure the design now; generation remains unavailable until a service and storage folder are ready.</span></div><button type="button" className="nx-ap-btn" onClick={() => onNavigate('nexup')}>Connections</button></div>}
      <div className="nx-ap-generator-layout">
        <section className="nx-ap-panel">
          <header className="nx-ap-panel-head"><div><strong>Generator mode</strong><span>{generatorTab === 'dynamic' ? 'Dynamic intro settings' : 'Coming Soon list settings'}</span></div><div className="nx-ap-segmented"><button type="button" className={generatorTab === 'dynamic' ? 'active' : ''} onClick={() => setGeneratorTab('dynamic')}>Dynamic preroll</button><button type="button" className={generatorTab === 'coming-soon' ? 'active' : ''} onClick={() => setGeneratorTab('coming-soon')}>Coming Soon list</button></div></header>
          {generatorTab === 'dynamic' ? <div className="nx-ap-panel-body">
            <div className="nx-ap-section-label">1 / Choose a visual style</div>
            <div className="nx-ap-template-grid">{templateOptions.map((template, index) => <button type="button" key={template.id} className={dynamicSettings.template === template.id ? 'active' : ''} onClick={() => setDynamicSettings(previous => ({ ...previous, template: template.id }))}><i className={`art art-${index}`}>{template.name.split(' ')[0].toUpperCase()}</i><strong>{template.name}</strong><span>{template.description}</span></button>)}</div>
            <div className="nx-ap-divider" />
            <div className="nx-ap-section-label">2 / Personalize the intro</div>
            <div className="nx-ap-fields"><label><span>Server name</span><input value={dynamicSettings.server_name} onChange={event => setDynamicSettings(previous => ({ ...previous, server_name: event.target.value }))} placeholder="My Media Server" /></label><label><span>Duration</span><select value={dynamicSettings.duration} onChange={event => setDynamicSettings(previous => ({ ...previous, duration: Number(event.target.value) }))}>{[3, 5, 8, 10, 15, 20].map(value => <option key={value} value={value}>{value} seconds</option>)}</select></label></div>
            <div className="nx-ap-fields"><label><span>Color theme</span><select value={dynamicSettings.theme} onChange={event => setDynamicSettings(previous => ({ ...previous, theme: event.target.value }))}>{themeEntries.length ? themeEntries.map(([id]) => <option key={id} value={id}>{id.replaceAll('_', ' ')}</option>) : <option value={dynamicSettings.theme || 'midnight'}>Midnight</option>}</select></label><label><span>Language</span><select value={dynamicSettings.language} onChange={event => setDynamicSettings(previous => ({ ...previous, language: event.target.value }))}><option value="en">English</option><option value="fr">French</option><option value="es">Spanish</option><option value="de">German</option></select></label></div>
            <div className="nx-ap-divider" />
            <div className="nx-ap-section-label">3 / Branding and output</div>
            <div className="nx-ap-upload-row"><label><span>Custom logo overlay</span><input readOnly value={dynamicSettings.customLogoFilename || 'No custom logo selected'} /></label><label className="nx-ap-btn"><Upload size={11} /> Browse<input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={event => { const file = event.target.files?.[0]; if (file) onUploadAsset('dynamic-logo', file); event.target.value = ''; }} /></label>{dynamicSettings.customLogoFilename && <button type="button" className="nx-ap-btn danger" onClick={() => onRemoveAsset('dynamic-logo')}><X size={11} /> Remove</button>}</div>
            <footer className="nx-ap-form-actions"><button type="button" className="nx-ap-btn" onClick={onSaveDynamic}>Save defaults</button><button type="button" className="nx-ap-btn amber" disabled={!connected || !settings.storage_path || !ffmpegAvailable || dynamicGenerating || !dynamicSettings.server_name.trim()} onClick={onGenerateDynamic}>{dynamicGenerating ? <Loader2 size={12} className="spin" /> : <Sparkles size={12} />} Generate preroll</button></footer>
          </div> : <div className="nx-ap-panel-body">
            <div className="nx-ap-section-label">1 / Layout and content</div>
            <div className="nx-ap-choice-grid">{[['grid', 'Poster grid', 'Cinematic art-led layout.'], ['list', 'Text list', 'Compact title and date layout.'], ['both', 'Generate both', 'Create grid and list versions.']].map(([id, label, copy]) => <button type="button" key={id} className={comingSettings.layout === id ? 'active' : ''} onClick={() => updateComing({ layout: id })}><strong>{label}</strong><span>{copy}</span></button>)}</div>
            <div className="nx-ap-fields three"><label><span>Content source</span><select value={comingSettings.source} onChange={event => updateComing({ source: event.target.value })}><option value="both">Movies and TV</option><option value="movies">Movies only</option><option value="shows">TV only</option></select></label><label><span>Language</span><select value={comingSettings.language} onChange={event => updateComing({ language: event.target.value })}><option value="en">English</option><option value="fr">French</option><option value="es">Spanish</option><option value="de">German</option></select></label><label><span>Max items</span><select value={comingSettings.maxItems} onChange={event => updateComing({ maxItems: Number(event.target.value) })}>{[6, 8, 10, 12].map(value => <option key={value} value={value}>{value} items</option>)}</select></label></div>
            <div className="nx-ap-divider" />
            <div className="nx-ap-section-label">2 / Presentation</div>
            <div className="nx-ap-fields three"><label><span>Duration</span><select value={comingSettings.duration} onChange={event => updateComing({ duration: Number(event.target.value) })}>{[10, 20, 30].map(value => <option key={value} value={value}>{value} seconds</option>)}</select></label><label><span>Background</span><input type="color" value={comingSettings.bgColor} onChange={event => updateComing({ bgColor: event.target.value })} /></label><label><span>Accent</span><input type="color" value={comingSettings.accentColor} onChange={event => updateComing({ accentColor: event.target.value })} /></label></div>
            <div className="nx-ap-upload-row"><label><span>Background music</span><input readOnly value={comingSettings.customAudioFilename || (comingSettings.includeAudio ? 'Default cinematic' : 'No music')} /></label><label className="nx-ap-btn"><Upload size={11} /> Browse<input type="file" accept="audio/*" onChange={event => { const file = event.target.files?.[0]; if (file) onUploadAsset('coming-audio', file); event.target.value = ''; }} /></label><label><span>Custom logo</span><input readOnly value={comingSettings.customLogoFilename || 'No custom logo selected'} /></label><label className="nx-ap-btn"><Upload size={11} /> Browse<input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={event => { const file = event.target.files?.[0]; if (file) onUploadAsset('coming-logo', file); event.target.value = ''; }} /></label></div>
            <div className="nx-ap-divider" />
            <div className="nx-ap-section-label">3 / Automation</div>
            <div className="nx-ap-status-line"><i>ON</i><div><strong>Include Available Now section</strong><span>Show recently released media after upcoming titles.</span></div><Switch checked={Number(comingSettings.maxAvailableNow) !== 0} onChange={checked => updateComing({ maxAvailableNow: checked ? 8 : 0 })} label="Include Available Now section" /></div>
            <div className="nx-ap-status-line"><i>ON</i><div><strong>Auto-regenerate after sync</strong><span>Rebuild the list when new eligible media is discovered.</span></div><Switch checked={Boolean(comingSettings.autoRegen)} onChange={checked => updateComing({ autoRegen: checked })} label="Auto-regenerate after sync" /></div>
            <footer className="nx-ap-form-actions"><button type="button" className="nx-ap-btn" onClick={onSaveComing}>Save defaults</button><button type="button" className="nx-ap-btn amber" disabled={!connected || !settings.storage_path || comingGenerating} onClick={() => onGenerateComing(comingSettings.layout)}>{comingGenerating ? <Loader2 size={12} className="spin" /> : <Sparkles size={12} />} Generate {comingSettings.layout === 'both' ? 'both lists' : 'Coming Soon list'}</button></footer>
          </div>}
        </section>
        <aside className="nx-ap-panel nx-ap-generator-preview">
          {generatorTab === 'dynamic' ? <><div ref={previewRef} className="nx-ap-generator-art" style={{ '--preview-bg': String(selectedTheme.bg || '#17130e').replace('0x', '#'), '--preview-accent': String(selectedTheme.primary || '#f4b83f').replace('0x', '#') }}><strong>{dynamicSettings.server_name || 'YOUR MEDIA SERVER'}</strong><span><b>{selectedTemplate?.name || 'Cinematic glow'}</b><small>{dynamicSettings.duration} seconds</small></span></div><div className="nx-ap-preview-body"><dl className="nx-ap-info-list"><div><dt>Canvas</dt><dd>1920 × 1080</dd></div><div><dt>Template</dt><dd>{selectedTemplate?.name}</dd></div><div><dt>Language</dt><dd>{dynamicSettings.language.toUpperCase()}</dd></div></dl><button type="button" className="nx-ap-btn amber wide" disabled={!dynamicSettings.preroll_path && !generatedPrerolls.length} onClick={() => onPreviewDynamic(dynamicSettings.preroll_path ? { filename: String(dynamicSettings.preroll_path).split(/[\\/]/).pop() } : generatedPrerolls[0])}><Play size={11} /> Preview animation</button></div></> : <><div className="nx-ap-generator-art coming"><strong>COMING SOON</strong><div><i /><i /><i /></div><span><b>{comingSettings.layout === 'list' ? 'Text list' : comingSettings.layout === 'both' ? 'Grid + list' : 'Poster grid'} / {comingSettings.maxItems} titles</b><small>{comingSettings.duration} seconds</small></span></div><div className="nx-ap-preview-body"><dl className="nx-ap-info-list"><div><dt>Eligible media</dt><dd>Movies + TV</dd></div><div><dt>Output</dt><dd>1080p MP4</dd></div><div><dt>Auto-regenerate</dt><dd>{comingSettings.autoRegen ? 'On' : 'Off'}</dd></div></dl><button type="button" className="nx-ap-btn amber wide" disabled={!generatedComingLists.length} onClick={() => onPreviewComing(generatedComingLists[0])}><Play size={11} /> Preview list</button></div></>}
        </aside>
      </div>
      {recent.length > 0 && <section className="nx-ap-panel nx-ap-generated"><header className="nx-ap-panel-head"><div><strong>Recent generated {generatorTab === 'dynamic' ? 'prerolls' : 'lists'}</strong><span>Saved to the NeXroll library</span></div></header><div className="nx-ap-generated-list">{recent.slice(0, 6).map((item, index) => <article key={item.filename || index}><button type="button" className={`nx-ap-generated-art art-${index % 3}`} onClick={() => generatorTab === 'dynamic' ? onPreviewDynamic(item) : onPreviewComing(item)}><Play size={13} /><span>{generatorTab === 'dynamic' ? 'SERVER INTRO' : 'COMING SOON'}</span></button><div><strong>{item.name || item.filename || 'Generated video'}</strong><span>{item.created_at ? formatDate(Number(item.created_at) > 100000000000 ? Number(item.created_at) : Number(item.created_at) * 1000) : 'Saved'} / {formatSize(item)}</span><button type="button" onClick={() => generatorTab === 'dynamic' ? onDeleteDynamic(item.filename) : onDeleteComing(item.filename)}><Trash2 size={11} /></button></div></article>)}</div></section>}
    </div>
  );
}

function SettingsPage(props) {
  const {
    settings, storage, potoken, youtubeSetup,
    onUpdateSettings, onOpenFolder, onTestPotoken, onConfigureYoutube,
    onInstallPotoken, onTestTmdbKey, tmdbKeyTest,
  } = props;
  const update = (key, parser = value => value) => event => onUpdateSettings({ [key]: parser(event.target.value) });
  const select = (label, key, options, parser) => <div className="nx-ap-control-row"><div><strong>{label[0]}</strong><span>{label[1]}</span></div><select aria-label={label[0]} value={settings[key] ?? options[0][0]} onChange={update(key, parser)}>{options.map(([value, copy]) => <option key={value} value={value}>{copy}</option>)}</select></div>;
  const providerReady = Boolean(potoken?.status?.configured || potoken?.status?.healthy || youtubeSetup?.status?.authenticated);
  // Whether the dependency is on disk, which is a separate question from whether
  // the provider server is up. The status payload gained an explicit `installed`
  // flag; the component parts are the fallback for an older backend.
  const providerInstalled = Boolean(
    potoken?.status?.installed
    ?? (potoken?.status?.plugin_installed && potoken?.status?.provider_present)
  );
  const usedGb = Number(storage?.total_size_gb || storage?.used_gb || 0);
  const maxGb = Number(settings.max_storage_gb || storage?.max_gb || 5);
  const percent = maxGb > 0 ? Math.min(100, (usedGb / maxGb) * 100) : 0;
  return (
    <div className="nx-ap-page nx-ap-settings" data-nexup-page="settings">
      <div className="nx-ap-settings-grid">
          <section className="nx-ap-panel"><header className="nx-ap-panel-head"><div><strong>YouTube access</strong><span>Download provider and authentication health</span></div><Badge tone={providerReady ? 'live' : 'warn'}>{providerReady ? 'Ready' : 'Needs setup'}</Badge></header><div className="nx-ap-panel-body"><div className={`nx-ap-health-card${providerReady ? '' : ' warning'}`}><strong>{providerReady ? 'PO-token provider is configured' : 'YouTube access needs attention'}</strong><p>{providerReady ? 'Authenticated trailer downloads are available.' : 'Configure the provider or sign in before downloading protected trailers.'}</p><div><button type="button" className="nx-ap-btn" disabled={potoken.testing} onClick={onTestPotoken}>{potoken.testing ? <Loader2 size={11} className="spin" /> : <Check size={11} />} Test provider</button><button type="button" className="nx-ap-btn" onClick={onConfigureYoutube}>Reconfigure sign-in</button></div></div><div className="nx-ap-control-row"><div><strong>Provider dependency</strong><span>{providerInstalled ? 'Installed and available.' : 'Required for automatic downloads.'}</span></div>{providerInstalled ? <Badge tone="live">Installed</Badge> : <button type="button" className="nx-ap-btn" onClick={onInstallPotoken}>Install</button>}</div></div></section>
          <section className="nx-ap-panel"><header className="nx-ap-panel-head"><div><strong>Upcoming and retention</strong><span>Eligibility windows and cleanup limits</span></div></header><div className="nx-ap-panel-body">{select(['Upcoming window', 'How far ahead to include media.'], 'days_ahead', [[30, '30 days'], [60, '60 days'], [90, '90 days'], [180, '180 days']], Number)}{select(['Release date preference', 'Date source used for movie eligibility.'], 'release_date_preference', [['digital_first', 'Digital release first'], ['digital_only', 'Digital only'], ['theatrical', 'Theatrical']])}{select(['Maximum stored trailers', 'Oldest unused trailers are removed first.'], 'max_trailers', [[10, '10 trailers'], [25, '25 trailers'], [50, '50 trailers'], [0, 'No limit']], Number)}{select(['Delete trailers after', 'Counted from the release date, or the download if that is later. This deletes the trailer files.'], 'trailer_retention_days', [[7, '7 days'], [14, '14 days'], [30, '30 days'], [0, 'Never delete']], Number)}</div></section>
          <section className="nx-ap-panel"><header className="nx-ap-panel-head"><div><strong>Trailer storage</strong><span>Folder and current utilization</span></div><Badge tone="violet">{usedGb.toFixed(1)} GB</Badge></header><div className="nx-ap-panel-body"><label className="nx-ap-folder-field"><span>Storage folder</span><div><input readOnly value={settings.storage_path || ''} placeholder="Choose a storage folder" /><button type="button" className="nx-ap-btn" onClick={() => onOpenFolder('nexup-storage', settings.storage_path || '')}><FolderOpen size={11} /> Browse</button></div></label><div className="nx-ap-usage"><i><span style={{ width: `${percent}%` }} /></i><strong>{usedGb.toFixed(1)} / {maxGb.toFixed(0)} GB</strong></div></div></section>
          <section className="nx-ap-panel"><header className="nx-ap-panel-head"><div><strong>Rate limits and safety</strong><span>Reduce provider blocks and failed batches</span></div></header><div className="nx-ap-panel-body">{select(['Delay between downloads', 'Longer delays reduce YouTube blocking risk.'], 'download_delay', [[5, '5 seconds / Recommended'], [10, '10 seconds'], [30, '30 seconds']], Number)}{select(['Concurrent downloads', 'Parallel trailer download workers.'], 'max_concurrent', [[1, '1 at a time / Safest'], [2, '2 concurrent']], Number)}{select(['Batch warning', 'Confirm before large download batches.'], 'bulk_warning_threshold', [[5, 'Warn at 5+ trailers'], [10, 'Warn at 10+'], [0, 'Never warn']], Number)}</div></section>
          <section className="nx-ap-panel"><header className="nx-ap-panel-head"><div><strong>Download defaults</strong><span>Quality, refresh, and duration</span></div></header><div className="nx-ap-panel-body">{select(['Video quality', 'Resolution used for new trailers.'], 'quality', [['1080', '1080p / Recommended'], ['720', '720p'], ['2160', '4K'], ['best', 'Best available']])}{select(['Automatic refresh', 'How often NeX-Up checks connected services.'], 'auto_refresh_hours', [[12, 'Every 12 hours'], [24, 'Daily'], [168, 'Weekly']], Number)}{select(['Maximum trailer length', 'Skip videos longer than this limit.'], 'max_trailer_duration', [[120, '2 minutes'], [180, '3 minutes'], [0, 'No limit']], Number)}</div></section>
          <section className="nx-ap-panel"><header className="nx-ap-panel-head"><div><strong>Metadata and automation</strong><span>TMDB lookups and media types</span></div></header><div className="nx-ap-panel-body"><label className="nx-ap-folder-field"><span>TMDB API key (optional)</span><div><input type="password" value={settings.tmdb_api_key || ''} onChange={event => onUpdateSettings({ tmdb_api_key: event.target.value })} /><button type="button" className="nx-ap-btn" onClick={onTestTmdbKey}>{tmdbKeyTest?.testing ? <Loader2 size={11} className="spin" /> : null} Test key</button></div></label><div className="nx-ap-status-line"><i>MOV</i><div><strong>Movie trailer automation</strong><span>Use Radarr media during sync.</span></div><Switch checked={Boolean(settings.enabled)} onChange={checked => onUpdateSettings({ enabled: checked })} label="Movie trailer automation" /></div><div className="nx-ap-status-line"><i>TV</i><div><strong>TV trailer automation</strong><span>Use Sonarr seasons during sync.</span></div><Switch checked={Boolean(settings.sonarr_enabled)} onChange={checked => onUpdateSettings({ sonarr_enabled: checked })} label="TV trailer automation" /></div></div></section>
      </div>
    </div>
  );
}

export default function NexUpApprovedPages(props) {
  if (props.activeTab === 'nexup/upcoming') return <UpcomingPage {...props} />;
  if (props.activeTab === 'nexup/trailers') return <TrailersPage {...props} />;
  if (props.activeTab === 'nexup/library') return <LibraryTrailersPage {...props} />;
  if (props.activeTab === 'nexup/generator') return <NeXUpGeneratorStudio {...props} />;
  if (props.activeTab === 'nexup/settings') return <SettingsPage {...props} />;
  return <ConnectionsPage {...props} />;
}
