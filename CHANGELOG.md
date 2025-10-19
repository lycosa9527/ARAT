# Changelog

All notable changes to the ARAT (Associative Reasoning Assessment Tool) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Admin Panel** - Complete admin interface at `/admin` with three main sections:
  - **Database Manager**: View, filter, edit, and delete puzzle inventory
    - Filter by language (Chinese/English) and difficulty (Easy/Medium/Hard/Professional)
    - Manual search with "Find Puzzles" button (on-demand loading)
    - Pagination controls (25/50/100 records per page)
    - Display puzzles in A+B=C format
    - Edit and delete functionality for individual puzzles
  - **Inventory Status**: View diversity analysis metrics
    - Percentage of unique words/characters used per difficulty level
    - Total puzzle counts by language and difficulty
  - **Game Demo**: Embedded game demo for testing
  - Passkey protection (default: `888888`)

### Changed
- **`.gitignore`**: Added exception for `wordbridge.db` to allow version control tracking
  - Puzzle inventory database is now included in repository
  - Other `.db` files remain ignored
- **Database Manager UI**: Improved button styling
  - Enhanced "Find Puzzles" button with gradient background and shadow effects
  - Refined "Clear" button styling for better visual hierarchy
  - Added hover and active state animations

### Fixed
- **Admin Panel Performance**: Filters now load instantly
  - Moved filter controls to static HTML (no API call delay)
  - Database only loads when "Find Puzzles" button is clicked
  - Improved user experience with progressive loading

### Removed
- **Inventory Cleanup**: Deleted 5 problematic Chinese puzzles
  - Removed puzzles where any word (A, B, or C) was longer than 2 characters
  - Affected puzzles: IDs 822, 863, 2335, 3687, 3694
  - Remaining Chinese inventory: 2,387 puzzles (from 2,392)
  - English puzzles remain untouched

### Database
- **Current Inventory Stats** (as of cleanup):
  - **Chinese**: 2,387 puzzles
    - Easy: 1,139
    - Medium: 645
    - Hard: 290
    - Professional: 313
  - **English**: Unchanged
  - **Database Size**: ~1.6 MB

### Technical Details
- Added API endpoints for admin panel:
  - `GET /api/admin/database/records` - Fetch puzzle inventory with filters
  - `GET /api/admin/diversity/stats` - Get diversity analysis metrics
  - `POST /api/admin/puzzle_inventory/update` - Update puzzle data
  - `POST /api/admin/puzzle_inventory/delete` - Delete puzzles
- Admin panel uses session storage for authentication persistence
- Implemented client-side pagination and filtering

---

## [0.1.0] - Initial Release

### Added
- Core game functionality
- FastAPI backend
- SQLite database with puzzle inventory
- Basic game interface
- LLM-generated puzzle system

---

*Note: Version numbers will be updated upon formal releases.*

