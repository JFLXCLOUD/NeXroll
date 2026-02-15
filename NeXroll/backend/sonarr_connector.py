"""
NeX-Up: Sonarr Integration Module
Connects to Sonarr to fetch upcoming TV shows and seasons for trailers
"""

import os
import re
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# TMDB API for getting trailer sources
TMDB_API_KEY = "8d6d91941230817f7571f3524e6d49fc"  # Public API key for trailer lookups
TMDB_BASE_URL = "https://api.themoviedb.org/3"


class SonarrConnector:
    """Handles all Sonarr API interactions"""
    
    def __init__(self, url: str, api_key: str, timeout: int = 30):
        self.base_url = url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {
            'X-Api-Key': api_key,
            'Content-Type': 'application/json'
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the Sonarr connection and return system status"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/system/status",
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                return {
                    'success': True,
                    'version': data.get('version', 'Unknown'),
                    'appName': data.get('appName', 'Sonarr'),
                    'instanceName': data.get('instanceName', ''),
                    'message': 'Connection successful'
                }
        except httpx.TimeoutException:
            return {'success': False, 'message': 'Connection timed out'}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return {'success': False, 'message': 'Invalid API key'}
            return {'success': False, 'message': f'HTTP error: {e.response.status_code}'}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    async def get_all_series(self) -> List[Dict[str, Any]]:
        """Fetch all series from Sonarr"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/series",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching series from Sonarr: {e}")
            return []
    
    async def get_upcoming_shows(self, days_ahead: int = 90) -> List[Dict[str, Any]]:
        """
        Fetch upcoming new shows and new seasons from Sonarr.
        Returns shows that:
        - Are monitored
        - Have upcoming seasons that haven't aired yet
        - Are within the look-ahead window
        """
        try:
            all_series = await self.get_all_series()
            
            upcoming = []
            today = datetime.now().date()
            cutoff_date = today + timedelta(days=days_ahead)
            # Allow shows up to 7 days past their premiere date
            past_cutoff = today - timedelta(days=7)
            
            for series in all_series:
                # Skip if not monitored
                if not series.get('monitored', False):
                    continue
                
                tvdb_id = series.get('tvdbId')
                title = series.get('title', 'Unknown')
                year = series.get('year')
                
                # Get series images
                poster_url = None
                fanart_url = None
                for image in series.get('images', []):
                    if image.get('coverType') == 'poster':
                        poster_url = image.get('remoteUrl') or image.get('url')
                    elif image.get('coverType') == 'fanart':
                        fanart_url = image.get('remoteUrl') or image.get('url')
                
                # Check for upcoming seasons
                seasons = series.get('seasons', [])
                statistics = series.get('statistics', {})
                
                # Check if this is a new show (no episodes downloaded yet)
                total_episode_count = statistics.get('totalEpisodeCount', 0)
                episode_file_count = statistics.get('episodeFileCount', 0)
                is_new_show = episode_file_count == 0 and total_episode_count > 0
                
                # Get first air date for the series
                first_aired = series.get('firstAired')
                if first_aired:
                    try:
                        first_aired_date = datetime.fromisoformat(first_aired.replace('Z', '+00:00')).date()
                    except:
                        first_aired_date = None
                else:
                    first_aired_date = None
                
                # New show that hasn't aired yet
                if is_new_show and first_aired_date:
                    if past_cutoff <= first_aired_date <= cutoff_date:
                        upcoming.append({
                            'sonarr_id': series.get('id'),
                            'tvdb_id': tvdb_id,
                            'imdb_id': series.get('imdbId'),
                            'title': title,
                            'year': year,
                            'overview': series.get('overview', ''),
                            'status': series.get('status', ''),
                            'network': series.get('network', ''),
                            'release_date': first_aired_date.isoformat(),
                            'release_type': 'new_show',
                            'season_number': 1,
                            'days_until_release': (first_aired_date - today).days,
                            'poster_url': poster_url,
                            'fanart_url': fanart_url,
                            'runtime': series.get('runtime', 0),
                            'genres': series.get('genres', []),
                            'ratings': series.get('ratings', {}),
                            'monitored': series.get('monitored', False)
                        })
                        continue  # Don't also add as new season
                
                # Check each season for upcoming new seasons
                for season in seasons:
                    if not season.get('monitored', False):
                        continue
                    
                    season_number = season.get('seasonNumber', 0)
                    if season_number == 0:  # Skip specials
                        continue
                    
                    season_stats = season.get('statistics', {})
                    season_episode_count = season_stats.get('totalEpisodeCount', 0)
                    season_file_count = season_stats.get('episodeFileCount', 0)
                    
                    # This is a new season if it has episodes but none downloaded
                    # and we need to check if it's about to premiere
                    if season_episode_count > 0 and season_file_count == 0:
                        # We need to get more detailed info about this season
                        # For now, we'll add it and let the user decide
                        # A better approach would be to check episode air dates
                        
                        # Check if any previous seasons have episodes
                        has_previous_content = False
                        for prev_season in seasons:
                            if prev_season.get('seasonNumber', 0) < season_number:
                                prev_stats = prev_season.get('statistics', {})
                                if prev_stats.get('episodeFileCount', 0) > 0:
                                    has_previous_content = True
                                    break
                        
                        # Only add as "new season" if there's previous content (otherwise it's a new show)
                        if has_previous_content:
                            upcoming.append({
                                'sonarr_id': series.get('id'),
                                'tvdb_id': tvdb_id,
                                'imdb_id': series.get('imdbId'),
                                'title': title,
                                'year': year,
                                'overview': series.get('overview', ''),
                                'status': series.get('status', ''),
                                'network': series.get('network', ''),
                                'release_date': first_aired_date.isoformat() if first_aired_date else None,
                                'release_type': 'new_season',
                                'season_number': season_number,
                                'days_until_release': None,  # Would need episode data
                                'poster_url': poster_url,
                                'fanart_url': fanart_url,
                                'runtime': series.get('runtime', 0),
                                'genres': series.get('genres', []),
                                'ratings': series.get('ratings', {}),
                                'monitored': series.get('monitored', False)
                            })
            
            # Sort by release date (soonest first, None at end)
            upcoming.sort(key=lambda x: x['release_date'] or '9999-99-99')
            
            return upcoming
            
        except Exception as e:
            logger.error(f"Error fetching upcoming shows from Sonarr: {e}")
            return []
    
    async def get_calendar(self, start_date: datetime = None, end_date: datetime = None) -> List[Dict[str, Any]]:
        """
        Get upcoming episodes from Sonarr calendar.
        This gives us more accurate premiere dates for new seasons.
        """
        try:
            if not start_date:
                start_date = datetime.now()
            if not end_date:
                end_date = start_date + timedelta(days=90)
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/calendar",
                    headers=self.headers,
                    params={
                        'start': start_date.strftime('%Y-%m-%d'),
                        'end': end_date.strftime('%Y-%m-%d'),
                        'includeSeries': 'true',
                        'includeEpisodeFile': 'false',
                        'includeEpisodeImages': 'false'
                    }
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching Sonarr calendar: {e}")
            return []
    
    async def get_upcoming_premieres(self, days_ahead: int = 90) -> List[Dict[str, Any]]:
        """
        Get upcoming season premieres and new show premieres using the calendar API.
        Only returns future shows (today or later).
        """
        try:
            calendar = await self.get_calendar(
                start_date=datetime.now(),  # Only future shows from today
                end_date=datetime.now() + timedelta(days=days_ahead)
            )
            
            premieres = {}  # Use dict to deduplicate by series+season
            today = datetime.now().date()
            
            for episode in calendar:
                # Only interested in premiere episodes (episode 1 of a season)
                if episode.get('episodeNumber', 0) != 1:
                    continue
                
                series = episode.get('series', {})
                season_number = episode.get('seasonNumber', 0)
                if season_number == 0:  # Skip specials
                    continue
                
                sonarr_id = series.get('id')
                key = f"{sonarr_id}_S{season_number}"
                
                if key in premieres:
                    continue  # Already have this premiere
                
                # Get air date
                air_date_str = episode.get('airDateUtc') or episode.get('airDate')
                if not air_date_str:
                    continue
                
                try:
                    air_date = datetime.fromisoformat(air_date_str.replace('Z', '+00:00')).date()
                except:
                    continue
                
                # Get series images
                poster_url = None
                fanart_url = None
                for image in series.get('images', []):
                    if image.get('coverType') == 'poster':
                        poster_url = image.get('remoteUrl') or image.get('url')
                    elif image.get('coverType') == 'fanart':
                        fanart_url = image.get('remoteUrl') or image.get('url')
                
                # Determine if this is a new show or new season
                is_new_show = season_number == 1
                release_type = 'new_show' if is_new_show else 'new_season'
                
                premieres[key] = {
                    'sonarr_id': sonarr_id,
                    'tvdb_id': series.get('tvdbId'),
                    'imdb_id': series.get('imdbId'),
                    'title': series.get('title', 'Unknown'),
                    'year': series.get('year'),
                    'overview': series.get('overview', ''),
                    'status': series.get('status', ''),
                    'network': series.get('network', ''),
                    'release_date': air_date.isoformat(),
                    'release_type': release_type,
                    'season_number': season_number,
                    'days_until_release': (air_date - today).days,
                    'episode_title': episode.get('title', ''),
                    'poster_url': poster_url,
                    'fanart_url': fanart_url,
                    'runtime': series.get('runtime', 0),
                    'genres': series.get('genres', []),
                    'has_file': episode.get('hasFile', False),
                    'monitored': series.get('monitored', False)
                }
            
            # Convert to list, filter to only future shows, and sort by release date
            result = [p for p in premieres.values() if p['days_until_release'] >= 0]
            result.sort(key=lambda x: x['release_date'] or '9999-99-99')
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching Sonarr premieres: {e}")
            return []


class TVTrailerFetcher:
    """Fetches trailer URLs from TMDB and IMDB for TV shows"""
    
    def __init__(self, tmdb_api_key: str = None):
        self.api_key = tmdb_api_key or TMDB_API_KEY
        self.base_url = TMDB_BASE_URL
        self.tmdb_available = True  # Track if TMDB is working
    
    async def get_imdb_trailers(self, imdb_id: str) -> List[Dict[str, Any]]:
        """
        Fetch trailer URLs from IMDB for a TV show.
        IMDB often has trailers that aren't on YouTube/TMDB.
        """
        trailers = []
        
        if not imdb_id or not imdb_id.startswith('tt'):
            return trailers
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # IMDB video gallery page
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                }
                
                # Try to fetch the title's video page
                video_url = f"https://www.imdb.com/title/{imdb_id}/videogallery/"
                response = await client.get(video_url, headers=headers, follow_redirects=True)
                
                if response.status_code == 200:
                    html = response.text
                    
                    # Look for video IDs in the page
                    # IMDB video URLs format: /video/vi{VIDEO_ID}/ or data-video="vi{VIDEO_ID}"
                    video_pattern = re.compile(r'vi\d{9,12}')
                    video_ids = list(set(video_pattern.findall(html)))
                    
                    # Also try the main title page for embedded videos
                    if not video_ids:
                        title_url = f"https://www.imdb.com/title/{imdb_id}/"
                        title_response = await client.get(title_url, headers=headers, follow_redirects=True)
                        if title_response.status_code == 200:
                            video_ids = list(set(video_pattern.findall(title_response.text)))
                    
                    # Get the first few trailer video IDs (limit to avoid too many requests)
                    for vid in video_ids[:5]:
                        # IMDB video embed URL
                        embed_url = f"https://www.imdb.com/video/{vid}/"
                        
                        trailers.append({
                            'source': 'imdb',
                            'url': embed_url,
                            'key': vid,
                            'name': 'IMDB Trailer',
                            'official': True,
                            'size': 1080,
                            'type': 'trailer',
                            'imdb_video_id': vid,
                            'embed_url': f"https://www.imdb.com/video/{vid}/imdb/embed"
                        })
                
        except Exception as e:
            logger.error(f"Error fetching IMDB trailers for {imdb_id}: {e}")
        
        return trailers
    
    async def search_tv_by_tvdb(self, tvdb_id: int) -> Optional[int]:
        """Find TMDB ID from TVDB ID"""
        if not self.tmdb_available:
            return None
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}/find/{tvdb_id}",
                    params={
                        'api_key': self.api_key,
                        'external_source': 'tvdb_id'
                    }
                )
                if response.status_code == 401:
                    logger.warning("TMDB API key invalid or expired - will use IMDB fallback")
                    self.tmdb_available = False
                    return None
                response.raise_for_status()
                data = response.json()
                
                tv_results = data.get('tv_results', [])
                if tv_results:
                    return tv_results[0].get('id')
                return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.warning("TMDB API key invalid or expired - will use IMDB fallback")
                self.tmdb_available = False
            else:
                logger.error(f"Error finding TMDB ID for TVDB {tvdb_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error finding TMDB ID for TVDB {tvdb_id}: {e}")
            return None
    
    async def get_tv_trailers(self, tmdb_id: int = None, tvdb_id: int = None, imdb_id: str = None) -> List[Dict[str, Any]]:
        """
        Get trailer URLs for a TV show from TMDB and IMDB.
        Can search by TMDB ID, TVDB ID, or IMDB ID.
        Tries TMDB first, then falls back to IMDB if no trailers found.
        """
        trailers = []
        
        # If TMDB is unavailable, skip straight to IMDB
        if not self.tmdb_available:
            if imdb_id:
                logger.info(f"TMDB unavailable, trying IMDB directly for {imdb_id}...")
                return await self.get_imdb_trailers(imdb_id)
            return trailers
        
        # If we have TVDB ID but not TMDB ID, look it up
        if not tmdb_id and tvdb_id:
            tmdb_id = await self.search_tv_by_tvdb(tvdb_id)
        
        # Try TMDB first
        if tmdb_id and self.tmdb_available:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(
                        f"{self.base_url}/tv/{tmdb_id}/videos",
                        params={'api_key': self.api_key}
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    for video in data.get('results', []):
                        video_type = video.get('type', '').lower()
                        if video_type in ['trailer', 'teaser', 'opening credits']:
                            site = video.get('site', '').lower()
                            key = video.get('key', '')
                            
                            if site == 'youtube' and key:
                                trailers.append({
                                    'source': 'youtube',
                                    'url': f"https://www.youtube.com/watch?v={key}",
                                    'key': key,
                                    'name': video.get('name', 'Trailer'),
                                    'official': video.get('official', False),
                                    'size': video.get('size', 1080),
                                    'type': video_type
                                })
                            elif site == 'vimeo' and key:
                                trailers.append({
                                    'source': 'vimeo',
                                    'url': f"https://vimeo.com/{key}",
                                    'key': key,
                                    'name': video.get('name', 'Trailer'),
                                    'official': video.get('official', False),
                                    'size': video.get('size', 1080),
                                    'type': video_type
                                })
                    
            except Exception as e:
                logger.error(f"Error fetching TV trailers from TMDB for {tmdb_id}: {e}")
        
        # If no TMDB trailers found, try IMDB
        if not trailers and imdb_id:
            logger.info(f"No TMDB trailers found for {imdb_id}, trying IMDB...")
            imdb_trailers = await self.get_imdb_trailers(imdb_id)
            trailers.extend(imdb_trailers)
        
        # Sort: YouTube first, then IMDB, official trailers first, then by size
        trailers.sort(key=lambda x: (
            x['source'] == 'imdb',  # YouTube/Vimeo before IMDB (yt-dlp compatible first)
            x['type'] != 'trailer',  # Trailers before teasers
            not x.get('official', False),
            -x.get('size', 1080)
        ))
        
        return trailers
    
    async def get_season_trailers(self, tmdb_id: int = None, season_number: int = 1, tvdb_id: int = None, imdb_id: str = None) -> List[Dict[str, Any]]:
        """
        Get trailer URLs for a specific season of a TV show.
        Falls back to show-level trailers if no season-specific ones exist.
        Now also supports IMDB fallback.
        """
        trailers = []
        
        # If TMDB is unavailable, skip straight to IMDB
        if not self.tmdb_available:
            if imdb_id:
                logger.info(f"TMDB unavailable, trying IMDB directly for {imdb_id} season {season_number}...")
                imdb_trailers = await self.get_imdb_trailers(imdb_id)
                for t in imdb_trailers:
                    t['season_specific'] = False
                return imdb_trailers
            return trailers
        
        # If we have TVDB ID but not TMDB ID, look it up
        if not tmdb_id and tvdb_id:
            tmdb_id = await self.search_tv_by_tvdb(tvdb_id)
        
        if tmdb_id and self.tmdb_available:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    # Try season-specific videos first
                    response = await client.get(
                        f"{self.base_url}/tv/{tmdb_id}/season/{season_number}/videos",
                        params={'api_key': self.api_key}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        for video in data.get('results', []):
                            video_type = video.get('type', '').lower()
                            if video_type in ['trailer', 'teaser']:
                                site = video.get('site', '').lower()
                                key = video.get('key', '')
                                
                                if site == 'youtube' and key:
                                    trailers.append({
                                        'source': 'youtube',
                                        'url': f"https://www.youtube.com/watch?v={key}",
                                        'key': key,
                                        'name': f"S{season_number}: {video.get('name', 'Trailer')}",
                                        'official': video.get('official', False),
                                        'size': video.get('size', 1080),
                                        'type': video_type,
                                        'season_specific': True
                                    })
                    
                    # If no season-specific trailers, fall back to show trailers from TMDB
                    if not trailers:
                        show_trailers = await self.get_tv_trailers(tmdb_id=tmdb_id, imdb_id=imdb_id)
                        for t in show_trailers:
                            t['season_specific'] = False
                        trailers = show_trailers
                    
            except Exception as e:
                logger.error(f"Error fetching season trailers: {e}")
                # Fall back to show-level trailers
                trailers = await self.get_tv_trailers(tmdb_id=tmdb_id, imdb_id=imdb_id)
                for t in trailers:
                    t['season_specific'] = False
        
        # If still no trailers and we have IMDB ID, try IMDB directly
        if not trailers and imdb_id:
            logger.info(f"No TMDB trailers for season {season_number}, trying IMDB for {imdb_id}...")
            imdb_trailers = await self.get_imdb_trailers(imdb_id)
            for t in imdb_trailers:
                t['season_specific'] = False
            trailers = imdb_trailers
        
        return trailers
