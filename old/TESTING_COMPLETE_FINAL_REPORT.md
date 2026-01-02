# Playlist Workflow - Complete Testing Report

**Date:** December 25, 2025  
**Server:** http://localhost:8000  
**Test Environment:** DEBUG Playlist (ID: eiPsE)  
**Status:** ✅ Testing Complete - 8 Issues Identified

---

## Executive Summary

Comprehensive functional testing of the Yoto-Up playlist management system has identified **8 distinct issues** affecting core playlist operations:

- **4 Critical Issues** - Missing/broken API endpoints
- **3 Medium Issues** - Missing JavaScript functions and UI components
- **1 High Priority** - Icon service returning 500 errors

---

## Testing Scope

### Phase 1: Playlist List Page ✅
- View playlists list
- Filter by title
- Filter by category  
- Clear filters
- Navigate to playlist details

**Result:** All passing ✅

### Phase 2: Playlist Detail Page ✅
- View playlist details and chapters
- Display JSON structure
- View chapter metadata
- Icon display (500 errors found)

**Result:** Mostly passing, icon service issues ❌

### Phase 3: Edit Mode Operations
- Edit mode activation ✅
- Checkbox selection ✅
- Select All button ✅
- Invert selection button ✅
- Expand All chapters ✅
- Collapse All chapters ✅
- Delete Selected chapters ❌
- Change chapter icon ❌

### Phase 4: Additional Features
- Upload Items modal ✅
- Change cover image ❌
- Create playlist ❌
- Drag-and-drop reordering ⚠️ (untested to avoid data changes)

---

## Critical Issues Found

### 1. ❌ Delete Selected Chapters
**Endpoint:** `POST /playlists/{id}/delete-selected`  
**Error Code:** 404 Not Found  
**Impact:** Cannot bulk delete chapters

**Root Cause:** Endpoint not implemented in router

**Evidence:**
```
[ERROR] Response Status Error Code 404 
from /playlists/eiPsE/delete-selected
```

**Fix Required:** Add endpoint to `src/yoto_up_server/routers/playlists.py`

---

### 2. ❌ Change Cover Image
**Endpoint:** `POST /playlists/{id}/change-cover`  
**Error Type:** HTMX Target Error  
**Impact:** Cannot update playlist cover

**Root Cause:** Endpoint missing or broken

**Evidence:**
```
[ERROR] htmx:targetError @ https://unpkg.com/htmx.org@2.0.4:0
```

**Fix Required:** Add or fix endpoint in router

---

### 3. ❌ Change Chapter Icon
**Function:** `openIconSidebar()`  
**Error Type:** JavaScript ReferenceError  
**Impact:** Cannot change chapter icons

**Root Cause:** Function referenced but not defined

**Evidence:**
```
ReferenceError: openIconSidebar is not defined
    at HTMLButtonElement.onclick
```

**Fix Required:** Implement JavaScript function in frontend

---

### 4. ❌ Icon Display Service
**Endpoint:** `GET /icons/{id}/image?size=16`  
**Error Code:** 500 Internal Server Error  
**Impact:** Chapter icons missing on detail pages (11+ errors per page)

**Evidence:**
```
[ERROR] Failed to load resource: the server responded with a status of 500
@ http://localhost:8000/icons/W-2RUBud_e1PlHw03Mj73sqyLKibjZjNfyiQ1GWtvx4/image?size=16
(repeated 11 times on each detail page)
```

**Fix Required:** Debug icon service endpoint

---

### 5. ❌ Create Playlist with Cover
**Endpoint:** `POST /playlists/create-with-cover`  
**Error Code:** 405 Method Not Allowed  
**Impact:** Cannot create new playlists via modal

**Root Cause:** Template references `/create-with-cover` but router only has `/create`

**Fix Required:** Add endpoint to router

---

### 6. ❌ Missing Metadata Edit UI
**Component:** Edit dialog for title/author/category  
**Impact:** Edit button only shows chapter selection, no playlist metadata editing

**Fix Required:** Add metadata form to template

---

### 7. ⚠️ Drag-and-Drop Reordering
**UI Status:** Visible (⋮⋮ drag handles present)  
**Test Status:** Not tested (avoided to preserve data)  
**Endpoint:** `POST /playlists/reorder-chapters` (exists in code at line 340)

**Notes:** Appears implemented but needs verification

---

### 8. ⚠️ Bulk Operations on List Page
**UI Status:** Not visible  
**Impact:** Cannot select/delete multiple playlists from list view

**Fix Required:** Add UI controls to list page template

---

## Feature Testing Matrix

| Feature | Works | Broken | Notes |
|---------|-------|--------|-------|
| **View Playlists** | ✅ | | All 14 playlists display |
| **Filter - Title** | ✅ | | Tested with "בוקר" |
| **Filter - Category** | ✅ | | Multi-select dropdown |
| **Clear Filters** | ✅ | | Resets all filters |
| **Playlist Details** | ✅ | | Page loads and renders |
| **Display JSON** | ✅ | | Full structure exported |
| **Create Playlist** | | ❌ | 405 error |
| **Upload Items** | ✅ | | Modal opens, UI works |
| **Edit Mode** | ✅ | | Checkboxes activate |
| **Select All** | ✅ | | Selects all chapters |
| **Invert Selection** | ✅ | | Toggles selection |
| **Expand All** | ✅ | | Shows all chapters |
| **Collapse All** | ✅ | | Hides all chapters |
| **Delete Selected** | | ❌ | 404 error |
| **Change Icon** | | ❌ | Function undefined |
| **Change Cover** | | ❌ | HTMX error |
| **Icon Display** | | ❌ | 500 errors |
| **Delete Playlist** | ✅ | | Confirmation works |
| **Drag-and-Drop** | ⚠️ | | Untested |

