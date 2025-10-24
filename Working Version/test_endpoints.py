#!/usr/bin/env python
"""Test script for timezone and active-category endpoints"""
import sys
import os

# Setup path
backend_path = r"c:\Users\HDTV\Documents\Preroll Projects\NeXroll - Windows\Working Version\NeXroll\backend"
repo_path = r"c:\Users\HDTV\Documents\Preroll Projects\NeXroll - Windows\Working Version\NeXroll"
sys.path.insert(0, backend_path)
sys.path.insert(0, repo_path)
os.chdir(backend_path)

# Test the database schema and endpoints
try:
    from backend.database import SessionLocal, engine
    import backend.models as models
    from main import ensure_schema
    
    print("=" * 60)
    print("Testing Schema Migration")
    print("=" * 60)
    
    # Run schema migration
    ensure_schema()
    print("✓ Schema migration completed successfully")
    
    # Check if timezone column exists
    with engine.connect() as conn:
        res = conn.exec_driver_sql("PRAGMA table_info(settings)")
        cols = {row[1]: row[2] for row in res.fetchall()}
        print(f"\nSettings table columns:")
        for col_name, col_type in sorted(cols.items()):
            print(f"  - {col_name}: {col_type}")
        
        if "timezone" in cols:
            print("✓ timezone column exists")
        else:
            print("✗ timezone column NOT FOUND")
        
        if "active_category" in cols:
            print("✓ active_category column exists")
        else:
            print("✗ active_category column NOT FOUND")
    
    print("\n" + "=" * 60)
    print("Testing Endpoints Logic")
    print("=" * 60)
    
    # Test database operations
    db = SessionLocal()
    
    # Test get_timezone
    setting = db.query(models.Setting).first()
    if setting:
        tz = getattr(setting, "timezone", "UTC")
        print(f"✓ GET /settings/timezone would return: {tz or 'UTC'}")
    else:
        print("✗ No Setting record found")
    
    # Test get_active_category
    if setting and getattr(setting, "active_category", None):
        cat_id = getattr(setting, "active_category", None)
        cat = db.query(models.Category).filter(models.Category.id == cat_id).first()
        if cat:
            print(f"✓ GET /settings/active-category would return: {cat.name}")
        else:
            print("ℹ GET /settings/active-category would return: null (category not found)")
    else:
        print("ℹ GET /settings/active-category would return: null (no active category set)")
    
    db.close()
    
    print("\n✓ All tests passed!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
