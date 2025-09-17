from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
import datetime
import os
import ffmpeg
import json
import random
import zipfile
import io
import shutil
from pathlib import Path

import sys
import os

# Add the current directory and parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

from database import SessionLocal, engine
import models
from plex_connector import PlexConnector
from scheduler import scheduler

models.Base.metadata.create_all(bind=engine)

# Pydantic models for API
class ScheduleCreate(BaseModel):
    name: str
    type: str
    start_date: str  # Accept as string from frontend
    end_date: str = None  # Accept as string from frontend
    category_id: int
    shuffle: bool = False
    playlist: bool = False
    recurrence_pattern: str = None
    preroll_ids: str = None
    fallback_category_id: int = None

class ScheduleResponse(BaseModel):
    id: int
    name: str
    type: str
    start_date: datetime.datetime
    end_date: datetime.datetime | None = None
    category_id: int
    shuffle: bool
    playlist: bool
    is_active: bool
    last_run: datetime.datetime | None = None
    next_run: datetime.datetime | None = None
    recurrence_pattern: str | None = None
    preroll_ids: str | None = None

class CategoryCreate(BaseModel):
    name: str
    description: str = None
    apply_to_plex: bool = False

class PlexConnectRequest(BaseModel):
    url: str
    token: str

app = FastAPI(title="NeXroll Backend", version="1.0.0")

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:9393"],  # React dev server and production port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes are defined here (they need to be before static mounts)

# Start scheduler on app startup
@app.on_event("startup")
def startup_event():
    scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.stop()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/plex/connect")
def connect_plex(request: PlexConnectRequest, db: Session = Depends(get_db)):
    url = request.url
    token = request.token

    # Validate input
    if not url or not url.strip():
        raise HTTPException(status_code=422, detail="Plex server URL is required")
    if not token or not token.strip():
        raise HTTPException(status_code=422, detail="Plex authentication token is required")

    # Validate URL format
    if not url.startswith(('http://', 'https://')):
        raise HTTPException(status_code=422, detail="Plex server URL must start with http:// or https://")

    try:
        connector = PlexConnector(url.strip(), token.strip())
        if connector.test_connection():
            # Save to settings
            setting = db.query(models.Setting).first()
            if not setting:
                setting = models.Setting(plex_url=url.strip(), plex_token=token.strip())
                db.add(setting)
            else:
                setting.plex_url = url.strip()
                setting.plex_token = token.strip()
                setting.updated_at = datetime.datetime.utcnow()
            db.commit()
            return {"connected": True, "message": "Successfully connected to Plex server"}
        else:
            raise HTTPException(status_code=422, detail="Failed to connect to Plex server. Please check your URL and token.")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Connection error: {str(e)}")

@app.get("/plex/status")
def get_plex_status(db: Session = Depends(get_db)):
    setting = db.query(models.Setting).first()
    if setting:
        connector = PlexConnector(setting.plex_url, setting.plex_token)
        info = connector.get_server_info()
        return info or {"connected": False}
    return {"connected": False}

@app.post("/plex/disconnect")
def disconnect_plex(db: Session = Depends(get_db)):
    """Disconnect from Plex server by clearing stored credentials"""
    setting = db.query(models.Setting).first()
    if setting:
        # Clear Plex settings
        setting.plex_url = None
        setting.plex_token = None
        setting.updated_at = datetime.datetime.utcnow()
        db.commit()
        return {"disconnected": True, "message": "Successfully disconnected from Plex server"}
    else:
        return {"disconnected": True, "message": "No Plex connection found"}

@app.post("/plex/connect/stable-token")
def connect_plex_stable_token(request: PlexConnectRequest, db: Session = Depends(get_db)):
    """Connect to Plex server using stable token from config file"""
    url = request.url

    # Validate URL format
    if not url or not url.strip():
        raise HTTPException(status_code=422, detail="Plex server URL is required")
    if not url.startswith(('http://', 'https://')):
        raise HTTPException(status_code=422, detail="Plex server URL must start with http:// or https://")

    try:
        # Create connector without token - it will try to load stable token
        connector = PlexConnector(url.strip())
        if connector.token:
            if connector.test_connection():
                # Save to settings
                setting = db.query(models.Setting).first()
                if not setting:
                    setting = models.Setting(plex_url=url.strip(), plex_token=connector.token)
                    db.add(setting)
                else:
                    setting.plex_url = url.strip()
                    setting.plex_token = connector.token
                    setting.updated_at = datetime.datetime.utcnow()
                db.commit()
                return {
                    "connected": True,
                    "message": "Successfully connected to Plex server using stable token",
                    "method": "stable_token"
                }
            else:
                raise HTTPException(status_code=422, detail="Failed to connect to Plex server with stable token. Please check your URL and ensure the stable token is valid.")
        else:
            raise HTTPException(status_code=422, detail="No stable token found. Please run the setup script to configure your stable token.")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Connection error: {str(e)}")

