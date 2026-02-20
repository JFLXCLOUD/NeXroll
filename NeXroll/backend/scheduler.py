import datetime
import json
import random
import threading
import time
from typing import List, Optional
import os
import sys
import requests
import re
import pytz

from sqlalchemy.orm import Session
from sqlalchemy import or_, func
import backend.models as models
from backend.plex_connector import PlexConnector
from backend.jellyfin_connector import JellyfinConnector
from backend.database import SessionLocal

# Logging helpers - direct file writes to avoid circular imports
def _get_log_path():
    """Get the log file path"""
    if sys.platform == "win32":
        log_dir = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "NeXroll", "logs")
    else:
        log_dir = "/var/log/nexroll"
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "app.log")

def _scheduler_log(msg: str, level: str = "INFO"):
    """Log scheduler messages with consistent formatting"""
    try:
        log_path = _get_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] [{level}] SCHEDULER: {msg}\n")
    except Exception as e:
        # Fallback to print if logging fails
        print(f"[SCHEDULER] [{level}] {msg} (log error: {e})")

def _scheduler_verbose(msg: str):
    """Log verbose scheduler messages (only if verbose logging enabled)"""
    try:
        # Check if verbose logging is enabled by querying database
        db = SessionLocal()
        try:
            setting = db.query(models.Setting).first()
            if setting and getattr(setting, 'verbose_logging', False):
                _scheduler_log(msg, level="DEBUG")
        finally:
            db.close()
    except Exception:
        pass

