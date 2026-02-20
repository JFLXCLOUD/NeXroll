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
    is_system = Column(Boolean, default=False)  # System categories cannot be edited/deleted (e.g., NeX-Up Trailers)
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


class ComingSoonTrailer(Base):
    """NeX-Up: Tracks trailers for upcoming movies from Radarr"""
    __tablename__ = "coming_soon_trailers"

    id = Column(Integer, primary_key=True, index=True)
    radarr_movie_id = Column(Integer, index=True)  # Radarr's internal movie ID
    tmdb_id = Column(Integer, index=True)  # TMDB ID for cross-referencing
    imdb_id = Column(String, nullable=True)  # IMDB ID
    title = Column(String, index=True)  # Movie title
    year = Column(Integer, nullable=True)  # Release year
    overview = Column(Text, nullable=True)  # Movie description
    release_date = Column(DateTime, nullable=True)  # Expected release date
    release_type = Column(String, nullable=True)  # 'digital', 'physical', 'theatrical'
    trailer_url = Column(String, nullable=True)  # Original YouTube URL
    local_path = Column(String, nullable=True)  # Path to downloaded trailer file
    file_size_mb = Column(Float, nullable=True)  # Size of downloaded trailer in MB
    duration_seconds = Column(Integer, nullable=True)  # Trailer duration
    resolution = Column(String, nullable=True)  # e.g., "1080p"
    poster_url = Column(String, nullable=True)  # Movie poster URL
    fanart_url = Column(String, nullable=True)  # Fanart/background URL
    downloaded_at = Column(DateTime, nullable=True)  # When trailer was downloaded
    status = Column(String, default='pending')  # 'pending', 'downloading', 'downloaded', 'error', 'expired'
    error_message = Column(Text, nullable=True)  # Error details if download failed
    is_enabled = Column(Boolean, default=True)  # User can enable/disable individual trailers
    play_count = Column(Integer, default=0)  # How many times this trailer has been played
    last_played = Column(DateTime, nullable=True)  # Last time trailer was played
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class ComingSoonTVTrailer(Base):
    """NeX-Up: Tracks trailers for upcoming TV shows/seasons from Sonarr"""
    __tablename__ = "coming_soon_tv_trailers"

    id = Column(Integer, primary_key=True, index=True)
    sonarr_series_id = Column(Integer, index=True)  # Sonarr's internal series ID
    tvdb_id = Column(Integer, index=True)  # TVDB ID for cross-referencing
    tmdb_id = Column(Integer, nullable=True)  # TMDB ID
    imdb_id = Column(String, nullable=True)  # IMDB ID
    title = Column(String, index=True)  # Show title
    year = Column(Integer, nullable=True)  # Show start year
    season_number = Column(Integer, nullable=True)  # Season number (1 for new shows)
    overview = Column(Text, nullable=True)  # Show/season description
    network = Column(String, nullable=True)  # Network/streaming service
    release_date = Column(DateTime, nullable=True)  # Premiere date
    release_type = Column(String, nullable=True)  # 'new_show' or 'new_season'
    trailer_url = Column(String, nullable=True)  # Original YouTube URL
    local_path = Column(String, nullable=True)  # Path to downloaded trailer file
    file_size_mb = Column(Float, nullable=True)  # Size of downloaded trailer in MB
    duration_seconds = Column(Integer, nullable=True)  # Trailer duration
    resolution = Column(String, nullable=True)  # e.g., "1080p"
    poster_url = Column(String, nullable=True)  # Show poster URL
    fanart_url = Column(String, nullable=True)  # Fanart/background URL
    downloaded_at = Column(DateTime, nullable=True)  # When trailer was downloaded
    status = Column(String, default='pending')  # 'pending', 'downloading', 'downloaded', 'error', 'expired'
    error_message = Column(Text, nullable=True)  # Error details if download failed
    is_enabled = Column(Boolean, default=True)  # User can enable/disable individual trailers
    play_count = Column(Integer, default=0)  # How many times this trailer has been played
    last_played = Column(DateTime, nullable=True)  # Last time trailer was played
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


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
    # Coexistence mode (passive mode)
    passive_mode = Column(Boolean, default=False)  # When enabled, only manage prerolls during active schedules (allows coexistence with other preroll managers)
    # Clear prerolls when inactive
    clear_when_inactive = Column(Boolean, default=False)  # When enabled, clear Plex preroll field when no schedules are active
    
    # NeX-Up Settings (Radarr integration for upcoming movie trailers)
    nexup_enabled = Column(Boolean, default=False)  # Master enable/disable for NeX-Up feature
    nexup_radarr_url = Column(String, nullable=True)  # Radarr server URL
    nexup_radarr_api_key = Column(String, nullable=True)  # Radarr API key
    nexup_storage_path = Column(String, nullable=True)  # Path for temporary trailer storage
    nexup_quality = Column(String, default='1080')  # Trailer quality: '720', '1080', '4k', 'best'
    nexup_days_ahead = Column(Integer, default=90)  # How many days ahead to look for upcoming movies
    nexup_max_trailers = Column(Integer, default=10)  # Maximum number of trailers to keep
    nexup_max_storage_gb = Column(Float, default=5.0)  # Maximum storage space for trailers
    nexup_trailers_per_playback = Column(Integer, default=2)  # How many trailers to include per preroll session
    nexup_playback_order = Column(String, default='release_date')  # 'release_date', 'random', 'download_date'
    nexup_auto_refresh_hours = Column(Integer, default=24)  # How often to refresh from Radarr (hours)
    nexup_last_sync = Column(DateTime, nullable=True)  # Last time NeX-Up synced with Radarr
    nexup_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)  # Auto-created category for trailers
    
    # YouTube Rate Limiting Settings
    nexup_download_delay = Column(Integer, default=5)  # Seconds to wait between downloads (YouTube rate limiting)
    nexup_max_concurrent = Column(Integer, default=1)  # Max concurrent downloads (1 = sequential)
    nexup_bulk_warning_threshold = Column(Integer, default=5)  # Show warning when downloading more than this many
    nexup_tmdb_api_key = Column(String, nullable=True)  # User's TMDB API key (optional, uses fallback if not provided)
    
    # NeX-Up Sonarr Settings (TV show trailers)
    nexup_sonarr_enabled = Column(Boolean, default=False)  # Enable Sonarr integration
    nexup_sonarr_url = Column(String, nullable=True)  # Sonarr server URL
    nexup_sonarr_api_key = Column(String, nullable=True)  # Sonarr API key
    nexup_tv_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)  # Auto-created category for TV trailers
    nexup_last_sonarr_sync = Column(DateTime, nullable=True)  # Last time NeX-Up synced with Sonarr
    nexup_max_trailer_duration = Column(Integer, default=180)  # Maximum trailer duration in seconds (0 = no limit)
    
    # Dynamic Preroll Generation Settings
    nexup_dynamic_preroll_template = Column(String, nullable=True)  # Template name: 'coming_soon', 'now_playing', etc.
    nexup_dynamic_preroll_server_name = Column(String, nullable=True)  # Server name to display in generated preroll
    nexup_dynamic_preroll_duration = Column(Integer, nullable=True)  # Duration of generated preroll in seconds
    nexup_dynamic_preroll_theme = Column(String, nullable=True)  # Color theme: 'midnight', 'sunset', 'forest', 'royal', 'monochrome'
    
    # Coming Soon List Auto-Regeneration Settings
    nexup_coming_soon_list_auto_regen = Column(Boolean, default=False)  # Auto-regenerate Coming Soon List after sync
    nexup_coming_soon_list_layout = Column(String, default='grid')  # Layout to use: 'grid', 'list', or 'both'
    nexup_coming_soon_list_source = Column(String, default='both')  # Source: 'movies', 'shows', or 'both'
    nexup_coming_soon_list_duration = Column(Integer, default=10)  # Duration in seconds
    nexup_coming_soon_list_max_items = Column(Integer, default=8)  # Max items to show
    nexup_coming_soon_list_bg_color = Column(String, default='#141428')  # Background color
    nexup_coming_soon_list_text_color = Column(String, default='#ffffff')  # Text color
    nexup_coming_soon_list_accent_color = Column(String, default='#00d4ff')  # Accent color
    nexup_coming_soon_list_server_name = Column(String, default='')  # Server name to display
    
    # Authentication Settings (Optional - for PWA/remote access)
    auth_enabled = Column(Boolean, default=False)  # Master toggle - auth is OPTIONAL
    auth_session_timeout_hours = Column(Integer, default=24)  # Session duration in hours
    auth_allow_registration = Column(Boolean, default=False)  # Allow new user registration
    auth_require_https = Column(Boolean, default=False)  # Require HTTPS for login (production mode)
    
    # Update System Settings
    update_check_interval = Column(String, default='daily')  # 'never', 'startup', 'hourly', 'daily', 'weekly'
    update_include_prerelease = Column(Boolean, default=False)  # Include beta/pre-release versions
    update_last_check = Column(DateTime, nullable=True)  # Last time we checked for updates
    update_dismissed_version = Column(String, nullable=True)  # Version user dismissed
    
    # Enhanced Logging Settings
    log_level = Column(String, default='INFO')  # 'DEBUG', 'INFO', 'WARNING', 'ERROR'
    log_retention_days = Column(Integer, default=30)  # How long to keep logs in database
    log_to_database = Column(Boolean, default=True)  # Enable database logging (for UI viewer)
    log_request_logging = Column(Boolean, default=True)  # Log all API requests with timing
    log_scheduler_logging = Column(Boolean, default=True)  # Log scheduler activity
    log_api_logging = Column(Boolean, default=True)  # Log external API calls (Plex, Radarr, etc.)
    
    # Filler Category Settings - Used when no schedules are active (different from per-schedule fallback)
    # The filler kicks in when there are NO active schedules at all, filling the gap globally
    filler_enabled = Column(Boolean, default=False)  # Enable filler category feature
    filler_type = Column(String, default='category')  # 'category', 'sequence', or 'coming_soon'
    filler_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)  # Category to use as filler
    filler_sequence_id = Column(Integer, ForeignKey("saved_sequences.id"), nullable=True)  # Sequence to use as filler
    filler_coming_soon_layout = Column(String, default='grid')  # 'grid' or 'list' for Coming Soon List
    filler_active = Column(String, nullable=True)  # Tracks active filler: "category:ID", "sequence:ID", "coming_soon:layout", or null

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