@app.post("/prerolls/upload")
def upload_preroll(
    file: UploadFile = File(...),
    tags: str = Form(""),
    category_id: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    # Ensure directories exist
    os.makedirs(os.path.join(data_dir, "prerolls"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "prerolls", "thumbnails"), exist_ok=True)

    # Determine category directory
    category_dir = "Default"  # Default category
    if category_id and category_id.strip():
        try:
            cat_id_int = int(category_id)
            # Get category name from database
            from database import SessionLocal
            db_session = SessionLocal()
            category = db_session.query(models.Category).filter(models.Category.id == cat_id_int).first()
            if category:
                category_dir = category.name
            db_session.close()
        except:
            pass

    # Create category directory if it doesn't exist
    category_path = os.path.join(data_dir, "prerolls", category_dir)
    thumbnail_category_path = os.path.join(data_dir, "prerolls", "thumbnails", category_dir)
    os.makedirs(category_path, exist_ok=True)
    os.makedirs(thumbnail_category_path, exist_ok=True)

    # Save file
    file_path = os.path.join(category_path, file.filename)
    file_size = 0
    with open(file_path, "wb") as f:
        content = file.file.read()
        file_size = len(content)
        f.write(content)

    # Get video duration using ffprobe
    duration = None
    try:
        import subprocess
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', file_path
        ], capture_output=True, text=True)
        if result.returncode == 0:
            probe_data = json.loads(result.stdout)
            duration = float(probe_data['format']['duration'])
    except:
        pass  # ffprobe not available or failed

    # Generate thumbnail
    thumbnail_path = os.path.join(thumbnail_category_path, f"{file.filename}.jpg")
    try:
        # Use subprocess to run ffmpeg with proper single image output
        import subprocess
        result = subprocess.run([
            'ffmpeg', '-i', file_path, '-ss', '5', '-vframes', '1', '-q:v', '2',
            '-y', thumbnail_path  # -y to overwrite existing files
        ], capture_output=True, text=True)

        if result.returncode == 0:
            # Store path relative to data_dir for static serving
            thumbnail_path = os.path.relpath(thumbnail_path, data_dir).replace("\\", "/") if thumbnail_path else None
        else:
            print(f"FFmpeg thumbnail generation failed: {result.stderr}")
            thumbnail_path = None
    except Exception as e:
        print(f"Thumbnail generation error: {e}")
        thumbnail_path = None  # If ffmpeg fails

    # Process tags
    processed_tags = None
    if tags and tags.strip():
        try:
            # Try to parse as JSON array
            processed_tags = json.dumps(json.loads(tags))
        except:
            # Treat as comma-separated string and convert to JSON array
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            processed_tags = json.dumps(tag_list)

    # Convert category_id to int if provided
    category_id_int = None
    if category_id and category_id.strip():
        try:
            category_id_int = int(category_id)
        except ValueError:
            pass  # Invalid category_id, ignore

    # Save to DB
    preroll = models.Preroll(
        filename=file.filename,
        path=file_path,
        thumbnail=thumbnail_path,
        tags=processed_tags,
        category_id=category_id_int,
        description=description,
        duration=duration,
        file_size=file_size
    )
    db.add(preroll)
    db.commit()
    db.refresh(preroll)

    return {
        "uploaded": True,
        "id": preroll.id,
        "filename": file.filename,
        "thumbnail": thumbnail_path,
        "duration": duration,
        "file_size": file_size
    }

