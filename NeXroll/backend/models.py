from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Float, Table
from sqlalchemy.orm import relationship
from backend.database import Base
import datetime
from sqlalchemy import func

# Association (many-to-many) between prerolls and categories
preroll_categories = Table(
    "preroll_categories",
    Base.metadata,
    Column("preroll_id", Integer, ForeignKey("prerolls.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)

class Preroll(Base):
    __tablename__ = "prerolls"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    display_name = Column(String, nullable=True)  # Optional UI/display label separate from disk filename
    path = Column(String)
    thumbnail = Column(String)
    tags = Column(Text)  # JSON array of tags
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    description = Column(Text, nullable=True)
    duration = Column(Float, nullable=True)  # Duration in seconds
    file_size = Column(Integer, nullable=True)  # File size in bytes
    managed = Column(Boolean, default=True)  # True = uploaded/managed by NeXroll; False = externally mapped
    upload_date = Column(DateTime, default=datetime.datetime.utcnow)

    category = relationship("Category")
    # Additional categories (many-to-many via preroll_categories)
    categories = relationship("Category", secondary="preroll_categories")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text)
    plex_mode = Column(String, default="shuffle")  # 'shuffle' or 'playlist' for Plex delimiter behavior
    apply_to_plex = Column(Boolean, default=False)  # Whether this category should be applied to Plex
    # Optional: reverse relation to list all prerolls tagged with this category (view-only)
    prerolls = relationship("Preroll", secondary="preroll_categories", viewonly=True)

class GenreMap(Base):
    __tablename__ = "genre_maps"

    id = Column(Integer, primary_key=True, index=True)
    genre = Column(String, unique=True, index=True)  # e.g., "Horror", "Comedy" from Plex metadata
    genre_norm = Column(String, unique=True, index=True, nullable=True)  # canonical normalized key (lowercased, synonyms applied)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)

    # When this Plex genre is detected, apply this category's prerolls
    category = relationship("Category")
class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # Schedule name
    type = Column(String)  # monthly, yearly, holiday, custom
    start_date = Column(DateTime)
    end_date = Column(DateTime, nullable=True)  # Optional for ongoing schedules
    category_id = Column(Integer, ForeignKey("categories.id"))
    fallback_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)  # Fallback category
    shuffle = Column(Boolean, default=False)
    playlist = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    recurrence_pattern = Column(String, nullable=True)  # For cron-like patterns
    preroll_ids = Column(Text, nullable=True)  # JSON array of preroll IDs for playlists
    sequence = Column(Text, nullable=True)  # JSON describing stacked prerolls (e.g., random blocks + fixed)

    category = relationship("Category", foreign_keys=[category_id])
    fallback_category = relationship("Category", foreign_keys=[fallback_category_id])

class HolidayPreset(Base):
    __tablename__ = "holiday_presets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text)
    month = Column(Integer)  # 1-12 (legacy single-day support)
    day = Column(Integer)  # 1-31 (legacy single-day support)
    start_month = Column(Integer, nullable=True)  # 1-12 (for date ranges)
    start_day = Column(Integer, nullable=True)  # 1-31 (for date ranges)
    end_month = Column(Integer, nullable=True)  # 1-12 (for date ranges)
    end_day = Column(Integer, nullable=True)  # 1-31 (for date ranges)
    is_recurring = Column(Boolean, default=True)
    category_id = Column(Integer, ForeignKey("categories.id"))

    category = relationship("Category")

class CommunityTemplate(Base):
    __tablename__ = "community_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    author = Column(String)
    template_data = Column(Text)  # JSON string containing schedule data
    category = Column(String)  # Template category (e.g., "Holiday", "Seasonal", "Custom")
    tags = Column(Text)  # JSON array of tags
    downloads = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_public = Column(Boolean, default=True)

class PrerollPlay(Base):
    __tablename__ = "preroll_plays"

    id = Column(Integer, primary_key=True, index=True)
    preroll_id = Column(Integer, ForeignKey("prerolls.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)  # Category that was active when played
    played_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    trigger_type = Column(String, default="manual")  # 'manual', 'schedule', 'genre_auto', 'fallback'
    rating_key = Column(String, nullable=True)  # Plex rating key that triggered the play (if available)
    genre = Column(String, nullable=True)  # Genre that triggered the play (if genre_auto)

    preroll = relationship("Preroll")
    category = relationship("Category")

class CategoryUsage(Base):
    __tablename__ = "category_usage"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    applied_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    trigger_type = Column(String, default="manual")  # 'manual', 'schedule', 'genre_auto', 'fallback'
    duration_seconds = Column(Integer, nullable=True)  # How long this category was active
    preroll_count = Column(Integer, default=0)  # Number of prerolls in the category at time of application

    category = relationship("Category")

class ScheduleExecution(Base):
    __tablename__ = "schedule_executions"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=False)
    executed_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    success = Column(Boolean, default=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)  # Category that was applied
    preroll_count = Column(Integer, default=0)  # Number of prerolls applied
    error_message = Column(Text, nullable=True)

    schedule = relationship("Schedule")
    category = relationship("Category")

class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    plex_url = Column(String)  # Chosen Plex server base URL (e.g., http://192.168.1.x:32400)
    plex_token = Column(String)  # Plex auth token (manual/stable/OAuth)
    jellyfin_url = Column(String)  # Jellyfin base URL (e.g., http://192.168.1.x:8096)
    # Plex.tv Connect (OAuth-style) metadata
    plex_client_id = Column(String, nullable=True)  # X-Plex-Client-Identifier
    plex_server_base_url = Column(String, nullable=True)  # Best-resolved server URL (local preferred)
    plex_server_machine_id = Column(String, nullable=True)  # Server machineIdentifier
    plex_server_name = Column(String, nullable=True)  # Server name (friendly)
    # App state
    active_category = Column(Integer, ForeignKey("categories.id"))
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
    override_expires_at = Column(DateTime, nullable=True)
    path_mappings = Column(Text, nullable=True)  # JSON list of {"local": "...", "plex": "..."} path prefix mappings
    # Genre-based preroll settings
    genre_auto_apply = Column(Boolean, default=False)  # Enable/disable automatic genre-based preroll application
    genre_priority_mode = Column(String, default="schedules_override")  # "schedules_override" or "genres_override" - which takes priority when both are active
    genre_override_ttl_seconds = Column(Integer, default=10)  # TTL in seconds for genre override window (prevents re-applying same genre preroll)
    # Dashboard widget customization
    dashboard_layout = Column(Text, nullable=True)  # JSON structure for widget positions, visibility, and lock state