class APIKey(Base):
    """API Keys for external system authentication"""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # User-friendly name for the key
    key_hash = Column(String, nullable=False, index=True)  # SHA256 hash of the API key
    key_prefix = Column(String(8), nullable=False)  # First 8 chars for identification (e.g., "nx_abc123")
    permissions = Column(String, default='full')  # 'read' or 'full'
    expires_at = Column(DateTime, nullable=True)  # Optional expiration date
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)  # Track last usage
    is_active = Column(Boolean, default=True)  # Soft revoke without deleting
    description = Column(Text, nullable=True)  # Optional description/notes


class User(Base):
    """User accounts for web UI authentication (optional feature)"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)  # bcrypt hash
    display_name = Column(String, nullable=True)  # Friendly display name
    email = Column(String, nullable=True)  # Optional email
    role = Column(String, default='user')  # 'admin' or 'user'
    is_active = Column(Boolean, default=True)  # Account enabled/disabled
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)  # Track last login
    failed_login_attempts = Column(Integer, default=0)  # For lockout protection
    locked_until = Column(DateTime, nullable=True)  # Account lockout timestamp


class Session(Base):
    """User sessions for web UI authentication"""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(String, unique=True, nullable=False, index=True)  # Random token
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    ip_address = Column(String, nullable=True)  # Client IP for security
    user_agent = Column(String, nullable=True)  # Browser/client info
    is_valid = Column(Boolean, default=True)  # Can be invalidated on logout

    user = relationship("User")


class AuthAuditLog(Base):
    """Audit log for authentication events (login, logout, failed attempts)"""
    __tablename__ = "auth_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)  # 'login_success', 'login_failed', 'logout', 'account_locked', 'user_created', 'user_deleted', 'password_changed'
    username = Column(String, nullable=True, index=True)  # Username involved (nullable for system events)
    user_id = Column(Integer, nullable=True)  # User ID if applicable
    ip_address = Column(String, nullable=True)  # Client IP
    user_agent = Column(String, nullable=True)  # Browser/client info
    details = Column(String, nullable=True)  # Additional details (e.g., "locked after 5 failed attempts")


class LogEntry(Base):
    """Structured application log entries for the enhanced logging system"""
    __tablename__ = "log_entries"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    level = Column(String, nullable=False, index=True)  # 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    category = Column(String, nullable=False, index=True)  # 'system', 'scheduler', 'api', 'user', 'plex', 'jellyfin', 'nexup'
    source = Column(String, nullable=True)  # Module/function name (e.g., 'scheduler.apply_prerolls')
    message = Column(Text, nullable=False)  # Log message
    details = Column(Text, nullable=True)  # JSON string with additional context
    request_id = Column(String, nullable=True, index=True)  # Request ID for correlating logs
    user_id = Column(Integer, nullable=True)  # User ID if action was user-initiated
    duration_ms = Column(Integer, nullable=True)  # Duration in milliseconds for timed operations
    ip_address = Column(String, nullable=True)  # Client IP for API requests