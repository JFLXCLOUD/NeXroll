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

from sqlalchemy.orm import Session
from sqlalchemy import or_, func
import backend.models as models
from backend.plex_connector import PlexConnector
from backend.jellyfin_connector import JellyfinConnector
from backend.database import SessionLocal

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

    def _run_scheduler(self):
        """Main scheduler loop - runs based on SCHEDULER_INTERVAL (default 60s)"""
        while self.running:
            try:
                # Auto-apply mapped category from currently playing Plex item (genre-based)
                self._apply_genre_mapping_from_playback()
            except Exception as e:
                print(f"Scheduler genre-monitor error: {e}")
            try:
                self._check_and_execute_schedules()
            except Exception as e:
                print(f"Scheduler error: {e}")
            try:
                # Periodically verify Plex has the correct prerolls set
                self._verify_and_reapply_if_needed()
            except Exception as e:
                print(f"Scheduler verification error: {e}")
            # Use configurable interval (default 60s, set via SCHEDULER_INTERVAL env var)
            time.sleep(self._scheduler_check_interval)

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
                print("SCHEDULER: Jellyfin not configured (missing URL); cannot apply prerolls.")
                return False
            
            jellyfin_url = setting.jellyfin_url.rstrip("/")
            jellyfin_api_key = getattr(setting, "jellyfin_api_key", None)
            
            if not jellyfin_api_key:
                print("SCHEDULER: Jellyfin API key not configured; cannot apply prerolls.")
                return False
            
            # Get prerolls for this category
            prerolls = db.query(models.Preroll) \
                .outerjoin(models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id) \
                .filter(or_(models.Preroll.category_id == category_id,
                           models.preroll_categories.c.category_id == category_id)) \
                .distinct().all()
            
            if not prerolls:
                print(f"SCHEDULER: No prerolls found for category_id={category_id}. Cannot apply to Jellyfin.")
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
            
            print(f"SCHEDULER: Preparing to apply {len(prerolls)} prerolls to Jellyfin (total {total_intro_seconds}s intro)…")
            
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
                        print(f"  ✓ Applied intro to: {item_name}")
                    else:
                        print(f"  ✗ Failed to apply intro to: {item_name}")
                
                except Exception as e:
                    print(f"  ✗ Error applying to item: {e}")
                    continue
            
            print(f"SCHEDULER: Successfully applied prerolls to {applied_count}/{len(search_results)} Jellyfin items.")
            return applied_count > 0
        
        except Exception as e:
            print(f"SCHEDULER: Error applying prerolls to Jellyfin: {e}")
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
                print(f"SCHEDULER: Failed to fetch sessions: {e}")
                return
            if getattr(r, "status_code", 0) != 200:
                print(f"SCHEDULER: Sessions API returned status {r.status_code}")
                return
            if not r.content:
                print("SCHEDULER: Sessions API returned empty content")
                return

            import xml.etree.ElementTree as ET
            try:
                root = ET.fromstring(r.content)
            except Exception as e:
                print(f"SCHEDULER: Failed to parse sessions XML: {e}")
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
                    print(f"SCHEDULER: Metadata API for {chosen_key} returned status {rm.status_code}")
                    return
                if not rm.content:
                    print(f"SCHEDULER: Metadata API for {chosen_key} returned empty content")
                    return
                rootm = ET.fromstring(rm.content)
            except Exception as e:
                print(f"SCHEDULER: Failed to fetch/parse metadata for {chosen_key}: {e}")
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
                now = datetime.datetime.utcnow()
                active_schedules = [s for s in schedules if self._is_schedule_active(s, now)]
                if active_schedules:
                    print(f"SCHEDULER: Skipping genre mapping for ratingKey={chosen_key} due to active schedule (priority mode: {priority_mode})")
                    return

            # Apply to Plex and set override to protect from scheduler immediately overriding
            ok = self._apply_category_to_plex(matched_cat.id, db)
            if not ok:
                print(f"SCHEDULER: Failed to apply matched category '{matched_cat.name}' (ID {matched_cat.id}) for genre '{matched_genre_display}'")
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

            print(f"SCHEDULER: Genre mapping applied for ratingKey={chosen_key}: '{matched_genre_display}' -> category '{matched_cat.name}'")

        finally:
            try:
                db.close()
            except Exception:
                pass

    def _check_and_execute_schedules(self):
        """Evaluate schedules, apply active category to Plex, and handle fallback when idle."""
        db = SessionLocal()
        try:
            now = datetime.datetime.utcnow()
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
                            print(f"SCHEDULER: override active until {ovr.isoformat()}Z; skipping schedule apply")
                            self._last_logged_state = state_key
                            self._last_logged_time = now
                        return
                except Exception:
                    # If comparison fails for any reason, ignore override
                    pass

            desired_category_id = None
            chosen_schedule = None

            if active:
                # Prefer the schedule that ends soonest, then earliest start, then lowest id
                def _sort_key(s):
                    end = s.end_date if s.end_date else datetime.datetime.max
                    start = s.start_date or datetime.datetime.min
                    return (end, start, s.id)
                active.sort(key=_sort_key)
                chosen_schedule = active[0]
                desired_category_id = chosen_schedule.category_id
                
                # Sanity check: ensure category_id is set
                if not desired_category_id:
                    state_key = f"error:no_category:{chosen_schedule.id}"
                    if self._last_logged_state != state_key:
                        print(f"SCHEDULER: ERROR - Schedule '{chosen_schedule.name}' (ID {chosen_schedule.id}) has no category_id set. Cannot apply prerolls.")
                        self._last_logged_state = state_key
                        self._last_logged_time = now
                    desired_category_id = None
                else:
                    # Use a consistent state key that works with the "already active" check below
                    state_key = f"schedule_active:{chosen_schedule.id}:{desired_category_id}"
                    if self._last_logged_state != state_key:
                        print(f"SCHEDULER: Active schedule selected: '{chosen_schedule.name}' (ID {chosen_schedule.id}) -> Category {desired_category_id}")
                        self._last_logged_state = state_key
                        self._last_logged_time = now
            else:
                # No active schedules -> attempt fallback from any schedule that defines it
                fallback_ids = [s.fallback_category_id for s in schedules if getattr(s, "fallback_category_id", None)]
                if fallback_ids:
                    desired_category_id = fallback_ids[0]
                    state_key = f"fallback:{desired_category_id}"
                    if self._last_logged_state != state_key:
                        print(f"SCHEDULER: No active schedules; using fallback category {desired_category_id}")
                        self._last_logged_state = state_key
                        self._last_logged_time = now
                else:
                    state_key = "no_schedules"
                    if self._last_logged_state != state_key:
                        print(f"SCHEDULER: No active schedules and no fallback defined; Plex preroll will remain unchanged")
                        self._last_logged_state = state_key
                        self._last_logged_time = now

            # Apply category change to Plex only if it differs from current
            if desired_category_id and setting.active_category != desired_category_id:
                applied_ok = False
                # If this schedule defines an explicit sequence, honor it; otherwise apply whole category
                if chosen_schedule and getattr(chosen_schedule, "sequence", None):
                    applied_ok = self._apply_schedule_sequence_to_plex(chosen_schedule, db)
                else:
                    applied_ok = self._apply_category_to_plex(desired_category_id, db)
                if applied_ok:
                    setting.active_category = desired_category_id
                    if chosen_schedule:
                        chosen_schedule.last_run = now
                        chosen_schedule.next_run = self._calculate_next_run(chosen_schedule)
                    db.commit()
            elif desired_category_id is None:
                state_key = "no_category_to_apply"
                if self._last_logged_state != state_key:
                    print(f"SCHEDULER: No category to apply (desired_category_id is None)")
                    self._last_logged_state = state_key
                    self._last_logged_time = now
            elif setting.active_category == desired_category_id:
                # Only log if state changed OR if we haven't logged this schedule in 5 minutes
                state_key = f"schedule_active:{chosen_schedule.id if chosen_schedule else 'none'}:{desired_category_id}"
                if self._last_logged_state != state_key:
                    # State changed (different schedule/category) - log immediately
                    print(f"SCHEDULER: Category {desired_category_id} already active; no change needed")
                    self._last_logged_state = state_key
                    self._last_logged_time = now
                elif self._last_logged_time and (now - self._last_logged_time).total_seconds() > 300:
                    # Same state but 5 minutes passed - log for status visibility
                    print(f"SCHEDULER: Category {desired_category_id} still active")
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
        now = datetime.datetime.utcnow()
        
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
            
            # Only verify if we have an active category
            if not setting.active_category:
                return
            
            # Get the expected prerolls for the active category
            prerolls = (
                db.query(models.Preroll)
                .filter(models.Preroll.category_id == setting.active_category)
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
            
            # Determine separator based on category's plex_mode
            try:
                cat = db.query(models.Category).filter(models.Category.id == setting.active_category).first()
                mode = getattr(cat, "plex_mode", "shuffle") if cat else "shuffle"
            except Exception:
                mode = "shuffle"
            separator = "," if isinstance(mode, str) and mode.lower() == "playlist" else ";"
            expected_preroll_string = separator.join(expected_paths)
            
            # Get actual preroll setting from Plex
            plex_connector = PlexConnector(setting.plex_url, setting.plex_token)
            actual_preroll_string = plex_connector.get_preroll()
            
            # Normalize for comparison (strip whitespace, handle empty strings)
            expected_normalized = expected_preroll_string.strip()
            actual_normalized = actual_preroll_string.strip()
            
            # Compare expected vs actual
            if expected_normalized != actual_normalized:
                print(f"SCHEDULER VERIFICATION: Plex preroll mismatch detected!")
                print(f"  Expected: {expected_normalized}")
                print(f"  Actual:   {actual_normalized}")
                print(f"  Reapplying category {setting.active_category}...")
                
                # Reapply the current category
                success = self._apply_category_to_plex(setting.active_category, db)
                if success:
                    print(f"SCHEDULER VERIFICATION: Successfully reapplied prerolls")
                else:
                    print(f"SCHEDULER VERIFICATION: Failed to reapply prerolls")
            
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
        """
        if not schedule or not getattr(schedule, "start_date", None):
            return False

        # Windowed schedules: active between start and end (inclusive)
        if getattr(schedule, "end_date", None):
            return schedule.start_date <= now <= schedule.end_date

        # Indefinite schedule: active from start onward
        return now >= schedule.start_date

    def _apply_category_to_plex(self, category_id: int, db: Session) -> bool:
        """
        Apply all prerolls from a category (including many-to-many) to Plex as a semicolon-separated list.
        Mirrors the logic in the /categories/{id}/apply-to-plex endpoint.
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
            print(f"SCHEDULER: ERROR - No prerolls found for category_id={category_id} (name='{cat_name}'). Ensure prerolls are assigned to this category.")
            return False

        # Build combined path string for Plex multi-preroll format, honoring category.plex_mode
        preroll_paths_local = [os.path.abspath(p.path) for p in prerolls]
        try:
            cat = db.query(models.Category).filter(models.Category.id == category_id).first()
            mode = getattr(cat, "plex_mode", "shuffle") if cat else "shuffle"
        except Exception:
            mode = "shuffle"
        delimiter = "," if isinstance(mode, str) and mode.lower() == "playlist" else ";"

        setting = db.query(models.Setting).first()
        # Allow secure-store token fallback via PlexConnector; only require URL here
        if not setting or not getattr(setting, "plex_url", None):
            print("SCHEDULER: Plex not configured (missing URL); cannot apply category.")
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
            print(f"SCHEDULER: Path style mismatch with Plex platform '{platform_str}'; example: {mismatches[0]}")
            return False

        combined = delimiter.join(preroll_paths_plex)

        print(f"SCHEDULER: Applying category_id={category_id} with {len(prerolls)} prerolls to Plex (mode={mode}, delim={'comma' if delimiter==',' else 'semicolon'})…")
        ok = connector.set_preroll(combined)
        print(f"SCHEDULER: {'SUCCESS' if ok else 'FAIL'} setting multi-preroll (mode={mode}).")
        if ok:
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
                try:
                    pid = int(step.get("preroll_id") or 0)
                except Exception:
                    pid = 0
                if not pid:
                    continue
                p = db.query(models.Preroll).filter(models.Preroll.id == pid).first()
                if p:
                    paths.append(os.path.abspath(p.path))
            else:
                # ignore unknown step types
                continue

        if not paths:
            print("SCHEDULER: Sequence produced no preroll paths; aborting.")
            return False

        # Choose delimiter: sequences must play in order. Always use playlist (comma) for sequences.
        mode = "playlist"
        delimiter = ","

        setting = db.query(models.Setting).first()
        # Allow secure-store token fallback via PlexConnector; only require URL here
        if not setting or not getattr(setting, "plex_url", None):
            print("SCHEDULER: Plex not configured (missing URL); cannot apply sequence.")
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
            print(f"SCHEDULER: Path style mismatch with Plex platform '{platform_str}'; example: {mismatches[0]}")
            return False

        combined = delimiter.join(paths_plex)

        print(f"SCHEDULER: Applying schedule sequence with {len(paths)} items (mode={mode}, delim={'comma' if delimiter==',' else 'semicolon'})…")
        ok = connector.set_preroll(combined)
        print(f"SCHEDULER: {'SUCCESS' if ok else 'FAIL'} setting sequence preroll list.")
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

    def _get_active_schedules(self) -> List[models.Schedule]:
        """Return a list of schedules currently active (for diagnostics/status)."""
        db = SessionLocal()
        try:
            now = datetime.datetime.utcnow()
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
            # Execute on the same date each year
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
        print(f"SCHEDULER: Starting Plex update with {len(prerolls)} prerolls")

        setting = db.query(models.Setting).first()
        if not setting or not prerolls:
            print("SCHEDULER: No settings or prerolls found for Plex update")
            return

        print(f"SCHEDULER: Plex URL: {setting.plex_url}")
        print(f"SCHEDULER: Plex token available: {bool(setting.plex_token)}")

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

            print(f"SCHEDULER: Setting {len(prerolls)} prerolls for schedule:")
            for i, preroll in enumerate(prerolls, 1):
                print(f"SCHEDULER:   {i}. {preroll.filename}")
            print(f"SCHEDULER: Combined path: {multi_preroll_path}")

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

            print(f"SCHEDULER: Attempting to update Plex with single preroll: {preroll_path}")

        # Actually call the Plex connector to set the preroll
        print("SCHEDULER: Calling connector.set_preroll()...")
        success = connector.set_preroll(preroll_path)

        if success:
            print(f"SCHEDULER: SUCCESS: Plex preroll updated to: {preroll_path}")
        else:
            print(f"SCHEDULER: FAILED: Could not update Plex preroll to: {preroll_path}")

    def _calculate_next_run(self, schedule: models.Schedule) -> Optional[datetime.datetime]:
        """Calculate when this schedule should run next"""
        now = datetime.datetime.utcnow()

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
        """Simple pattern matching (could be enhanced with cron parser)"""
        # For now, just check if it's time to run
        # This is a simplified implementation
        return True

# Global scheduler instance
scheduler = Scheduler()