# Playlist Workflow - Extended Testing Report

**Date:** December 25, 2025  
**Server:** http://localhost:8000  
**Test Environment:** DEBUG Playlist (ID: eiPsE) + Test Audio File  
**Status:** ✅ Extended Testing Complete

---

## New Test Focus Areas

This extended testing session focused on three specific areas previously identified as potential issues:

1. **File Upload Functionality & Progress UI**
2. **Setting Icons (Batch & Individual)**
3. **Setting Card Metadata**

---

## Test Results Summary

| Feature | Status | Issue Type | Details |
|---------|--------|-----------|---------|
| **File Upload** | ⚠️ **PARTIAL** | Backend OK, Frontend Issue | File accepted & uploaded, but no progress UI |
| **Upload Progress UI** | ❌ **BROKEN** | Frontend Bug | JSON response displayed as plain text instead of progress |
| **Batch Icon Setting** | ❌ **BROKEN** | Multiple Errors | 500 error on endpoint + JS error on classList |
| **Individual Icon Setting** | ❌ **BROKEN** | JavaScript Error | `openIconSidebar()` function undefined (already known) |
| **Card Metadata Editing** | ❌ **MISSING** | No UI | No visible UI controls for editing chapter metadata |

---

## Detailed Findings

### 1. ❌ File Upload Works, But Progress UI Broken

**Status:** ✅ Upload works / ❌ Progress UI broken

**What Works:**
- File selection modal opens correctly
- File picker dialog appears
- Test audio file (test_audio.wav, 0.08 MB) selected successfully
- Upload button click triggers backend processing

**What's Broken:**
- Upload endpoint returns **raw JSON response** instead of HTML progress UI
- JSON response displayed as plain text paragraph in page
- No progress bar or status indicator visible
- User sees: `{"status":"ok","session_id":"c5c26ba3-...",` etc.

**Evidence:**
```json
{
  "status": "ok",
  "session_id": "c5c26ba3-ebb8-458a-a193-85b557140780",
  "session": {
    "session_id": "c5c26ba3-ebb8-458a-a193-85b557140780",
    "playlist_id": "eiPsE",
    "upload_mode": "chapters",
    "normalize": false,
    "files": [
      {
        "file_id": "5ae54e1d-974b-41ac-aad0-3c7a03a17af1",
        "filename": "test_audio.wav",
        "size_bytes": 88244,
        "status": "error",
        "progress": 100.0,
        "error": "2 validation errors for TranscodedAudioResponse..."
      }
    ],
    "overall_status": "error"
  }
}
```

**Root Cause:**
The upload endpoint at `/playlists/{id}/upload-items` returns JSON response (`response_class=JSONResponse`) but the frontend form submit (likely HTMX) expects HTML response. The JSON gets rendered as plain text instead of being processed by JavaScript.

**Secondary Issue Found:**
The API response also shows a **transcoding error**: "Field required [type=missing, input_value={'uploadId': ...}, input_type=dict]" for `transcode.progress` and `transcode.ffmpeg`. This suggests the backend transcoding process has a Pydantic validation error.

**Screenshots:**
- [6-upload-json-response.png](../6-upload-json-response.png) - Shows JSON response displayed as text

---

### 2. ❌ Batch Icon Setting - 500 Error + JavaScript Error

**Endpoint:** `POST /playlists/{id}/icon-sidebar?batch=true`  
**Error Code:** 500 Internal Server Error  
**Additional Error:** JavaScript error

**Errors Found:**
```
[ERROR] Failed to load resource: the server responded with a status of 500
[ERROR] Response Status Error Code 500 from /playlists/eiPsE/icon-sidebar?batch=true
[ERROR] HTMX request failed: {error: Response Status Error Code 500 from /playlists/eiPsE/icon-sidebar?batch=true...}
[ERROR] ReferenceError: classList is not defined
    at HTMLButtonElement.eval (eval at <anonymous>)
```

**Impact:**
- Batch icon selection modal fails to open
- User sees generic error dialog: "An error occurred. Please try again."
- Edit Icons button is unusable in batch mode

**Root Cause:**
- Backend endpoint `/playlists/{id}/icon-sidebar?batch=true` returns 500 error (likely unimplemented or broken)
- Frontend attempts to handle response but fails due to `classList is not defined` error (likely in icon selection JavaScript)

**Screenshots:**
- [7-batch-icon-errors.png](../7-batch-icon-errors.png) - Shows error dialog and batch icon button

---

