"""
NeX-Up: Radarr Integration Module
Connects to Radarr to fetch upcoming movies and manage trailers
"""

import os
import re
import json
import asyncio
import logging
import subprocess
import platform
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# TMDB API for getting trailer sources
TMDB_API_KEY = "8d6d91941230817f7571f3524e6d49fc"  # Public API key for trailer lookups
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Apple Trailers base URL
APPLE_TRAILERS_BASE = "https://trailers.apple.com"


class AppleTrailerFetcher:
    """Fetches high-quality trailers directly from Apple Trailers (no bot detection)"""
    
    async def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Search for a movie on Apple Trailers"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Apple's trailer search API
                search_url = f"https://trailers.apple.com/trailers/home/scripts/quickfind.php"
                response = await client.get(search_url, params={'q': title})
                
                if response.status_code != 200:
                    return None
                
                # Check if response is JSON
                content_type = response.headers.get('content-type', '')
                if 'json' not in content_type.lower():
                    logger.debug(f"Apple Trailers returned non-JSON: {content_type}")
                    return None
                
                try:
                    data = response.json()
                except Exception:
                    logger.debug("Apple Trailers returned invalid JSON")
                    return None
                    
                results = data.get('results', [])
                
                for result in results:
                    result_title = result.get('title', '').lower()
                    result_year = result.get('releasedate', '')[:4] if result.get('releasedate') else None
                    
                    # Match by title (and optionally year)
                    if title.lower() in result_title or result_title in title.lower():
                        if year is None or result_year == str(year):
                            return result
                
                return results[0] if results else None
                
        except Exception as e:
            logger.debug(f"Apple Trailers search failed: {e}")
            return None
    
    async def get_trailer_url(self, movie_location: str) -> Optional[str]:
        """Get the best quality trailer URL from Apple"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Get movie page data
                page_url = f"https://trailers.apple.com{movie_location}"
                response = await client.get(page_url)
                
                if response.status_code != 200:
                    return None
                
                # Parse for trailer URLs - Apple uses specific patterns
                content = response.text
                
                # Look for high-quality trailer patterns
                patterns = [
                    r'https://movietrailers\.apple\.com/movies/[^"\']+1080p[^"\'\s]+\.mov',
                    r'https://movietrailers\.apple\.com/movies/[^"\']+720p[^"\'\s]+\.mov',
                    r'https://movietrailers\.apple\.com/movies/[^"\']+\.mov',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        return matches[0]
                
                return None
                
        except Exception as e:
            logger.debug(f"Apple Trailers URL fetch failed: {e}")
            return None


class TMDBTrailerFetcher:
    """Fetches trailer URLs from TMDB with multiple source support"""
    
    def __init__(self, tmdb_api_key: str = None):
        self.api_key = tmdb_api_key or TMDB_API_KEY
        self.base_url = TMDB_BASE_URL
        self.apple_fetcher = AppleTrailerFetcher()
        self.tmdb_available = True  # Track if TMDB is working
    
    async def get_trailer_sources(self, tmdb_id: int, title: str = None, year: int = None) -> List[Dict[str, Any]]:
        """
        Get all trailer sources for a movie from TMDB and Apple Trailers.
        Returns list of trailers with source info (YouTube, Vimeo, Apple, etc.)
        Prioritizes sources that don't have bot detection.
        """
        trailers = []
        
        # Try Apple Trailers first (no bot detection!)
        if title:
            try:
                apple_movie = await self.apple_fetcher.search_movie(title, year)
                if apple_movie and apple_movie.get('location'):
                    apple_url = await self.apple_fetcher.get_trailer_url(apple_movie['location'])
                    if apple_url:
                        trailers.append({
                            'source': 'apple',
                            'url': apple_url,
                            'key': apple_url,
                            'name': 'Apple Trailer (Direct)',
                            'official': True,
                            'size': 1080,
                            'priority': 0  # Highest priority
                        })
                        logger.info(f"Found Apple Trailer for {title}")
            except Exception as e:
                logger.debug(f"Apple Trailers lookup failed: {e}")
        
        # Then try TMDB videos (if available)
        if self.tmdb_available:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(
                        f"{self.base_url}/movie/{tmdb_id}/videos",
                        params={'api_key': self.api_key}
                    )
                    if response.status_code == 401:
                        logger.warning("TMDB API key invalid or expired - will use alternative sources")
                        self.tmdb_available = False
                    else:
                        response.raise_for_status()
                        data = response.json()
                        
                        for video in data.get('results', []):
                            if video.get('type', '').lower() in ['trailer', 'teaser']:
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
                                        'priority': 2  # Lower priority due to bot detection
                                    })
                                elif site == 'vimeo' and key:
                                    trailers.append({
                                        'source': 'vimeo',
                                        'url': f"https://vimeo.com/{key}",
                                        'key': key,
                                        'name': video.get('name', 'Trailer'),
                                        'official': video.get('official', False),
                                        'size': video.get('size', 1080),
                                        'priority': 1  # Medium priority
                                    })
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    logger.warning("TMDB API key invalid or expired - will use alternative sources")
                    self.tmdb_available = False
                else:
                    logger.error(f"Error fetching TMDB trailers for {tmdb_id}: {e}")
            except Exception as e:
                logger.error(f"Error fetching TMDB trailers for {tmdb_id}: {e}")
        
        # Sort by: priority (lower is better), then official, then size
        trailers.sort(key=lambda x: (
            x.get('priority', 99),
            not x['official'],
            -x['size']
        ))
        
        return trailers


class RadarrConnector:
    """Handles all Radarr API interactions"""
    
    def __init__(self, url: str, api_key: str, timeout: int = 30):
        self.base_url = url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {
            'X-Api-Key': api_key,
            'Content-Type': 'application/json'
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the Radarr connection and return system status"""
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
                    'appName': data.get('appName', 'Radarr'),
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
    
    async def get_upcoming_movies(self, days_ahead: int = 90) -> List[Dict[str, Any]]:
        """
        Fetch movies from Radarr that are:
        - Announced/In Cinemas (not yet released digitally)
        - Have a release date within the look-ahead window
        - Not yet downloaded/available
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/movie",
                    headers=self.headers
                )
                response.raise_for_status()
                all_movies = response.json()
                
            upcoming = []
            today = datetime.now().date()
            cutoff_date = today + timedelta(days=days_ahead)
            # Allow movies up to 7 days past their release date (recently released, not downloaded yet)
            past_cutoff = today - timedelta(days=7)
            
            for movie in all_movies:
                # Skip if already downloaded/has file
                if movie.get('hasFile', False):
                    continue
                
                # Check status - we want movies that are monitored but not available
                status = movie.get('status', '').lower()
                if status not in ['announced', 'incinemas', 'released']:
                    continue
                
                # Get digital/physical release date
                digital_release = movie.get('digitalRelease')
                physical_release = movie.get('physicalRelease')
                in_cinemas = movie.get('inCinemas')
                
                # Determine the most relevant release date
                release_date = None
                release_type = None
                
                if digital_release:
                    try:
                        release_date = datetime.fromisoformat(digital_release.replace('Z', '+00:00')).date()
                        release_type = 'digital'
                    except:
                        pass
                elif physical_release:
                    try:
                        release_date = datetime.fromisoformat(physical_release.replace('Z', '+00:00')).date()
                        release_type = 'physical'
                    except:
                        pass
                elif in_cinemas:
                    try:
                        release_date = datetime.fromisoformat(in_cinemas.replace('Z', '+00:00')).date()
                        release_type = 'theatrical'
                    except:
                        pass
                
                # Skip if no release date
                if not release_date:
                    continue
                    
                # Skip if too far in the future
                if release_date > cutoff_date:
                    continue
                    
                # Skip if too far in the past (more than 7 days ago)
                if release_date < past_cutoff:
                    continue
                
                # Get trailer info from YouTube
                trailer_url = None
                if movie.get('youTubeTrailerId'):
                    trailer_url = f"https://www.youtube.com/watch?v={movie['youTubeTrailerId']}"
                
                upcoming.append({
                    'radarr_id': movie.get('id'),
                    'tmdb_id': movie.get('tmdbId'),
                    'imdb_id': movie.get('imdbId'),
                    'title': movie.get('title', 'Unknown'),
                    'year': movie.get('year'),
                    'overview': movie.get('overview', ''),
                    'status': status,
                    'release_date': release_date.isoformat() if release_date else None,
                    'release_type': release_type,
                    'days_until_release': (release_date - today).days if release_date else None,
                    'trailer_url': trailer_url,
                    'poster_url': self._get_poster_url(movie),
                    'fanart_url': self._get_fanart_url(movie),
                    'runtime': movie.get('runtime', 0),
                    'genres': movie.get('genres', []),
                    'ratings': movie.get('ratings', {}),
                    'has_file': movie.get('hasFile', False),
                    'monitored': movie.get('monitored', False)
                })
            
            # Sort by release date (soonest first)
            upcoming.sort(key=lambda x: x['release_date'] or '9999-99-99')
            
            return upcoming
            
        except Exception as e:
            logger.error(f"Error fetching upcoming movies from Radarr: {e}")
            return []
    
    async def get_all_movies_raw(self) -> List[Dict[str, Any]]:
        """
        Fetch ALL movies from Radarr in a single API call.
        Returns raw movie data including hasFile status.
        Used for batch checking download status without multiple API calls.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/movie",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching all movies from Radarr: {e}")
            return []
    
    def parse_upcoming_from_raw(self, all_movies: List[Dict[str, Any]], days_ahead: int = 90) -> List[Dict[str, Any]]:
        """
        Parse upcoming movies from raw Radarr movie data.
        This avoids a second API call when we already have all movie data.
        """
        upcoming = []
        today = datetime.now().date()
        cutoff_date = today + timedelta(days=days_ahead)
        past_cutoff = today - timedelta(days=7)
        
        for movie in all_movies:
            # Skip if already downloaded/has file
            if movie.get('hasFile', False):
                continue
            
            # Check status
            status = movie.get('status', '').lower()
            if status not in ['announced', 'incinemas', 'released']:
                continue
            
            # Get release date
            digital_release = movie.get('digitalRelease')
            physical_release = movie.get('physicalRelease')
            in_cinemas = movie.get('inCinemas')
            
            release_date = None
            release_type = None
            
            if digital_release:
                try:
                    release_date = datetime.fromisoformat(digital_release.replace('Z', '+00:00')).date()
                    release_type = 'digital'
                except:
                    pass
            elif physical_release:
                try:
                    release_date = datetime.fromisoformat(physical_release.replace('Z', '+00:00')).date()
                    release_type = 'physical'
                except:
                    pass
            elif in_cinemas:
                try:
                    release_date = datetime.fromisoformat(in_cinemas.replace('Z', '+00:00')).date()
                    release_type = 'theatrical'
                except:
                    pass
            
            if not release_date:
                continue
            if release_date > cutoff_date:
                continue
            if release_date < past_cutoff:
                continue
            
            # Get trailer URL from Radarr - check multiple possible fields
            trailer_url = None
            youtube_trailer_id = movie.get('youTubeTrailerId')
            
            if youtube_trailer_id:
                trailer_url = f"https://www.youtube.com/watch?v={youtube_trailer_id}"
                logger.debug(f"Found YouTube trailer for {movie.get('title')}: {youtube_trailer_id}")
            else:
                # Check if there's trailer info in movie file or other fields
                # Radarr stores this in the root level
                logger.debug(f"No youTubeTrailerId for {movie.get('title')} (TMDB: {movie.get('tmdbId')})")
            
            upcoming.append({
                'radarr_id': movie.get('id'),
                'tmdb_id': movie.get('tmdbId'),
                'imdb_id': movie.get('imdbId'),
                'title': movie.get('title', 'Unknown'),
                'year': movie.get('year'),
                'overview': movie.get('overview', ''),
                'status': status,
                'release_date': release_date.isoformat() if release_date else None,
                'release_type': release_type,
                'days_until_release': (release_date - today).days if release_date else None,
                'trailer_url': trailer_url,
                'youtube_trailer_id': youtube_trailer_id,  # Store the raw ID too
                'poster_url': self._get_poster_url(movie),
                'fanart_url': self._get_fanart_url(movie),
                'runtime': movie.get('runtime', 0),
                'genres': movie.get('genres', []),
                'ratings': movie.get('ratings', {}),
                'has_file': movie.get('hasFile', False),
                'monitored': movie.get('monitored', False)
            })
        
        upcoming.sort(key=lambda x: x['release_date'] or '9999-99-99')
        return upcoming

    async def get_movie_by_id(self, radarr_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a specific movie by Radarr ID"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v3/movie/{radarr_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching movie {radarr_id}: {e}")
            return None
    
    async def check_movie_downloaded(self, radarr_id: int) -> bool:
        """Check if a movie has been downloaded"""
        movie = await self.get_movie_by_id(radarr_id)
        if movie:
            return movie.get('hasFile', False)
        return False
    
    def _get_poster_url(self, movie: Dict) -> Optional[str]:
        """Extract poster URL from movie images"""
        images = movie.get('images', [])
        for img in images:
            if img.get('coverType') == 'poster':
                url = img.get('remoteUrl') or img.get('url')
                if url:
                    return url
        return None
    
    def _get_fanart_url(self, movie: Dict) -> Optional[str]:
        """Extract fanart URL from movie images"""
        images = movie.get('images', [])
        for img in images:
            if img.get('coverType') == 'fanart':
                url = img.get('remoteUrl') or img.get('url')
                if url:
                    return url
        return None


