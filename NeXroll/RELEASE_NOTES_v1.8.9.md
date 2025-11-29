# NeXroll v1.8.9 Release Notes

**Release Date:** November 28, 2025  
**Version Jump:** 1.7.16 → 1.8.9

---

## Overview

Version 1.8.9 represents a significant advancement in NeXroll's capabilities, jumping from v1.7.16 with major improvements to holiday scheduling, tag management, and data backup systems. This release focuses on enhancing the user experience with an expanded holiday library, modernized tag interface, and comprehensive backup protection for sequences.

---

## What's New

### Sequence Builder (NEW)

A powerful new visual tool for creating custom preroll sequences with precise control over playback order, timing, and category selection.

**Key Features:**
- **Visual Block-Based Interface:** Drag-and-drop blocks representing individual prerolls or category selections
- **Timeline Preview:** See the complete sequence structure at a glance with duration indicators
- **Multiple Block Types:**
  - Single preroll selection
  - Category-based selection (random or sequential)
  - Time-based duration controls
- **Real-time Validation:** Instant feedback on sequence structure and compatibility
- **Save & Load:** Store custom sequences for reuse across different schedules
- **Export/Import:** Share sequences between NeXroll instances
- **Preview Mode:** Test sequences before applying them to schedules

**Technical Features:**
- Block-level metadata storage
- JSON-based sequence format for portability
- Integration with existing preroll and category systems
- Support for complex multi-category sequences

**Impact:** Users can now create sophisticated, predictable preroll sequences for special events, themed nights, or custom playback patterns that go beyond simple random or sequential category playback.

---

### Expanded Holiday Preset Library

NeXroll now includes **32 comprehensive holiday presets**, up from the original 6, covering a diverse range of cultural celebrations, seasonal events, and special occasions throughout the year.

**New Holidays Added:**
- **Winter Holidays:** Hanukkah, Kwanzaa
- **Spring Celebrations:** St. Patrick's Day, Passover, Cinco de Mayo, Mother's Day, Memorial Day
- **Summer Events:** Father's Day, Independence Day, Labor Day
- **Fall Observances:** Veterans Day
- **Cultural & International:** Diwali, Chinese New Year, Mardi Gras, Ramadan, Eid al-Fitr, Day of the Dead, Martin Luther King Jr. Day
- **Seasonal Themes:** Spring Season, Summer Season, Fall Season, Winter Season
- **Special Events:** Back to School, Black Friday, Cyber Monday, Earth Day, Pride Month

**Key Features:**
- Each holiday includes carefully selected date ranges for optimal scheduling
- Seamless integration with the Holiday Preset dropdown in schedule creation
- Extended date ranges for major holidays (Christmas, Halloween, Thanksgiving now span full months)
- Automatic date population when selecting holiday presets in schedule forms

**Impact:** Users can now schedule themed prerolls for virtually any holiday or seasonal event throughout the year, enabling more dynamic and relevant content delivery.

---

### Enhanced Tag Management System

A complete overhaul of the tag management interface provides a modern, intuitive experience for organizing and categorizing prerolls.

**New Features:**
- **Visual Tag Display:** Tags appear as clean purple pill-shaped badges in both grid and list views
- **Interactive Tag Editor:** Chip-based interface in Edit Preroll modal for easy tag management
- **Browse Dropdown:** Quick selection button showing all available tags in the system
- **Individual Removal:** Each tag chip includes an X button for instant removal
- **Autocomplete Support:** Smart suggestions when typing tag names
- **Dual Format Support:** Handles both JSON array format and legacy comma-separated strings

**Visual Improvements:**
- Removed emoji icons for cleaner appearance
- Consistent purple theme across all views
- Optimized badge font size for readability (0.7-0.8rem)
- Tags display as clean text without JSON brackets or formatting artifacts

**Impact:** Tag management is now significantly faster and more intuitive, with a modern interface that matches contemporary UI standards.

---

### Backup and Restore Enhancements

Critical improvements to data protection ensure that sequences are fully preserved during backup and restore operations.

**Enhanced Backup Coverage:**
- **Database Backups:** Sequences table now included in all database exports
- **Files Backups:** `/sequences/` directory included alongside `/prerolls/` in ZIP archives
- **Metadata Preservation:** Sequence names, descriptions, block structures, and timestamps maintained
- **Block Structure Integrity:** Complex sequence block JSON structures preserved through backup cycle

**Improved Restore Operations:**
- Proper deletion and recreation of sequences with full data integrity
- Enhanced datetime parsing with fallback handling for sequence timestamps
- Per-sequence error logging during restore operations
- Cascade deletion handling for sequence dependencies

**Impact:** Complete data protection for both prerolls and sequences with zero data loss during backup operations. Users can confidently backup and restore their entire NeXroll configuration including all custom sequences.

---

## Changes & Improvements

### Tag Display Format