@app.post("/prerolls/upload-multiple")
def upload_multiple_prerolls(
    files: list[UploadFile] = File(...),
    tags: str = Form(""),
    category_id: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """Upload multiple preroll files at once"""
    if not files or len(files) == 0:
        raise HTTPException(status_code=422, detail="No files provided")

    results = []
    successful_uploads = 0

    for file in files:
        try:
            # Ensure directories exist
            os.makedirs(os.path.join(data_dir, "prerolls"), exist_ok=True)
            os.makedirs(os.path.join(data_dir, "prerolls", "thumbnails"), exist_ok=True)

            # Determine category directory
            category_dir = "Default"  # Default category
            if category_id and category_id.strip():
                try:
                    cat_id_int = int(category_id)
                    # Get category name from database
                    category = db.query(models.Category).filter(models.Category.id == cat_id_int).first()
                    if category:
                        category_dir = category.name
                except:
                    pass

            # Create category directory if it doesn't exist
            category_path = os.path.join(data_dir, "prerolls", category_dir)
            thumbnail_category_path = os.path.join(data_dir, "prerolls", "thumbnails", category_dir)
            os.makedirs(category_path, exist_ok=True)
            os.makedirs(thumbnail_category_path, exist_ok=True)

            # Save file
            file_path = os.path.join(category_path, file.filename)
            file_size = 0
            with open(file_path, "wb") as f:
                content = file.file.read()
                file_size = len(content)
                f.write(content)

            # Get video duration using ffprobe
            duration = None
            try:
                import subprocess
                result = subprocess.run([
                    'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', file_path
                ], capture_output=True, text=True)
                if result.returncode == 0:
                    probe_data = json.loads(result.stdout)
                    duration = float(probe_data['format']['duration'])
            except:
                pass  # ffprobe not available or failed

            # Generate thumbnail
            thumbnail_path = os.path.join(thumbnail_category_path, f"{file.filename}.jpg")
            try:
                # Use subprocess to run ffmpeg with proper single image output
                import subprocess
                result = subprocess.run([
                    'ffmpeg', '-i', file_path, '-ss', '5', '-vframes', '1', '-q:v', '2',
                    '-y', thumbnail_path  # -y to overwrite existing files
                ], capture_output=True, text=True)
        
                if result.returncode == 0:
                    # Store path relative to data_dir for static serving
                    thumbnail_path = os.path.relpath(thumbnail_path, data_dir).replace("\\", "/") if thumbnail_path else None
                else:
                    print(f"FFmpeg thumbnail generation failed: {result.stderr}")
                    thumbnail_path = None
            except Exception as e:
                print(f"Thumbnail generation error: {e}")
                thumbnail_path = None  # If ffmpeg fails

            # Process tags
            processed_tags = None
            if tags and tags.strip():
                try:
                    # Try to parse as JSON array
                    processed_tags = json.dumps(json.loads(tags))
                except:
                    # Treat as comma-separated string and convert to JSON array
                    tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
                    processed_tags = json.dumps(tag_list)

            # Convert category_id to int if provided
            category_id_int = None
            if category_id and category_id.strip():
                try:
                    category_id_int = int(category_id)
                except ValueError:
                    pass  # Invalid category_id, ignore

            # Save to DB
            preroll = models.Preroll(
                filename=file.filename,
                path=file_path,
                thumbnail=thumbnail_path,
                tags=processed_tags,
                category_id=category_id_int,
                description=description,
                duration=duration,
                file_size=file_size
            )
            db.add(preroll)
            db.commit()
            db.refresh(preroll)

            results.append({
                "filename": file.filename,
                "uploaded": True,
                "id": preroll.id,
                "thumbnail": thumbnail_path,
                "duration": duration,
                "file_size": file_size
            })
            successful_uploads += 1

        except Exception as e:
            results.append({
                "filename": file.filename,
                "uploaded": False,
                "error": str(e)
            })

    return {
        "total_files": len(files),
        "successful_uploads": successful_uploads,
        "failed_uploads": len(files) - successful_uploads,
        "results": results
    }

@app.get("/prerolls")
def get_prerolls(db: Session = Depends(get_db), category_id: str = "", tags: str = ""):
    query = db.query(models.Preroll)

    # Handle category filtering
    if category_id and category_id.strip():
        try:
            cat_id = int(category_id)
            query = query.filter(models.Preroll.category_id == cat_id)
        except ValueError:
            pass  # Invalid category_id, ignore filter

    # Handle tag filtering
    if tags and tags.strip():
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        for tag in tag_list:
            query = query.filter(models.Preroll.tags.contains(tag))

    prerolls = query.all()
    return [{
        "id": p.id,
        "filename": p.filename,
        "path": p.path,
        "thumbnail": p.thumbnail,
        "tags": p.tags,
        "category": {"id": p.category.id, "name": p.category.name} if p.category else None,
        "description": p.description,
        "duration": p.duration,
        "file_size": p.file_size,
        "upload_date": p.upload_date
    } for p in prerolls]

@app.put("/prerolls/{preroll_id}")
def update_preroll(preroll_id: int, tags: str = None, category_id: int = None, description: str = None, db: Session = Depends(get_db)):
    preroll = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
    if not preroll:
        raise HTTPException(status_code=404, detail="Preroll not found")

    if tags is not None:
        preroll.tags = tags
    if category_id is not None:
        preroll.category_id = category_id
    if description is not None:
        preroll.description = description

    db.commit()
    return {"message": "Preroll updated"}

@app.delete("/prerolls/{preroll_id}")
def delete_preroll(preroll_id: int, db: Session = Depends(get_db)):
    preroll = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
    if not preroll:
        raise HTTPException(status_code=404, detail="Preroll not found")

    # Delete the actual files
    try:
        # Handle new path structure
        full_path = preroll.path
        if not os.path.isabs(full_path):
            full_path = os.path.join(data_dir, full_path)

        if os.path.exists(full_path):
            os.remove(full_path)

        if preroll.thumbnail:
            thumbnail_path = preroll.thumbnail
            if not os.path.isabs(thumbnail_path):
                thumbnail_path = os.path.join(data_dir, thumbnail_path)

            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
    except Exception as e:
        print(f"Warning: Could not delete files for preroll {preroll_id}: {e}")

    # Delete from database
    db.delete(preroll)
    db.commit()

    return {"message": "Preroll deleted successfully"}

@app.get("/tags")
def get_all_tags(db: Session = Depends(get_db)):
    """Get all unique tags from prerolls"""
    prerolls = db.query(models.Preroll).filter(models.Preroll.tags.isnot(None)).all()
    all_tags = set()

    for preroll in prerolls:
        if preroll.tags:
            try:
                tags = json.loads(preroll.tags)
                all_tags.update(tags)
            except:
                # Handle comma-separated tags
                tags = [tag.strip() for tag in preroll.tags.split(',')]
                all_tags.update(tags)

    return {"tags": sorted(list(all_tags))}

@app.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Check if category is used by prerolls or schedules
    preroll_count = db.query(models.Preroll).filter(models.Preroll.category_id == category_id).count()
    schedule_count = db.query(models.Schedule).filter(models.Schedule.category_id == category_id).count()

    if preroll_count > 0 or schedule_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete category that is in use")

    db.delete(category)
    db.commit()
    return {"message": "Category deleted"}

# Category endpoints
@app.post("/categories")
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    db_category = models.Category(name=category.name, description=category.description)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@app.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(models.Category).all()
    return categories

@app.put("/categories/{category_id}")
def update_category(category_id: int, category: CategoryCreate, db: Session = Depends(get_db)):
    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    for key, value in category.dict().items():
        setattr(db_category, key, value)

    db.commit()
    return {"message": "Category updated"}

@app.post("/categories/{category_id}/apply-to-plex")
def apply_category_to_plex(category_id: int, rotation_hours: int = 24, db: Session = Depends(get_db)):
    """Apply a category's videos to Plex as the active preroll with optional rotation"""
    # Get the category
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Get all prerolls in this category
    prerolls = db.query(models.Preroll).filter(models.Preroll.category_id == category_id).all()
    if not prerolls:
        raise HTTPException(status_code=404, detail="No prerolls found in this category")

    # Create semicolon-separated list of all preroll file paths
    preroll_paths = []
    for preroll in prerolls:
        full_local_path = os.path.abspath(preroll.path)
        preroll_paths.append(full_local_path)

    # Join all paths with semicolons for Plex multi-preroll format
    multi_preroll_path = ";".join(preroll_paths)

    # Get Plex settings
    setting = db.query(models.Setting).first()
    if not setting:
        raise HTTPException(status_code=400, detail="Plex not configured")

    # Apply to Plex
    connector = PlexConnector(setting.plex_url, setting.plex_token)

    print(f"Setting {len(prerolls)} prerolls for category '{category.name}':")
    for i, preroll in enumerate(prerolls, 1):
        print(f"  {i}. {preroll.filename}")
    print(f"Combined path: {multi_preroll_path}")

    # Attempt to set the multi-preroll in Plex
    success = False

    if connector.set_preroll(multi_preroll_path):
        success = True
        print("Successfully set multi-preroll using combined file paths")
    else:
        print("Failed to set multi-preroll")

    if success:
        # Mark this category as applied and remove from others
        db.query(models.Category).update({"apply_to_plex": False})
        category.apply_to_plex = True
        db.commit()

        return {
            "message": f"Category '{category.name}' applied to Plex successfully",
            "preroll_count": len(prerolls),
            "prerolls": [p.filename for p in prerolls],
            "rotation_info": "Plex will automatically rotate through all prerolls in this category",
            "plex_updated": True
        }
    else:
        # Don't update the database if Plex update failed
        raise HTTPException(
            status_code=500,
            detail="Failed to update Plex preroll settings. The CinemaTrailersPrerollID could not be set. Please check your Plex server connection and ensure you have the necessary permissions."
        )

@app.post("/categories/{category_id}/remove-from-plex")
def remove_category_from_plex(category_id: int, db: Session = Depends(get_db)):
    """Remove a category from Plex application"""
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    category.apply_to_plex = False
    db.commit()

    return {"message": f"Category '{category.name}' removed from Plex"}


@app.post("/categories/default")
def create_default_category(db: Session = Depends(get_db)):
    """Create a default category for fallback preroll selection"""
    existing = db.query(models.Category).filter(models.Category.name == "Default").first()
    if existing:
        return {"message": "Default category already exists", "category": existing}

    default_category = models.Category(
        name="Default",
        description="Default category for fallback preroll selection when no schedule is active"
    )
    db.add(default_category)
    db.commit()
    db.refresh(default_category)
    return {"message": "Default category created", "category": default_category}

@app.get("/categories/default")
def get_default_category(db: Session = Depends(get_db)):
    """Get the default category for fallback"""
    default_category = db.query(models.Category).filter(models.Category.name == "Default").first()
    return default_category

# Schedule endpoints
@app.post("/schedules")
def create_schedule(schedule: ScheduleCreate, db: Session = Depends(get_db)):
    # Validate category exists
    category = db.query(models.Category).filter(models.Category.id == schedule.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Parse dates from strings
    start_date = None
    end_date = None

    try:
        if schedule.start_date:
            start_date = datetime.datetime.fromisoformat(schedule.start_date.replace('Z', '+00:00'))
        if schedule.end_date:
            end_date = datetime.datetime.fromisoformat(schedule.end_date.replace('Z', '+00:00'))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

    db_schedule = models.Schedule(
        name=schedule.name,
        type=schedule.type,
        start_date=start_date,
        end_date=end_date,
        category_id=schedule.category_id,
        fallback_category_id=schedule.fallback_category_id,
        shuffle=schedule.shuffle,
        playlist=schedule.playlist,
        recurrence_pattern=schedule.recurrence_pattern,
        preroll_ids=schedule.preroll_ids
    )
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)

    # Load the category relationship for the response
    created_schedule = db.query(models.Schedule).options(joinedload(models.Schedule.category)).filter(models.Schedule.id == db_schedule.id).first()

    return {
        "id": created_schedule.id,
        "name": created_schedule.name,
        "type": created_schedule.type,
        "start_date": created_schedule.start_date,
        "end_date": created_schedule.end_date,
        "category_id": created_schedule.category_id,
        "category": {"id": created_schedule.category.id, "name": created_schedule.category.name} if created_schedule.category else None,
        "shuffle": created_schedule.shuffle,
        "playlist": created_schedule.playlist,
        "is_active": created_schedule.is_active,
        "last_run": created_schedule.last_run,
        "next_run": created_schedule.next_run,
        "recurrence_pattern": created_schedule.recurrence_pattern,
        "preroll_ids": created_schedule.preroll_ids
    }

@app.get("/schedules")
def get_schedules(db: Session = Depends(get_db)):
    schedules = db.query(models.Schedule).options(joinedload(models.Schedule.category)).all()
    return [{
        "id": s.id,
        "name": s.name,
        "type": s.type,
        "start_date": s.start_date,
        "end_date": s.end_date,
        "category_id": s.category_id,
        "category": {"id": s.category.id, "name": s.category.name} if s.category else None,
        "shuffle": s.shuffle,
        "playlist": s.playlist,
        "is_active": s.is_active,
        "last_run": s.last_run,
        "next_run": s.next_run,
        "recurrence_pattern": s.recurrence_pattern,
        "preroll_ids": s.preroll_ids
    } for s in schedules]

@app.put("/schedules/{schedule_id}")
def update_schedule(schedule_id: int, schedule: ScheduleCreate, db: Session = Depends(get_db)):
    db_schedule = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Parse dates from strings
    start_date = None
    end_date = None

    try:
        if schedule.start_date:
            start_date = datetime.datetime.fromisoformat(schedule.start_date.replace('Z', '+00:00'))
        if schedule.end_date:
            end_date = datetime.datetime.fromisoformat(schedule.end_date.replace('Z', '+00:00'))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

    # Update fields
    db_schedule.name = schedule.name
    db_schedule.type = schedule.type
    db_schedule.start_date = start_date
    db_schedule.end_date = end_date
    db_schedule.category_id = schedule.category_id
    db_schedule.shuffle = schedule.shuffle
    db_schedule.playlist = schedule.playlist
    db_schedule.recurrence_pattern = schedule.recurrence_pattern
    db_schedule.preroll_ids = schedule.preroll_ids
    db_schedule.fallback_category_id = schedule.fallback_category_id

    db.commit()
    return {"message": "Schedule updated"}

@app.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    db_schedule = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    db.delete(db_schedule)
    db.commit()
    return {"message": "Schedule deleted"}

# Holiday presets
@app.post("/holiday-presets/init")
def initialize_holiday_presets(db: Session = Depends(get_db)):
    # Create default category for holidays if it doesn't exist
    holiday_category = db.query(models.Category).filter(models.Category.name == "Holidays").first()
    if not holiday_category:
        holiday_category = models.Category(name="Holidays", description="Holiday-themed prerolls")
        db.add(holiday_category)
        db.commit()
        db.refresh(holiday_category)

    # Add common holiday presets with month-long date ranges
    holidays = [
        {
            "name": "Christmas",
            "description": "Christmas season (December 1-31)",
            "start_month": 12, "start_day": 1,
            "end_month": 12, "end_day": 31
        },
        {
            "name": "New Year",
            "description": "New Year season (January 1-31)",
            "start_month": 1, "start_day": 1,
            "end_month": 1, "end_day": 31
        },
        {
            "name": "Halloween",
            "description": "Halloween season (October 1-31)",
            "start_month": 10, "start_day": 1,
            "end_month": 10, "end_day": 31
        },
        {
            "name": "Thanksgiving",
            "description": "Thanksgiving season (November 1-30)",
            "start_month": 11, "start_day": 1,
            "end_month": 11, "end_day": 30
        },
        {
            "name": "Valentine's Day",
            "description": "Valentine's season (February 1-28/29)",
            "start_month": 2, "start_day": 1,
            "end_month": 2, "end_day": 29  # Will handle leap year in scheduler
        },
        {
            "name": "Easter",
            "description": "Easter season (April 1-30)",
            "start_month": 4, "start_day": 1,
            "end_month": 4, "end_day": 30
        }
    ]

    for holiday in holidays:
        existing = db.query(models.HolidayPreset).filter(models.HolidayPreset.name == holiday["name"]).first()
        if not existing:
            preset = models.HolidayPreset(
                name=holiday["name"],
                description=holiday["description"],
                # Keep legacy fields for backward compatibility (use first day of range)
                month=holiday["start_month"],
                day=holiday["start_day"],
                # New range fields
                start_month=holiday["start_month"],
                start_day=holiday["start_day"],
                end_month=holiday["end_month"],
                end_day=holiday["end_day"],
                category_id=holiday_category.id
            )
            db.add(preset)

    db.commit()
    return {"message": "Holiday presets initialized"}

@app.get("/holiday-presets")
def get_holiday_presets(db: Session = Depends(get_db)):
    presets = db.query(models.HolidayPreset).all()
    return presets

# Community templates endpoints
@app.get("/community-templates")
def get_community_templates(db: Session = Depends(get_db), category: str = None):
    query = db.query(models.CommunityTemplate)
    if category:
        query = query.filter(models.CommunityTemplate.category == category)
    templates = query.filter(models.CommunityTemplate.is_public == True).all()
    return [{
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "author": t.author,
        "category": t.category,
        "tags": t.tags,
        "downloads": t.downloads,
        "rating": t.rating,
        "created_at": t.created_at
    } for t in templates]

@app.post("/community-templates")
def create_community_template(
    name: str,
    description: str,
    author: str,
    category: str,
    schedule_ids: str,  # JSON array of schedule IDs
    tags: str = None,
    db: Session = Depends(get_db)
):
    """Create a community template from existing schedules"""
    try:
        schedule_id_list = json.loads(schedule_ids)
        schedules = db.query(models.Schedule).filter(models.Schedule.id.in_(schedule_id_list)).all()

        if not schedules:
            raise HTTPException(status_code=404, detail="No schedules found")

        # Create template data
        template_data = {
            "schedules": [{
                "name": s.name,
                "type": s.type,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "category_id": s.category_id,
                "shuffle": s.shuffle,
                "playlist": s.playlist,
                "recurrence_pattern": s.recurrence_pattern,
                "preroll_ids": s.preroll_ids
            } for s in schedules]
        }

        template = models.CommunityTemplate(
            name=name,
            description=description,
            author=author,
            category=category,
            template_data=json.dumps(template_data),
            tags=tags or json.dumps([]),
            is_public=True
        )

        db.add(template)
        db.commit()
        db.refresh(template)

        return {"message": "Template created successfully", "id": template.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template creation failed: {str(e)}")

@app.post("/community-templates/{template_id}/import")
def import_community_template(template_id: int, db: Session = Depends(get_db)):
    """Import a community template into the user's schedules"""
    template = db.query(models.CommunityTemplate).filter(models.CommunityTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        template_data = json.loads(template.template_data)

        # Import schedules
        imported_schedules = []
        for schedule_data in template_data.get("schedules", []):
            # Check if category exists, create if not
            category = None
            if schedule_data.get("category_id"):
                category = db.query(models.Category).filter(models.Category.id == schedule_data["category_id"]).first()

            if not category and schedule_data.get("category_id"):
                # Try to find by name if ID doesn't match
                pass  # For now, skip category linking

            new_schedule = models.Schedule(
                name=f"{schedule_data['name']} (Imported)",
                type=schedule_data["type"],
                start_date=datetime.datetime.fromisoformat(schedule_data["start_date"]) if schedule_data.get("start_date") else None,
                end_date=datetime.datetime.fromisoformat(schedule_data["end_date"]) if schedule_data.get("end_date") else None,
                category_id=schedule_data.get("category_id"),
                shuffle=schedule_data.get("shuffle", False),
                playlist=schedule_data.get("playlist", False),
                recurrence_pattern=schedule_data.get("recurrence_pattern"),
                preroll_ids=schedule_data.get("preroll_ids")
            )

            db.add(new_schedule)
            imported_schedules.append(new_schedule)

        # Increment download count
        template.downloads += 1
        db.commit()

        return {
            "message": "Template imported successfully",
            "imported_schedules": len(imported_schedules)
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@app.post("/community-templates/init")
def initialize_community_templates(db: Session = Depends(get_db)):
    """Initialize with some default community templates"""
    templates = [
        {
            "name": "Christmas Celebration",
            "description": "Festive holiday schedule with Christmas-themed prerolls",
            "author": "NeXroll Team",
            "category": "Holiday",
            "tags": json.dumps(["christmas", "holiday", "festive"]),
            "template_data": json.dumps({
                "schedules": [{
                    "name": "Christmas Morning",
                    "type": "holiday",
                    "start_date": "2024-12-25T08:00:00",
                    "shuffle": True,
                    "playlist": False
                }]
            })
        },
        {
            "name": "Halloween Spooky",
            "description": "Spooky Halloween schedule for trick-or-treaters",
            "author": "NeXroll Team",
            "category": "Holiday",
            "tags": json.dumps(["halloween", "spooky", "fun"]),
            "template_data": json.dumps({
                "schedules": [{
                    "name": "Halloween Night",
                    "type": "holiday",
                    "start_date": "2024-10-31T18:00:00",
                    "shuffle": True,
                    "playlist": False
                }]
            })
        },
        {
            "name": "Monthly Rotation",
            "description": "Basic monthly preroll rotation schedule",
            "author": "NeXroll Team",
            "category": "General",
            "tags": json.dumps(["monthly", "rotation", "basic"]),
            "template_data": json.dumps({
                "schedules": [{
                    "name": "Monthly Update",
                    "type": "monthly",
                    "start_date": "2024-01-01T12:00:00",
                    "shuffle": True,
                    "playlist": False
                }]
            })
        }
    ]

    for template_data in templates:
        existing = db.query(models.CommunityTemplate).filter(
            models.CommunityTemplate.name == template_data["name"]
        ).first()

        if not existing:
            template = models.CommunityTemplate(**template_data)
            db.add(template)

    db.commit()
    return {"message": "Community templates initialized"}

# Scheduler control endpoints
@app.post("/scheduler/start")
def start_scheduler():
    scheduler.start()
    return {"message": "Scheduler started"}

@app.post("/scheduler/stop")
def stop_scheduler():
    scheduler.stop()
    return {"message": "Scheduler stopped"}

@app.get("/scheduler/status")
def get_scheduler_status():
    return {
        "running": scheduler.running,
        "active_schedules": len(scheduler._get_active_schedules()) if hasattr(scheduler, '_get_active_schedules') else 0
    }

@app.post("/scheduler/run-now")
def run_scheduler_now(db: Session = Depends(get_db)):
    """Manually trigger scheduler execution"""
    try:
        scheduler._check_and_execute_schedules()
        return {"message": "Scheduler executed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scheduler execution failed: {str(e)}")

# Stable token workflow endpoints
@app.get("/plex/stable-token/status")
def get_stable_token_status():
    """Check if stable token is configured"""
    connector = PlexConnector(None)  # Will try to load from config
    return {
        "has_stable_token": bool(connector.token),
        "config_file_exists": os.path.exists("plex_config.json"),
        "token_length": len(connector.token) if connector.token else 0
    }

@app.post("/plex/stable-token/save")
def save_stable_token(token: str):
    """Save a stable token manually"""
    connector = PlexConnector(None)
    if connector.save_stable_token(token):
        return {"message": "Stable token saved successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save stable token")

@app.get("/plex/stable-token/config")
def get_stable_token_config():
    """Get current stable token configuration"""
    try:
        if os.path.exists("plex_config.json"):
            with open("plex_config.json", "r") as f:
                config = json.load(f)
                # Don't return the actual token for security
                return {
                    "configured": True,
                    "setup_date": config.get("setup_date"),
                    "note": config.get("note"),
                    "token_length": len(config.get("plex_token", ""))
                }
        else:
            return {"configured": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading config: {str(e)}")

@app.get("/plex/current-preroll")
def get_current_preroll(db: Session = Depends(get_db)):
    """Get the current preroll setting from Plex"""
    setting = db.query(models.Setting).first()
    if not setting:
        raise HTTPException(status_code=400, detail="Plex not configured")

    connector = PlexConnector(setting.plex_url, setting.plex_token)
    current_preroll = connector.get_current_preroll()

    return {
        "current_preroll": current_preroll,
        "has_preroll": current_preroll is not None and current_preroll != ""
    }

@app.delete("/plex/stable-token")
def delete_stable_token():
    """Delete the stable token configuration"""
    try:
        if os.path.exists("plex_config.json"):
            os.remove("plex_config.json")
            return {"message": "Stable token configuration deleted"}
        else:
            return {"message": "No stable token configuration found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting config: {str(e)}")

# Backup and Restore endpoints
@app.get("/backup/database")
def backup_database(db: Session = Depends(get_db)):
    """Export database to JSON"""
    try:
        # Export all data
        data = {
            "prerolls": [
                {
                    "filename": p.filename,
                    "path": p.path,
                    "thumbnail": p.thumbnail,
                    "tags": p.tags,
                    "category_id": p.category_id,
                    "description": p.description,
                    "upload_date": p.upload_date.isoformat() if p.upload_date else None
                } for p in db.query(models.Preroll).all()
            ],
            "categories": [
                {
                    "name": c.name,
                    "description": c.description
                } for c in db.query(models.Category).all()
            ],
            "schedules": [
                {
                    "name": s.name,
                    "type": s.type,
                    "start_date": s.start_date.isoformat() if s.start_date else None,
                    "end_date": s.end_date.isoformat() if s.end_date else None,
                    "category_id": s.category_id,
                    "shuffle": s.shuffle,
                    "playlist": s.playlist,
                    "is_active": s.is_active,
                    "recurrence_pattern": s.recurrence_pattern,
                    "preroll_ids": s.preroll_ids
                } for s in db.query(models.Schedule).all()
            ],
            "holiday_presets": [
                {
                    "name": h.name,
                    "description": h.description,
                    "month": h.month,
                    "day": h.day,
                    "category_id": h.category_id
                } for h in db.query(models.HolidayPreset).all()
            ],
            "exported_at": datetime.datetime.utcnow().isoformat()
        }

        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")

@app.post("/backup/files")
def backup_files():
    """Create ZIP archive of all preroll files"""
    try:
        # Create in-memory ZIP file
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add preroll files
            prerolls_dir = Path(os.path.join(data_dir, "prerolls"))
            if prerolls_dir.exists():
                for file_path in prerolls_dir.rglob("*"):
                    if file_path.is_file():
                        # Add file to ZIP with relative path
                        zip_file.write(file_path, file_path.relative_to(prerolls_dir.parent))

        zip_buffer.seek(0)
        return {
            "filename": f"prerolls_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            "content": zip_buffer.getvalue(),
            "content_type": "application/zip"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File backup failed: {str(e)}")

@app.post("/restore/database")
def restore_database(backup_data: dict, db: Session = Depends(get_db)):
    """Import database from JSON backup"""
    try:
        # Clear existing data
        db.query(models.Preroll).delete()
        db.query(models.Category).delete()
        db.query(models.Schedule).delete()
        db.query(models.HolidayPreset).delete()
        db.commit()

        # Restore categories first (needed for foreign keys)
        for cat_data in backup_data.get("categories", []):
            category = models.Category(
                name=cat_data["name"],
                description=cat_data.get("description")
            )
            db.add(category)
        db.commit()

        # Get category mapping
        category_map = {c.name: c.id for c in db.query(models.Category).all()}

        # Restore prerolls
        for preroll_data in backup_data.get("prerolls", []):
            preroll = models.Preroll(
                filename=preroll_data["filename"],
                path=preroll_data["path"],
                thumbnail=preroll_data.get("thumbnail"),
                tags=preroll_data.get("tags"),
                category_id=preroll_data.get("category_id"),
                description=preroll_data.get("description"),
                upload_date=datetime.datetime.fromisoformat(preroll_data["upload_date"]) if preroll_data.get("upload_date") else None
            )
            db.add(preroll)

        # Restore schedules
        for schedule_data in backup_data.get("schedules", []):
            schedule = models.Schedule(
                name=schedule_data["name"],
                type=schedule_data["type"],
                start_date=datetime.datetime.fromisoformat(schedule_data["start_date"]) if schedule_data.get("start_date") else None,
                end_date=datetime.datetime.fromisoformat(schedule_data["end_date"]) if schedule_data.get("end_date") else None,
                category_id=schedule_data.get("category_id"),
                shuffle=schedule_data.get("shuffle", False),
                playlist=schedule_data.get("playlist", False),
                is_active=schedule_data.get("is_active", True),
                recurrence_pattern=schedule_data.get("recurrence_pattern"),
                preroll_ids=schedule_data.get("preroll_ids")
            )
            db.add(schedule)

        # Restore holiday presets
        for holiday_data in backup_data.get("holiday_presets", []):
            holiday = models.HolidayPreset(
                name=holiday_data["name"],
                description=holiday_data.get("description"),
                month=holiday_data["month"],
                day=holiday_data["day"],
                category_id=holiday_data.get("category_id")
            )
            db.add(holiday)

        db.commit()
        return {"message": "Database restored successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")

@app.post("/restore/files")
def restore_files(file: UploadFile = File(...)):
    """Import preroll files from ZIP archive"""
    try:
        # Create backup directory if it doesn't exist
        backup_dir = Path("prerolls_backup")
        backup_dir.mkdir(exist_ok=True)

        # Save uploaded ZIP file temporarily
        zip_path = backup_dir / "temp_restore.zip"
        with open(zip_path, "wb") as f:
            content = file.file.read()
            f.write(content)

        # Extract ZIP file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(os.path.join(data_dir, "prerolls"))

        # Clean up temp file
        zip_path.unlink()

        return {"message": "Files restored successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File restore failed: {str(e)}")

@app.post("/maintenance/fix-thumbnail-paths")
def fix_thumbnail_paths(db: Session = Depends(get_db)):
    """Fix thumbnail paths in database to remove 'data/' prefix for static serving"""
    try:
        prerolls = db.query(models.Preroll).filter(models.Preroll.thumbnail.isnot(None)).all()
        updated_count = 0

        for preroll in prerolls:
            if preroll.thumbnail and preroll.thumbnail.startswith("data/"):
                # Remove 'data/' prefix
                new_path = preroll.thumbnail.replace("data/", "", 1)
                preroll.thumbnail = new_path
                updated_count += 1

        db.commit()
        return {"message": f"Fixed {updated_count} thumbnail paths"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error fixing thumbnail paths: {str(e)}")

# Debug: Print current working directory
print(f"Backend running from: {os.getcwd()}")

# Get absolute paths for static files
# Get absolute paths for static files relative to project root
# Determine install and resource roots
if getattr(sys, "frozen", False):
    install_root = os.path.dirname(sys.executable)
    resource_root = getattr(sys, "_MEIPASS", install_root)
else:
    install_root = os.path.dirname(os.path.dirname(__file__))
    resource_root = install_root
frontend_dir = os.path.join(resource_root, "frontend")

def _get_windows_preroll_path_from_registry():
    try:
        if sys.platform.startswith("win"):
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\NeXroll")
            value, _ = winreg.QueryValueEx(key, "PrerollPath")
            winreg.CloseKey(key)
            if value and str(value).strip():
                return str(value).strip()
    except Exception:
        return None
    return None

def _resolve_data_dir(project_root_path: str) -> str:
    # Priority: ENV var -> Windows Registry -> default inside install dir
    env_path = os.getenv("NEXROLL_PREROLL_PATH")
    if env_path and env_path.strip():
        return env_path.strip()
    reg_path = _get_windows_preroll_path_from_registry()
    if reg_path and reg_path.strip():
        return reg_path.strip()
    return os.path.join(project_root_path, "data")

data_dir = _resolve_data_dir(install_root)

# Create necessary directories
os.makedirs(os.path.join(data_dir, "prerolls"), exist_ok=True)
os.makedirs(os.path.join(data_dir, "prerolls", "thumbnails"), exist_ok=True)

# Debug prints
print(f"Backend running from: {os.getcwd()}")
print(f"Frontend dir: {frontend_dir}")
print(f"Data dir: {data_dir}")

# Static files for prerolls
app.mount("/data", StaticFiles(directory=data_dir), name="data")

# Static files for preroll thumbnails (frontend expects them at /static/prerolls/thumbnails)
app.mount("/static/prerolls/thumbnails", StaticFiles(directory=os.path.join(data_dir, "prerolls/thumbnails")), name="thumbnails")



# Mount frontend static files LAST so API routes are checked first
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9393, log_config=None)