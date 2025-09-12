from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Preroll(Base):
    __tablename__ = "prerolls"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    path = Column(String)
    thumbnail = Column(String)
    tags = Column(Text)  # JSON array of tags
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    description = Column(Text, nullable=True)
    duration = Column(Float, nullable=True)  # Duration in seconds
    file_size = Column(Integer, nullable=True)  # File size in bytes
    upload_date = Column(DateTime, default=datetime.datetime.utcnow)

    category = relationship("Category")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text)
    apply_to_plex = Column(Boolean, default=False)  # Whether this category should be applied to Plex

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

class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    plex_url = Column(String)
    plex_token = Column(String)
    active_category = Column(Integer, ForeignKey("categories.id"))
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)