- Removed emoji icons from tag badges for professional appearance
- Implemented robust JSON parsing to handle array string format tags
- Standardized purple color theme (#8b5cf6) across all tag displays
- Fixed tags displaying with JSON array brackets in UI
- Resolved parsing errors with legacy comma-separated format
- Added proper event parameter declaration to fix ESLint warnings

### Holiday Preset Date Ranges

- **Christmas:** Extended to full month (December 1-31)
- **Halloween:** Extended to full month (October 1-31)
- **Thanksgiving:** Extended to full month (November 1-30)
- All new holidays configured with culturally appropriate observation periods
- Schedule form automatically populates start and end dates based on preset selection

### Backup System Architecture

- Database backup endpoint updated to export sequences table alongside existing tables
- Files backup endpoint enhanced with `/sequences/` directory traversal
- Restore endpoint includes proper sequence deletion cascade before recreation
- Improved error handling for malformed sequence data during restore
- Enhanced logging for troubleshooting backup/restore operations

---

## Bug Fixes

### Tag System Fixes

- Fixed tags displaying with JSON array brackets [tag1, tag2] instead of clean text
- Fixed emoji icons appearing alongside tag text in badge displays
- Resolved parsing errors when tags stored as stringified JSON arrays
- Added fallback parsing for comma-separated legacy tag format
- Corrected ESLint error regarding event parameter declaration in tag editor

### Backup Data Integrity

- Fixed sequences not being included in database backup exports
- Fixed sequence video files and thumbnails not included in ZIP archives
- Fixed restore operations failing to recreate sequence records in database
- Added proper error handling for malformed sequence JSON data during restore
- Fixed sequence timestamps not parsing correctly during restore operations

---

## Technical Details

### Sequence Builder Architecture

- **New Components:**
  - `SequenceBuilder.js` - Main builder interface with block management
  - `SequenceBlock.js` - Individual block representation
  - `SequenceTimeline.js` - Visual timeline preview
  - `SequencePreview.js` - Playback preview modal
  - `SequencePreviewModal.js` - Full-screen sequence viewer
  - `SequenceStats.js` - Sequence statistics display
  - `BlockEditor.js` - Block configuration interface
- **Validation:** `sequenceValidator.js` utility for structure validation
- **Storage:** JSON-based sequence format with block-level metadata
- **API Integration:** Endpoints for save, load, export, and import operations

### Database Changes

- Sequences table now included in backup/restore SQL exports
- Enhanced sequence data validation during restore operations
- Improved cascade deletion handling for sequence dependencies
- Sequence metadata storage for custom playback patterns

### API Enhancements

- `/api/backup/database` endpoint updated to include sequences table
- `/api/backup/files` endpoint enhanced to traverse `/sequences/` directory
- `/api/restore/database` endpoint improved with sequence recreation logic
- `/api/restore/files` endpoint handles sequence file extraction
- `/api/holiday-presets/init` endpoint now returns detailed statistics

### Frontend Updates

- New sequence builder interface with drag-and-drop functionality
- Enhanced schedule creation with sequence builder integration
- New tag editor component with chip-based interface
- Enhanced tag parsing utilities with dual format support
- Improved error handling for tag-related operations and holiday initialization
- Holiday preset data structure expanded to 32 entries
- Schedule form date auto-population logic enhanced

### File Structure

- `/sequences/` directory now included in backup ZIP files
- Sequence thumbnails preserved in backup archives
- Video files linked to sequences included in full backups

---

## Upgrade Notes

### From v1.7.16 to v1.8.9

This is a significant version jump that includes multiple major feature additions and improvements. The upgrade process is seamless:

**Docker Users:**
```bash
docker pull jbrns/nexroll:1.8.9
docker-compose down
docker-compose up -d
```

**Windows Users:**
1. Download NeXroll_Installer_v1.8.9.exe
2. Run the installer (will upgrade existing installation)
3. Restart NeXroll service

**Data Compatibility:**
- All existing prerolls, categories, schedules, and sequences remain fully compatible
- Tags stored in legacy comma-separated format will be automatically parsed
- No manual migration required for holiday presets
- Existing backups from v1.7.16 can be restored in v1.8.9
- Backups created in v1.8.9 include additional sequence data

**Recommendations:**
- Create a full backup before upgrading (standard best practice)
- Review the new holiday presets and consider creating schedules for upcoming events
- Test tag editing functionality on a sample preroll to familiarize yourself with the new interface
- Create a new backup after upgrade to take advantage of enhanced sequence protection

---

## Known Issues

- None reported at time of release

---

## Coming Soon

Future releases will focus on:
- Enhanced sequence builder with timeline visualization
- Pattern export/import system for sharing sequence configurations
- Full sequence pack system with video file bundling
- Advanced scheduling with conflict detection
- Multi-server management enhancements

---

## Support & Feedback

**Docker Image:** jbrns/nexroll:1.8.9  
**GitHub Repository:** https://github.com/JFLXCLOUD/NeXroll  
**Documentation:** https://github.com/JFLXCLOUD/NeXroll/wiki  

For bug reports, feature requests, or general support, please open an issue on GitHub.

---

## Credits

Thank you to all users who provided feedback and suggestions that shaped this release. Special recognition for feature requests around holiday scheduling and tag management that directly influenced v1.8.9's development priorities.

---

**Full Changelog:** See CHANGELOG.md for complete technical details of all changes since v1.7.16.