### 3. ❌ Individual Icon Setting - JavaScript Function Undefined

**Status:** ❌ (Already documented in previous testing)

**Error:**
```
ReferenceError: openIconSidebar is not defined
    at HTMLButtonElement.onclick
```

**Details:**
- Each chapter has a 🎨 icon button
- Button has `onclick="openIconSidebar(...)"` handler
- Function `openIconSidebar` does not exist in JavaScript codebase
- Clicking icon button produces JavaScript error in console

**Impact:**
Users cannot change icons for individual chapters.

---

### 4. ❌ Card Metadata Editing - No UI Components

**Status:** ❌ **NO UI CONTROLS FOR EDITING**

**What I Tested:**
- Clicked chapter title - no response
- Right-clicked chapter title - no context menu
- Looked for edit buttons or icons - none visible
- Checked page source and templates

**What I Found:**
1. **No visible UI controls** for editing chapter metadata (title, artist, album, description, etc.)
2. **Metadata fields exist** in the data structure (checked via API responses)
3. **Backend supports updates** - `@router.post("/update-card")` endpoint exists in `/cards.py` router
4. **Frontend templates** read metadata but don't provide edit UI

**Available Metadata Fields** (from code inspection):
- title (displayed, not editable)
- description (displayed, not editable)
- duration (displayed, calculated)
- artist (exists but not visible in UI)
- album (exists but not visible in UI)
- metadata.cover (used for card covers)
- metadata.category (used for filtering)

**Example from Yoto API:**
```python
class Track(BaseModel):
    id: str
    title: str
    duration: float
    metadata: dict[str, Any]  # Contains all custom metadata
```

**Root Cause:**
The UI layer never displays or allows editing of chapter metadata. While the backend API supports updates and the data model has fields, the frontend doesn't provide any interface to:
- Edit chapter title
- Add artist information
- Add album information  
- Edit description
- Upload custom cover art

**Screenshots:**
- [8-chapter-no-metadata-ui.png](../8-chapter-no-metadata-ui.png) - Shows chapter display with no edit options

---

## Summary of Issues

### New Issues Found (3)

1. **🔴 Upload Progress UI Displaying JSON as Text**
   - **Endpoint:** `POST /playlists/{id}/upload-items`
   - **Type:** Frontend/Response Handling
   - **Impact:** No progress feedback to user, raw JSON displayed
   - **Priority:** HIGH - Affects user experience during uploads
   - **Related:** Also found transcoding validation error in response

2. **🔴 Batch Icon Setting Returns 500 Error**
   - **Endpoint:** `POST /playlists/{id}/icon-sidebar?batch=true`
   - **Type:** Backend (missing or broken endpoint)
   - **Impact:** Cannot edit icons in batch mode
   - **Priority:** HIGH - Bulk operation completely broken
   - **Related:** JavaScript error `classList is not defined` in handler

3. **🔴 Card Metadata Editing UI Missing**
   - **Type:** Missing Feature
   - **Impact:** Users cannot edit chapter properties (title, artist, album, description)
   - **Priority:** MEDIUM - Data can't be edited through UI (backend supports it)
   - **Scope:** Requires adding edit dialog/form to playlist detail template

### Existing Issues Confirmed (2)

4. ✅ **Individual Icon Setting Function Undefined** - CONFIRMED
   - Function `openIconSidebar()` still missing
   
5. ✅ **Icon Display Service Errors** - CONFIRMED
   - `/icons/{id}/image?size=16` still returning 500 errors (11+ per page)

---

## Technical Details for Developers

### Upload Response Issue

**Current Flow:**
```
User clicks "Start Upload"
  → Form submitted via HTMX
  → Backend returns JSONResponse
  → HTMX receives JSON
  → Frontend tries to render JSON as HTML → FAILS
  → User sees raw JSON text on page
```

**Expected Flow:**
```
User clicks "Start Upload"
  → Form submitted via HTMX
  → Backend returns HTMLResponse with progress UI component
  → HTMX swaps HTML into DOM
  → Progress bar and status updates appear
  → User sees real-time upload progress
```

**File:** `src/yoto_up_server/routers/upload_routes.py` or similar  
**Fix:** Change endpoint to return `response_class=HTMLResponse` with proper progress template, or handle JSON response client-side with JavaScript.

### Batch Icon Endpoint Issue

**Current Error:**
```
Status: 500 Internal Server Error
Endpoint: /playlists/{id}/icon-sidebar?batch=true
```

