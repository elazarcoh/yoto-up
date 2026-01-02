# Extended Playlist Testing Report - DEBUG Playlist Playground

**Date:** December 25, 2025  
**Test Subject:** DEBUG Playlist (eiPsE) - Used as test playground  
**Status:** 🔴 **4 CRITICAL ISSUES FOUND**

---

## Test Summary

### Overview
Comprehensive testing of playlist editing features using the DEBUG playlist as a controlled test environment. Tested upload, deletion, cover change, chapter reordering, and icon management features.

**Results:**
- ✅ **Working:** Upload Items, Expand/Collapse, Checkboxes, Selection
- ⚠️ **Partial:** Edit Mode activated, but delete fails
- ❌ **Broken:** Change Cover, Delete Selected, Change Icon

---

## Detailed Feature Test Results

### Feature #11: Upload Items Feature
**Status:** ✅ **PASS** (UI Only)

**What Works:**
- Upload Items modal opens successfully
- File selection dialog appears when clicking "Select Files"
- Folder selection button ("📂 Select Folder") available
- Upload As option with radio buttons:
  - ✅ Chapters (default selected)
  - ✅ Tracks
- Additional options available:
  - ✅ Normalize Audio (checkbox)
  - ✅ Analyze Intro/Outro (checkbox)
  - ✅ Show waveform visualization (checkbox)
- Upload button appears and is disabled until files selected

