import datetime
import json
import random
import threading
import time
from typing import List, Optional
import os

from sqlalchemy.orm import Session
from sqlalchemy import or_
import nexroll_backend.models as models
from nexroll_backend.plex_connector import PlexConnector
from nexroll_backend.database import SessionLocal

class Scheduler:
    def __init__(self):
        self.running = False
        self.thread = None

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
        """Main scheduler loop - runs every ~15 seconds for better responsiveness"""
        while self.running:
            try:
                self._check_and_execute_schedules()
            except Exception as e:
                print(f"Scheduler error: {e}")
            time.sleep(15)  # Check every 15 seconds

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
            else:
                # No active schedules -> attempt fallback from any schedule that defines it
                fallback_ids = [s.fallback_category_id for s in schedules if getattr(s, "fallback_category_id", None)]
                if fallback_ids:
                    desired_category_id = fallback_ids[0]

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
            # If no desired_category_id, leave Plex as-is to avoid unintended clears

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
            print(f"SCHEDULER: No prerolls found for category_id={category_id}")
            return False

        # Build combined path string for Plex multi-preroll format, honoring category.plex_mode
        preroll_paths = [os.path.abspath(p.path) for p in prerolls]
        try:
            cat = db.query(models.Category).filter(models.Category.id == category_id).first()
            mode = getattr(cat, "plex_mode", "shuffle") if cat else "shuffle"
        except Exception:
            mode = "shuffle"
        delimiter = "," if isinstance(mode, str) and mode.lower() == "playlist" else ";"
        combined = delimiter.join(preroll_paths)

        setting = db.query(models.Setting).first()
        if not setting or not getattr(setting, "plex_url", None) or not getattr(setting, "plex_token", None):
            print("SCHEDULER: Plex not configured; cannot apply category.")
            return False

        connector = PlexConnector(setting.plex_url, setting.plex_token)
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
        combined = delimiter.join(paths)

        setting = db.query(models.Setting).first()
        if not setting or not getattr(setting, "plex_url", None) or not getattr(setting, "plex_token", None):
            print("SCHEDULER: Plex not configured; cannot apply sequence.")
            return False

        connector = PlexConnector(setting.plex_url, setting.plex_token)
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
            # Create semicolon-separated list of all preroll file paths
            preroll_paths = []
            for preroll in prerolls:
                full_local_path = os.path.abspath(preroll.path)
                preroll_paths.append(full_local_path)

            # Join all paths with semicolons for Plex multi-preroll format
            multi_preroll_path = ";".join(preroll_paths)

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

        return None

    def _matches_pattern(self, now: datetime.datetime, pattern: str) -> bool:
        """Simple pattern matching (could be enhanced with cron parser)"""
        # For now, just check if it's time to run
        # This is a simplified implementation
        return True

# Global scheduler instance
scheduler = Scheduler()