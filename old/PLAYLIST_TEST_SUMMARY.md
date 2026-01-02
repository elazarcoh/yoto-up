# Playlist Workflow Functionality Test - Executive Summary

**Date:** December 25, 2025  
**Server:** http://localhost:8000  
**Tested By:** Automated Browser Testing  
**Status:** 🔴 **6 CRITICAL ISSUES FOUND** (Extended testing with DEBUG playlist)

---

## Quick Status Overview (Extended)

| Category | Status | Notes |
|----------|--------|-------|
| View Playlists | ✅ **PASS** | All 14 playlists display correctly |
| Filter Playlists | ✅ **PASS** | Title and category filters work |
| Playlist Details | ✅ **PASS** | Detail pages load and display content |
| Create Playlist | ❌ **FAIL** | 405 error - endpoint missing |
| Icon Display | ❌ **FAIL** | 500 errors on icon requests |
| Upload Items | ✅ **PASS** | Modal and controls work (not tested actual upload) |
| **Change Cover** | ❌ **FAIL** | HTMX error - endpoint issue |
| **Edit Mode** | ✅ **PASS** | Checkboxes and expand/collapse work |
| **Delete Selected** | ❌ **FAIL** | 404 error - endpoint missing |
| **Change Icon** | ❌ **FAIL** | JavaScript error - function undefined |
| Edit Metadata | ⚠️ **PARTIAL** | No dialog for title/author/category |
| Delete Playlist | ✅ **PASS** | Deletion confirmation works |
| Bulk Operations | ⚠️ **NOT VISIBLE** | UI controls missing |
| Import/Export | ⚠️ **NOT VISIBLE** | UI controls missing |

---

## Original Quick Status Overview

| Category | Status | Notes |
|----------|--------|-------|
| View Playlists | ✅ **PASS** | All 14 playlists display correctly |
| Filter Playlists | ✅ **PASS** | Title and category filters work |
| Playlist Details | ✅ **PASS** | Detail pages load and display content |
| Create Playlist | ❌ **FAIL** | 405 error - endpoint missing |
| Icon Display | ❌ **FAIL** | 500 errors on icon requests |
| Edit Metadata | ⚠️ **PARTIAL** | No dialog for title/author/category |
| Delete Playlist | ✅ **PASS** | Deletion confirmation works |
| Bulk Operations | ⚠️ **NOT VISIBLE** | UI controls missing |
| Import/Export | ⚠️ **NOT VISIBLE** | UI controls missing |

---

## Critical Issues (Must Fix)

### 🔴 Issue #1: Create Playlist Returns 405 Error
**Impact:** Users cannot create new playlists  
**Error:** `405 Method Not Allowed on /playlists/create-with-cover`

**Problem:**
```
Frontend (template):  POST /playlists/create-with-cover
Backend (router):     @router.post("/create")
```

The endpoint names don't match. The modal tries to POST to `/playlists/create-with-cover` but the router only has `/playlists/create`.

**Quick Fix:**
Add this endpoint to `src/yoto_up_server/routers/playlists.py`:
```python
@router.post("/create-with-cover", response_class=HTMLResponse)
async def create_playlist_with_cover(
    request: Request,
    api_service: AuthenticatedApiDep,
    title: Annotated[str, Form(...)],
    cover_file: Optional[UploadFile] = File(None),
    cover_url: Optional[str] = Form(None),
) -> str:
    """Create playlist with optional cover image"""
    # Implementation...
```

**Status:** Not Fixed ❌

---

### 🔴 Issue #2: Icon Display Broken
**Impact:** Playlist detail pages show 11 icon 500 errors  
**Error:** `500 Internal Server Error on /icons/{id}/image?size=16`

**Problem:**
Each chapter tries to load its 16x16 icon. The endpoint is returning 500 errors repeatedly. This suggests:
- Icon service failing to retrieve images
- Missing file or permission issues
- Problems with icon URL handling

**Evidence:**
```
[ERROR] Failed to load resource: the server responded with a status of 500 
@ http://localhost:8000/icons/W-2RUBud_e1PlHw03Mj73sqyLKibjZjNfyiQ1GWtvx4/image?size=16
(repeated 11 times)
```

