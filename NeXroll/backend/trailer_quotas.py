"""Optional minimum targets for the playable Library Trailers pool."""
import os

from backend.trailer_filters import rating_key

RATINGS = ('G', 'PG', 'PG-13', 'R', 'NC-17', 'Unrated')


def normalize_quotas(value, strict=False):
    def invalid():
        if strict:
            raise ValueError('Each trailer target needs a rating or genre, at least one value, and a whole-number minimum from 1 to 500 (up to 12 targets).')
    if not isinstance(value, list) or len(value) > 12:
        invalid()
        return []
    result = []
    for rule in value:
        if not isinstance(rule, dict):
            invalid(); continue
        kind, values, minimum = rule.get('kind'), rule.get('values'), rule.get('min')
        if (kind not in ('rating', 'genre') or not isinstance(values, list) or not values
                or type(minimum) is not int or not 1 <= minimum <= 500
                or any(not isinstance(v, str) or not v.strip() or len(v) > 100 for v in values)
                or len(values) > 50 or (kind == 'rating' and any(v not in RATINGS for v in values))):
            invalid(); continue
        unique = {v.strip().casefold(): v.strip() for v in values}
        result.append({'kind': kind, 'values': list(unique.values()), 'min': minimum})
    return result


def matches(movie, rule):
    if rule['kind'] == 'rating':
        return rating_key(movie.get('certification')) in {rating_key(v) for v in rule['values']}
    return bool({str(g).casefold() for g in movie.get('genres') or []}
                & {g.casefold() for g in rule['values']})


def playable_movies(candidates, rows):
    ready = {r.radarr_movie_id: r for r in rows if r.status == 'available' and r.is_enabled is not False
             and r.local_path and os.path.isfile(r.local_path)}
    # Report the metadata playback actually has, not newly discovered Radarr
    # metadata that has not been stored by a sync yet.
    return [{**m, 'certification': ready[m['id']].certification,
             'genres': ready[m['id']].genre_list()} for m in candidates if m['id'] in ready]


def counts(movies, quotas):
    return [sum(matches(m, q) for m in movies) for q in quotas]


def gain(movie, quotas, have):
    return sum(matches(movie, q) for q, count in zip(quotas, have) if count < q['min'])


def report(candidates, rows, config, notes=()):
    quotas = config.get('quotas', [])
    actual = counts(playable_movies(candidates, rows), quotas)
    possible = counts(candidates, quotas)
    return [{**q, 'available': have, 'matching_movies': total, 'shortfall': max(q['min'] - have, 0),
             'reason': ('Target met' if have >= q['min'] else
                        f'Only {total} movies match this target within your selection.' if total < q['min'] else
                        'Downloads are off; only existing trailers can meet this target.' if not config['download'] else
                        '; '.join(dict.fromkeys(notes)) if notes else
                        'Sync to try matching trailers within your download and storage limits.')}
            for q, have, total in zip(quotas, actual, possible)]
