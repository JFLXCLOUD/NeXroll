import datetime
import json
import random
import threading
import time
from typing import List, Optional
import os

from sqlalchemy.orm import Session
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
        """Main scheduler loop - runs every minute"""
        while self.running:
            try:
                self._check_and_execute_schedules()
            except Exception as e:
                print(f"Scheduler error: {e}")
            time.sleep(60)  # Check every minute

    def _check_and_execute_schedules(self):
        """Check all active schedules and execute if needed"""
        db = SessionLocal()
        try:
            now = datetime.datetime.utcnow()
            schedules = db.query(models.Schedule).filter(
                models.Schedule.is_active == True
            ).all()

            for schedule in schedules:
                if self._should_execute_schedule(schedule, now, db):
                    self._execute_schedule(schedule, db)
                    schedule.last_run = now
                    schedule.next_run = self._calculate_next_run(schedule)
                    db.commit()

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
        """Execute a schedule by updating Plex with selected preroll"""
        # Get prerolls for this schedule's category
        prerolls = []
        if schedule.category_id:
            # Correct: fetch prerolls by category_id, not by tag name
            category_prerolls = db.query(models.Preroll).filter(
                models.Preroll.category_id == schedule.category_id
            ).all()
            prerolls = category_prerolls

        if not prerolls:
            return

        # Select preroll(s) based on settings
        selected_prerolls = self._select_prerolls(schedule, prerolls)

        # Update Plex with selected preroll
        self._update_plex_preroll(selected_prerolls, db)

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