**Quick Fix:**
Check `/src/yoto_up_server/routers/icons.py` and add error handling:
```python
@router.get("/{icon_id}/image", response_class=FileResponse)
async def get_icon_image(icon_id: str, size: int = 16):
    try:
        # Fetch and return icon
        icon_file = get_icon_file(icon_id, size)
        if not icon_file:
            return FileResponse("default-icon.png")
        return FileResponse(icon_file)
    except Exception as e:
        logger.error(f"Icon retrieval failed for {icon_id}: {e}")
        return FileResponse("default-icon.png")  # Fallback
```

**Status:** Not Fixed ❌

---

## High Priority Issues (Should Fix)

### 🟡 Issue #3: Edit Metadata Dialog Missing
**Impact:** Users cannot edit playlist title, author, or category  
**Current State:** Edit button only shows chapter checkboxes, not metadata

**Fix:**
Add metadata edit form to detail page template

---

### 🟡 Issue #4: Bulk Operations Hidden
**Impact:** No UI for multi-select, delete selected, or export selected  
**Current State:** Buttons exist in code but aren't rendered on list page

**Fix:**
Add bulk operation controls to playlist list template

---

### 🟡 Issue #5: Import/Export Controls Missing
**Impact:** Cannot access import/export functionality from UI  
**Current State:** Mentioned in code but no UI controls visible

**Fix:**
Add import/export buttons to main playlist list page

---

## Test Evidence

### Working Features ✅
- **Playlist List Page:** Displays 14 playlists with covers, titles, categories
- **Title Filter:** Tested with "בוקר", correctly filtered results
- **Category Filter:** Dropdown available with all category options
- **Clear Filters:** Successfully resets all filters
- **View Details:** Navigates to detail page, shows all chapters
- **Display JSON:** Shows full playlist JSON structure
- **Delete Confirmation:** Dialog appears before deletion
- **Responsive Design:** Page works on desktop viewport

### Broken Features ❌
- **Create Playlist:** 405 Method Not Allowed
- **Icon Requests:** Multiple 500 errors for icon images
- **Edit Metadata:** No form to edit title/author/category

### Missing Features ⚠️
- **Bulk Select:** No checkboxes on list items
- **Select All Button:** Not visible
- **Delete Selected:** Not visible
- **Export Selected:** Not visible
- **Import Button:** Not visible on main page

---

## Test Results Summary

```
Total Features Tested:      10 categories
✅ Fully Working:           5 (50%)
⚠️  Partially Working:      3 (30%)
❌ Broken:                  2 (20%)

Critical Issues:            2
High Priority Issues:       3
```

---

## Files to Modify

1. **`src/yoto_up_server/routers/playlists.py`**
   - Add `/create-with-cover` endpoint
   - Add `/update-metadata` endpoint
   - Add `/{playlist_id}/delete-selected` endpoint (NEW)
   - Add `/{playlist_id}/change-cover` endpoint (NEW)

2. **`src/yoto_up_server/routers/icons.py`**
   - Fix icon image retrieval endpoint
   - Add error handling for missing icons

3. **`src/yoto_up_server/templates/playlists.py`**
   - Add metadata edit dialog to detail view
   - Add bulk operation controls to list view
   - Add import/export buttons

4. **`src/yoto_up_server/templates/upload_components.py`**
   - Update form action to use correct endpoint (optional)

5. **Frontend JavaScript (LOCATION TBD)**
   - Implement `openIconSidebar()` function (NEW)

---

## Next Steps

1. **Immediately Fix:**
   - Add missing `/playlists/create-with-cover` endpoint
   - Fix `/icons/{id}/image` endpoint

2. **Soon After:**
   - Add metadata edit functionality
   - Implement bulk operations UI

3. **Testing Checklist:**
   - [ ] Test create playlist with title only
   - [ ] Test create playlist with cover image
   - [ ] Verify icon display on detail page
   - [ ] Test edit title/author/category
   - [ ] Test bulk delete
   - [ ] Test bulk export
   - [ ] Test import playlist

---

## Screenshots & Evidence

- See `PLAYLIST_FUNCTIONALITY_TEST.md` for detailed issue analysis
- See `.playwright-mcp/` folder for screenshot evidence:
  - `1-homepage.png` - Home page
  - `2-playlists-list.png` - Playlists list with filter
  - `3-detail-page-with-500-errors.png` - Playlist detail showing icon errors