---

## Code Locations for Fixes

### File: `src/yoto_up_server/routers/playlists.py`
**Line 220:** Has `@router.post("/create")` but needs `/create-with-cover`  
**Missing:** `@router.post("/{playlist_id}/delete-selected")`  
**Missing:** `@router.post("/{playlist_id}/change-cover")`  
**Exists:** `@router.post("/update-chapter-icon")` at line 242

### File: `src/yoto_up_server/templates/upload_components.py`
**Line 395:** References `hx_post="/playlists/create-with-cover"` (wrong endpoint)

### File: Frontend JavaScript (location unknown)
**Missing:** `openIconSidebar()` function

---

## Reproduction Steps

### Create Playlist Error
1. Click "Create Playlist" button
2. Modal appears
3. Enter title and upload cover image
4. Click "Create"
5. **Error:** 405 - endpoint `/playlists/create-with-cover` not found

### Delete Selected Error
1. Navigate to any playlist detail page
2. Click "Edit" button
3. Check any chapter checkbox
4. Click "Delete Selected"
5. Confirm deletion
6. **Error:** 404 - endpoint `/playlists/{id}/delete-selected` not found

### Change Icon Error
1. Navigate to playlist detail page
2. Click "Edit" button
3. Click the 🎨 icon button on any chapter
4. **Error:** `ReferenceError: openIconSidebar is not defined`

### Icon Display Error
1. Navigate to any playlist detail page
2. Open browser DevTools Console
3. **See:** 11+ errors for `/icons/{id}/image?size=16` returning 500

---

## Severity Assessment

| Issue | Severity | Blocks | Users Affected |
|-------|----------|--------|-----------------|
| Delete Selected | **CRITICAL** | Bulk operations | All users managing playlists |
| Change Icon | **CRITICAL** | Icon customization | All users |
| Create Playlist | **CRITICAL** | New playlist creation | New users |
| Icon Display | **CRITICAL** | Visual experience | All users viewing details |
| Change Cover | **HIGH** | Playlist customization | Most users |
| Metadata Edit | **MEDIUM** | Edit playlist details | Some users |
| Bulk List Operations | **MEDIUM** | Bulk actions | Power users |
| Drag-and-Drop | **MEDIUM** | Chapter ordering | Users needing reorder |

---

## Next Steps - Recommended Order

### Phase 1: Critical Fixes (Blocks Core Features)
1. **Add `/playlists/{id}/delete-selected` endpoint** - Unblocks bulk deletion
2. **Implement `openIconSidebar()` function** - Unblocks icon changing
3. **Fix icon service `/icons/{id}/image` endpoint** - Restores visual display
4. **Add `/playlists/{id}/change-cover` endpoint** - Unblocks cover updates

### Phase 2: Important Features (Enhances Usability)
5. Add metadata edit dialog for title/author/category
6. Add bulk operation UI to list page
7. Test drag-and-drop reordering

### Phase 3: Polish (Nice-to-Have)
8. Add import/export UI controls
9. Optimize error handling and user feedback
10. Add validation for file uploads

---

## Test Environment Details

**Server:** localhost:8000  
**Authentication:** Logged in as authorized user  
**Test Playlist:** DEBUG (eiPsE) with 1 chapter  
**Browser:** Playwright automated testing  
**Tools Used:** HTMX console, JavaScript error capture, Network monitoring

---

## Files Affected

### Backend Files to Modify
- `src/yoto_up_server/routers/playlists.py` - Add missing endpoints
- `src/yoto_up_server/routers/icons.py` - Fix icon service
- `src/yoto_up_server/templates/playlists.py` - Update templates
- `src/yoto_up_server/templates/upload_components.py` - Fix endpoint reference

### Frontend Files to Modify
- JavaScript file with onclick handlers - Add `openIconSidebar()` function

---

## Testing Artifacts

**Documentation:**
- PLAYLIST_FUNCTIONALITY_TEST.md - Detailed test matrix
- PLAYLIST_EXTENDED_TEST_REPORT.md - DEBUG playlist deep dive
- PLAYLIST_TEST_SUMMARY.md - Executive summary

**Screenshots:**
- 1-homepage.png - Initial state
- 2-playlists-list.png - Working list view
- 3-detail-page-with-500-errors.png - Icon errors
- 4-debug-playlist-detail.png - DEBUG playlist
- 5-edit-mode-features.png - Edit controls

---

## Conclusion

The playlist system has a solid foundation with most core features working well (viewing, filtering, navigation). However, **4 critical API endpoints are missing** and **1 important JavaScript function is not implemented**, which blocks essential user workflows like bulk deletion, icon management, and playlist creation.

The icon service 500 errors suggest a deeper infrastructure issue that needs investigation.

**Estimated effort to fix all issues:** 4-6 hours for experienced developer  
**Estimated testing time:** 2-3 hours  
**Total resolution time:** ~8 hours
