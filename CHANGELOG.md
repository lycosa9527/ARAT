# Changelog

All notable changes to the ARAT (Associative Reasoning Assessment Tool) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Puzzle Validation System** - Comprehensive validation to ensure puzzle quality
  - Added `validate_puzzle_uniqueness()` function to check puzzle validity
  - Validation rules: Answer must be different from all input characters/words
  - LLM generation now includes automatic retry logic (up to 3 attempts) for invalid puzzles
  - Database loading automatically filters out invalid puzzles
  - Admin endpoint: `GET /api/admin/puzzle_inventory/validate` - Scan for invalid puzzles
  - Admin endpoint: `POST /api/admin/puzzle_inventory/cleanup` - Auto-delete invalid puzzles

- **Leaderboard Footer** - Added informational footer with clickable About link
  - Directs users to learn more about the application
  - "关于" (About) link opens the About modal directly from leaderboard
  - Smooth modal transition with proper styling
  - Fully internationalized (Chinese/English)

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
- **LLM Prompts Enhanced** - Updated puzzle generation prompts with stricter rules
  - Chinese prompt now explicitly forbids answer = char1 or char2
  - English prompt now explicitly forbids answer matching any input word
  - Added examples and CRITICAL rule sections in both prompts

- **Mobile Responsive Design** - Major improvements for mobile user experience
  - **Game Boxes**: Increased character/answer box sizes on mobile devices
    - Tablet (≤768px): 110×110px (was 80×80px)
    - Small mobile (≤480px): 95×95px (was 85×85px)
    - Very small (≤380px): 85×85px (was 75×75px)
    - Horizontal scroll enabled for overflow
  - **Modal Scrolling**: All modals now fully scrollable on mobile
    - Added `max-height: 90vh` and `overflow-y: auto`
    - Smooth iOS scrolling with `-webkit-overflow-scrolling: touch`
    - Custom scrollbar styling for better visibility
    - Fixed captcha modal getting stuck on mobile
  - **Score Modal Header**: Compact layout on mobile
    - Emoji and "Game Over" text now side by side (saves vertical space)
    - Reduced padding and font sizes on small screens
    - More room for form fields and captcha
  - **About Modal**: Cat emoji 🐈‍⬛ and ARAT title now side by side on desktop/tablet
    - Stacks vertically only on very small screens (≤380px)
    - Better brand presentation
  
- **`.gitignore`**: Added exception for `wordbridge.db` to allow version control tracking
  - Puzzle inventory database is now included in repository
  - Other `.db` files remain ignored
  
- **Database Manager UI**: Improved button styling
  - Enhanced "Find Puzzles" button with gradient background and shadow effects
  - Refined "Clear" button styling for better visual hierarchy
  - Added hover and active state animations

### Fixed
- **Code Quality** - Fixed indentation error in `routers/api.py` line 524
  - Corrected `else:` statement alignment
  
- **Leaderboard UI** - Fixed button visibility issue
  - Period filter buttons (全部/本周/今日) now remain visible when active
  - Added explicit `display`, `visibility`, and `opacity` properties
  - Fixed `--primary-color` CSS variable definition
  
- **Captcha Display** - Fixed captcha image rendering
  - Changed from `object-fit: cover` to `object-fit: fill` for proper display
  - Set fixed container height (80px) matching captcha dimensions (200x80px)
  - Image now always fills its border completely
  - Refresh button resized to match (80x80px)
  - Improved visual consistency across all screen sizes
  
- **Admin Panel Performance**: Filters now load instantly
  - Moved filter controls to static HTML (no API call delay)
  - Database only loads when "Find Puzzles" button is clicked
  - Improved user experience with progressive loading

### Removed
- **Major Inventory Cleanup**: Deleted 103 invalid puzzles (October 19, 2025)
  - Removed puzzles where answer matched input characters/words
  - 83 Chinese puzzles removed (answer = char1, answer = char2, or char1 = char2)
  - 20 English puzzles removed (answer matched word1/word2/word3 or duplicate inputs)
  - Remaining inventory: 4,022 valid puzzles (from 4,125)
  - All future puzzles now validated automatically

- **Previous Cleanup**: Deleted 5 problematic Chinese puzzles
  - Removed puzzles where any word (A, B, or C) was longer than 2 characters
  - Affected puzzles: IDs 822, 863, 2335, 3687, 3694
  - This was before the major validation cleanup above

### Database
- **Current Inventory Stats** (as of October 19, 2025):
  - **Total Valid Puzzles**: 4,022 (down from 4,125 after cleanup)
  - **Chinese**: ~3,200 puzzles (estimated, 83 removed)
  - **English**: ~800 puzzles (estimated, 20 removed)
  - **Validation Status**: 100% valid (all invalid puzzles removed)
  - **Database Size**: ~1.6 MB

### Technical Details
- Added API endpoints for admin panel:
  - `GET /api/admin/database/records` - Fetch puzzle inventory with filters
  - `GET /api/admin/diversity/stats` - Get diversity analysis metrics
  - `GET /api/admin/puzzle_inventory/validate` - Scan for invalid puzzles
  - `POST /api/admin/puzzle_inventory/cleanup` - Auto-delete invalid puzzles
  - `POST /api/admin/puzzle_inventory/update` - Update puzzle data
  - `POST /api/admin/puzzle_inventory/delete` - Delete puzzles

- Puzzle validation system:
  - `validate_puzzle_uniqueness()` function in `services/game_service.py`
  - LLM retry logic: up to 3 attempts for valid puzzle generation
  - Database filtering: invalid puzzles automatically excluded during loading
  - Validation rules enforced in both Chinese and English puzzle generation

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

