import React from 'react';

// "Same genre as the movie that's starting" for NeX-Up and Library trailer
// blocks. match_playing turns it on; match_playing_only decides what happens
// when no trailer shares a genre, or the genre isn't known (always on Plex).
export default function TrailerGenreMatch({ value, onChange }) {
  const enabled = Boolean(value?.match_playing);
  const only = enabled && Boolean(value?.match_playing_only);
  return <fieldset style={{ border: '1px solid var(--border-color)', borderRadius: 8, padding: 10, minWidth: 0, margin: '8px 0' }}>
    <legend style={{ fontSize: 13 }}>Genre</legend>
    <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
      <input type="checkbox" checked={enabled} onChange={e => onChange({ match_playing: e.target.checked, match_playing_only: e.target.checked && only })} />
      Same genre as the movie that's starting
    </label>
    {enabled && <label style={{ display: 'block', fontSize: 13, marginTop: 10 }}>
      When no trailer shares its genre
      <select value={only ? 'only' : 'prefer'} onChange={e => onChange({ match_playing: true, match_playing_only: e.target.value === 'only' })}
        style={{ display: 'block', width: '100%', maxWidth: '100%', marginTop: 6, padding: '8px 10px', border: '1px solid var(--border-color)', borderRadius: 6, background: 'var(--input-bg)', color: 'var(--text-color)' }}>
        <option value="prefer">Play trailers of any genre</option>
        <option value="only">Play no trailers</option>
      </select>
    </label>}
    <p style={{ fontSize: 11, color: 'var(--text-secondary)', margin: '8px 0 0' }}>
      Jellyfin and Emby say which movie is starting, so this can pick horror trailers before a horror movie.
      {' '}{only
        ? 'Plex doesn\'t, so on Plex this block plays nothing.'
        : 'Plex doesn\'t, so on Plex trailers come from the whole selection.'}
      {enabled && ' Trailers get their genres from Radarr and Sonarr; older ones on the next NeX-Up sync.'}
    </p>
  </fieldset>;
}