**What Doesn't Work:**
- No files were uploaded (wouldn't test actual upload to avoid data changes)

**Evidence:**
See screenshot `4-debug-playlist-detail.png` and `5-edit-mode-features.png`

---

### Feature #12: Change Cover Feature
**Status:** ❌ **FAIL** - Endpoint Missing

**Issue:**
When clicking the "🖼️ Change Cover" button, an HTMX error occurs:
```
[ERROR] htmx:targetError @ https://unpkg.com/htmx.org@2.0.4:0
```

**Root Cause:**
The button likely triggers a POST to an endpoint that doesn't exist or isn't properly configured. The frontend is trying to load a modal/form but the backend endpoint is missing or returning an error.

**Missing Endpoint:**
- Expected: `/playlists/{playlist_id}/change-cover` or similar
- Status: ❌ Not found

**Suggested Fix:**
Implement the change cover endpoint:
```python
@router.post("/{playlist_id}/change-cover", response_class=HTMLResponse)
async def change_cover_image(
    request: Request,
    playlist_id: str,
    api_service: AuthenticatedApiDep,
    cover_file: Optional[UploadFile] = File(None),
    cover_url: Optional[str] = Form(None),
) -> str:
    """Change playlist cover image"""
    # Implementation...
```

---

### Feature #13: Edit Mode (Chapters/Tracks Management)
**Status:** ✅ **PASS** (Partial - Core features work, deletion fails)

**What Works:**
- ✅ Edit button activates edit mode successfully
- ✅ Checkboxes appear for each chapter/track for multi-select
- ✅ "Select All" button available
- ✅ "Invert" button available (for inverting selection)
- ✅ "Expand All" button works - expands nested track items
- ✅ "Collapse All" button works - collapses track items under chapters
- ✅ Edit Icons button appears
- ✅ Cancel button exits edit mode

**What Doesn't Work:**
- ❌ Delete Selected button functionality (see Feature #14)
- ❌ Edit Icons button (see Feature #15)

**Evidence:**
Screenshot `5-edit-mode-features.png` shows edit mode with checkboxes and all controls visible

---

### Feature #14: Delete Selected Chapters
**Status:** ❌ **FAIL** - Endpoint Missing (404)

**Issue:**
When selecting a chapter and clicking "🗑️ Delete Selected":
1. ✅ Confirmation dialog appears with message: "Delete selected items?"
2. ✅ Can dismiss or confirm
3. ❌ **On confirm:** HTTP 404 Error

**Error Details:**
```
[ERROR] Response Status Error Code 404 from /playlists/eiPsE/delete-selected
@ https://unpkg.com/htmx.org@2.0.4:0

[ERROR] HTMX request failed: {error: Response Status Error Code 404 from 
/playlists/eiPsE/delete-selected}
```

**Root Cause:**
Frontend is trying to POST to `/playlists/{playlist_id}/delete-selected` but this endpoint doesn't exist in the router.

**Missing Endpoint:**
The router has no `delete-selected` endpoint.

**Suggested Fix:**
Add the missing endpoint to `src/yoto_up_server/routers/playlists.py`:

```python
@router.post("/{playlist_id}/delete-selected", response_class=HTMLResponse)
async def delete_selected_chapters(
    request: Request,
    playlist_id: str,
    api_service: AuthenticatedApiDep,
    chapter_keys: List[str] = Form(...),  # Keys of chapters to delete
) -> str:
    """Delete selected chapters from a playlist"""
    try:
        # Get the playlist/card
        card = await api_service.get_card(playlist_id)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        
        # Remove selected chapters
        if hasattr(card, 'content') and hasattr(card.content, 'chapters'):
            card.content.chapters = [
                c for c in card.content.chapters 
                if c.key not in chapter_keys
            ]
        
        # Update the card
        updated_card = await api_service.update_card(card)
        
        # Return updated list partial
        return render_partial(PlaylistDetailRefactored(card=updated_card))
    except Exception as e:
        logger.error(f"Failed to delete selected chapters: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

### Feature #15: Change Chapter Icon
**Status:** ❌ **FAIL** - JavaScript Error

**Issue:**
When clicking the "🎨" (paint palette) button on a chapter to change its icon:
```
ReferenceError: openIconSidebar is not defined
    at HTMLButtonElement.onclick
```

**Root Cause:**
The button's onclick handler references `openIconSidebar()` but this function doesn't exist in the JavaScript code. The function is likely missing from the frontend code or not properly imported.

**Expected Behavior:**
Clicking the button should open an icon selection sidebar or dialog where users can choose a different icon for the chapter.

**Missing Function:**
`openIconSidebar()` is referenced but not defined

**Suggested Fix:**
Either:
1. Implement the missing function in the frontend JavaScript:
```javascript
function openIconSidebar(playlistId, chapterKey) {
    // Load icon sidebar and allow user to select icon
    // Then POST the selection to update-chapter-icon endpoint
}
```

2. Or use HTMX to trigger the endpoint instead:
```html
<button hx-post="/playlists/{playlistId}/select-icon"
        hx-vals='{"chapter_key": "{key}"}'
        hx-target="#icon-selector">
    🎨
</button>
```

---

### Feature #16: Drag & Drop Reordering
**Status:** ⚠️ **NOT TESTED** - Feature Visible but Not Tested

**What's Visible:**
- ✅ Drag handle "⋮⋮" appears before each chapter/track
- ✅ Draggable elements are visually indicated
- Label: "Drag to reorder"

**Why Not Tested:**
Drag-and-drop reordering could permanently change the playlist order in the DEBUG playlist. To be safe and avoid modifying test data, this feature wasn't tested during the browser session.

**Presumed Implementation:**
Based on the visible UI elements, drag-and-drop likely:
1. Uses HTML5 drag-drop or a library like Sortable.js
2. Posts the new order to an endpoint like `/playlists/{id}/reorder-chapters`
3. The endpoint likely exists (based on the route hints in code)

**Verification Needed:**
- [ ] Check if reorder endpoint exists: `@router.post("/reorder-chapters")`
- [ ] Test drag-and-drop reordering (in separate test session)

---

## Detailed Issues Breakdown

### Issue #6: Change Cover - HTMX Target Error
**Severity:** 🔴 **CRITICAL**
**Impact:** Users cannot change playlist cover images

**Problem:**
```javascript
[ERROR] htmx:targetError
```

**Diagnosis:**
1. Button click triggers HTMX request
2. HTMX target element doesn't exist or request fails
3. Likely missing endpoint or incorrect configuration

**Fix Priority:** IMMEDIATE

---

### Issue #7: Delete Selected Chapters - 404 Endpoint
**Severity:** 🔴 **CRITICAL**
**Impact:** Users cannot delete chapters from playlists in bulk

**Evidence:**
```
POST /playlists/eiPsE/delete-selected
Response: 404 Not Found
```

**Files to Modify:**
- `src/yoto_up_server/routers/playlists.py` - Add endpoint

**Fix Priority:** IMMEDIATE

---

### Issue #8: Change Chapter Icon - Missing Function
**Severity:** 🔴 **CRITICAL**
**Impact:** Users cannot change chapter icons

**Error Stack:**
```
ReferenceError: openIconSidebar is not defined
at HTMLButtonElement.onclick (...)
```

**Files to Modify:**
- Frontend JavaScript file (location unknown - need to find where onclick is set)
- OR modify template to use HTMX instead of onclick handler

**Fix Priority:** IMMEDIATE

---

## Summary of All Issues by Component

### Backend Issues (API/Router)
| Issue | Endpoint | Status | Fix |
|-------|----------|--------|-----|
| Create Playlist | POST `/playlists/create-with-cover` | Missing | Add endpoint |
| Delete Selected | POST `/playlists/{id}/delete-selected` | Missing (404) | Add endpoint |
| Change Cover | POST `/playlists/{id}/change-cover` | Error | Add/fix endpoint |
| Icon Images | GET `/icons/{id}/image?size=16` | 500 Error | Debug icon service |

### Frontend Issues (JS/Templates)
| Issue | Function | Status | Fix |
|-------|----------|--------|-----|
| Change Icon | `openIconSidebar()` | Undefined | Implement function |

---

## Test Evidence Files

- `4-debug-playlist-detail.png` - Initial DEBUG playlist view
- `5-edit-mode-features.png` - Edit mode with checkboxes and controls
- Console logs showing JavaScript and HTMX errors
- Error responses from browser console (404, 500 errors)

---

## Recommendations

### Priority 1 - Critical (Fix Immediately)
- [ ] Add `/playlists/{id}/delete-selected` endpoint
- [ ] Fix or add `/playlists/{id}/change-cover` endpoint
- [ ] Implement/fix `openIconSidebar()` JavaScript function
- [ ] Fix icon image service (500 errors)
- [ ] Add `/playlists/create-with-cover` endpoint

### Priority 2 - High (Fix Soon)
- [ ] Test drag-and-drop reordering functionality
- [ ] Verify all error messages are user-friendly
- [ ] Add success notifications for successful operations

### Priority 3 - Medium (Nice to Have)
- [ ] Add metadata edit dialog (title, author, category)
- [ ] Implement import/export functionality
- [ ] Add bulk operations UI to main playlists list page

---

## Additional Notes

The DEBUG playlist was a good test subject because:
1. It has minimal content (only 1 chapter)
2. Safe to experiment with (test data)
3. Shows all features in detail view

The edit mode features work well for selection and expansion/collapsing, but the actual modifications (delete, icon change, cover change) fail due to missing endpoints and JavaScript issues.