class TrailerDownloader:
    """Handles downloading trailers using yt-dlp with TMDB source discovery and browser cookie support"""
    
    def __init__(self, storage_path: str, quality: str = '1080', use_cookies: bool = True, cookie_browser: str = 'auto', tmdb_api_key: str = None, max_duration: int = 0):
        self.base_storage_path = Path(storage_path)
        self.base_storage_path.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for movies and tv
        self.movies_path = self.base_storage_path / 'movies'
        self.tv_path = self.base_storage_path / 'tv'
        self.movies_path.mkdir(parents=True, exist_ok=True)
        self.tv_path.mkdir(parents=True, exist_ok=True)
        
        # Default storage path (for backward compatibility)
        self.storage_path = self.base_storage_path
        
        self.quality = quality
        self.max_duration = max_duration  # Max trailer duration in seconds (0 = no limit)
        self.use_cookies = use_cookies
        self.cookie_browser = cookie_browser  # 'chrome', 'firefox', 'edge', 'brave', 'auto'
        self.tmdb = TMDBTrailerFetcher(tmdb_api_key=tmdb_api_key)
        
        # Quality format mapping
        self.quality_formats = {
            '720': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            '1080': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            '4k': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',
            'best': 'bestvideo+bestaudio/best'
        }
        
        # Detect available browser for cookies
        self._detected_browser = None
        if self.use_cookies and self.cookie_browser == 'auto':
            self._detected_browser = self._detect_browser()
    
    def _detect_browser(self) -> Optional[str]:
        """Detect which browser is available for cookie extraction"""
        # Order of preference - browsers most likely to have YouTube logged in
        browsers = ['chrome', 'firefox', 'edge', 'brave', 'chromium', 'opera', 'vivaldi']
        
        for browser in browsers:
            # Check if browser profile exists
            if platform.system() == 'Windows':
                browser_paths = {
                    'chrome': Path.home() / 'AppData/Local/Google/Chrome/User Data',
                    'firefox': Path.home() / 'AppData/Roaming/Mozilla/Firefox/Profiles',
                    'edge': Path.home() / 'AppData/Local/Microsoft/Edge/User Data',
                    'brave': Path.home() / 'AppData/Local/BraveSoftware/Brave-Browser/User Data',
                    'chromium': Path.home() / 'AppData/Local/Chromium/User Data',
                    'opera': Path.home() / 'AppData/Roaming/Opera Software/Opera Stable',
                    'vivaldi': Path.home() / 'AppData/Local/Vivaldi/User Data',
                }
            elif platform.system() == 'Darwin':  # macOS
                browser_paths = {
                    'chrome': Path.home() / 'Library/Application Support/Google/Chrome',
                    'firefox': Path.home() / 'Library/Application Support/Firefox/Profiles',
                    'edge': Path.home() / 'Library/Application Support/Microsoft Edge',
                    'brave': Path.home() / 'Library/Application Support/BraveSoftware/Brave-Browser',
                    'safari': Path.home() / 'Library/Safari',
                }
            else:  # Linux
                browser_paths = {
                    'chrome': Path.home() / '.config/google-chrome',
                    'firefox': Path.home() / '.mozilla/firefox',
                    'chromium': Path.home() / '.config/chromium',
                    'brave': Path.home() / '.config/BraveSoftware/Brave-Browser',
                }
            
            if browser in browser_paths and browser_paths[browser].exists():
                logger.info(f"Detected browser for cookies: {browser}")
                return browser
        
        logger.info("No browser detected for cookie extraction")
        return None
    
    def get_cookie_browser(self) -> Optional[str]:
        """Get the browser to use for cookies"""
        if not self.use_cookies:
            return None
        if self.cookie_browser != 'auto':
            return self.cookie_browser
        return self._detected_browser
    
    def get_format_string(self) -> str:
        """Get yt-dlp format string based on quality setting"""
        return self.quality_formats.get(self.quality, self.quality_formats['1080'])
    
    def sanitize_filename(self, title: str) -> str:
        """Create a safe filename from movie title"""
        # Remove invalid characters
        safe = re.sub(r'[<>:"/\\|?*]', '', title)
        # Replace spaces with underscores
        safe = safe.replace(' ', '_')
        # Limit length
        return safe[:100]
    
    async def _download_direct_url(
        self,
        url: str,
        output_path: Path,
        title: str
    ) -> Optional[Dict[str, Any]]:
        """Download a direct video URL (Apple Trailers, etc.) without yt-dlp"""
        try:
            async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
                logger.info(f"Direct downloading: {title} from {url[:50]}...")
                
                # Stream the download for large files
                async with client.stream('GET', url) as response:
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    with open(output_path, 'wb') as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0 and downloaded % (1024 * 1024) == 0:
                                percent = (downloaded / total_size) * 100
                                logger.debug(f"Download progress: {percent:.1f}%")
                
                file_size = output_path.stat().st_size / (1024 * 1024)
                logger.info(f"Direct download complete: {output_path} ({file_size:.1f} MB)")
                
                # Convert MOV to MP4 if needed (for better compatibility)
                if output_path.suffix.lower() == '.mov':
                    mp4_path = output_path.with_suffix('.mp4')
                    try:
                        cmd = [
                            'ffmpeg', '-y', '-i', str(output_path),
                            '-c:v', 'copy', '-c:a', 'aac',
                            str(mp4_path)
                        ]
                        # Run in background with hidden window on Windows
                        creationflags = 0
                        if platform.system() == 'Windows':
                            creationflags = subprocess.CREATE_NO_WINDOW
                        
                        process = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            creationflags=creationflags
                        )
                        await process.wait()
                        
                        if process.returncode == 0 and mp4_path.exists():
                            output_path.unlink()  # Remove original MOV
                            output_path = mp4_path
                            logger.info(f"Converted to MP4: {output_path}")
                        else:
                            logger.warning("FFmpeg conversion failed, keeping original MOV")
                    except Exception as conv_e:
                        logger.warning(f"Could not convert to MP4: {conv_e}")
                
                return {
                    'path': str(output_path),
                    'size_mb': round(file_size, 2),
                    'duration': 0,  # Would need ffprobe to get duration
                    'title': title,
                    'resolution': '1080p'
                }
        except Exception as e:
            logger.error(f"Direct download failed: {e}")
            return None
    
    async def download_trailer(
        self, 
        url: str, 
        title: str, 
        tmdb_id: int = None,
        year: int = None,
        tvdb_id: int = None
    ) -> Optional[Dict[str, Any]]:
        """
        Download a trailer for a movie or TV show.
        PRIORITY ORDER:
        1. Radarr-provided YouTube URL (from youTubeTrailerId) - most reliable!
        2. Apple Trailers (no bot detection)
        3. TMDB YouTube sources
        4. Other sources
        
        For TV shows, tmdb_id may be None - use tvdb_id instead for filename.
        Movies are stored in /movies subdirectory, TV shows in /tv subdirectory.
        """
        try:
            safe_title = self.sanitize_filename(title)
            
            # Determine output path based on media type (movies vs TV)
            if tvdb_id:
                # TV show - use tv subdirectory
                output_dir = self.tv_path
                output_template = str(output_dir / f"{safe_title}_tvdb{tvdb_id}_trailer.%(ext)s")
                logger.info(f"Finding trailer for TV show: {title} (TVDB ID: {tvdb_id}) -> tv/")
            elif tmdb_id:
                # Movie - use movies subdirectory
                output_dir = self.movies_path
                output_template = str(output_dir / f"{safe_title}_{tmdb_id}_trailer.%(ext)s")
                logger.info(f"Finding trailer sources for movie: {title} (TMDB ID: {tmdb_id}) -> movies/")
            else:
                # Unknown type - use base storage path
                output_dir = self.base_storage_path
                output_template = str(output_dir / f"{safe_title}_trailer.%(ext)s")
                logger.info(f"Finding trailer for: {title} -> base path")
            
            # Build trailer sources list with proper priority
            trailer_sources = []
            
            # PRIORITY 1: If we have a Radarr-provided URL, add it FIRST with highest priority
            # This is the same trailer you see when clicking "Trailer" in Radarr's external links
            if url:
                logger.info(f"Using Radarr-provided trailer URL: {url}")
                trailer_sources.append({
                    'source': 'youtube',
                    'url': url,
                    'name': 'Radarr Trailer (Primary)',
                    'priority': -1  # Highest priority (lowest number)
                })
            
            # PRIORITY 2+: Get additional sources from TMDB (Apple Trailers, Vimeo, other YouTube)
            # Only if we have a TMDB ID (movies, not TV shows)
            if tmdb_id:
                tmdb_sources = await self.tmdb.get_trailer_sources(tmdb_id, title=title, year=year)
                
                # Add TMDB sources, but avoid duplicates with the Radarr URL
                for source in tmdb_sources:
                    # Skip if this is the same YouTube video as Radarr provided
                    if url and source.get('url') == url:
                        continue
                    # Also check by video ID
                    if url and source.get('source') == 'youtube':
                        radarr_vid_id = url.split('v=')[-1].split('&')[0] if 'v=' in url else None
                        source_vid_id = source.get('key') or (source.get('url', '').split('v=')[-1].split('&')[0] if 'v=' in source.get('url', '') else None)
                        if radarr_vid_id and source_vid_id and radarr_vid_id == source_vid_id:
                            continue
                    trailer_sources.append(source)
            
            if not trailer_sources:
                logger.warning(f"No trailer sources found for {title}")
                return None
            
            # Sort by priority (lower = better)
            trailer_sources.sort(key=lambda x: x.get('priority', 99))
            
            logger.info(f"Found {len(trailer_sources)} trailer sources for {title}")
            for i, src in enumerate(trailer_sources[:3]):  # Log first 3
                logger.info(f"  Source {i+1}: {src.get('name', src['source'])} ({src['source']})")
            
            # Run yt-dlp with hidden window on Windows
            import sys
            creationflags = 0
            if sys.platform == 'win32':
                creationflags = subprocess.CREATE_NO_WINDOW
            
            last_error = None
            cookie_browser = self.get_cookie_browser()
            
            # Debug: Log cookie file status at download time
            debug_cookies_file = self.base_storage_path / 'youtube_cookies.txt'
            logger.info(f"TrailerDownloader: base_storage_path={self.base_storage_path}")
            logger.info(f"TrailerDownloader: cookies_file={debug_cookies_file} (exists={debug_cookies_file.exists()})")
            
            # Try each trailer source
            for source in trailer_sources:
                source_url = source['url']
                source_name = source.get('name', source['source'])
                source_type = source['source']
                
                logger.info(f"Trying {source_type} source: {source_name}")
                
                # Different strategies based on source
                if source_type == 'apple':
                    # Apple Trailers - direct download without yt-dlp (no bot detection!)
                    output_path = output_dir / f"{safe_title}_{tmdb_id}_trailer.mov"
                    result = await self._download_direct_url(source_url, output_path, title)
                    if result:
                        logger.info(f"Successfully downloaded from Apple Trailers: {title}")
                        return result
                    last_error = f"Apple Trailers download failed for {source_name}"
                
                elif source_type == 'vimeo':
                    # Vimeo usually works without cookies
                    result = await self._download_with_ytdlp(
                        source_url, output_template, title, tmdb_id, 
                        [], creationflags, output_dir
                    )
                    if result:
                        return result
                    last_error = f"Vimeo download failed for {source_name}"
                    
                elif source_type == 'youtube':
                    # Try multiple YouTube strategies in order of effectiveness
                    youtube_strategies = []
                    cookies_file = self.base_storage_path / 'youtube_cookies.txt'
                    oauth_file = self.base_storage_path / 'youtube_oauth.json'
                    
                    # Extract video ID for alternate URL formats
                    video_id = None
                    if 'watch?v=' in source_url:
                        video_id = source_url.split('watch?v=')[1].split('&')[0]
                    elif 'youtu.be/' in source_url:
                        video_id = source_url.split('youtu.be/')[1].split('?')[0]
                    
                    # Strategy 0: Use exported cookies.txt file (most reliable!)
                    if cookies_file.exists():
                        logger.info(f"Using cookies file: {cookies_file}")
                        youtube_strategies.append([
                            '--cookies', str(cookies_file),
                            '--force-ipv4', '--geo-bypass'
                        ])
                    else:
                        logger.info(f"Cookie file not found at: {cookies_file} (base_storage_path={self.base_storage_path})")
                    
                    # Strategy 1: OAuth token file (very reliable, no expiry issues)
                    if oauth_file.exists():
                        logger.info(f"Using OAuth file: {oauth_file}")
                        youtube_strategies.append([
                            '--username', 'oauth',
                            '--password', str(oauth_file),
                            '--force-ipv4', '--geo-bypass'
                        ])
                    
                    # Strategy 2: Try browser cookies with different browsers
                    if cookie_browser:
                        youtube_strategies.append([
                            '--cookies-from-browser', f'{cookie_browser}:+keyring',
                            '--force-ipv4', '--geo-bypass'
                        ])
                        youtube_strategies.append([
                            '--cookies-from-browser', cookie_browser,
                            '--force-ipv4', '--geo-bypass'
                        ])
                    
                    # Try all detected browsers
                    for browser in ['chrome', 'edge', 'firefox', 'brave', 'chromium', 'opera', 'vivaldi']:
                        if browser != cookie_browser:
                            youtube_strategies.append([
                                '--cookies-from-browser', browser,
                                '--force-ipv4', '--geo-bypass'
                            ])
                    
                    # Strategy 3: Embedded player URL (often bypasses restrictions)
                    if video_id:
                        embed_url = f"https://www.youtube.com/embed/{video_id}"
                        youtube_strategies.append([
                            '--force-ipv4', '--geo-bypass',
                            '--referer', 'https://www.google.com/',
                            # Will use embed_url instead of source_url
                            '__USE_EMBED_URL__', embed_url
                        ])
                    
                    # Strategy 4: Player client variants (bypass bot detection)
                    player_clients = [
                        'tv_embedded',      # Smart TV embedded player - often works
                        'mediaconnect',     # Chromecast-like - newer, good success
                        'tv',               # Smart TV app
                        'web_embedded',     # Web embedded player
                        'web_creator',      # YouTube Studio player
                        'web_music',        # YouTube Music player
                        'mweb',             # Mobile web
                        'android',          # Android app
                        'android_music',    # YouTube Music Android
                        'android_creator',  # YouTube Studio Android
                        'ios',              # iOS app
                        'ios_music',        # YouTube Music iOS
                    ]
                    
                    for client in player_clients:
                        youtube_strategies.append([
                            '--extractor-args', f'youtube:player_client={client}',
                            '--force-ipv4', '--geo-bypass'
                        ])
                    
                    # Strategy 5: Combine player client with user agent spoofing
                    user_agents = [
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                        'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36',
                        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
                        'com.google.android.youtube/19.04.38 (Linux; U; Android 13)',  # YouTube Android app
                    ]
                    
                    for ua in user_agents[:2]:  # Just try a couple
                        youtube_strategies.append([
                            '--extractor-args', 'youtube:player_client=web',
                            '--user-agent', ua,
                            '--force-ipv4', '--geo-bypass'
                        ])
                    
                    # Strategy 6: Age gate bypass methods
                    youtube_strategies.extend([
                        ['--extractor-args', 'youtube:player_client=tv_embedded,web', '--force-ipv4', '--geo-bypass'],
                        ['--extractor-args', 'youtube:player_skip=webpage', '--force-ipv4', '--geo-bypass'],
                    ])
                    
                    # Strategy 7: Last resort - minimal options with delay
                    youtube_strategies.append([
                        '--force-ipv4', '--geo-bypass',
                        '--sleep-requests', '2',
                        '--min-sleep-interval', '3',
                    ])
                    
                    # Track if cookies were tried and failed with bot detection
                    cookies_tried_but_failed = False
                    
                    for i, strategy_args in enumerate(youtube_strategies):
                        # Check for embed URL override
                        actual_url = source_url
                        actual_args = [a for a in strategy_args if not a.startswith('__USE_')]
                        for j, arg in enumerate(strategy_args):
                            if arg == '__USE_EMBED_URL__' and j + 1 < len(strategy_args):
                                actual_url = strategy_args[j + 1]
                                actual_args = [a for a in strategy_args[:j]]
                                break
                        
                        strategy_desc = actual_args[:2] if actual_args else ['default']
                        logger.info(f"Trying YouTube strategy {i+1}/{len(youtube_strategies)}: {strategy_desc}")
                        
                        result = await self._download_with_ytdlp(
                            actual_url, output_template, title, tmdb_id,
                            actual_args, creationflags, output_dir
                        )
                        if result:
                            if isinstance(result, dict) and result.get('path'):
                                logger.info(f"Strategy {i+1} succeeded!")
                                return result
                            elif isinstance(result, dict) and result.get('error'):
                                # Strategy failed with specific error
                                if i == 0 and '--cookies' in str(actual_args):
                                    # First strategy was cookies and it failed
                                    if 'bot' in result.get('error', '').lower() or 'sign in' in result.get('error', '').lower():
                                        cookies_tried_but_failed = True
                                        logger.warning(f"Cookie file exists but authentication failed - cookies may be stale or expired")
                        else:
                            # None result - check if this was the cookies strategy
                            if i == 0 and '--cookies' in str(actual_args):
                                cookies_tried_but_failed = True
                        
                        # Small delay between strategies to avoid rate limiting
                        if i < len(youtube_strategies) - 1:
                            await asyncio.sleep(0.5)
                    
                    # Provide more helpful error message based on what failed
                    if cookies_tried_but_failed:
                        last_error = f"YOUTUBE_BOT_BLOCK: YouTube bot detection triggered. Cookies exist but may be invalid/expired, or your IP is rate-limited. To fix: 1) Open Incognito/Private browser, 2) Login to YouTube, 3) Go to youtube.com/robots.txt, 4) Export cookies using a browser extension, 5) Save to your NeX-Up storage folder as 'youtube_cookies.txt'. See: github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies"
                        logger.warning(f"YouTube bot detection for {source_name}. Cookies file exists at {cookies_file} but YouTube still requires sign-in - may need proper cookie export or PO Token.")
                    else:
                        last_error = f"All {len(youtube_strategies)} YouTube strategies failed for {source_name}. Try: Export cookies to {cookies_file} from an Incognito window. See: github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies"
                    logger.warning(last_error)
            
            logger.error(f"All trailer sources failed for {title}. Last error: {last_error}")
            # Return error info so UI can show helpful message
            if last_error and ('YOUTUBE_BOT_BLOCK' in last_error or 'STALE_COOKIES' in last_error):
                return {'error': 'YOUTUBE_BOT_BLOCK', 'message': last_error}
            return None
            
        except Exception as e:
            logger.error(f"Error downloading trailer for {title}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    async def _download_with_ytdlp(
        self,
        url: str,
        output_template: str,
        title: str,
        tmdb_id: int,
        extra_args: List[str],
        creationflags: int,
        output_dir: Path = None
    ) -> Optional[Dict[str, Any]]:
        """Execute yt-dlp using the Python module directly (works in bundled builds)"""
        safe_title = self.sanitize_filename(title)
        
        # Use provided output_dir or fall back to base storage path
        search_dir = output_dir if output_dir else self.base_storage_path
        
        # Use yt_dlp Python module directly instead of CLI
        # This works in PyInstaller bundled builds where CLI may not be in PATH
        try:
            import yt_dlp
        except ImportError:
            logger.error("yt_dlp Python module not available!")
            return None
        
        # Build yt-dlp options dict
        ydl_opts = {
            'format': self.get_format_string(),
            'merge_output_format': 'mp4',
            'outtmpl': output_template,
            'noplaylist': True,
            'no_check_certificate': True,  # --no-check-certificates
            'socket_timeout': 60,
            'retries': 3,
            'quiet': True,  # --no-warnings equivalent
            'no_warnings': True,
            'sleep_interval': 1,  # Small delay to avoid rate limiting
            'max_sleep_interval': 3,
            'noprogress': True,  # Suppress progress output
        }
        
        # Add duration filter if max_duration is set
        if self.max_duration and self.max_duration > 0:
            ydl_opts['match_filter'] = yt_dlp.utils.match_filter_func(f'duration<={self.max_duration}')
            logger.info(f"Filtering trailers with max duration: {self.max_duration}s")
        
        # Parse extra_args and add to options
        # Handle common extra args like cookies
        i = 0
        while i < len(extra_args):
            arg = extra_args[i]
            if arg == '--cookies' and i + 1 < len(extra_args):
                ydl_opts['cookiefile'] = extra_args[i + 1]
                i += 2
            elif arg == '--cookies-from-browser' and i + 1 < len(extra_args):
                ydl_opts['cookiesfrombrowser'] = (extra_args[i + 1],)
                i += 2
            elif arg == '--username' and i + 1 < len(extra_args):
                ydl_opts['username'] = extra_args[i + 1]
                i += 2
            elif arg == '--extractor-args' and i + 1 < len(extra_args):
                ydl_opts['extractor_args'] = {'youtube': [extra_args[i + 1].replace('youtube:', '')]}
                i += 2
            else:
                i += 1
        
        logger.info(f"Running yt-dlp (Python module) for: {title} from {url[:60]}...")
        
        # Run in thread to avoid blocking async event loop
        def _run_ytdlp():
            info = None
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return {'success': True, 'info': info}
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                if 'Sign in to confirm' in error_msg or 'bot' in error_msg.lower():
                    logger.warning(f"YouTube bot detection: {error_msg[:300]}")
                    return {'success': False, 'error': 'bot_detection', 'message': error_msg[:300]}
                else:
                    logger.warning(f"yt-dlp download error: {error_msg[:300]}")
                    return {'success': False, 'error': 'download_error', 'message': error_msg[:300]}
            except Exception as e:
                logger.warning(f"yt-dlp exception: {e}")
                return {'success': False, 'error': 'exception', 'message': str(e)}
        
        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, _run_ytdlp),
                timeout=300
            )
            
            # Handle the structured result from _run_ytdlp
            if result and result.get('success'):
                info = result.get('info', {})
                # Get the filename from the info dict
                filepath = info.get('requested_downloads', [{}])[0].get('filepath') if info.get('requested_downloads') else None
                if not filepath:
                    filepath = info.get('_filename') or info.get('filename')
                
                # Find the file if we don't have filepath
                if not filepath or not os.path.exists(filepath):
                    # Try different filename patterns
                    for ext in ['mp4', 'mkv', 'webm']:
                        # Try with tmdb_id pattern (movies)
                        if tmdb_id:
                            potential_path = search_dir / f"{safe_title}_{tmdb_id}_trailer.{ext}"
                            if potential_path.exists():
                                filepath = str(potential_path)
                                break
                        # Try without ID pattern
                        potential_path = search_dir / f"{safe_title}_trailer.{ext}"
                        if potential_path.exists():
                            filepath = str(potential_path)
                            break
                
                if filepath and os.path.exists(filepath):
                    file_size = os.path.getsize(filepath) / (1024 * 1024)
                    duration = info.get('duration', 0)
                    resolution = info.get('height', 'Unknown')
                    logger.info(f"Downloaded trailer: {filepath} ({file_size:.1f} MB)")
                    return {
                        'path': filepath,
                        'size_mb': round(file_size, 2),
                        'duration': duration,
                        'title': info.get('title', title),
                        'resolution': f"{resolution}p" if resolution != 'Unknown' else 'Unknown'
                    }
                else:
                    logger.warning(f"Download reported success but file not found for {title}")
                    return None
            elif result and not result.get('success'):
                # Return the error info so the caller can detect stale cookies
                return {'error': result.get('error'), 'message': result.get('message', '')}
                    
        except asyncio.TimeoutError:
            logger.error(f"yt-dlp timed out after 300 seconds for {title}")
            return {'error': 'timeout', 'message': 'Download timed out after 300 seconds'}
        except Exception as e:
            logger.warning(f"yt-dlp exception: {e}")
            return {'error': 'exception', 'message': str(e)}
        
        return None
    
    def delete_trailer(self, filepath: str) -> bool:
        """Delete a trailer file"""
        try:
            path = Path(filepath)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted trailer: {filepath}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting trailer {filepath}: {e}")
            return False
    
    def get_storage_usage(self) -> Dict[str, Any]:
        """Get current storage usage statistics - checks all subdirectories"""
        total_size = 0
        file_count = 0
        movies_count = 0
        tv_count = 0
        
        try:
            # Check movies subdirectory
            for file in self.movies_path.glob('*_trailer.*'):
                total_size += file.stat().st_size
                file_count += 1
                movies_count += 1
            
            # Check tv subdirectory
            for file in self.tv_path.glob('*_trailer.*'):
                total_size += file.stat().st_size
                file_count += 1
                tv_count += 1
            
            # Also check base path for legacy files
            for file in self.base_storage_path.glob('*_trailer.*'):
                if file.parent == self.base_storage_path:  # Only direct children, not subdirs
                    total_size += file.stat().st_size
                    file_count += 1
                    
        except Exception as e:
            logger.error(f"Error calculating storage usage: {e}")
        
        return {
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'total_size_gb': round(total_size / (1024 * 1024 * 1024), 3),
            'file_count': file_count,
            'movies_count': movies_count,
            'tv_count': tv_count,
            'storage_path': str(self.base_storage_path)
        }
    
    def cleanup_orphaned_files(self, valid_paths: List[str]) -> int:
        """Remove trailer files not in the valid list - checks all subdirectories"""
        removed_count = 0
        try:
            # Check all locations: movies, tv, and base path
            for search_path in [self.movies_path, self.tv_path, self.base_storage_path]:
                for file in search_path.glob('*_trailer.*'):
                    if file.parent == search_path:  # Only direct children
                        if str(file) not in valid_paths:
                            file.unlink()
                            removed_count += 1
                            logger.info(f"Removed orphaned trailer: {file}")
        except Exception as e:
            logger.error(f"Error during orphan cleanup: {e}")
        return removed_count


