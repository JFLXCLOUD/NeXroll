from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Float, Table
from sqlalchemy.orm import relationship
from backend.database import Base
import datetime
import json

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
    community_preroll_id = Column(String, nullable=True, index=True)  # ID from community prerolls library
    exclude_from_matching = Column(Boolean, default=False)  # Exclude from auto-matching to community prerolls
    file_hash = Column(String, nullable=True, index=True)  # SHA256 hash for duplicate detection

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
    color = Column(String, nullable=True)  # Custom color for calendar display (hex format)
    blend_enabled = Column(Boolean, default=False)  # Allow blending with other overlapping schedules
    priority = Column(Integer, default=5)  # Priority level 1-10 (higher wins during overlap)
    exclusive = Column(Boolean, default=False)  # When active, this schedule wins exclusively (no blending)
    # Holiday tracking fields for auto-updating variable date holidays
    holiday_name = Column(String, nullable=True)  # e.g., "Thanksgiving", "Easter"
    holiday_country = Column(String, nullable=True)  # e.g., "US", "CA"

    category = relationship("Category", foreign_keys=[category_id])
    fallback_category = relationship("Category", foreign_keys=[fallback_category_id])

class SavedSequence(Base):
    __tablename__ = "saved_sequences"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # Sequence name
    description = Column(Text, nullable=True)  # Optional description
    blocks = Column(Text)  # JSON array of sequence blocks
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def get_blocks(self):
        """Parse and return blocks as list"""
        try:
            return json.loads(self.blocks) if self.blocks else []
        except:
            return []
    
    def set_blocks(self, blocks_list):
        """Set blocks from list"""
        try:
            self.blocks = json.dumps(blocks_list) if blocks_list else "[]"
            return True
        except:
            return False

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

class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    plex_url = Column(String)  # Chosen Plex server base URL (e.g., http://192.168.1.x:32400)
    plex_token = Column(String)  # Plex auth token (manual/stable/OAuth)
    jellyfin_url = Column(String)  # Jellyfin base URL (e.g., http://192.168.1.x:8096)
    jellyfin_api_key = Column(String, nullable=True)  # Jellyfin API key for auth
    # Community Prerolls settings
    community_fair_use_accepted = Column(Boolean, default=False)  # Whether user accepted Fair Use Policy
    community_fair_use_accepted_at = Column(DateTime, nullable=True)  # Timestamp of acceptance
    plex_client_id = Column(String, nullable=True)  # X-Plex-Client-Identifier
    plex_server_base_url = Column(String, nullable=True)  # Best-resolved server URL (local preferred)
    plex_server_machine_id = Column(String, nullable=True)  # Server machineIdentifier
    plex_server_name = Column(String, nullable=True)  # Server name (friendly)
    # App state
    active_category = Column(Integer, ForeignKey("categories.id"))
    timezone = Column(String, default="UTC")  # User's timezone (e.g., "America/New_York")
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
    override_expires_at = Column(DateTime, nullable=True)
    path_mappings = Column(Text, nullable=True)  # JSON list of {"local": "...", "plex": "..."} path prefix mappings
    last_schedule_fallback = Column(Integer, nullable=True)  # Fallback category from most recently active schedule (used when no schedules are active)
    # Genre-based preroll settings
    genre_auto_apply = Column(Boolean, default=False)  # Enable/disable automatic genre-based preroll application
    genre_priority_mode = Column(String, default="schedules_override")  # "schedules_override" or "genres_override" - which takes priority when both are active
    genre_override_ttl_seconds = Column(Integer, default=10)  # TTL in seconds for genre override window (prevents re-applying same genre preroll)
    # Dashboard customization
    dashboard_tile_order = Column(Text, nullable=True)  # JSON array of tile IDs for custom dashboard ordering
    dashboard_layout = Column(Text, nullable=True)  # JSON dashboard section layout configuration
    # Version tracking for changelog display
    last_seen_version = Column(String, nullable=True)  # Last version user has seen (for changelog display)
    # Logging settings
    verbose_logging = Column(Boolean, default=False)  # Enable verbose/debug logging for troubleshooting
    
    def get_json_value(self, key):
        """Get a JSON value from a column"""
        try:
            value = getattr(self, key, None)
            return json.loads(value) if value else None
        except:
            return None
            
    def set_json_value(self, key, value):
        """Set a JSON value for a column"""
        try:
            setattr(self, key, json.dumps(value) if value is not None else None)
            return True
        except:
            return False