class Scheduler:
    def __init__(self):
        self.running = False
        self.thread = None
        # Recent per-item apply dedupe and override TTL (seconds)
        self._last_applied: dict[str, datetime.datetime] = {}
        self._default_genre_override_ttl_seconds: float = 10.0  # Default if not configured
        # Track last logged state to prevent duplicate log spam
        self._last_logged_state = None
        self._last_logged_time = None
        # Track last verification time to prevent constant Plex API calls
        self._last_verification_time: Optional[datetime.datetime] = None
        self._verification_interval_seconds: float = 300.0  # Check every 5 minutes
        # Configurable scheduler check interval (seconds) - default 60s, can be overridden via SCHEDULER_INTERVAL env var
        self._scheduler_check_interval: float = float(os.environ.get('SCHEDULER_INTERVAL', '60.0'))
        # Track last rotation time for random blocks (schedule_id -> last_rotation_time)
        self._last_rotation_time: dict[int, datetime.datetime] = {}
        self._rotation_interval_seconds: float = 300.0  # 5 minutes for testing (change to 600.0 for 10 min production)
        # Cache for holiday dates (holiday_name_country_year -> date)
        self._holiday_date_cache: dict[str, Optional[datetime.date]] = {}
        # Track blend mode state for verification
        self._blend_mode_active: bool = False
        self._blend_expected_preroll: Optional[str] = None
        # Track last NeX-Up auto-sync time
        self._last_nexup_sync_time: Optional[datetime.datetime] = None

    def start(self):
        """Start the scheduler in a background thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_scheduler)
            self.thread.daemon = True
            self.thread.start()

    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.thread:
            self.thread.join()

    def apply_filler_now(self):
        """
        Immediately apply filler category/sequence/coming-soon to Plex.
        Called when filler settings are saved and enabled.
        Returns True if applied successfully, False otherwise.
        """
        db = SessionLocal()
        try:
            setting = db.query(models.Setting).first()
            if not setting:
                _scheduler_log("Settings not found; cannot apply filler", level="ERROR")
                return False
            
            filler_enabled = getattr(setting, "filler_enabled", False)
            if not filler_enabled:
                _scheduler_log("Filler is not enabled; skipping apply")
                # Clear filler_active if disabled
                setting.filler_active = None
                db.commit()
                return False
            
            filler_type = getattr(setting, "filler_type", "category")
            _scheduler_log(f"Applying filler immediately (type: {filler_type})")
            
            if filler_type == "category":
                filler_category_id = getattr(setting, "filler_category_id", None)
                if filler_category_id:
                    applied_ok = self._apply_category_to_plex(filler_category_id, db, schedule=None)
                    if applied_ok:
                        # Use filler_active to track filler state (not active_category to avoid FK issues)
                        setting.filler_active = f"category:{filler_category_id}"
                        setting.active_category = None  # Clear normal category tracking
                        db.commit()
                        _scheduler_log(f"Filler category {filler_category_id} applied immediately")
                        return True
                    else:
                        _scheduler_log(f"Failed to apply filler category {filler_category_id}", level="ERROR")
                        return False
                else:
                    _scheduler_log("Filler type is category but no category selected", level="WARNING")
                    return False
                    
            elif filler_type == "sequence":
                filler_sequence_id = getattr(setting, "filler_sequence_id", None)
                if filler_sequence_id:
                    applied_ok = self._apply_saved_sequence_to_plex(filler_sequence_id, db)
                    if applied_ok:
                        # Use filler_active to track sequence filler state
                        setting.filler_active = f"sequence:{filler_sequence_id}"
                        setting.active_category = None  # Clear normal category tracking
                        db.commit()
                        _scheduler_log(f"Filler sequence {filler_sequence_id} applied immediately")
                        return True
                    else:
                        _scheduler_log(f"Failed to apply filler sequence {filler_sequence_id}", level="ERROR")
                        return False
                else:
                    _scheduler_log("Filler type is sequence but no sequence selected", level="WARNING")
                    return False
                    
            elif filler_type == "coming_soon":
                filler_layout = getattr(setting, "filler_coming_soon_layout", "grid")
                applied_ok = self._apply_coming_soon_list_to_plex(filler_layout, db)
                if applied_ok:
                    # Use filler_active to track coming soon filler state
                    setting.filler_active = f"coming_soon:{filler_layout}"
                    setting.active_category = None  # Clear normal category tracking
                    db.commit()
                    _scheduler_log(f"Filler Coming Soon List ({filler_layout}) applied immediately")
                    return True
                else:
                    _scheduler_log(f"Failed to apply filler Coming Soon List", level="ERROR")
                    return False
            else:
                _scheduler_log(f"Unknown filler type: {filler_type}", level="ERROR")
                return False
        except Exception as e:
            _scheduler_log(f"Error applying filler immediately: {e}", level="ERROR")
            return False
        finally:
            db.close()

    def _run_scheduler(self):
        """Main scheduler loop - runs based on SCHEDULER_INTERVAL (default 60s)"""
        _scheduler_log(f"Scheduler started (interval: {self._scheduler_check_interval}s)")
        while self.running:
            try:
                # Auto-apply mapped category from currently playing Plex item (genre-based)
                self._apply_genre_mapping_from_playback()
            except Exception as e:
                _scheduler_log(f"Genre-monitor error: {e}", level="ERROR")
            try:
                self._check_and_execute_schedules()
            except Exception as e:
                _scheduler_log(f"Schedule check error: {e}", level="ERROR")
            try:
                # Periodically verify Plex has the correct prerolls set
                self._verify_and_reapply_if_needed()
            except Exception as e:
                _scheduler_log(f"Verification error: {e}", level="ERROR")
            try:
                # Check for NeX-Up auto-sync
                self._check_nexup_auto_sync()
            except Exception as e:
                _scheduler_log(f"NeX-Up auto-sync error: {e}", level="ERROR")
            # Use configurable interval (default 60s, set via SCHEDULER_INTERVAL env var)
            time.sleep(self._scheduler_check_interval)

    def _check_nexup_auto_sync(self):
        """
        Check if NeX-Up auto-sync should run based on auto_refresh_hours setting.
        Automatically syncs Radarr and Sonarr for new trailers on the configured interval.
        """
        import asyncio
        
        db = SessionLocal()
        try:
            setting = db.query(models.Setting).first()
            if not setting:
                return
            
            # Check if NeX-Up is enabled and auto-refresh is configured
            auto_refresh_hours = getattr(setting, 'nexup_auto_refresh_hours', 24)
            if not auto_refresh_hours or auto_refresh_hours <= 0:
                return  # Auto-sync disabled
            
            # Check if we have storage path configured
            storage_path = getattr(setting, 'nexup_storage_path', None)
            if not storage_path:
                return  # Storage not configured
            
            now = datetime.datetime.utcnow()
            
            # Check if enough time has passed since last auto-sync
            if self._last_nexup_sync_time:
                hours_since_sync = (now - self._last_nexup_sync_time).total_seconds() / 3600
                if hours_since_sync < auto_refresh_hours:
                    return  # Not time yet
            else:
                # First run - check last_sync from database
                last_sync = getattr(setting, 'nexup_last_sync', None)
                if last_sync:
                    hours_since_sync = (now - last_sync).total_seconds() / 3600
                    if hours_since_sync < auto_refresh_hours:
                        self._last_nexup_sync_time = last_sync
                        return  # Not time yet
            
            _scheduler_log(f"NeX-Up auto-sync starting (interval: every {auto_refresh_hours}h)")
            
            # Perform Radarr sync if configured
            radarr_url = getattr(setting, 'nexup_radarr_url', None)
            radarr_api_key = getattr(setting, 'nexup_radarr_api_key', None)
            nexup_enabled = getattr(setting, 'nexup_enabled', False)
            
            if nexup_enabled and radarr_url and radarr_api_key:
                try:
                    _scheduler_log("NeX-Up auto-sync: Syncing Radarr movie trailers...")
                    asyncio.run(self._sync_radarr_trailers(db, setting))
                except Exception as e:
                    _scheduler_log(f"NeX-Up auto-sync: Radarr sync error: {e}", level="ERROR")
            
            # Perform Sonarr sync if configured
            sonarr_enabled = getattr(setting, 'nexup_sonarr_enabled', False)
            sonarr_url = getattr(setting, 'nexup_sonarr_url', None)
            sonarr_api_key = getattr(setting, 'nexup_sonarr_api_key', None)
            
            if sonarr_enabled and sonarr_url and sonarr_api_key:
                try:
                    _scheduler_log("NeX-Up auto-sync: Syncing Sonarr TV trailers...")
                    asyncio.run(self._sync_sonarr_trailers(db, setting))
                except Exception as e:
                    _scheduler_log(f"NeX-Up auto-sync: Sonarr sync error: {e}", level="ERROR")
            
            # Auto-regenerate Coming Soon List videos if enabled
            auto_regen = getattr(setting, 'nexup_coming_soon_list_auto_regen', False)
            if auto_regen:
                try:
                    _scheduler_log("NeX-Up auto-sync: Regenerating Coming Soon List videos...")
                    self._regenerate_coming_soon_lists(db, setting)
                except Exception as e:
                    _scheduler_log(f"NeX-Up auto-sync: Coming Soon List regeneration error: {e}", level="ERROR")
            
            # Update last sync time
            self._last_nexup_sync_time = now
            _scheduler_log(f"NeX-Up auto-sync completed. Next sync in {auto_refresh_hours}h")
            
        except Exception as e:
            _scheduler_log(f"NeX-Up auto-sync error: {e}", level="ERROR")
        finally:
            db.close()

    def _regenerate_coming_soon_lists(self, db: Session, setting):
        """Regenerate Coming Soon List videos after sync"""
        from pathlib import Path
        from backend.dynamic_preroll import DynamicPrerollGenerator
        import datetime
        
        storage_path = getattr(setting, 'nexup_storage_path', None)
        if not storage_path:
            return
        
        layout = getattr(setting, 'nexup_coming_soon_list_layout', 'grid')
        source = getattr(setting, 'nexup_coming_soon_list_source', 'both')
        duration = getattr(setting, 'nexup_coming_soon_list_duration', 10) or 10
        max_items = getattr(setting, 'nexup_coming_soon_list_max_items', 8) or 8
        server_name = getattr(setting, 'nexup_dynamic_preroll_server_name', None) or \
                      getattr(setting, 'plex_server_name', None) or "Your Server"
        
        # Get items from downloaded trailers
        items = []
        now = datetime.datetime.now()
        
        if source in ["movies", "both"]:
            movie_trailers = db.query(models.ComingSoonTrailer).filter(
                models.ComingSoonTrailer.status == 'downloaded',
                models.ComingSoonTrailer.is_enabled == True,
                models.ComingSoonTrailer.release_date >= now
            ).order_by(models.ComingSoonTrailer.release_date.asc()).all()
            
            for t in movie_trailers:
                items.append({
                    'title': t.title,
                    'release_date': t.release_date.isoformat() if t.release_date else '',
                    'poster_url': t.poster_url,
                    'type': 'movie'
                })
        
        if source in ["shows", "both"]:
            tv_trailers = db.query(models.ComingSoonTVTrailer).filter(
                models.ComingSoonTVTrailer.status == 'downloaded',
                models.ComingSoonTVTrailer.is_enabled == True,
                models.ComingSoonTVTrailer.release_date >= now
            ).order_by(models.ComingSoonTVTrailer.release_date.asc()).all()
            
            for t in tv_trailers:
                title = t.title
                if t.season_number and t.season_number > 1:
                    title = f"{title} (S{t.season_number})"
                items.append({
                    'title': title,
                    'release_date': t.release_date.isoformat() if t.release_date else '',
                    'poster_url': t.poster_url,
                    'type': 'show'
                })
        
        if not items:
            _scheduler_log("NeX-Up auto-regen: No downloaded trailers found, skipping Coming Soon List generation")
            return
        
        items.sort(key=lambda x: x.get('release_date') or '9999-12-31')
        
        output_dir = Path(storage_path) / "dynamic_prerolls"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        generator = DynamicPrerollGenerator(str(output_dir))
        if not generator.check_ffmpeg_available():
            _scheduler_log("NeX-Up auto-regen: FFmpeg not found, skipping Coming Soon List generation", level="ERROR")
            return
        
        layouts_to_generate = ['grid', 'list'] if layout == 'both' else [layout]
        
        for l in layouts_to_generate:
            try:
                output_filename = f"coming_soon_{l}.mp4"
                output_path = generator.generate_coming_soon_list(
                    items=items,
                    server_name=server_name,
                    duration=float(duration),
                    output_filename=output_filename,
                    layout=l,
                    bg_color="0x141428",
                    text_color="0xffffff",
                    accent_color="0x00d4ff",
                    max_items=max_items
                )
                if output_path:
                    _scheduler_log(f"NeX-Up auto-regen: Generated {output_filename}")
                    # Register to category
                    self._register_coming_soon_list_to_category(db, Path(output_path), l)
            except Exception as e:
                _scheduler_log(f"NeX-Up auto-regen: Error generating {l} layout: {e}", level="ERROR")

    def _register_coming_soon_list_to_category(self, db: Session, output_path, layout: str):
        """Register a Coming Soon List video to the Coming Soon Lists system category"""
        try:
            category = db.query(models.Category).filter(
                models.Category.name == "Coming Soon Lists"
            ).first()
            
            if not category:
                category = models.Category(
                    name="Coming Soon Lists",
                    description="Generated Coming Soon list videos showing upcoming releases. Managed by NeX-Up.",
                    plex_mode="shuffle",
                    apply_to_plex=False,
                    is_system=True
                )
                db.add(category)
                db.commit()
                db.refresh(category)
                _scheduler_log("Created Coming Soon Lists system category")
            
            existing = db.query(models.Preroll).filter(
                models.Preroll.path == str(output_path)
            ).first()
            
            if existing:
                existing.category_id = category.id
                db.commit()
            else:
                display_name = f"Coming Soon List ({layout.title()})"
                new_preroll = models.Preroll(
                    filename=output_path.name,
                    path=str(output_path),
                    display_name=display_name,
                    category_id=category.id,
                    thumbnail="",
                    tags="[]",
                    managed=False
                )
                db.add(new_preroll)
                db.commit()
                _scheduler_log(f"Registered Coming Soon List to category: {output_path.name}")
        except Exception as e:
            _scheduler_log(f"Error registering Coming Soon List to category: {e}", level="ERROR")

    async def _sync_radarr_trailers(self, db: Session, setting):
        """Sync trailers from Radarr (called by auto-sync)"""
        import os
        from pathlib import Path
        from backend.radarr_connector import RadarrConnector, TrailerDownloader
        
        connector = RadarrConnector(setting.nexup_radarr_url, setting.nexup_radarr_api_key)
        storage_path = setting.nexup_storage_path
        quality = getattr(setting, 'nexup_quality', '1080') or '1080'
        max_duration = getattr(setting, 'nexup_max_trailer_duration', 180) or 0
        
        # Debug: Log storage path and cookie file status
        cookies_file = Path(storage_path) / 'youtube_cookies.txt' if storage_path else None
        _scheduler_log(f"NeX-Up sync: storage_path={storage_path}")
        _scheduler_log(f"NeX-Up sync: cookies_file={cookies_file} (exists={cookies_file.exists() if cookies_file else False})")
        
        downloader = TrailerDownloader(storage_path, quality, max_duration=max_duration)
        
        days_ahead = getattr(setting, 'nexup_days_ahead', 90) or 90
        max_trailers = getattr(setting, 'nexup_max_trailers', 10) or 10
        download_delay = getattr(setting, 'nexup_download_delay', 5) or 5
        
        # Get upcoming movies
        all_movies = await connector.get_all_movies_raw()
        upcoming = connector.parse_upcoming_from_raw(all_movies, days_ahead)
        
        # Get existing trailer IDs
        existing_ids = {t.radarr_movie_id for t in db.query(models.ComingSoonTrailer).all()}
        
        # Clean up expired/downloaded movies
        downloaded_movies = {m['id'] for m in all_movies if m.get('hasFile', False)}
        for trailer in db.query(models.ComingSoonTrailer).all():
            if trailer.radarr_movie_id in downloaded_movies:
                if trailer.local_path and os.path.exists(trailer.local_path):
                    try:
                        os.remove(trailer.local_path)
                    except:
                        pass
                db.delete(trailer)
                _scheduler_log(f"NeX-Up: Expired trailer for downloaded movie '{trailer.title}'")
        db.commit()
        
        # Download new trailers
        current_count = db.query(models.ComingSoonTrailer).count()
        downloaded = 0
        
        for movie in upcoming:
            if current_count >= max_trailers:
                break
            if movie['radarr_id'] in existing_ids:
                continue
            if not movie.get('trailer_url'):
                continue
            
            import time
            if downloaded > 0:
                time.sleep(download_delay)
            
            result = await downloader.download_trailer(
                url=movie.get('trailer_url', ''),
                title=movie['title'],
                tmdb_id=movie.get('tmdb_id'),
                year=movie.get('year')
            )
            
            if result and result.get('path'):
                # Create trailer record
                new_trailer = models.ComingSoonTrailer(
                    radarr_movie_id=movie['radarr_id'],
                    tmdb_id=movie.get('tmdb_id'),
                    title=movie['title'],
                    year=movie.get('year'),
                    release_date=datetime.datetime.strptime(movie['release_date'], '%Y-%m-%d').date() if movie.get('release_date') else None,
                    trailer_url=movie.get('trailer_url', ''),
                    local_path=result['path'],
                    downloaded_at=datetime.datetime.utcnow(),
                    file_size_mb=result.get('size_mb'),
                    duration_seconds=result.get('duration'),
                    is_enabled=True
                )
                db.add(new_trailer)
                db.commit()
                
                # Create preroll
                self._create_preroll_for_trailer(db, new_trailer, setting, is_tv=False)
                
                downloaded += 1
                current_count += 1
                _scheduler_log(f"NeX-Up auto-sync: Downloaded trailer for '{movie['title']}'")
        
        # Update last sync time
        setting.nexup_last_sync = datetime.datetime.utcnow()
        db.commit()
        
        _scheduler_log(f"NeX-Up Radarr auto-sync: Downloaded {downloaded} new movie trailers")

    async def _sync_sonarr_trailers(self, db: Session, setting):
        """Sync trailers from Sonarr (called by auto-sync)"""
        import os
        from pathlib import Path
        from backend.sonarr_connector import SonarrConnector
        from backend.radarr_connector import TrailerDownloader
        
        connector = SonarrConnector(setting.nexup_sonarr_url, setting.nexup_sonarr_api_key)
        storage_path = setting.nexup_storage_path
        quality = getattr(setting, 'nexup_quality', '1080') or '1080'
        max_duration = getattr(setting, 'nexup_max_trailer_duration', 180) or 0
        
        # Debug: Log storage path and cookie file status
        cookies_file = Path(storage_path) / 'youtube_cookies.txt' if storage_path else None
        _scheduler_log(f"NeX-Up Sonarr sync: storage_path={storage_path}")
        _scheduler_log(f"NeX-Up Sonarr sync: cookies_file={cookies_file} (exists={cookies_file.exists() if cookies_file else False})")
        
        downloader = TrailerDownloader(storage_path, quality, max_duration=max_duration)
        
        days_ahead = getattr(setting, 'nexup_days_ahead', 90) or 90
        max_trailers = getattr(setting, 'nexup_max_trailers', 10) or 10
        download_delay = getattr(setting, 'nexup_download_delay', 5) or 5
        
        # ========================================
        # CLEANUP: Expire trailers for aired shows
        # ========================================
        _scheduler_log("NeX-Up Sonarr auto-sync: Checking for expired TV trailers...")
        
        # Get all series from Sonarr to check download status
        all_series = await connector.get_all_series()
        
        # Build a map of series_id -> {season_number: episodeFileCount}
        series_download_status = {}
        for series in all_series:
            series_id = series.get('id')
            series_download_status[series_id] = {
                'title': series.get('title', 'Unknown'),
                'seasons': {}
            }
            for season in series.get('seasons', []):
                season_num = season.get('seasonNumber', 0)
                stats = season.get('statistics', {})
                series_download_status[series_id]['seasons'][season_num] = stats.get('episodeFileCount', 0)
        
        # Get existing trailers and check for expired ones
        existing_trailers = db.query(models.ComingSoonTVTrailer).filter(
            models.ComingSoonTVTrailer.status == 'downloaded'
        ).all()
        
        today = datetime.datetime.now().date()
        grace_period_days = 5  # Keep trailer for 5 days after air date
        expired_count = 0
        
        for trailer in existing_trailers:
            should_expire = False
            expire_reason = ""
            
            # Check 1: Has Sonarr downloaded episodes for this season?
            series_info = series_download_status.get(trailer.sonarr_series_id)
            if series_info:
                season_file_count = series_info['seasons'].get(trailer.season_number, 0)
                if season_file_count > 0:
                    should_expire = True
                    expire_reason = f"Season has {season_file_count} episode(s) downloaded"
            
            # Check 2: Has the release date passed by more than grace period?
            if not should_expire and trailer.release_date:
                release_date = trailer.release_date.date() if hasattr(trailer.release_date, 'date') else trailer.release_date
                days_since_release = (today - release_date).days
                if days_since_release > grace_period_days:
                    should_expire = True
                    expire_reason = f"Aired {days_since_release} days ago"
            
            if should_expire:
                _scheduler_log(f"NeX-Up Sonarr auto-sync: Expiring trailer for '{trailer.title}' S{trailer.season_number} - {expire_reason}")
                
                # Delete trailer file
                if trailer.local_path and os.path.exists(trailer.local_path):
                    try:
                        os.remove(trailer.local_path)
                    except Exception as e:
                        _scheduler_log(f"NeX-Up Sonarr auto-sync: Failed to delete file: {e}", level="ERROR")
                
                # Also remove from prerolls if it exists
                preroll = db.query(models.Preroll).filter(
                    models.Preroll.path == trailer.local_path
                ).first()
                if preroll:
                    db.delete(preroll)
                
                db.delete(trailer)
                expired_count += 1
        
        if expired_count > 0:
            db.commit()
            _scheduler_log(f"NeX-Up Sonarr auto-sync: Expired {expired_count} TV trailers")
        
        # ========================================
        # DOWNLOAD: Get new trailers
        # ========================================
        
        # Get upcoming shows
        upcoming = await connector.get_upcoming_shows(days_ahead=days_ahead)
        
        # Get existing trailer IDs (re-fetch after cleanup)
        existing_ids = {t.sonarr_series_id for t in db.query(models.ComingSoonTVTrailer).all()}
        
        # Download new trailers
        current_count = db.query(models.ComingSoonTVTrailer).count()
        downloaded = 0
        
        for show in upcoming:
            if current_count >= max_trailers:
                break
            if show['sonarr_id'] in existing_ids:
                continue
            if not show.get('trailer_url'):
                continue
            
            import time
            if downloaded > 0:
                time.sleep(download_delay)
            
            result = await downloader.download_trailer(
                url=show.get('trailer_url', ''),
                title=show['title'],
                tvdb_id=show.get('tvdb_id')
            )
            
            if result and result.get('path'):
                # Create TV trailer record
                new_trailer = models.ComingSoonTVTrailer(
                    sonarr_series_id=show['sonarr_id'],
                    tvdb_id=show.get('tvdb_id'),
                    title=show['title'],
                    year=show.get('year'),
                    release_date=datetime.datetime.strptime(show['release_date'], '%Y-%m-%d').date() if show.get('release_date') else None,
                    trailer_url=show.get('trailer_url', ''),
                    local_path=result['path'],
                    downloaded_at=datetime.datetime.utcnow(),
                    file_size_mb=result.get('size_mb'),
                    duration_seconds=result.get('duration'),
                    is_enabled=True
                )
                db.add(new_trailer)
                db.commit()
                
                # Create preroll
                self._create_preroll_for_trailer(db, new_trailer, setting, is_tv=True)
                
                downloaded += 1
                current_count += 1
                _scheduler_log(f"NeX-Up auto-sync: Downloaded trailer for TV show '{show['title']}'")
        
        # Update last sync time
        setting.nexup_last_sonarr_sync = datetime.datetime.utcnow()
        db.commit()
        
        _scheduler_log(f"NeX-Up Sonarr auto-sync: Downloaded {downloaded} new TV trailers")

    def _create_preroll_for_trailer(self, db: Session, trailer, setting, is_tv: bool = False):
        """Create a preroll entry for a downloaded trailer"""
        import os
        
        if is_tv:
            category_id = getattr(setting, 'nexup_tv_category_id', None)
        else:
            category_id = getattr(setting, 'nexup_category_id', None)
        
        if not category_id:
            return
        
        # Check if preroll already exists
        existing = db.query(models.Preroll).filter(
            models.Preroll.path == trailer.local_path
        ).first()
        
        if existing:
            return
        
        # Create preroll
        filename = os.path.basename(trailer.local_path)
        new_preroll = models.Preroll(
            filename=filename,
            display_name=f"[Trailer] {trailer.title}",
            path=trailer.local_path,
            category_id=category_id,
            description=f"Coming soon trailer for {trailer.title}" + (f" ({trailer.year})" if trailer.year else ""),
            duration=trailer.duration_seconds,
            file_size=trailer.file_size_mb * 1024 * 1024 if trailer.file_size_mb else None,
            managed=True
        )
        db.add(new_preroll)
        db.commit()

    def _apply_preroll_to_jellyfin_api(self, category_id: int, db: Session) -> bool:
        """
        Apply prerolls to Jellyfin using the Jellyfin REST API (metadata intro points).
        Works with Docker and remote Jellyfin instances.
        
        This method:
        1. Gets all prerolls for the category
        2. Calculates intro durations from preroll file lengths
        3. Updates matching series/movies with intro timestamps via Jellyfin API
        
        Returns True if successful, False otherwise.
        """
        try:
            setting = db.query(models.Setting).first()
            if not setting or not getattr(setting, "jellyfin_url", None):
                _scheduler_log("Jellyfin not configured (missing URL); cannot apply prerolls", level="WARNING")
                return False
            
            jellyfin_url = setting.jellyfin_url.rstrip("/")
            jellyfin_api_key = getattr(setting, "jellyfin_api_key", None)
            
            if not jellyfin_api_key:
                _scheduler_log("Jellyfin API key not configured; cannot apply prerolls", level="WARNING")
                return False
            
            # Get prerolls for this category
            prerolls = db.query(models.Preroll) \
                .outerjoin(models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id) \
                .filter(or_(models.Preroll.category_id == category_id,
                           models.preroll_categories.c.category_id == category_id)) \
                .distinct().all()
            
            if not prerolls:
                _scheduler_log(f"No prerolls found for category_id={category_id}; cannot apply to Jellyfin", level="WARNING")
                return False
            
            # Calculate total intro duration (sum of all preroll lengths in ticks)
            # Jellyfin uses ticks (100-nanosecond intervals), so 10,000,000 ticks = 1 second
            total_intro_seconds = 0
            for preroll in prerolls:
                try:
                    if os.path.exists(preroll.path):
                        # Try to get video duration using ffprobe or similar
                        # For now, use a reasonable default or file mod time as proxy
                        total_intro_seconds += getattr(preroll, 'duration_seconds', 60)
                except Exception:
                    total_intro_seconds += 60  # Default 60 seconds per preroll
            
            if total_intro_seconds <= 0:
                total_intro_seconds = 60 * len(prerolls)  # 60 seconds per preroll default
            
            # Convert seconds to Jellyfin ticks (10,000,000 ticks per second)
            intro_ticks_end = int(total_intro_seconds * 10_000_000)
            
            _scheduler_log(f"Preparing to apply {len(prerolls)} prerolls to Jellyfin (total {total_intro_seconds}s intro)…")
            
            # Get category name for search/matching
            category = db.query(models.Category).filter(models.Category.id == category_id).first()
            category_name = category.name if category else f"Category_{category_id}"
            
            # Initialize Jellyfin connector
            connector = JellyfinConnector(jellyfin_url, jellyfin_api_key)
            
            # Search for items matching category name (simplified approach)
            # In production, you'd want more sophisticated matching logic
            search_results = connector.search_items_by_name(category_name) or []
            
            applied_count = 0
            for item in search_results:
                try:
                    item_id = item.get("Id")
                    item_name = item.get("Name", "Unknown")
                    
                    if not item_id:
                        continue
                    
                    # Set intro timestamps for this item
                    intro_data = {
                        "IntroStartTicks": 0,
                        "IntroEndTicks": intro_ticks_end
                    }
                    
                    if connector.set_item_intros(item_id, intro_data):
                        applied_count += 1
                        _scheduler_verbose(f"  ✓ Applied intro to: {item_name}")
                    else:
                        _scheduler_log(f"  ✗ Failed to apply intro to: {item_name}", level="ERROR")
                
                except Exception as e:
                    _scheduler_log(f"  ✗ Error applying to item: {e}", level="ERROR")
                    continue
            
            _scheduler_log(f"Successfully applied prerolls to {applied_count}/{len(search_results)} Jellyfin items.")
            return applied_count > 0
        
        except Exception as e:
            _scheduler_log(f"SCHEDULER: Error applying prerolls to Jellyfin: {e}", level="ERROR")
            return False

    def _apply_genre_mapping_from_playback(self):
        """
        Poll Plex /status/sessions. If a currently playing item has mapped genres,
        apply the mapped category and set an override window to prevent schedule overrides.
        Respects genre_auto_apply setting and priority mode.
        """
        db = SessionLocal()
        try:
            setting = db.query(models.Setting).first()
            if not setting or not getattr(setting, "plex_url", None):
                return

            # Check if genre auto-apply is enabled
            genre_auto_apply = getattr(setting, "genre_auto_apply", True)
            if not genre_auto_apply:
                return

            connector = PlexConnector(setting.plex_url, getattr(setting, "plex_token", None))
            headers = connector.headers or ({"X-Plex-Token": getattr(setting, "plex_token", None)} if getattr(setting, "plex_token", None) else {})
            verify = getattr(connector, "_verify", True)

            # Fetch current sessions
            try:
                r = requests.get(f"{str(setting.plex_url).rstrip('/')}/status/sessions", headers=headers, timeout=6, verify=verify)
            except Exception as e:
                _scheduler_log(f"Failed to fetch sessions: {e}")
                return
            if getattr(r, "status_code", 0) != 200:
                _scheduler_log(f"Sessions API returned status {r.status_code}")
                return
            if not r.content:
                _scheduler_log("Sessions API returned empty content")
                return

            import xml.etree.ElementTree as ET
            try:
                root = ET.fromstring(r.content)
            except Exception as e:
                _scheduler_log(f"Failed to parse sessions XML: {e}")
                return

            # Choose the first playing video; otherwise any active with viewOffset/viewCount signal
            chosen_key = None
            for video in root.iter():
                try:
                    tag = str(getattr(video, "tag", "") or "")
                    if tag.endswith("Video") or tag == "Video":
                        vtype = (video.get("type") or "").lower()
                        if vtype not in ("movie", "episode", "clip"):
                            continue
                        # inspect child Player state
                        state = None
                        for child in list(video):
                            try:
                                ctag = str(getattr(child, "tag", "") or "")
                                if ctag.endswith("Player") or ctag == "Player":
                                    state = (child.get("state") or "").lower()
                                    break
                            except Exception:
                                pass
                        rk = video.get("ratingKey") or video.get("ratingkey")
                        if rk and (state == "playing" or video.get("viewOffset") or (video.get("viewCount") is not None)):
                            chosen_key = str(rk).strip()
                            if state == "playing":
                                break
                except Exception:
                    continue

            if not chosen_key:
                return

            # Dedupe per ratingKey within TTL
            now = datetime.datetime.utcnow()
            ttl_seconds = getattr(setting, "genre_override_ttl_seconds", self._default_genre_override_ttl_seconds)
            last = self._last_applied.get(chosen_key)
            if last and (now - last) < datetime.timedelta(seconds=ttl_seconds):
                return

            # Fetch metadata for genres (with parent/grandparent fallback)
            try:
                rm = requests.get(f"{str(setting.plex_url).rstrip('/')}/library/metadata/{chosen_key}", headers=headers, timeout=6, verify=verify)
                if getattr(rm, "status_code", 0) != 200:
                    _scheduler_log(f"Metadata API for {chosen_key} returned status {rm.status_code}")
                    return
                if not rm.content:
                    _scheduler_log(f"Metadata API for {chosen_key} returned empty content")
                    return
                rootm = ET.fromstring(rm.content)
            except Exception as e:
                _scheduler_log(f"Failed to fetch/parse metadata for {chosen_key}: {e}")
                return

            # Collect and normalize Genre tags from the item metadata
            genres: list[str] = []
            for node in rootm.iter():
                try:
                    tagname = str(getattr(node, "tag", "") or "")
                    if tagname.endswith("Genre") or tagname == "Genre":
                        g = node.get("tag")
                        if g and str(g).strip():
                            genres.append(str(g).strip())
                except Exception:
                    continue
            # Dedupe case-insensitive preserving order
            seen = set()
            genres = [g for g in genres if not (g.lower() in seen or seen.add(g.lower()))]
            # If no genres present (episodes often), fetch parent/grandparent metadata and merge their Genre tags
            if not genres:
                try:
                    primary_video = None
                    for _n in rootm.iter():
                        _t = str(getattr(_n, "tag", "") or "")
                        if _t.endswith("Video") or _t == "Video":
                            primary_video = _n
                            break
                    prk = (primary_video.get("parentRatingKey") or "").strip() if primary_video is not None else ""
                    grk = (primary_video.get("grandparentRatingKey") or "").strip() if primary_video is not None else ""
                    for rk2 in [k for k in [prk, grk] if k]:
                        try:
                            r2 = requests.get(f"{str(setting.plex_url).rstrip('/')}/library/metadata/{rk2}", headers=headers, timeout=6, verify=verify)
                            if getattr(r2, "status_code", 0) == 200 and getattr(r2, "content", None):
                                import xml.etree.ElementTree as _ET2
                                root2 = _ET2.fromstring(r2.content)
                                for node2 in root2.iter():
                                    try:
                                        t2 = str(getattr(node2, "tag", "") or "")
                                        if t2.endswith("Genre") or t2 == "Genre":
                                            g2 = node2.get("tag")
                                            if g2 and str(g2).strip():
                                                genres.append(str(g2).strip())
                                    except Exception:
                                        continue
                        except Exception:
                            continue
                    _seen2 = set()
                    genres = [g for g in genres if not (g.lower() in _seen2 or _seen2.add(g.lower()))]
                except Exception:
                    pass

            if not genres:
                return

            # Local normalization + synonyms (mirror backend route behavior)
            def _norm_genre_local(s):
                try:
                    import unicodedata, re
                    t = unicodedata.normalize("NFKC", str(s or ""))
                    t = t.replace("&", " and ")
                    t = re.sub(r"[/_]", " ", t)
                    t = re.sub(r"-+", " ", t)
                    t = " ".join(t.split()).strip().lower()
                    return t
                except Exception:
                    return ""

            def _canonical_local(s):
                g = _norm_genre_local(s)
                if not g:
                    return ""
                synonyms = {
                    "sci fi": "science fiction",
                    "scifi": "science fiction",
                    "sci-fi": "science fiction",
                    "kids and family": "family",
                    "kids family": "family",
                }
                return synonyms.get(g, g)

            import re as _re
            def _candidates(s):
                base = _canonical_local(s)
                out = []
                if base:
                    out.append(base)
                    parts = [p.strip() for p in _re.split(r"(?:\s+and\s+|,|\||/)", base) if p and p.strip()]
                    for p in parts:
                        if p and p not in out:
                            out.append(p)
                # unique preserve order
                seen = set()
                return [x for x in out if not (x in seen or seen.add(x))]

            # Resolve mapping
            matched_cat = None
            matched_genre_display = None
            for raw in genres:
                for key in _candidates(raw):
                    gm = None
                    try:
                        gm = db.query(models.GenreMap).filter(models.GenreMap.genre_norm == key).first()
                    except Exception:
                        gm = None
                    if not gm:
                        try:
                            gm = db.query(models.GenreMap).filter(func.lower(models.GenreMap.genre) == key).first()
                        except Exception:
                            gm = None
                    if gm:
                        cat = db.query(models.Category).filter(models.Category.id == gm.category_id).first()
                        if cat:
                            matched_cat = cat
                            matched_genre_display = raw
                            break
                if matched_cat:
                    break

            if not matched_cat:
                return

            # Check priority mode: if schedules_override and there's an active schedule, don't apply genre
            priority_mode = getattr(setting, "genre_priority_mode", "schedules_override")
            if priority_mode == "schedules_override":
                # Check if any schedule is currently active
                schedules = db.query(models.Schedule).filter(models.Schedule.is_active == True).all()
                # Use local time for comparisons since schedules are stored as naive local datetimes
                now = datetime.datetime.now()
                active_schedules = [s for s in schedules if self._is_schedule_active(s, now)]
                if active_schedules:
                    _scheduler_log(f"Skipping genre mapping for ratingKey={chosen_key} due to active schedule (priority mode: {priority_mode})")
                    return

            # Apply to Plex and set override to protect from scheduler immediately overriding
            ok = self._apply_category_to_plex(matched_cat.id, db)
            if not ok:
                _scheduler_log(f"Failed to apply matched category '{matched_cat.name}' (ID {matched_cat.id}) for genre '{matched_genre_display}'")
                return

            try:
                st = db.query(models.Setting).first()
                if not st:
                    st = models.Setting(plex_url=None, plex_token=None, active_category=matched_cat.id)
                    db.add(st)
                st.active_category = matched_cat.id
                st.override_expires_at = now + datetime.timedelta(seconds=ttl_seconds)
                st.updated_at = now
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass

            self._last_applied[chosen_key] = now

            # Record for UI feedback
            from backend.main import RECENT_GENRE_APPLICATIONS
            application = {
                "timestamp": now.isoformat() + "Z",
                "genre": matched_genre_display,
                "category_name": matched_cat.name,
                "rating_key": chosen_key
            }
            RECENT_GENRE_APPLICATIONS.append(application)
            # Keep only last 10
            if len(RECENT_GENRE_APPLICATIONS) > 10:
                RECENT_GENRE_APPLICATIONS.pop(0)

            _scheduler_log(f"Genre mapping applied for ratingKey={chosen_key}: '{matched_genre_display}' -> category '{matched_cat.name}'")

        finally:
            try:
                db.close()
            except Exception:
                pass

    def _check_and_execute_schedules(self):
        """Evaluate schedules, apply active category to Plex, and handle fallback when idle."""
        db = SessionLocal()
        try:
            # Use local time for comparisons since schedules are stored as naive local datetimes
            now = datetime.datetime.now()
            schedules = db.query(models.Schedule).filter(models.Schedule.is_active == True).all()

            # Determine active schedules (window-aware)
            active = [s for s in schedules if self._is_schedule_active(s, now)]

            # Ensure a settings row exists to track current active category
            setting = db.query(models.Setting).first()
            if not setting:
                setting = models.Setting(plex_url=None, plex_token=None, active_category=None)
                db.add(setting)
                db.commit()
                db.refresh(setting)

            # Check passive mode (coexistence mode) - if enabled and no active schedules, skip all preroll management
            # This allows other preroll managers (like Preroll Plus) to control prerolls outside scheduled times
            passive_mode = getattr(setting, "passive_mode", False)
            if passive_mode and not active:
                state_key = "passive_mode_idle"
                if self._last_logged_state != state_key:
                    _scheduler_log(f"Passive mode enabled - no active schedules, skipping preroll management (allowing other preroll managers to control)")
                    self._last_logged_state = state_key
                    self._last_logged_time = now
                return  # Exit early - don't apply prerolls or fallback

            # Respect temporary override window set by genre-apply (prevents immediate scheduler override)
            try:
                ovr = getattr(setting, "override_expires_at", None)
            except Exception:
                ovr = None
            if ovr is not None:
                try:
                    if now < ovr:
                        # Only log override once per minute to avoid spam
                        state_key = f"override:{ovr.isoformat()}"
                        if self._last_logged_state != state_key or (self._last_logged_time and (now - self._last_logged_time).total_seconds() > 60):
                            _scheduler_log(f"override active until {ovr.isoformat()}Z; skipping schedule apply")
                            self._last_logged_state = state_key
                            self._last_logged_time = now
                        return
                except Exception:
                    # If comparison fails for any reason, ignore override
                    pass

            desired_category_id = None
            chosen_schedule = None
            current_fallback_id = None
            blend_schedules = []  # Schedules to blend together

            if active:
                # STEP 1: Check for EXCLUSIVE schedules first
                # Exclusive schedules override everything - they win exclusively (no blending)
                exclusive_schedules = [s for s in active if getattr(s, "exclusive", False)]
                
                if exclusive_schedules:
                    # Multiple exclusive schedules: highest priority wins, then earliest end, then lowest id
                    def _exclusive_sort_key(s):
                        priority = getattr(s, "priority", 5)
                        end = s.end_date if s.end_date else datetime.datetime.max
                        return (-priority, end, s.id)  # Negative priority so higher values sort first
                    exclusive_schedules.sort(key=_exclusive_sort_key)
                    chosen_schedule = exclusive_schedules[0]
                    desired_category_id = chosen_schedule.category_id
                    priority = getattr(chosen_schedule, "priority", 5)
                    
                    state_key = f"exclusive:{chosen_schedule.id}:{desired_category_id}"
                    if self._last_logged_state != state_key:
                        _scheduler_log(f"EXCLUSIVE: '{chosen_schedule.name}' (Priority {priority}) wins exclusively over {len(active)-1} other schedule(s)")
                        self._last_logged_state = state_key
                        self._last_logged_time = now
                    
                    # Store fallback from winning exclusive schedule
                    current_fallback_id = getattr(chosen_schedule, "fallback_category_id", None)
                    stored_fallback = getattr(setting, "last_schedule_fallback", None)
                    if stored_fallback != current_fallback_id:
                        setting.last_schedule_fallback = current_fallback_id
                        db.commit()
                    
                    # Skip to normal apply logic (below the blend section)
                else:
                    # STEP 2: Check for blend mode (only non-exclusive schedules)
                    blend_schedules = [s for s in active if getattr(s, "blend_enabled", False)]
                    
                    # Log blend mode eligibility check
                    if blend_schedules:
                        blend_names = [f"'{s.name}'" for s in blend_schedules]
                        _scheduler_verbose(f"Blend check: {len(blend_schedules)} schedule(s) with blend enabled: {', '.join(blend_names)}")
                        if len(blend_schedules) == 1:
                            _scheduler_verbose(f"Blend mode requires 2+ overlapping schedules with blend enabled. '{blend_schedules[0].name}' will use normal mode.")
                    
                    if len(blend_schedules) >= 2:
                        # Multiple blendable schedules - use blend mode
                        _scheduler_log(f"BLEND MODE ACTIVATED: {len(blend_schedules)} schedules blending together")
                        for bs in blend_schedules:
                            cat_name = bs.category.name if bs.category else f"Category {bs.category_id}"
                            priority = getattr(bs, "priority", 5)
                            _scheduler_log(f"  -> '{bs.name}' (Category: {cat_name}, Priority: {priority})")
                        
                        # Apply blended schedules
                        applied_ok = self._apply_blended_schedules_to_plex(blend_schedules, db)
                        if applied_ok:
                            # Use the first schedule's category as the "active" one for tracking
                            chosen_schedule = blend_schedules[0]
                            desired_category_id = chosen_schedule.category_id
                            setting.active_category = desired_category_id
                            for sched in blend_schedules:
                                sched.last_run = now
                                sched.next_run = self._calculate_next_run(sched)
                            db.commit()
                            
                            state_key = f"blend_active:{','.join(str(s.id) for s in blend_schedules)}"
                            if self._last_logged_state != state_key:
                                names = ', '.join(f"'{s.name}'" for s in blend_schedules)
                                _scheduler_log(f"BLEND: Blend mode active: {names}")
                                self._last_logged_state = state_key
                                self._last_logged_time = now
                        else:
                            _scheduler_log(f"BLEND: Blend mode failed to apply prerolls to Plex", level="WARNING")
                        return  # Skip normal processing when in blend mode
                    
                    # STEP 3: No exclusive, no blend - use normal winner selection
                    # Priority (highest wins), then earliest end date, then earliest start, then lowest id
                    def _sort_key(s):
                        priority = getattr(s, "priority", 5)
                        end = s.end_date if s.end_date else datetime.datetime.max
                        start = s.start_date or datetime.datetime.min
                        return (-priority, end, start, s.id)  # Negative priority so higher values sort first
                    active.sort(key=_sort_key)
                    chosen_schedule = active[0]
                    desired_category_id = chosen_schedule.category_id
                
                # Store the fallback for the WINNING schedule only
                # This ensures that when a schedule wins, its fallback (or lack thereof) takes precedence
                # even if other overlapping schedules have fallbacks defined
                current_fallback_id = getattr(chosen_schedule, "fallback_category_id", None)
                
                # Only update the stored fallback if it's different from what's currently stored
                # This prevents unnecessary database writes and log spam
                stored_fallback = getattr(setting, "last_schedule_fallback", None)
                if stored_fallback != current_fallback_id:
                    setting.last_schedule_fallback = current_fallback_id
                    db.commit()  # Persist the fallback change immediately
                    if current_fallback_id:
                        _scheduler_verbose(f"Schedule '{chosen_schedule.name}' has fallback category {current_fallback_id} (will be used when no schedules are active)")
                    else:
                        _scheduler_verbose(f"Schedule '{chosen_schedule.name}' has no fallback; cleared previous fallback")
                
                # Sanity check: ensure category_id is set
                if not desired_category_id:
                    state_key = f"error:no_category:{chosen_schedule.id}"
                    if self._last_logged_state != state_key:
                        _scheduler_log(f"Schedule '{chosen_schedule.name}' (ID {chosen_schedule.id}) has no category_id set. Cannot apply prerolls.", level="ERROR")
                        self._last_logged_state = state_key
                        self._last_logged_time = now
                    desired_category_id = None
                else:
                    # Use a consistent state key that works with the "already active" check below
                    state_key = f"schedule_active:{chosen_schedule.id}:{desired_category_id}"
                    if self._last_logged_state != state_key:
                        _scheduler_log(f"Active schedule selected: '{chosen_schedule.name}' (ID {chosen_schedule.id}) -> Category {desired_category_id}")
                        self._last_logged_state = state_key
                        self._last_logged_time = now
            else:
                # No active schedules -> check clear_when_inactive setting first
                clear_when_inactive = getattr(setting, "clear_when_inactive", False)
                if clear_when_inactive:
                    # Clear prerolls when no schedule is active
                    state_key = "clearing_inactive"
                    if self._last_logged_state != state_key:
                        _scheduler_log(f"No active schedules; clearing Plex preroll field (clear_when_inactive enabled)")
                        self._last_logged_state = state_key
                        self._last_logged_time = now
                    # Clear prerolls by setting empty string
                    if setting.active_category is not None or getattr(setting, "filler_active", None) is not None:
                        cleared_ok = self._clear_plex_prerolls(db)
                        if cleared_ok:
                            setting.active_category = None
                            setting.filler_active = None  # Also clear filler state
                            db.commit()
                else:
                    # Use fallback from most recently active schedule
                    stored_fallback = getattr(setting, "last_schedule_fallback", None)
                    if stored_fallback:
                        desired_category_id = stored_fallback
                        state_key = f"fallback:{desired_category_id}"
                        if self._last_logged_state != state_key:
                            _scheduler_log(f"No active schedules; using fallback category {desired_category_id} from last active schedule")
                            self._last_logged_state = state_key
                            self._last_logged_time = now
                    else:
                        # Check for Filler Category setting (global gap filler)
                        filler_enabled = getattr(setting, "filler_enabled", False)
                        filler_type = getattr(setting, "filler_type", "category")
                        
                        if filler_enabled:
                            # Apply filler based on type
                            filler_applied = False
                            
                            if filler_type == "category":
                                filler_category_id = getattr(setting, "filler_category_id", None)
                                if filler_category_id:
                                    desired_category_id = filler_category_id
                                    state_key = f"filler_category:{filler_category_id}"
                                    if self._last_logged_state != state_key:
                                        _scheduler_log(f"No active schedules; using FILLER category {filler_category_id}")
                                        self._last_logged_state = state_key
                                        self._last_logged_time = now
                                    # Set filler_active to track filler state
                                    setting.filler_active = f"category:{filler_category_id}"
                                    filler_applied = True
                                    
                            elif filler_type == "sequence":
                                filler_sequence_id = getattr(setting, "filler_sequence_id", None)
                                if filler_sequence_id:
                                    state_key = f"filler_sequence:{filler_sequence_id}"
                                    if self._last_logged_state != state_key:
                                        _scheduler_log(f"No active schedules; using FILLER sequence {filler_sequence_id}")
                                        self._last_logged_state = state_key
                                        self._last_logged_time = now
                                    # Apply the sequence directly
                                    applied_ok = self._apply_saved_sequence_to_plex(filler_sequence_id, db)
                                    if applied_ok:
                                        # Use filler_active to track filler state
                                        setting.filler_active = f"sequence:{filler_sequence_id}"
                                        setting.active_category = None  # Clear normal category tracking
                                        db.commit()
                                    filler_applied = True
                                    return  # Sequence applied, exit early
                                    
                            elif filler_type == "coming_soon":
                                filler_layout = getattr(setting, "filler_coming_soon_layout", "grid")
                                state_key = f"filler_coming_soon:{filler_layout}"
                                if self._last_logged_state != state_key:
                                    _scheduler_log(f"No active schedules; using FILLER Coming Soon List ({filler_layout})")
                                    self._last_logged_state = state_key
                                    self._last_logged_time = now
                                # Apply the coming soon list video
                                applied_ok = self._apply_coming_soon_list_to_plex(filler_layout, db)
                                if applied_ok:
                                    # Use filler_active to track filler state
                                    setting.filler_active = f"coming_soon:{filler_layout}"
                                    setting.active_category = None  # Clear normal category tracking
                                    db.commit()
                                filler_applied = True
                                return  # Coming soon applied, exit early
                            
                            if not filler_applied:
                                state_key = "filler_not_configured"
                                if self._last_logged_state != state_key:
                                    _scheduler_log(f"Filler enabled but not configured properly; Plex preroll will remain unchanged")
                                    self._last_logged_state = state_key
                                    self._last_logged_time = now
                        else:
                            state_key = "no_schedules"
                            if self._last_logged_state != state_key:
                                _scheduler_log(f"No active schedules and no fallback/filler defined; Plex preroll will remain unchanged")
                                self._last_logged_state = state_key
                                self._last_logged_time = now

            # Apply category change to Plex only if it differs from current
            if desired_category_id and setting.active_category != desired_category_id:
                applied_ok = False
                # If this schedule defines an explicit sequence, honor it; otherwise apply whole category
                if chosen_schedule and getattr(chosen_schedule, "sequence", None):
                    applied_ok = self._apply_schedule_sequence_to_plex(chosen_schedule, db)
                    # Track rotation time for schedules with sequences
                    if applied_ok and chosen_schedule.id:
                        self._last_rotation_time[chosen_schedule.id] = now
                else:
                    applied_ok = self._apply_category_to_plex(desired_category_id, db, schedule=chosen_schedule)
                if applied_ok:
                    setting.active_category = desired_category_id
                    setting.filler_active = None  # Clear filler state when a schedule is active
                    if chosen_schedule:
                        chosen_schedule.last_run = now
                        chosen_schedule.next_run = self._calculate_next_run(chosen_schedule)
                    db.commit()
            elif desired_category_id is None:
                state_key = "no_category_to_apply"
                if self._last_logged_state != state_key:
                    _scheduler_log(f"No category to apply (desired_category_id is None)")
                    self._last_logged_state = state_key
                    self._last_logged_time = now
            elif setting.active_category == desired_category_id:
                # Check if we need to rotate random blocks in a sequence
                should_rotate = False
                if chosen_schedule and getattr(chosen_schedule, "sequence", None):
                    # Check if this schedule has random blocks
                    try:
                        seq = chosen_schedule.sequence
                        if isinstance(seq, str):
                            seq = json.loads(seq)
                        if isinstance(seq, list):
                            has_random = any(block.get("type") == "random" for block in seq)
                            if has_random:
                                # Check if 10 minutes have passed since last rotation
                                last_rotation = self._last_rotation_time.get(chosen_schedule.id)
                                if last_rotation is None or (now - last_rotation).total_seconds() >= self._rotation_interval_seconds:
                                    should_rotate = True
                    except Exception as e:
                        _scheduler_log(f"SCHEDULER: Error checking rotation for schedule {chosen_schedule.id}: {e}", level="ERROR")
                
                if should_rotate:
                    # Re-apply the sequence to rotate random blocks
                    applied_ok = self._apply_schedule_sequence_to_plex(chosen_schedule, db)
                    if applied_ok:
                        self._last_rotation_time[chosen_schedule.id] = now
                        _scheduler_log(f"Rotated random blocks for schedule '{chosen_schedule.name}' (ID {chosen_schedule.id})")
                        db.commit()
                else:
                    # Only log if state changed OR if we haven't logged this schedule in 5 minutes
                    state_key = f"schedule_active:{chosen_schedule.id if chosen_schedule else 'none'}:{desired_category_id}"
                    if self._last_logged_state != state_key:
                        # State changed (different schedule/category) - log immediately
                        _scheduler_log(f"Category {desired_category_id} already active; no change needed")
                        self._last_logged_state = state_key
                        self._last_logged_time = now
                    elif self._last_logged_time and (now - self._last_logged_time).total_seconds() > 300:
                        # Same state but 5 minutes passed - log for status visibility
                        _scheduler_log(f"Category {desired_category_id} still active")
                        self._last_logged_time = now
            # If no desired_category_id, leave Plex as-is to avoid unintended clears

        finally:
            db.close()

    def _verify_and_reapply_if_needed(self):
        """
        Periodically verify that Plex has the correct prerolls set.
        If there's a mismatch, reapply the current active category.
        This ensures scheduled prerolls remain active even if manually changed or API calls fail.
        """
        # Use local time for comparisons since schedules are stored as naive local datetimes
        now = datetime.datetime.now()
        
        # Check if enough time has passed since last verification
        if self._last_verification_time:
            elapsed = (now - self._last_verification_time).total_seconds()
            if elapsed < self._verification_interval_seconds:
                return  # Too soon to check again
        
        # Get database session
        db = SessionLocal()
        try:
            # Get current settings
            setting = db.query(models.Setting).first()
            if not setting:
                return
            
            # Skip verification in passive mode when no active schedules
            # (Let other preroll managers control prerolls outside scheduled times)
            passive_mode = getattr(setting, "passive_mode", False)
            if passive_mode:
                schedules = db.query(models.Schedule).filter(models.Schedule.is_active == True).all()
                active_schedules = [s for s in schedules if self._is_schedule_active(s, now)]
                if not active_schedules:
                    self._last_verification_time = now
                    return  # Passive mode, no active schedules - skip verification
            
            # Only verify if we have an active category
            if not setting.active_category:
                return
            
            # Skip verification when blend mode is active - blend has its own validation
            if self._blend_mode_active:
                self._last_verification_time = now
                return
            
            # Check if there's an active schedule with a sequence
            # If so, skip verification as sequences have their own rotation logic
            schedules = db.query(models.Schedule).filter(models.Schedule.is_active == True).all()
            active_schedules = [s for s in schedules if self._is_schedule_active(s, now)]
            if active_schedules:
                # Check if any active schedule has a sequence
                for sched in active_schedules:
                    if sched.category_id == setting.active_category and getattr(sched, "sequence", None):
                        # Active schedule with sequence - skip verification
                        self._last_verification_time = now
                        return
            
            # Get the expected prerolls for the active category (including many-to-many)
            # Must match the logic in _apply_category_to_plex
            prerolls = (
                db.query(models.Preroll)
                .outerjoin(models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id)
                .filter(or_(models.Preroll.category_id == setting.active_category,
                            models.preroll_categories.c.category_id == setting.active_category))
                .distinct()
                .all()
            )
            
            if not prerolls:
                return  # No prerolls to verify
            
            # Build expected preroll paths using the same logic as _apply_category_to_plex
            preroll_paths_local = [os.path.abspath(p.path) for p in prerolls]
            
            # Get path mappings from settings
            mappings = []
            try:
                raw = getattr(setting, "path_mappings", None)
                if raw:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        mappings = [m for m in data if isinstance(m, dict) and m.get("local") and m.get("plex")]
            except Exception:
                mappings = []
            
            # Translate local paths to Plex paths using the same function as scheduler
            def _translate_for_plex(local_path: str) -> str:
                try:
                    lp = os.path.normpath(local_path)
                    best = None
                    best_src = None
                    best_len = -1
                    for m in mappings:
                        src = os.path.normpath(str(m.get("local")))
                        if sys.platform.startswith("win"):
                            if lp.lower().startswith(src.lower()) and len(src) > best_len:
                                best = m
                                best_src = src
                                best_len = len(src)
                        else:
                            if lp.startswith(src) and len(src) > best_len:
                                best = m
                                best_src = src
                                best_len = len(src)
                    if best:
                        dst_prefix = str(best.get("plex"))
                        rest = lp[len(best_src):].lstrip("\\/")
                        try:
                            if ("/" in dst_prefix) and ("\\" not in dst_prefix):
                                out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                            elif "\\" in dst_prefix:
                                out = dst_prefix.rstrip("\\") + "\\" + rest.replace("/", "\\")
                            else:
                                out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                        except Exception:
                            out = dst_prefix + (("/" if not dst_prefix.endswith(("/", "\\")) else "") + rest)
                        return out
                except Exception:
                    pass
                return local_path
            
            expected_paths = [_translate_for_plex(p) for p in preroll_paths_local]
            
            # Note: Verification uses semicolon by default since we don't track which schedule is active
            # This is a limitation - verification may trigger false positives if the active schedule
            # uses comma (sequential) mode. Consider storing active schedule ID in settings for proper verification.
            separator = ";"
            expected_preroll_string = separator.join(expected_paths)
            
            # Get actual preroll setting from Plex
            plex_connector = PlexConnector(setting.plex_url, setting.plex_token)
            actual_preroll_string = plex_connector.get_preroll()
            
            # Normalize for comparison (strip whitespace, handle empty strings)
            expected_normalized = expected_preroll_string.strip()
            actual_normalized = actual_preroll_string.strip()
            
            # Compare expected vs actual
            if expected_normalized != actual_normalized:
                _scheduler_log(f"VERIFICATION: Plex preroll mismatch detected!")
                _scheduler_verbose(f"  Expected: {expected_normalized}")
                _scheduler_verbose(f"  Actual:   {actual_normalized}")
                _scheduler_verbose(f"  Reapplying category {setting.active_category}...")
                
                # Reapply the current category
                success = self._apply_category_to_plex(setting.active_category, db)
                if success:
                    _scheduler_log(f"VERIFICATION: Successfully reapplied prerolls")
                else:
                    _scheduler_log(f"VERIFICATION: Failed to reapply prerolls")
            
            # Update last verification time
            self._last_verification_time = now
            
        except Exception as e:
            print(f"Verification error: {e}")
        finally:
            db.close()

    def _is_schedule_active(self, schedule: models.Schedule, now: datetime.datetime) -> bool:
        """
        Determine whether a schedule should be considered active at 'now'.
        - If end_date is provided: active for the whole window [start_date, end_date].
        - If no end_date: treat as an ongoing schedule starting at start_date (indefinite)
          until another schedule takes precedence or a fallback is applied when no schedule is active.
        - For daily schedules with timeRange: also check if current time is within the time window.
        
        NOTE: Both schedule dates and 'now' are expected to be in local time (naive datetimes).
        This simplifies comparisons and avoids timezone conversion bugs.
        """
        if not schedule or not getattr(schedule, "start_date", None):
            return False

        # First check date window
        date_active = False
        if getattr(schedule, "end_date", None):
            # Windowed schedules: active between start and end (inclusive)
            date_active = schedule.start_date <= now <= schedule.end_date
        else:
            # Indefinite schedule: active from start onward
            date_active = now >= schedule.start_date
        
        if not date_active:
            return False
        
        # Now check time range for daily schedules with timeRange in recurrence_pattern
        if schedule.recurrence_pattern:
            try:
                pattern = json.loads(schedule.recurrence_pattern)
                time_range = pattern.get("timeRange")
                if time_range and time_range.get("start"):
                    # This schedule has a time-of-day constraint
                    start_time_str = time_range.get("start", "")  # e.g., "22:00"
                    end_time_str = time_range.get("end", "")  # e.g., "03:00"
                    
                    if start_time_str:
                        # Parse time strings (HH:MM format)
                        try:
                            start_parts = start_time_str.split(":")
                            start_hour = int(start_parts[0])
                            start_minute = int(start_parts[1]) if len(start_parts) > 1 else 0
                            
                            end_hour = 23
                            end_minute = 59
                            if end_time_str:
                                end_parts = end_time_str.split(":")
                                end_hour = int(end_parts[0])
                                end_minute = int(end_parts[1]) if len(end_parts) > 1 else 59
                            
                            # Both 'now' and timeRange are in local time
                            current_hour = now.hour
                            current_minute = now.minute
                            
                            current_time_val = current_hour * 60 + current_minute
                            start_time_val = start_hour * 60 + start_minute
                            end_time_val = end_hour * 60 + end_minute
                            
                            # Handle overnight ranges (e.g., 22:00 to 03:00)
                            if start_time_val <= end_time_val:
                                # Normal range (e.g., 09:00 to 17:00)
                                time_active = start_time_val <= current_time_val <= end_time_val
                            else:
                                # Overnight range (e.g., 22:00 to 03:00)
                                # Active if current time is >= start OR <= end
                                time_active = current_time_val >= start_time_val or current_time_val <= end_time_val
                            
                            if not time_active:
                                _scheduler_verbose(f"Schedule '{schedule.name}' outside time range {start_time_str}-{end_time_str} (local: {current_hour:02d}:{current_minute:02d})")
                            return time_active
                            
                        except (ValueError, IndexError) as e:
                            _scheduler_log(f"Error parsing time range for schedule '{schedule.name}': {e}", level="WARNING")
                            # If we can't parse the time, fall through to date-only logic
            except json.JSONDecodeError:
                pass  # Invalid JSON, ignore time range
        
        # No time range or couldn't parse - schedule is active based on date only
        return True

    def _apply_category_to_plex(self, category_id: int, db: Session, schedule: models.Schedule = None) -> bool:
        """
        Apply all prerolls from a category (including many-to-many) to Plex.
        Uses semicolon (random) or comma (sequential) delimiter based on schedule settings.
        If no schedule provided, defaults to random (semicolon).
        """
        if not category_id:
            return False

        # Collect prerolls (primary or associated) for the category
        prerolls = db.query(models.Preroll) \
            .outerjoin(models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id) \
            .filter(or_(models.Preroll.category_id == category_id,
                        models.preroll_categories.c.category_id == category_id)) \
            .distinct().all()

        if not prerolls:
            cat_name = "UNKNOWN"
            try:
                cat = db.query(models.Category).filter(models.Category.id == category_id).first()
                if cat:
                    cat_name = cat.name
            except Exception:
                pass
            _scheduler_log(f"No prerolls found for category_id={category_id} (name='{cat_name}'). Ensure prerolls are assigned to this category.", level="ERROR")
            return False

        # Build combined path string for Plex multi-preroll format
        # Determine delimiter from schedule settings (not category)
        preroll_paths_local = [os.path.abspath(p.path) for p in prerolls]
        
        # Use schedule's shuffle/playlist settings to determine delimiter
        # playlist=True means sequential (comma), shuffle=True or default means random (semicolon)
        if schedule and getattr(schedule, "playlist", False):
            delimiter = ","  # Sequential playback
        else:
            delimiter = ";"  # Random playback (default)

        setting = db.query(models.Setting).first()
        # Allow secure-store token fallback via PlexConnector; only require URL here
        if not setting or not getattr(setting, "plex_url", None):
            _scheduler_log("Plex not configured (missing URL); cannot apply category.", level="WARNING")
            return False

        # Translate local paths to Plex-accessible paths using configured mappings
        mappings = []
        try:
            raw = getattr(setting, "path_mappings", None)
            if raw:
                data = json.loads(raw)
                if isinstance(data, list):
                    mappings = [m for m in data if isinstance(m, dict) and m.get("local") and m.get("plex")]
        except Exception:
            mappings = []

        def _translate_for_plex(local_path: str) -> str:
            try:
                lp = os.path.normpath(local_path)
                best = None
                best_src = None
                best_len = -1
                for m in mappings:
                    src = os.path.normpath(str(m.get("local")))
                    if sys.platform.startswith("win"):
                        if lp.lower().startswith(src.lower()) and len(src) > best_len:
                            best = m
                            best_src = src
                            best_len = len(src)
                    else:
                        if lp.startswith(src) and len(src) > best_len:
                            best = m
                            best_src = src
                            best_len = len(src)
                if best:
                    dst_prefix = str(best.get("plex"))
                    rest = lp[len(best_src):].lstrip("\\/")
                    try:
                        if ("/" in dst_prefix) and ("\\" not in dst_prefix):
                            out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                        elif "\\" in dst_prefix:
                            out = dst_prefix.rstrip("\\") + "\\" + rest.replace("/", "\\")
                        else:
                            out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                    except Exception:
                        out = dst_prefix + (("/" if not dst_prefix.endswith(("/", "\\")) else "") + rest)
                    return out
            except Exception:
                pass
            return local_path

        preroll_paths_plex = [_translate_for_plex(p) for p in preroll_paths_local]

        # Preflight: ensure translated paths match Plex host platform path style
        connector = PlexConnector(setting.plex_url, setting.plex_token)
        try:
            info = connector.get_server_info() or {}
        except Exception:
            info = {}
        platform_str = str(info.get("platform") or info.get("Platform") or "").lower()

        def _looks_windows_path(s: str) -> bool:
            try:
                if not s:
                    return False
                if s.startswith("\\\\"):
                    return True
                if len(s) >= 3 and s[1] == ":" and (s[2] == "\\" or s[2] == "/"):
                    return True
            except Exception:
                pass
            return False

        def _looks_posix_path(s: str) -> bool:
            try:
                if not s:
                    return False
                if _looks_windows_path(s):
                    return False
                return s.startswith("/")
            except Exception:
                return False

        target_windows = ("win" in platform_str) or ("windows" in platform_str)
        mismatches: list[str] = []
        try:
            for out in preroll_paths_plex:
                if target_windows and _looks_posix_path(out):
                    mismatches.append(out)
                elif (not target_windows) and _looks_windows_path(out):
                    mismatches.append(out)
        except Exception:
            mismatches = []

        if mismatches:
            _scheduler_log(f"Path style mismatch with Plex platform '{platform_str}'; example: {mismatches[0]}")
            return False

        combined = delimiter.join(preroll_paths_plex)

        # Determine mode from delimiter
        mode_str = 'sequential' if delimiter == ',' else 'random'
        _scheduler_log(f"Applying category_id={category_id} with {len(prerolls)} prerolls to Plex (mode={mode_str}, delim={'comma' if delimiter==',' else 'semicolon'})…")
        ok = connector.set_preroll(combined)
        _scheduler_log(f"{'SUCCESS' if ok else 'FAIL'} setting multi-preroll (mode={mode_str}).")
        if ok:
            # Clear blend mode tracking since we're in normal mode now
            self._blend_mode_active = False
            self._blend_expected_preroll = None
            # Mirror manual "Apply to Plex" behavior so UI reflects the active category
            try:
                db.query(models.Category).update({"apply_to_plex": False})
                cat = db.query(models.Category).filter(models.Category.id == category_id).first()
                if cat:
                    cat.apply_to_plex = True
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
        return ok

    def _clear_plex_prerolls(self, db: Session) -> bool:
        """
        Clear the Plex preroll field (set to empty string).
        Used when no schedules are active and clear_when_inactive is enabled.
        """
        setting = db.query(models.Setting).first()
        if not setting or not getattr(setting, "plex_url", None):
            _scheduler_log("Plex not configured (missing URL); cannot clear prerolls.", level="WARNING")
            return False

        connector = PlexConnector(setting.plex_url, setting.plex_token)
        _scheduler_log("Clearing Plex preroll field (no active schedules, clear_when_inactive enabled)…")
        ok = connector.set_preroll("")  # Empty string clears prerolls
        _scheduler_log(f"{'SUCCESS' if ok else 'FAIL'} clearing Plex preroll field.")
        if ok:
            # Clear blend mode tracking
            self._blend_mode_active = False
            self._blend_expected_preroll = None
            # Clear apply_to_plex flag from all categories
            try:
                db.query(models.Category).update({"apply_to_plex": False})
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
        return ok

    def _apply_schedule_sequence_to_plex(self, schedule: models.Schedule, db: Session) -> bool:
        """
        Apply an explicit ordered sequence for a schedule to Plex.
        Sequence format (JSON list):
          - {"type":"random", "category_id": <int>, "count": <int>}
          - {"type":"fixed", "preroll_id": <int>}
        """
        if not schedule or not schedule.category_id or not getattr(schedule, "sequence", None):
            return False
        try:
            seq = schedule.sequence
            if isinstance(seq, str):
                seq = json.loads(seq)
            if not isinstance(seq, list):
                return False
        except Exception:
            return False

        # Helper to gather prerolls for a category (primary and many-to-many)
        def _prerolls_for_category(cid: int):
            return db.query(models.Preroll) \
                .outerjoin(models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id) \
                .filter(or_(models.Preroll.category_id == cid, models.preroll_categories.c.category_id == cid)) \
                .distinct().all()

        # Build ordered list of file paths per sequence steps
        paths = []
        for step in seq:
            try:
                stype = str(step.get("type", "")).lower()
            except Exception:
                stype = ""
            if stype == "random":
                try:
                    cid = int(step.get("category_id") or schedule.category_id or 0)
                except Exception:
                    cid = schedule.category_id or 0
                if not cid:
                    continue
                try:
                    count = int(step.get("count") or 1)
                except Exception:
                    count = 1
                pool = _prerolls_for_category(cid)
                if not pool:
                    continue
                k = min(max(count, 1), len(pool))
                picks = random.sample(pool, k) if len(pool) > k else pool
                for p in picks:
                    paths.append(os.path.abspath(p.path))
            elif stype == "fixed":
                # Support both single preroll_id and array preroll_ids
                pids = []
                try:
                    # Try array format first (preroll_ids)
                    ids_array = step.get("preroll_ids")
                    if ids_array and isinstance(ids_array, list):
                        pids = [int(x) for x in ids_array if x]
                    else:
                        # Fall back to single preroll_id
                        pid = int(step.get("preroll_id") or 0)
                        if pid:
                            pids = [pid]
                except Exception:
                    pass
                
                if not pids:
                    continue
                
                # Query and add each preroll in order
                for pid in pids:
                    p = db.query(models.Preroll).filter(models.Preroll.id == pid).first()
                    if p:
                        paths.append(os.path.abspath(p.path))
            else:
                # ignore unknown step types
                continue

        if not paths:
            _scheduler_log("Sequence produced no preroll paths; aborting.")
            return False

        _scheduler_log(f"Sequence built {len(paths)} paths:")
        for i, p in enumerate(paths):
            _scheduler_verbose(f"  {i+1}. {p}")

        # Choose delimiter: sequences must play in order. Always use playlist (comma) for sequences.
        mode = "playlist"
        delimiter = ","

        setting = db.query(models.Setting).first()
        # Allow secure-store token fallback via PlexConnector; only require URL here
        if not setting or not getattr(setting, "plex_url", None):
            _scheduler_log("Plex not configured (missing URL); cannot apply sequence.", level="WARNING")
            return False

        # Translate each path to Plex-visible paths using configured mappings
        mappings = []
        try:
            raw = getattr(setting, "path_mappings", None)
            if raw:
                data = json.loads(raw)
                if isinstance(data, list):
                    mappings = [m for m in data if isinstance(m, dict) and m.get("local") and m.get("plex")]
        except Exception:
            mappings = []

        def _translate_for_plex(local_path: str) -> str:
            try:
                lp = os.path.normpath(local_path)
                best = None
                best_src = None
                best_len = -1
                for m in mappings:
                    src = os.path.normpath(str(m.get("local")))
                    if sys.platform.startswith("win"):
                        if lp.lower().startswith(src.lower()) and len(src) > best_len:
                            best = m
                            best_src = src
                            best_len = len(src)
                    else:
                        if lp.startswith(src) and len(src) > best_len:
                            best = m
                            best_src = src
                            best_len = len(src)
                if best:
                    dst_prefix = str(best.get("plex"))
                    rest = lp[len(best_src):].lstrip("\\/")
                    try:
                        if ("/" in dst_prefix) and ("\\" not in dst_prefix):
                            out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                        elif "\\" in dst_prefix:
                            out = dst_prefix.rstrip("\\") + "\\" + rest.replace("/", "\\")
                        else:
                            out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                    except Exception:
                        out = dst_prefix + (("/" if not dst_prefix.endswith(("/", "\\")) else "") + rest)
                    return out
            except Exception:
                pass
            return local_path

        paths_plex = [_translate_for_plex(p) for p in paths]
        
        _scheduler_log(f"After translation, {len(paths_plex)} Plex paths:")
        for i, p in enumerate(paths_plex):
            _scheduler_verbose(f"  {i+1}. {p}")

        # Preflight: ensure translated paths match Plex platform path style
        connector = PlexConnector(setting.plex_url, setting.plex_token)
        try:
            info = connector.get_server_info() or {}
        except Exception:
            info = {}
        platform_str = str(info.get("platform") or info.get("Platform") or "").lower()

        def _looks_windows_path(s: str) -> bool:
            try:
                if not s:
                    return False
                if s.startswith("\\\\"):
                    return True
                if len(s) >= 3 and s[1] == ":" and (s[2] == "\\" or s[2] == "/"):
                    return True
            except Exception:
                pass
            return False

        def _looks_posix_path(s: str) -> bool:
            try:
                if not s:
                    return False
                if _looks_windows_path(s):
                    return False
                return s.startswith("/")
            except Exception:
                return False

        target_windows = ("win" in platform_str) or ("windows" in platform_str)
        mismatches: list[str] = []
        try:
            for out in paths_plex:
                if target_windows and _looks_posix_path(out):
                    mismatches.append(out)
                elif (not target_windows) and _looks_windows_path(out):
                    mismatches.append(out)
        except Exception:
            mismatches = []

        if mismatches:
            _scheduler_log(f"Path style mismatch with Plex platform '{platform_str}'; example: {mismatches[0]}")
            return False

        combined = delimiter.join(paths_plex)

        _scheduler_log(f"Applying schedule sequence with {len(paths)} items (mode={mode}, delim={'comma' if delimiter==',' else 'semicolon'})…")
        ok = connector.set_preroll(combined)
        _scheduler_log(f"{'SUCCESS' if ok else 'FAIL'} setting sequence preroll list.")
        if ok:
            # Mirror manual "Apply to Plex" behavior: mark schedule's category as applied
            try:
                db.query(models.Category).update({"apply_to_plex": False})
                cat = db.query(models.Category).filter(models.Category.id == schedule.category_id).first()
                if cat:
                    cat.apply_to_plex = True
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
        return ok

    def _apply_blended_schedules_to_plex(self, schedules: List[models.Schedule], db: Session) -> bool:
        """
        Apply prerolls from multiple blended schedules to Plex.
        Interleaves prerolls from each schedule for a mixed experience.
        """
        if not schedules:
            return False
        
        _scheduler_log(f"BLEND: Building blended playlist from {len(schedules)} schedules...")
        
        # Helper to gather prerolls for a category (primary and many-to-many)
        def _prerolls_for_category(cid: int):
            return db.query(models.Preroll) \
                .outerjoin(models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id) \
                .filter(or_(models.Preroll.category_id == cid, models.preroll_categories.c.category_id == cid)) \
                .distinct().all()

        # Collect preroll paths from each schedule
        all_schedule_paths = []  # List of (schedule_name, paths_list)
        
        for schedule in schedules:
            paths = []
            
            # If schedule has a sequence, use it
            if getattr(schedule, "sequence", None):
                try:
                    seq = schedule.sequence
                    if isinstance(seq, str):
                        seq = json.loads(seq)
                    if isinstance(seq, list):
                        for step in seq:
                            stype = str(step.get("type", "")).lower()
                            if stype == "random":
                                cid = int(step.get("category_id") or schedule.category_id or 0)
                                if not cid:
                                    continue
                                count = int(step.get("count") or 1)
                                pool = _prerolls_for_category(cid)
                                if pool:
                                    k = min(max(count, 1), len(pool))
                                    picks = random.sample(pool, k) if len(pool) > k else pool
                                    for p in picks:
                                        paths.append(os.path.abspath(p.path))
                            elif stype == "fixed":
                                pids = []
                                ids_array = step.get("preroll_ids")
                                if ids_array and isinstance(ids_array, list):
                                    pids = [int(x) for x in ids_array if x]
                                else:
                                    pid = step.get("preroll_id")
                                    if pid:
                                        pids = [int(pid)]
                                for pid in pids:
                                    p = db.query(models.Preroll).filter(models.Preroll.id == pid).first()
                                    if p:
                                        paths.append(os.path.abspath(p.path))
                except Exception as e:
                    _scheduler_log(f"Error parsing sequence for blended schedule '{schedule.name}': {e}", level="WARNING")
            
            # Otherwise, use the category's prerolls
            elif schedule.category_id:
                pool = _prerolls_for_category(schedule.category_id)
                # For blending, take a random sample (up to 3) from each category to keep it manageable
                if pool:
                    k = min(3, len(pool))
                    picks = random.sample(pool, k) if len(pool) > k else pool
                    for p in picks:
                        paths.append(os.path.abspath(p.path))
            
            if paths:
                all_schedule_paths.append((schedule.name, paths))
                _scheduler_log(f"BLEND:   '{schedule.name}': {len(paths)} prerolls collected")
                for i, p in enumerate(paths[:3]):  # Log first 3 paths
                    _scheduler_verbose(f"      {i+1}. {os.path.basename(p)}")
                if len(paths) > 3:
                    _scheduler_verbose(f"      ... and {len(paths) - 3} more")
        
        if not all_schedule_paths:
            _scheduler_log("BLEND: No preroll paths collected from any schedule", level="WARNING")
            return False
        
        # Interleave paths from all schedules (round-robin)
        final_paths = []
        max_len = max(len(paths) for _, paths in all_schedule_paths)
        for i in range(max_len):
            for schedule_name, paths in all_schedule_paths:
                if i < len(paths):
                    final_paths.append(paths[i])
        
        _scheduler_log(f"BLEND: Blend complete: {len(final_paths)} total prerolls interleaved from {len(all_schedule_paths)} schedules")
        
        # Apply path mappings and send to Plex
        setting = db.query(models.Setting).first()
        if not setting or not getattr(setting, "plex_url", None):
            _scheduler_log("Plex not configured (missing URL); cannot apply blended schedules.", level="WARNING")
            return False
        
        # Get path mappings
        mappings = []
        try:
            raw = getattr(setting, "path_mappings", None)
            if raw:
                data = json.loads(raw)
                if isinstance(data, list):
                    mappings = [m for m in data if isinstance(m, dict) and m.get("local") and m.get("plex")]
        except Exception:
            mappings = []
        
        def _translate_for_plex(local_path: str) -> str:
            try:
                lp = os.path.normpath(local_path)
                best = None
                best_src = None
                best_len = -1
                for m in mappings:
                    src = os.path.normpath(str(m.get("local")))
                    if sys.platform.startswith("win"):
                        if lp.lower().startswith(src.lower()) and len(src) > best_len:
                            best = m
                            best_src = src
                            best_len = len(src)
                    else:
                        if lp.startswith(src) and len(src) > best_len:
                            best = m
                            best_src = src
                            best_len = len(src)
                if best:
                    dst_prefix = str(best.get("plex"))
                    rest = lp[len(best_src):].lstrip("\\/")
                    if ("/" in dst_prefix) and ("\\" not in dst_prefix):
                        out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                    elif "\\" in dst_prefix:
                        out = dst_prefix.rstrip("\\") + "\\" + rest.replace("/", "\\")
                    else:
                        out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                    return out
            except Exception:
                pass
            return local_path
        
        paths_plex = [_translate_for_plex(p) for p in final_paths]
        
        # Use semicolon (random mode) so Plex picks one random preroll from the blended pool
        # The interleaving ensures fair distribution between schedules in the pool
        delimiter = ";"
        combined = delimiter.join(paths_plex)
        
        connector = PlexConnector(setting.plex_url, setting.plex_token)
        _scheduler_log(f"BLEND: Sending blended playlist to Plex ({len(paths_plex)} prerolls, random mode)...")
        ok = connector.set_preroll(combined)
        if ok:
            _scheduler_log(f"BLEND: Blended preroll list applied successfully to Plex")
            # Track blend mode for verification
            self._blend_mode_active = True
            self._blend_expected_preroll = combined
        else:
            _scheduler_log(f"BLEND: Failed to apply blended preroll list to Plex", level="ERROR")
        
        return ok

    def _apply_saved_sequence_to_plex(self, sequence_id: int, db: Session) -> bool:
        """
        Apply a saved sequence by ID to Plex (used for filler sequences).
        This is similar to _apply_schedule_sequence_to_plex but uses SavedSequence instead of Schedule.
        """
        try:
            saved_seq = db.query(models.SavedSequence).filter(models.SavedSequence.id == sequence_id).first()
            if not saved_seq:
                _scheduler_log(f"Filler sequence ID {sequence_id} not found", level="ERROR")
                return False
            
            blocks = saved_seq.get_blocks()
            if not blocks:
                _scheduler_log(f"Filler sequence '{saved_seq.name}' has no blocks", level="WARNING")
                return False
            
            _scheduler_log(f"FILLER: Applying saved sequence '{saved_seq.name}' with {len(blocks)} blocks")
            
            # Helper to gather prerolls for a category (primary and many-to-many)
            def _prerolls_for_category(cid: int):
                return db.query(models.Preroll) \
                    .outerjoin(models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id) \
                    .filter(or_(models.Preroll.category_id == cid, models.preroll_categories.c.category_id == cid)) \
                    .distinct().all()
            
            # Build ordered list of file paths per sequence steps
            paths = []
            for block in blocks:
                try:
                    block_type = str(block.get("type", "")).lower()
                except Exception:
                    block_type = ""
                
                if block_type == "random":
                    cid = int(block.get("category_id") or 0)
                    count = int(block.get("count") or 1)
                    if not cid:
                        continue
                    pool = _prerolls_for_category(cid)
                    if not pool:
                        continue
                    k = min(max(count, 1), len(pool))
                    picks = random.sample(pool, k) if len(pool) > k else pool
                    for p in picks:
                        paths.append(os.path.abspath(p.path))
                        
                elif block_type == "fixed":
                    pids = []
                    ids_array = block.get("preroll_ids")
                    if ids_array and isinstance(ids_array, list):
                        pids = [int(x) for x in ids_array if x]
                    else:
                        pid = block.get("preroll_id")
                        if pid:
                            pids = [int(pid)]
                    
                    for pid in pids:
                        p = db.query(models.Preroll).filter(models.Preroll.id == pid).first()
                        if p:
                            paths.append(os.path.abspath(p.path))
            
            if not paths:
                _scheduler_log(f"Filler sequence '{saved_seq.name}' produced no preroll paths", level="WARNING")
                return False
            
            _scheduler_log(f"FILLER: Sequence built {len(paths)} paths")
            
            # Apply path mappings and send to Plex
            setting = db.query(models.Setting).first()
            if not setting or not getattr(setting, "plex_url", None):
                _scheduler_log("Plex not configured (missing URL); cannot apply filler sequence.", level="WARNING")
                return False
            
            # Get path mappings
            mappings = []
            try:
                raw = getattr(setting, "path_mappings", None)
                if raw:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        mappings = [m for m in data if isinstance(m, dict) and m.get("local") and m.get("plex")]
            except Exception:
                mappings = []
            
            def _translate_for_plex(local_path: str) -> str:
                try:
                    lp = os.path.normpath(local_path)
                    best = None
                    best_src = None
                    best_len = -1
                    for m in mappings:
                        src = os.path.normpath(str(m.get("local")))
                        if sys.platform.startswith("win"):
                            if lp.lower().startswith(src.lower()) and len(src) > best_len:
                                best = m
                                best_src = src
                                best_len = len(src)
                        else:
                            if lp.startswith(src) and len(src) > best_len:
                                best = m
                                best_src = src
                                best_len = len(src)
                    if best:
                        dst_prefix = str(best.get("plex"))
                        rest = lp[len(best_src):].lstrip("\\/")
                        if ("/" in dst_prefix) and ("\\" not in dst_prefix):
                            out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                        elif "\\" in dst_prefix:
                            out = dst_prefix.rstrip("\\") + "\\" + rest.replace("/", "\\")
                        else:
                            out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                        return out
                except Exception:
                    pass
                return local_path
            
            paths_plex = [_translate_for_plex(p) for p in paths]
            
            # Use comma (playlist mode) for sequences to preserve order
            delimiter = ","
            combined = delimiter.join(paths_plex)
            
            connector = PlexConnector(setting.plex_url, setting.plex_token)
            _scheduler_log(f"FILLER: Sending sequence to Plex ({len(paths_plex)} prerolls)...")
            ok = connector.set_preroll(combined)
            if ok:
                _scheduler_log(f"FILLER: Sequence '{saved_seq.name}' applied successfully")
            else:
                _scheduler_log(f"FILLER: Failed to apply sequence to Plex", level="ERROR")
            
            return ok
        except Exception as e:
            _scheduler_log(f"Error applying filler sequence: {e}", level="ERROR")
            return False

    def _apply_coming_soon_list_to_plex(self, layout: str, db: Session) -> bool:
        """
        Apply a Coming Soon List video to Plex (used for filler mode).
        Layout can be 'grid' or 'list'.
        """
        try:
            setting = db.query(models.Setting).first()
            if not setting:
                _scheduler_log("Settings not found; cannot apply Coming Soon List", level="ERROR")
                return False
            
            # Find the Coming Soon List video file
            storage_path = getattr(setting, "nexup_storage_path", None)
            if not storage_path:
                _scheduler_log("NeX-Up storage path not configured; cannot find Coming Soon List", level="WARNING")
                return False
            
            # The coming soon list files are named: coming_soon_grid.mp4 or coming_soon_list.mp4
            # They are generated in the dynamic_prerolls subfolder
            filename = f"coming_soon_{layout}.mp4"
            video_path = os.path.join(storage_path, "dynamic_prerolls", filename)
            
            if not os.path.exists(video_path):
                _scheduler_log(f"Coming Soon List video not found: {video_path}", level="WARNING")
                return False
            
            video_path = os.path.abspath(video_path)
            _scheduler_log(f"FILLER: Applying Coming Soon List ({layout}) from {video_path}")
            
            # Get path mappings
            mappings = []
            try:
                raw = getattr(setting, "path_mappings", None)
                if raw:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        mappings = [m for m in data if isinstance(m, dict) and m.get("local") and m.get("plex")]
            except Exception:
                mappings = []
            
            def _translate_for_plex(local_path: str) -> str:
                try:
                    lp = os.path.normpath(local_path)
                    best = None
                    best_src = None
                    best_len = -1
                    for m in mappings:
                        src = os.path.normpath(str(m.get("local")))
                        if sys.platform.startswith("win"):
                            if lp.lower().startswith(src.lower()) and len(src) > best_len:
                                best = m
                                best_src = src
                                best_len = len(src)
                        else:
                            if lp.startswith(src) and len(src) > best_len:
                                best = m
                                best_src = src
                                best_len = len(src)
                    if best:
                        dst_prefix = str(best.get("plex"))
                        rest = lp[len(best_src):].lstrip("\\/")
                        if ("/" in dst_prefix) and ("\\" not in dst_prefix):
                            out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                        elif "\\" in dst_prefix:
                            out = dst_prefix.rstrip("\\") + "\\" + rest.replace("/", "\\")
                        else:
                            out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                        return out
                except Exception:
                    pass
                return local_path
            
            plex_path = _translate_for_plex(video_path)
            
            if not setting.plex_url:
                _scheduler_log("Plex not configured; cannot apply Coming Soon List", level="WARNING")
                return False
            
            connector = PlexConnector(setting.plex_url, setting.plex_token)
            _scheduler_log(f"FILLER: Sending Coming Soon List to Plex...")
            ok = connector.set_preroll(plex_path)
            if ok:
                _scheduler_log(f"FILLER: Coming Soon List ({layout}) applied successfully")
            else:
                _scheduler_log(f"FILLER: Failed to apply Coming Soon List to Plex", level="ERROR")
            
            return ok
        except Exception as e:
            _scheduler_log(f"Error applying Coming Soon List: {e}", level="ERROR")
            return False

    def _get_active_schedules(self) -> List[models.Schedule]:
        """Return a list of schedules currently active (for diagnostics/status)."""
        db = SessionLocal()
        try:
            # Use local time for comparisons since schedules are stored as naive local datetimes
            now = datetime.datetime.now()
            schedules = db.query(models.Schedule).filter(models.Schedule.is_active == True).all()
            return [s for s in schedules if self._is_schedule_active(s, now)]
        finally:
            db.close()

    def _should_execute_schedule(self, schedule: models.Schedule, now: datetime.datetime, db: Session) -> bool:
        """Determine if a schedule should execute now"""
        if schedule.type == "monthly":
            # Execute on the same day each month
            return (now.day == schedule.start_date.day and
                   now.hour == schedule.start_date.hour and
                   now.minute == schedule.start_date.minute)

        elif schedule.type == "yearly":
            # Check if this schedule uses dynamic holiday lookup
            if schedule.recurrence_pattern:
                try:
                    pattern = json.loads(schedule.recurrence_pattern)
                    if pattern.get('type') == 'holiday_dynamic':
                        # Dynamic holiday: look up current year's date from Holiday API
                        holiday_date = self._get_holiday_date(pattern.get('name'), pattern.get('country'), now.year)
                        if holiday_date:
                            return (now.month == holiday_date.month and
                                   now.day == holiday_date.day and
                                   now.hour == schedule.start_date.hour and
                                   now.minute == schedule.start_date.minute)
                        return False
                except Exception as e:
                    _scheduler_log(f"Error parsing holiday pattern: {e}", level="ERROR")
            
            # Standard yearly schedule: execute on the same date each year
            return (now.month == schedule.start_date.month and
                   now.day == schedule.start_date.day and
                   now.hour == schedule.start_date.hour and
                   now.minute == schedule.start_date.minute)

        elif schedule.type == "holiday":
            # Check holiday presets
            holiday = db.query(models.HolidayPreset).filter(
                models.HolidayPreset.category_id == schedule.category_id
            ).first()
            if holiday:
                return (now.month == holiday.month and
                       now.day == holiday.day and
                       now.hour == schedule.start_date.hour and
                       now.minute == schedule.start_date.minute)

        elif schedule.type == "custom":
            # Custom recurrence pattern (simplified - could use cron parser)
            if schedule.recurrence_pattern:
                return self._matches_pattern(now, schedule.recurrence_pattern)

        return False

    def _get_holiday_date(self, holiday_name: str, country_code: str, year: int) -> Optional[datetime.date]:
        """
        Look up the date for a holiday in a specific year using the Holiday API.
        This handles variable-date holidays like Thanksgiving, Easter, etc.
        
        Args:
            holiday_name: Name of the holiday (e.g., "Thanksgiving")
            country_code: ISO country code (e.g., "US")
            year: Year to look up
            
        Returns:
            datetime.date object if found, None otherwise
        """
        # Check cache first
        cache_key = f"{holiday_name}_{country_code}_{year}"
        if cache_key in self._holiday_date_cache:
            return self._holiday_date_cache[cache_key]
        
        try:
            # Import Holiday API
            from backend.holiday_api import HolidayAPI
            
            # Fetch holidays for this country and year
            holidays = HolidayAPI.get_holidays(country_code, year)
            
            # Find matching holiday (case-insensitive)
            holiday_name_lower = holiday_name.lower()
            for holiday in holidays:
                if holiday_name_lower in holiday.get('name', '').lower():
                    # Found it! Parse the date
                    holiday_date_str = holiday.get('date')
                    if holiday_date_str:
                        holiday_date = datetime.datetime.strptime(holiday_date_str, '%Y-%m-%d').date()
                        # Cache it
                        self._holiday_date_cache[cache_key] = holiday_date
                        _scheduler_log(f"Found {holiday_name} in {country_code} {year}: {holiday_date}")
                        return holiday_date
            
            # Not found - cache None to avoid repeated API calls
            self._holiday_date_cache[cache_key] = None
            _scheduler_log(f"Holiday '{holiday_name}' not found in {country_code} {year}", level="WARNING")
            return None
            
        except Exception as e:
            _scheduler_log(f"SCHEDULER: Error looking up holiday date: {e}", level="ERROR")
            # Don't cache errors - try again next time
            return None

    def _execute_schedule(self, schedule: models.Schedule, db: Session):
        """
        Execute a schedule by applying its entire category to Plex
        (multi-preroll rotation), instead of a single random preroll.
        """
        if not schedule or not schedule.category_id:
            return
        self._apply_category_to_plex(schedule.category_id, db)

    def _select_prerolls(self, schedule: models.Schedule, prerolls: List[models.Preroll]) -> List[models.Preroll]:
        """Select prerolls based on shuffle and playlist settings"""
        if schedule.playlist and schedule.preroll_ids:
            # Use specific preroll IDs for playlist
            try:
                preroll_ids = json.loads(schedule.preroll_ids)
                selected = [p for p in prerolls if p.id in preroll_ids]
                if selected:
                    return selected
            except:
                pass

        if schedule.shuffle:
            # Random selection
            return [random.choice(prerolls)]
        else:
            # Sequential or first available
            return [prerolls[0]]

    def _update_plex_preroll(self, prerolls: List[models.Preroll], db: Session):
        """Update Plex server with selected preroll"""
        _scheduler_log(f"Starting Plex update with {len(prerolls)} prerolls")

        setting = db.query(models.Setting).first()
        if not setting or not prerolls:
            _scheduler_log("No settings or prerolls found for Plex update")
            return

        _scheduler_log(f"Plex URL: {setting.plex_url}")
        _scheduler_log(f"Plex token available: {bool(setting.plex_token)}")

        connector = PlexConnector(setting.plex_url, setting.plex_token)

        # For multiple prerolls (like categories), create semicolon-separated list
        if len(prerolls) > 1:
            # Create list of all local preroll file paths
            preroll_paths_local = []
            for preroll in prerolls:
                full_local_path = os.path.abspath(preroll.path)
                preroll_paths_local.append(full_local_path)

            # Translate using configured mappings
            mappings = []
            try:
                raw = getattr(setting, "path_mappings", None)
                if raw:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        mappings = [m for m in data if isinstance(m, dict) and m.get("local") and m.get("plex")]
            except Exception:
                mappings = []

            def _translate_for_plex(local_path: str) -> str:
                try:
                    lp = os.path.normpath(local_path)
                    best = None
                    best_src = None
                    best_len = -1
                    for m in mappings:
                        src = os.path.normpath(str(m.get("local")))
                        if sys.platform.startswith("win"):
                            if lp.lower().startswith(src.lower()) and len(src) > best_len:
                                best = m
                                best_src = src
                                best_len = len(src)
                        else:
                            if lp.startswith(src) and len(src) > best_len:
                                best = m
                                best_src = src
                                best_len = len(src)
                    if best:
                        dst_prefix = str(best.get("plex"))
                        rest = lp[len(best_src):].lstrip("\\/")
                        out = os.path.join(dst_prefix, rest)
                        return out
                except Exception:
                    pass
                return local_path

            preroll_paths_plex = [_translate_for_plex(p) for p in preroll_paths_local]

            # Join all paths with semicolons for Plex multi-preroll format
            multi_preroll_path = ";".join(preroll_paths_plex)

            _scheduler_log(f"Setting {len(prerolls)} prerolls for schedule:")
            for i, preroll in enumerate(prerolls, 1):
                _scheduler_log(f"  {i}. {preroll.filename}")
            _scheduler_log(f"Combined path: {multi_preroll_path}")

            preroll_path = multi_preroll_path
        else:
            # Single preroll
            preroll_path = prerolls[0].path
            # Ensure the path is absolute for Plex
            if not os.path.isabs(preroll_path):
                preroll_path = os.path.abspath(preroll_path)

            # Translate single path too
            mappings = []
            try:
                raw = getattr(setting, "path_mappings", None)
                if raw:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        mappings = [m for m in data if isinstance(m, dict) and m.get("local") and m.get("plex")]
            except Exception:
                mappings = []

            def _translate_for_plex(local_path: str) -> str:
                try:
                    lp = os.path.normpath(local_path)
                    best = None
                    best_src = None
                    best_len = -1
                    for m in mappings:
                        src = os.path.normpath(str(m.get("local")))
                        if sys.platform.startswith("win"):
                            if lp.lower().startswith(src.lower()) and len(src) > best_len:
                                best = m
                                best_src = src
                                best_len = len(src)
                        else:
                            if lp.startswith(src) and len(src) > best_len:
                                best = m
                                best_src = src
                                best_len = len(src)
                    if best:
                        dst_prefix = str(best.get("plex"))
                        rest = lp[len(best_src):].lstrip("\\/")
                        out = os.path.join(dst_prefix, rest)
                        return out
                except Exception:
                    pass
                return local_path

            preroll_path = _translate_for_plex(preroll_path)

            _scheduler_log(f"Attempting to update Plex with single preroll: {preroll_path}")

        # Actually call the Plex connector to set the preroll
        _scheduler_log("Calling connector.set_preroll()...")
        success = connector.set_preroll(preroll_path)

        if success:
            _scheduler_log(f"SUCCESS: Plex preroll updated to: {preroll_path}")
        else:
            _scheduler_log(f"Could not update Plex preroll to: {preroll_path}", level="ERROR")

    def _calculate_next_run(self, schedule: models.Schedule) -> Optional[datetime.datetime]:
        """Calculate when this schedule should run next"""
        # Use local time for comparisons since schedules are stored as naive local datetimes
        now = datetime.datetime.now()

        if schedule.type == "monthly":
            # Next month, same day
            next_run = now.replace(day=schedule.start_date.day, hour=schedule.start_date.hour,
                                 minute=schedule.start_date.minute, second=0, microsecond=0)
            if next_run <= now:
                # If we're past the time today, schedule for next month
                if now.month == 12:
                    next_run = next_run.replace(year=now.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=now.month + 1)
            return next_run

        elif schedule.type == "yearly":
            # Next year, same date
            next_run = schedule.start_date.replace(year=now.year)
            if next_run <= now:
                next_run = next_run.replace(year=now.year + 1)
            return next_run

        elif schedule.type == "holiday":
            # Find the associated holiday preset and calculate next occurrence
            db = SessionLocal()
            try:
                holiday = db.query(models.HolidayPreset).filter(
                    models.HolidayPreset.category_id == schedule.category_id
                ).first()
                if holiday:
                    # Use start_month/start_day if available, otherwise fall back to legacy month/day
                    target_month = getattr(holiday, 'start_month', None) or holiday.month
                    target_day = getattr(holiday, 'start_day', None) or holiday.day

                    if target_month and target_day:
                        # Calculate next occurrence of this holiday date
                        next_run = now.replace(month=target_month, day=target_day,
                                             hour=schedule.start_date.hour,
                                             minute=schedule.start_date.minute,
                                             second=0, microsecond=0)
                        if next_run <= now:
                            # If we're past this year's occurrence, schedule for next year
                            next_run = next_run.replace(year=now.year + 1)
                        return next_run
            finally:
                db.close()

        return None

    def _matches_pattern(self, now: datetime.datetime, pattern: str) -> bool:
        """Check if current time matches a recurrence pattern.
        
        IMPORTANT: timeRange values are stored in user's local timezone,
        so we must convert 'now' (which is UTC) to local time before comparing.
        """
        try:
            pattern_data = json.loads(pattern)
            
            # Check time range if present
            time_range = pattern_data.get("timeRange")
            if time_range and time_range.get("start"):
                start_time_str = time_range.get("start", "")
                end_time_str = time_range.get("end", "")
                
                if start_time_str:
                    start_parts = start_time_str.split(":")
                    start_hour = int(start_parts[0])
                    start_minute = int(start_parts[1]) if len(start_parts) > 1 else 0
                    
                    end_hour = 23
                    end_minute = 59
                    if end_time_str:
                        end_parts = end_time_str.split(":")
                        end_hour = int(end_parts[0])
                        end_minute = int(end_parts[1]) if len(end_parts) > 1 else 59
                    
                    # CRITICAL: Convert UTC 'now' to user's local timezone
                    db = SessionLocal()
                    try:
                        setting = db.query(models.Setting).first()
                        user_tz_str = setting.timezone if setting and setting.timezone else "UTC"
                        try:
                            user_tz = pytz.timezone(user_tz_str)
                        except:
                            user_tz = pytz.UTC
                        
                        utc_now = now.replace(tzinfo=pytz.UTC) if now.tzinfo is None else now
                        local_now = utc_now.astimezone(user_tz)
                        current_hour = local_now.hour
                        current_minute = local_now.minute
                    finally:
                        db.close()
                    
                    current_time_val = current_hour * 60 + current_minute
                    start_time_val = start_hour * 60 + start_minute
                    end_time_val = end_hour * 60 + end_minute
                    
                    # Handle overnight ranges
                    if start_time_val <= end_time_val:
                        if not (start_time_val <= current_time_val <= end_time_val):
                            return False
                    else:
                        # Overnight range (e.g., 22:00 to 03:00)
                        if not (current_time_val >= start_time_val or current_time_val <= end_time_val):
                            return False
            
            # Check days of week if present
            days = pattern_data.get("daysOfWeek")
            if days and isinstance(days, list):
                # Python weekday: Monday=0, Sunday=6
                # Note: we should also use local time for day-of-week check
                db = SessionLocal()
                try:
                    setting = db.query(models.Setting).first()
                    user_tz_str = setting.timezone if setting and setting.timezone else "UTC"
                    try:
                        user_tz = pytz.timezone(user_tz_str)
                    except:
                        user_tz = pytz.UTC
                    
                    utc_now = now.replace(tzinfo=pytz.UTC) if now.tzinfo is None else now
                    local_now = utc_now.astimezone(user_tz)
                    if local_now.weekday() not in days:
                        return False
                finally:
                    db.close()
            
            return True
        except (json.JSONDecodeError, ValueError, IndexError):
            return True  # If pattern is invalid, default to match

# Global scheduler instance
scheduler = Scheduler()