class NexUpManager:
    """
    Main manager for NeX-Up feature
    Coordinates between Radarr, trailer downloads, and the database
    """
    
    def __init__(
        self,
        radarr_url: str,
        radarr_api_key: str,
        storage_path: str,
        quality: str = '1080',
        days_ahead: int = 90,
        max_trailers: int = 10,
        max_storage_gb: float = 5.0
    ):
        self.radarr = RadarrConnector(radarr_url, radarr_api_key)
        self.downloader = TrailerDownloader(storage_path, quality)
        self.days_ahead = days_ahead
        self.max_trailers = max_trailers
        self.max_storage_gb = max_storage_gb
        self.storage_path = storage_path
    
    async def sync_upcoming_movies(self, db_session) -> Dict[str, Any]:
        """
        Full sync: fetch from Radarr, download new trailers, cleanup expired
        Returns summary of actions taken
        """
        from . import models  # Import here to avoid circular imports
        
        results = {
            'fetched': 0,
            'downloaded': 0,
            'expired': 0,
            'errors': [],
            'movies': []
        }
        
        try:
            # Fetch upcoming movies from Radarr
            upcoming = await self.radarr.get_upcoming_movies(self.days_ahead)
            results['fetched'] = len(upcoming)
            
            # Get existing trailers from database
            existing = db_session.query(models.ComingSoonTrailer).all()
            existing_radarr_ids = {t.radarr_movie_id for t in existing}
            
            # Check for movies that have been downloaded (cleanup)
            for trailer in existing:
                is_downloaded = await self.radarr.check_movie_downloaded(trailer.radarr_movie_id)
                if is_downloaded:
                    # Movie has been added to library - remove trailer
                    self.downloader.delete_trailer(trailer.local_path)
                    db_session.delete(trailer)
                    results['expired'] += 1
                    logger.info(f"Expired trailer for downloaded movie: {trailer.title}")
            
            # Download trailers for new movies (up to limit)
            current_count = db_session.query(models.ComingSoonTrailer).count()
            storage = self.downloader.get_storage_usage()
            
            for movie in upcoming:
                # Check limits
                if current_count >= self.max_trailers:
                    break
                if storage['total_size_gb'] >= self.max_storage_gb:
                    break
                
                # Skip if already have this movie
                if movie['radarr_id'] in existing_radarr_ids:
                    continue
                
                # Skip if no trailer URL
                if not movie['trailer_url']:
                    continue
                
                # Download trailer
                download_result = await self.downloader.download_trailer(
                    movie['trailer_url'],
                    movie['title'],
                    movie['tmdb_id']
                )
                
                if download_result:
                    # Create database entry
                    trailer = models.ComingSoonTrailer(
                        radarr_movie_id=movie['radarr_id'],
                        tmdb_id=movie['tmdb_id'],
                        imdb_id=movie.get('imdb_id'),
                        title=movie['title'],
                        year=movie.get('year'),
                        overview=movie.get('overview', ''),
                        release_date=datetime.fromisoformat(movie['release_date']).date() if movie['release_date'] else None,
                        release_type=movie.get('release_type'),
                        trailer_url=movie['trailer_url'],
                        local_path=download_result['path'],
                        file_size_mb=download_result['size_mb'],
                        duration_seconds=download_result.get('duration', 0),
                        resolution=download_result.get('resolution', ''),
                        poster_url=movie.get('poster_url'),
                        fanart_url=movie.get('fanart_url'),
                        downloaded_at=datetime.utcnow(),
                        status='downloaded',
                        is_enabled=True,
                        play_count=0
                    )
                    db_session.add(trailer)
                    current_count += 1
                    results['downloaded'] += 1
                    results['movies'].append(movie['title'])
                    
                    # Update storage tracking
                    storage = self.downloader.get_storage_usage()
                else:
                    results['errors'].append(f"Failed to download: {movie['title']}")
            
            db_session.commit()
            
        except Exception as e:
            logger.error(f"Error during NeX-Up sync: {e}")
            results['errors'].append(str(e))
            db_session.rollback()
        
        return results
    
    async def get_enabled_trailers(self, db_session, count: int = 3) -> List[Dict]:
        """Get trailers to include in preroll rotation"""
        from . import models
        
        trailers = db_session.query(models.ComingSoonTrailer)\
            .filter(models.ComingSoonTrailer.is_enabled == True)\
            .filter(models.ComingSoonTrailer.status == 'downloaded')\
            .order_by(models.ComingSoonTrailer.release_date.asc())\
            .limit(count)\
            .all()
        
        return [
            {
                'id': t.id,
                'title': t.title,
                'year': t.year,
                'path': t.local_path,
                'release_date': t.release_date.isoformat() if t.release_date else None,
                'days_until': (t.release_date - datetime.now().date()).days if t.release_date else None,
                'poster_url': t.poster_url
            }
            for t in trailers
        ]
    
    def increment_play_count(self, db_session, trailer_id: int):
        """Track when a trailer is played"""
        from . import models
        
        trailer = db_session.query(models.ComingSoonTrailer).get(trailer_id)
        if trailer:
            trailer.play_count += 1
            trailer.last_played = datetime.utcnow()
            db_session.commit()