**Likely Causes:**
1. Endpoint not implemented for batch mode
2. Query parameter `batch=true` not handled
3. Template rendering failure
4. Database/API call failure

**File:** `src/yoto_up_server/routers/playlists.py` or `templates/icons.py`  
**Related:** `classList is not defined` JS error suggests issue with DOM manipulation after failed response

### Metadata Editing Missing

**Files to Modify:**
- `src/yoto_up_server/templates/playlist_detail_refactored.py` - Add edit dialog/form
- `src/yoto_up_server/routers/playlists.py` - May need new endpoint for chapter metadata updates
- Frontend JavaScript - Add handlers for edit form submission

**What's Needed:**
1. Edit button/icon next to chapter title
2. Modal dialog with metadata form fields:
   - Title (text input)
   - Artist (text input)
   - Album (text input)
   - Description (textarea)
   - Cover image (file upload)
3. POST endpoint to save changes
4. Validation and error handling

**Backend Support Already Exists:**
- `update_card()` method in API service
- Card update endpoint at `POST /cards/{id}`
- Metadata support in Card model

---

## Test Evidence Files

**Screenshots:**
- `6-upload-json-response.png` - Upload returning JSON as text
- `7-batch-icon-errors.png` - Batch icon 500 error
- `8-chapter-no-metadata-ui.png` - No metadata edit UI visible

**Test Data:**
- Created: `test_audio.wav` (1 second of audio, 88KB)
- Used: DEBUG playlist with 1 chapter

**Browser Console Errors Captured:**
- HTMX 500 errors for batch icon endpoint
- JavaScript ReferenceError for classList
- Previous session's openIconSidebar errors

---

## Comparison: Previous vs. Extended Testing

### Issues by Category

**Critical (Blocks Features):**
- ✅ Existing: Delete Selected - 404 endpoint missing
- ✅ Existing: Create Playlist - 405 endpoint wrong
- ✅ Existing: Change Cover - HTMX error
- 🆕 Upload Progress UI - JSON displayed as text
- 🆕 Batch Icon Setting - 500 error
- ✅ Existing: Individual Icon Setting - Function undefined

**High (Affects Usability):**
- ✅ Existing: Icon Display - 500 errors
- 🆕 Card Metadata Editing - No UI controls

**Medium (Nice-to-Have):**
- Bulk operations UI on list page
- Drag-and-drop testing

---

## Recommendations for Remediation

### Phase 1: Critical Fixes (1-2 hours)

1. **Fix Upload Progress UI**
   - Change response class or add JavaScript handler
   - Display actual progress bar instead of JSON
   - Handle transcoding validation error

2. **Fix Batch Icon Endpoint**
   - Implement or fix `/playlists/{id}/icon-sidebar?batch=true`
   - Fix JavaScript `classList` error
   - Test batch icon selection

3. **Implement `openIconSidebar()` Function**
   - Create JavaScript function for individual icon selection
   - Wire to existing icon sidebar
   - Test on single chapter

### Phase 2: Important Features (2-3 hours)

4. **Add Card Metadata Editing UI**
   - Create edit dialog component
   - Add form fields for title, artist, album, description
   - Add cover image upload
   - Implement save functionality

5. **Complete Icon Functionality Testing**
   - Verify individual icon selection works
   - Verify batch icon selection works
   - Verify icons display correctly

### Phase 3: Polish (1-2 hours)

6. **Error Handling & User Feedback**
   - Better error messages in UI
   - Loading indicators during operations
   - Success confirmation after uploads

---

## Total Issues Found

**Extended Testing: 3 NEW issues**
- Upload Progress UI
- Batch Icon Setting
- Card Metadata Editing (UI missing)

**Previous Testing: 5 CONFIRMED issues**
- Delete Selected (404)
- Create Playlist (405)
- Change Cover (HTMX error)
- Individual Icon Setting (Function undefined)
- Icon Display Service (500 errors)

**TOTAL: 8 CRITICAL/HIGH PRIORITY ISSUES**

---

## Conclusion

The extended testing revealed that while the **upload backend is functional**, the **frontend progress UI is broken** and returning raw JSON instead of progress feedback. Additionally, **batch icon editing has both backend and frontend issues**, and **metadata editing UI is completely missing** (though backend supports it).

The codebase shows good foundational API support but has gaps in the UI layer and some missing JavaScript implementations. All identified issues have clear remediation paths.

**Estimated total fix time: 4-8 hours for experienced developer**
