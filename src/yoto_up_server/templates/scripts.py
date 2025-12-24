"""
JavaScript functions for playlist detail page.
"""


def get_playlist_scripts() -> str:
    """Return JavaScript for playlist editing, tree view, reordering, and upload."""
    return """//js
            let editMode = false;
            let sidebarOpen = false;
            let currentChapterIndex = null;
            let selectedChapters = new Set();
            
            function toggleEditMode() {
                editMode = !editMode;
                const editToggleBtn = document.getElementById('edit-toggle-btn');
                const editControls = document.getElementById('edit-controls');
                const chaptersListItems = document.querySelectorAll('#chapters-list li');
                
                editToggleBtn.textContent = editMode ? '❌ Cancel' : '✏️ Edit';
                editControls.classList.toggle('hidden');
                
                chaptersListItems.forEach(item => {
                    const checkbox = item.querySelector('input[type="checkbox"]');
                    if (checkbox) {
                        checkbox.classList.toggle('hidden');
                    }
                });
                
                // Close sidebar if open when exiting edit mode
                if (!editMode && sidebarOpen) {
                    closeIconSidebar();
                }
                
                // Clear selection when exiting edit mode
                if (!editMode) {
                    selectedChapters.clear();
                }
            }
            
            function selectAllChapters() {
                const checkboxes = document.querySelectorAll('#chapters-list input[type="checkbox"]');
                selectedChapters.clear();
                checkboxes.forEach((checkbox, index) => {
                    checkbox.checked = true;
                    selectedChapters.add(index);
                });
            }
            
            function invertSelection() {
                const checkboxes = document.querySelectorAll('#chapters-list input[type="checkbox"]');
                selectedChapters.clear();
                checkboxes.forEach((checkbox, index) => {
                    checkbox.checked = !checkbox.checked;
                    if (checkbox.checked) {
                        selectedChapters.add(index);
                    }
                });
            }
            
            function openBatchIconEdit() {
                const checkboxes = document.querySelectorAll('#chapters-list input[type="checkbox"]:checked');
                if (checkboxes.length === 0) {
                    alert('Please select at least one item');
                    return;
                }
                
                // Store selected chapter indices
                selectedChapters.clear();
                checkboxes.forEach(checkbox => {
                    const li = checkbox.closest('li');
                    if (li) {
                        const index = Array.from(li.parentElement.children).indexOf(li);
                        selectedChapters.add(index);
                    }
                });
                
                // Open sidebar for batch edit (no specific chapter)
                const sidebar = document.getElementById('icon-sidebar');
                const overlay = document.getElementById('edit-overlay');
                sidebar.classList.remove('hidden');
                overlay.classList.remove('hidden');
                overlay.style.pointerEvents = 'auto';
                sidebarOpen = true;
                currentChapterIndex = null;  // Null indicates batch mode
                
                // Load user icons on sidebar open
                loadUserIcons();
            }
            
            function openIconSidebar(chapterIndex) {
                const sidebar = document.getElementById('icon-sidebar');
                const overlay = document.getElementById('edit-overlay');
                sidebar.classList.remove('hidden');
                overlay.classList.remove('hidden');
                overlay.style.pointerEvents = 'auto';
                sidebarOpen = true;
                currentChapterIndex = chapterIndex;
                selectedChapters.clear();
                
                // Load user icons on sidebar open
                loadUserIcons();
            }
            
            async function loadUserIcons() {
                const iconsGrid = document.getElementById('icons-grid');
                // Show container early with loading state
                iconsGrid.innerHTML = '<div class="col-span-4 p-4 text-center text-gray-500">Loading your icons...</div>';
                
                try {
                    const response = await fetch('/icons/list?source=user&limit=100');
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    const icons = data.icons || [];
                    
                    if (icons.length === 0) {
                        iconsGrid.innerHTML = '<div class="col-span-4 p-4 text-center text-gray-500">No user icons found</div>';
                    } else {
                        displayIcons(icons, 'My Icons');
                    }
                } catch (error) {
                    console.error('Error loading user icons:', error);
                    iconsGrid.innerHTML = '<div class="col-span-4 p-4 text-center text-red-500">Failed to load icons</div>';
                }
            }
            
            async function searchIcons(query) {
                const searchInput = document.getElementById('icon-search');
                const searchValue = (query || searchInput.value || '').trim();
                
                if (!searchValue) {
                    alert('Please enter a search term');
                    return;
                }
                
                const iconsGrid = document.getElementById('icons-grid');
                // Show container early and clear it
                iconsGrid.innerHTML = '<div class="col-span-4 p-4 text-center text-gray-500">Searching...</div>';
                
                try {
                    // Fetch from both Yoto and YotoIcons in parallel
                    const yotoPromise = fetch('/icons/list?query=' + encodeURIComponent(searchValue) + '&source=yoto&limit=50');
                    const yotoiconsPromise = fetch('/icons/list?query=' + encodeURIComponent(searchValue) + '&source=yotoicons&limit=50');
                    
                    const [yotoResponse, yotoiconsResponse] = await Promise.all([yotoPromise, yotoiconsPromise]);
                    
                    if (!yotoResponse.ok) throw new Error('Failed to fetch Yoto icons');
                    if (!yotoiconsResponse.ok) throw new Error('Failed to fetch YotoIcons');
                    
                    const yotoData = await yotoResponse.json();
                    const yotoiconsData = await yotoiconsResponse.json();
                    
                    const allIcons = [
                        ...(yotoData.icons || []),
                        ...(yotoiconsData.icons || [])
                    ];
                    
                    if (allIcons.length === 0) {
                        iconsGrid.innerHTML = '<div class="col-span-4 p-4 text-center text-gray-500">No icons found for "' + searchValue + '"</div>';
                    } else {
                        displayIcons(allIcons, `Search Results (${allIcons.length})`);
                    }
                } catch (error) {
                    console.error('Error searching icons:', error);
                    iconsGrid.innerHTML = '<div class="col-span-4 p-4 text-center text-red-500">Search failed: ' + error.message + '</div>';
                }
            }
            
            function displayIcons(icons, sectionTitle) {
                const iconsGrid = document.getElementById('icons-grid');
                
                let html = '<div class="col-span-4 mb-4"><h4 class="font-semibold text-gray-700">' + sectionTitle + '</h4></div>';
                html += icons.map(icon => {
                    const thumbnail = icon.thumbnail ? `<img src="${icon.thumbnail}" alt="${icon.title}" class="w-full h-full object-cover rounded" />` : '<div class="w-full h-full bg-gray-200 rounded flex items-center justify-center text-xs text-gray-400">No image</div>';
                    
                    return `
                        <button 
                            class="w-16 h-16 rounded border-2 border-gray-200 hover:border-indigo-500 hover:shadow-lg transition-all cursor-pointer flex items-center justify-center"
                            onclick="selectIcon('${icon.mediaId || icon.id}', null)"
                            title="${icon.title}"
                        >
                            ${thumbnail}
                        </button>
                    `;
                }).join('');
                
                iconsGrid.innerHTML = html;
            }
            
            async function selectIcon(iconId, chapterIndex) {
                try {
                    // Determine which chapters to update
                    let chaptersToUpdate = [];
                    if (currentChapterIndex !== null) {
                        // Single chapter mode
                        chaptersToUpdate = [currentChapterIndex];
                    } else if (selectedChapters.size > 0) {
                        // Batch mode
                        chaptersToUpdate = Array.from(selectedChapters);
                    } else {
                        alert('No chapters selected');
                        return;
                    }
                    
                    console.log(`Updating ${chaptersToUpdate.length} chapter(s) with icon ${iconId}`);
                    
                    // Get playlist ID from data attribute
                    const playlistDetail = document.getElementById('playlist-detail');
                    const playlistId = playlistDetail ? playlistDetail.getAttribute('data-playlist-id') : null;
                    
                    if (!playlistId) {
                        console.error('Playlist ID not found');
                        alert('Error: Could not find playlist ID');
                        return;
                    }
                    
                    // Update all chapters in parallel
                    const updatePromises = chaptersToUpdate.map(chapterIdx =>
                        fetch(`/playlists/update-chapter-icon`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                chapter_index: chapterIdx,
                                icon_id: iconId,
                                playlist_id: playlistId,
                            }),
                        })
                    );
                    
                    const responses = await Promise.all(updatePromises);
                    
                    // Check if all updates were successful
                    const allSuccessful = responses.every(r => r.ok);
                    if (allSuccessful) {
                        // Refresh the page to show updated icons
                        window.location.reload();
                    } else {
                        const failedCount = responses.filter(r => !r.ok).length;
                        alert(`Failed to update ${failedCount} chapter(s)`);
                    }
                } catch (error) {
                    console.error('Error selecting icon:', error);
                    alert('Error: ' + error.message);
                }
                
                closeIconSidebar();
            }
            
            function closeIconSidebar() {
                document.getElementById('icon-sidebar').classList.add('hidden');
                document.getElementById('edit-overlay').classList.add('hidden');
                document.getElementById('edit-overlay').style.pointerEvents = 'none';
                sidebarOpen = false;
                currentChapterIndex = null;
                
                // Clear search input
                const searchInput = document.getElementById('icon-search');
                if (searchInput) {
                    searchInput.value = '';
                }
            }
            
            // Tree view functions for chapters and tracks
            function toggleChapter(chapterIndex) {
                const tracksContainer = document.getElementById(`tracks-container-${chapterIndex}`);
                const toggleBtn = document.getElementById(`toggle-btn-${chapterIndex}`);
                
                if (!tracksContainer || !toggleBtn) return;
                
                const isHidden = tracksContainer.style.display === 'none';
                tracksContainer.style.display = isHidden ? 'block' : 'none';
                toggleBtn.textContent = isHidden ? '▼' : '▶';
            }
            
            function expandAll() {
                const chaptersListItems = document.querySelectorAll('#chapters-list > li');
                chaptersListItems.forEach((item, index) => {
                    const tracksContainer = item.querySelector(`[id^="tracks-container-"]`);
                    if (tracksContainer) {
                        tracksContainer.style.display = 'block';
                        const toggleBtn = item.querySelector(`[id^="toggle-btn-"]`);
                        if (toggleBtn) {
                            toggleBtn.textContent = '▼';
                        }
                    }
                });
            }
            
            function collapseAll() {
                const chaptersListItems = document.querySelectorAll('#chapters-list > li');
                chaptersListItems.forEach((item, index) => {
                    const tracksContainer = item.querySelector(`[id^="tracks-container-"]`);
                    if (tracksContainer) {
                        tracksContainer.style.display = 'none';
                        const toggleBtn = item.querySelector(`[id^="toggle-btn-"]`);
                        if (toggleBtn) {
                            toggleBtn.textContent = '▶';
                        }
                    }
                });
            }
            
            // Set up search button listener when page loads
            document.addEventListener('DOMContentLoaded', function() {
                const searchInput = document.getElementById('icon-search');
                const searchBtn = document.getElementById('icon-search-btn');
                
                // Search on button click
                if (searchBtn) {
                    searchBtn.addEventListener('click', function() {
                        searchIcons();
                    });
                }
                
                // Also search on Enter key
                if (searchInput) {
                    searchInput.addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') {
                            searchIcons();
                        }
                    });
                }
                
                // Initialize Sortable.js for chapter reordering
                const chaptersList = document.getElementById('chapters-list');
                if (chaptersList && typeof Sortable !== 'undefined') {
                    Sortable.create(chaptersList, {
                        handle: '.cursor-grab',
                        animation: 150,
                        ghostClass: 'opacity-50 bg-indigo-100',
                        onEnd: function(evt) {
                            // Save the new order
                            saveChapterOrder();
                        }
                    });
                }
            });
            
            // Save chapter order to server
            function saveChapterOrder() {
                const chaptersList = document.getElementById('chapters-list');
                const items = Array.from(chaptersList.querySelectorAll('li[data-chapter-index]'));
                const newOrder = items.map(item => parseInt(item.getAttribute('data-chapter-index')));
                const playlistId = document.getElementById('playlist-detail').getAttribute('data-playlist-id');
                
                // Show loading state
                const saveBtn = document.createElement('div');
                saveBtn.textContent = 'Saving order...';
                saveBtn.className = 'fixed bottom-4 right-4 bg-indigo-600 text-white px-4 py-2 rounded-lg shadow-lg z-50';
                document.body.appendChild(saveBtn);
                
                fetch('/playlists/reorder-chapters', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        playlist_id: playlistId,
                        new_order: newOrder,
                    })
                })
                .then(response => {
                    if (response.ok) {
                        saveBtn.textContent = 'Order saved!';
                        saveBtn.className = 'fixed bottom-4 right-4 bg-green-600 text-white px-4 py-2 rounded-lg shadow-lg z-50';
                        setTimeout(() => saveBtn.remove(), 2000);
                    } else {
                        saveBtn.textContent = 'Failed to save order';
                        saveBtn.className = 'fixed bottom-4 right-4 bg-red-600 text-white px-4 py-2 rounded-lg shadow-lg z-50';
                        setTimeout(() => saveBtn.remove(), 3000);
                    }
                })
                .catch(error => {
                    console.error('Error saving order:', error);
                    saveBtn.textContent = 'Error: ' + error.message;
                    saveBtn.className = 'fixed bottom-4 right-4 bg-red-600 text-white px-4 py-2 rounded-lg shadow-lg z-50';
                    setTimeout(() => saveBtn.remove(), 3000);
                });
            }
            
            // Upload modal functions
            let selectedFiles = [];
            
            function openUploadModal() {
                document.getElementById('upload-modal').classList.remove('hidden');
                selectedFiles = [];
                updateFilesList();
            }
            
            function closeUploadModal() {
                document.getElementById('upload-modal').classList.add('hidden');
                selectedFiles = [];
                document.getElementById('file-input').value = '';
                updateFilesList();
            }
            
            function selectFiles() {
                const fileInput = document.getElementById('file-input');
                fileInput.click();
            }
            
            async function selectFolder() {
                // Use the File System Access API if available, otherwise fall back to file picker
                if ('showDirectoryPicker' in window) {
                    try {
                        const dirHandle = await showDirectoryPicker();
                        selectedFiles = [];
                        await collectFilesFromDirectory(dirHandle);
                        updateFilesList();
                    } catch (err) {
                        if (err.name !== 'AbortError') {
                            console.error('Error selecting folder:', err);
                            alert('Error selecting folder: ' + err.message);
                        }
                    }
                } else {
                    // Fallback: use file input with webkitdirectory attribute
                    const fileInput = document.getElementById('file-input');
                    const originalAccept = fileInput.accept;
                    fileInput.webkitdirectory = true;
                    fileInput.click();
                    fileInput.webkitdirectory = false;
                    fileInput.accept = originalAccept;
                }
            }
            
            async function collectFilesFromDirectory(dirHandle) {
                for await (const entry of dirHandle.values()) {
                    if (entry.kind === 'file') {
                        // Check if it's an audio file
                        const audioExtensions = ['.mp3', '.m4a', '.wav', '.flac', '.aac', '.ogg'];
                        if (audioExtensions.some(ext => entry.name.toLowerCase().endsWith(ext))) {
                            const file = await entry.getFile();
                            selectedFiles.push(file);
                        }
                    } else if (entry.kind === 'directory') {
                        // Recursively process subdirectories
                        await collectFilesFromDirectory(entry);
                    }
                }
            }
            
            function updateFilesList() {
                const filesList = document.getElementById('files-list');
                const startBtn = document.getElementById('start-upload-btn');
                
                if (selectedFiles.length === 0) {
                    filesList.innerHTML = '<div class="text-sm text-gray-500 text-center py-2">No files selected</div>';
                    startBtn.disabled = true;
                } else {
                    filesList.innerHTML = selectedFiles.map(file => {
                        const sizeMB = (file.size / 1024 / 1024).toFixed(2);
                        return `<div class="text-sm text-gray-700 py-1">📄 ${file.name} (${sizeMB} MB)</div>`;
                    }).join('');
                    startBtn.disabled = false;
                }
            }
            
            // Handle file input change - attach handler and also set up initial listeners
            function setupUploadListeners() {
                const fileInput = document.getElementById('file-input');
                if (fileInput) {
                    fileInput.addEventListener('change', function() {
                        selectedFiles = Array.from(fileInput.files);
                        updateFilesList();
                    });
                }
                
                // Handle normalization checkbox
                const normalizeCheckbox = document.getElementById('normalize-checkbox');
                const normalizeOptions = document.getElementById('normalize-options');
                if (normalizeCheckbox) {
                    normalizeCheckbox.addEventListener('change', function() {
                        normalizeOptions.classList.toggle('hidden', !this.checked);
                    });
                }
                
                // Handle analysis checkbox
                const analysisCheckbox = document.getElementById('analyze-intro-outro-checkbox');
                const analysisOptions = document.getElementById('analysis-options');
                if (analysisCheckbox) {
                    analysisCheckbox.addEventListener('change', function() {
                        analysisOptions.classList.toggle('hidden', !this.checked);
                    });
                }
            }
            
            // Set up listeners when DOM is ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => {
                    setupUploadListeners();
                    loadActiveUploadSessions();
                });
            } else {
                setupUploadListeners();
                loadActiveUploadSessions();
            }
            
            async function startUpload() {
                if (selectedFiles.length === 0) {
                    alert('Please select at least one file');
                    return;
                }
                
                const playlistId = document.getElementById('playlist-detail').getAttribute('data-playlist-id');
                const uploadMode = document.querySelector('input[name="upload-mode"]:checked').value;
                const normalize = document.getElementById('normalize-checkbox').checked;
                const targetLufsElem = document.getElementById('target-lufs');
                const targetLufs = targetLufsElem ? parseFloat(targetLufsElem.value) : -23.0;
                const normalizeBatch = document.getElementById('normalize-batch').checked;
                const analyzeIntroOutro = document.getElementById('analyze-intro-outro-checkbox').checked;
                const segmentSecondsElem = document.getElementById('segment-seconds');
                const segmentSeconds = segmentSecondsElem ? parseFloat(segmentSecondsElem.value) : 10.0;
                const similarityThresholdElem = document.getElementById('similarity-threshold');
                const similarityThreshold = similarityThresholdElem ? parseFloat(similarityThresholdElem.value) : 0.85;
                const showWaveform = document.getElementById('show-waveform-checkbox').checked;
                
                // Show upload progress
                const startBtn = document.getElementById('start-upload-btn');
                const originalText = startBtn.textContent;
                startBtn.disabled = true;
                startBtn.textContent = '⏳ Initializing...';
                
                try {
                    // Step 1: Create upload session on server
                    const sessionResponse = await fetch(`/playlists/${playlistId}/upload-session`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            playlist_id: playlistId,
                            upload_mode: uploadMode,
                            normalize: normalize,
                            target_lufs: targetLufs,
                            normalize_batch: normalizeBatch,
                            analyze_intro_outro: analyzeIntroOutro,
                            segment_seconds: segmentSeconds,
                            similarity_threshold: similarityThreshold,
                            show_waveform: showWaveform,
                        })
                    });
                    
                    if (!sessionResponse.ok) {
                        const error = await sessionResponse.json();
                        throw new Error(error.detail || 'Failed to create upload session');
                    }
                    
                    const sessionData = await sessionResponse.json();
                    const sessionId = sessionData.session_id;
                    
                    // Show uploading section
                    const uploadingSection = document.getElementById('uploading-section');
                    uploadingSection.classList.remove('hidden');
                    
                    startBtn.textContent = '⏳ Uploading files...';
                    
                    // Step 2: Upload all files to the session
                    const filePromises = selectedFiles.map(file => uploadFileToSession(playlistId, sessionId, file, startBtn));
                    await Promise.all(filePromises);
                    
                    // Step 3: Close modal and poll for status
                    closeUploadModal();
                    showUploadNotification('Upload started! Files will be processed...', 'success');
                    
                    // Poll for upload status updates
                    pollUploadStatus(playlistId, sessionId);
                    
                } catch (error) {
                    console.error('Upload error:', error);
                    showUploadNotification('Upload error: ' + error.message, 'error');
                } finally {
                    startBtn.disabled = false;
                    startBtn.textContent = originalText;
                }
            }
            
            async function uploadFileToSession(playlistId, sessionId, file, statusBtn) {
                try {
                    const formData = new FormData();
                    formData.append('file', file);
                    
                    const response = await fetch(`/playlists/${playlistId}/upload-session/${sessionId}/files`, {
                        method: 'POST',
                        body: formData,
                    });
                    
                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'File upload failed');
                    }
                    
                    const result = await response.json();
                    addUploadingFile(file.name, result.file_id, sessionId, playlistId);
                    return result;
                } catch (error) {
                    console.error(`Failed to upload ${file.name}:`, error);
                    addUploadingFile(file.name, `error-${Date.now()}`, sessionId, playlistId, true, error.message);
                    throw error;
                }
            }
            
            function addUploadingFile(filename, fileId, sessionId, playlistId, isError = false, errorMsg = '') {
                const filesList = document.getElementById('uploading-files-list');
                const fileEl = document.createElement('div');
                fileEl.id = `upload-file-${fileId}`;
                fileEl.className = 'p-4 rounded-lg border-l-4 ' + (isError ? 'border-red-500 bg-red-50' : 'border-blue-500 bg-blue-50');
                
                const statusBadge = isError ? 'Error' : 'Pending';
                const statusColor = isError ? 'bg-red-200 text-red-800' : 'bg-blue-200 text-blue-800';
                
                fileEl.innerHTML = `
                    <div class="flex justify-between items-start gap-4">
                        <div class="flex-1">
                            <p class="font-medium text-gray-900">${escapeHtml(filename)}</p>
                            <span class="inline-block mt-2 px-2 py-1 rounded text-xs font-medium ${statusColor}">
                                ${statusBadge}
                            </span>
                            ${isError ? `<p class="text-red-700 text-sm mt-2">${escapeHtml(errorMsg)}</p>` : ''}
                        </div>
                        <button onclick="removeUploadingFile('${fileId}', '${sessionId}', '${playlistId}')" class="text-gray-500 hover:text-gray-700 text-xl">✕</button>
                    </div>
                    <div class="mt-3 bg-gray-200 rounded-full h-2 overflow-hidden">
                        <div id="progress-${fileId}" class="bg-blue-600 h-full transition-all duration-300" style="width: 100%"></div>
                    </div>
                `;
                filesList.appendChild(fileEl);
            }
            
            function updateUploadingFileProgress(fileId, progress, status) {
                const fileEl = document.getElementById(`upload-file-${fileId}`);
                if (!fileEl) return;
                
                const progressBar = document.getElementById(`progress-${fileId}`);
                if (progressBar) {
                    progressBar.style.width = progress + '%';
                }
                
                // Update status badge
                const statusBadge = fileEl.querySelector('span');
                if (statusBadge) {
                    let badgeClass = 'bg-blue-200 text-blue-800';
                    let badgeText = 'Pending';
                    
                    if (status === 'pending') badgeText = 'Pending';
                    else if (status === 'uploading') badgeText = 'Uploading';
                    else if (status === 'queued') badgeText = 'Queued';
                    else if (status === 'processing') badgeText = 'Processing';
                    else if (status === 'done') {
                        badgeClass = 'bg-green-200 text-green-800';
                        badgeText = 'Done';
                    }
                    else if (status === 'error') {
                        badgeClass = 'bg-red-200 text-red-800';
                        badgeText = 'Error';
                    }
                    
                    statusBadge.className = `inline-block px-2 py-1 rounded text-xs font-medium ${badgeClass}`;
                    statusBadge.textContent = badgeText;
                }
            }
            
            function removeUploadingFile(fileId, sessionId, playlistId) {
                const fileEl = document.getElementById(`upload-file-${fileId}`);
                if (fileEl) {
                    fileEl.remove();
                }
                // TODO: Call server to remove file from session
            }
            
            async function pollUploadStatus(playlistId, sessionId, pollInterval = 2000) {
                let pollCount = 0;
                const maxPolls = 300; // Poll for up to 10 minutes
                
                const poll = async () => {
                    try {
                        const response = await fetch(`/playlists/${playlistId}/upload-session/${sessionId}/status`);
                        if (!response.ok) {
                            console.error('Failed to get upload status');
                            return;
                        }
                        
                        const data = await response.json();
                        const session = data.session;
                        
                        // Update file statuses
                        session.files.forEach(file => {
                            updateUploadingFileProgress(file.file_id, file.progress, file.status);
                        });
                        
                        // Check if all files are done
                        if (session.overall_status === 'done' || session.overall_status === 'error') {
                            console.log('Upload session complete');
                            // Reload playlist to show new items
                            setTimeout(() => window.location.reload(), 1500);
                            return; // Stop polling
                        }
                        
                        pollCount++;
                        if (pollCount < maxPolls) {
                            setTimeout(poll, pollInterval);
                        }
                    } catch (error) {
                        console.error('Polling error:', error);
                        pollCount++;
                        if (pollCount < maxPolls) {
                            setTimeout(poll, pollInterval);
                        }
                    }
                };
                
                poll(); // Start first poll
            }
            
            function escapeHtml(text) {
                const map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'};
                return text.replace(/[&<>"']/g, m => map[m]);
            }
            
            // Load active upload sessions when page loads
            async function loadActiveUploadSessions() {
                try {
                    const playlistId = document.getElementById('playlist-detail').getAttribute('data-playlist-id');
                    const response = await fetch(`/playlists/${playlistId}/upload-sessions`);
                    if (!response.ok) return;
                    
                    const data = await response.json();
                    if (data.sessions && data.sessions.length > 0) {
                        const uploadingSection = document.getElementById('uploading-section');
                        uploadingSection.classList.remove('hidden');
                        
                        data.sessions.forEach(session => {
                            session.files.forEach(file => {
                                addUploadingFile(file.filename, file.file_id, session.session_id, playlistId, file.status === 'error', file.error);
                                updateUploadingFileProgress(file.file_id, file.progress, file.status);
                            });
                            // Resume polling for this session
                            pollUploadStatus(playlistId, session.session_id);
                        });
                    }
                } catch (error) {
                    console.error('Failed to load upload sessions:', error);
                }
            }
            
            function showUploadNotification(message, type) {
                const notification = document.createElement('div');
                notification.textContent = message;
                notification.className = `fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg text-white z-[100] ${
                    type === 'success' ? 'bg-green-600' : 'bg-red-600'
                }`;
                document.body.appendChild(notification);
                setTimeout(() => notification.remove(), 4000);
            }
            
            async function displayJsonModal() {
                const playlistId = document.getElementById('playlist-detail').getAttribute('data-playlist-id');
                const jsonModal = document.getElementById('json-modal');
                const jsonContent = document.getElementById('json-content');
                
                try {
                    jsonContent.innerHTML = '<div class="text-gray-400">Loading...</div>';
                    jsonModal.classList.remove('hidden');
                    
                    const response = await fetch(`/playlists/${playlistId}/json`);
                    if (!response.ok) {
                        throw new Error(`Failed to fetch playlist JSON: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    const jsonString = JSON.stringify(data, null, 2);
                    jsonContent.innerHTML = '<code>' + escapeHtml(jsonString) + '</code>';
                } catch (error) {
                    console.error('Error loading playlist JSON:', error);
                    jsonContent.innerHTML = '<div class="text-red-400">Error: ' + escapeHtml(error.message) + '</div>';
                }
            }
            
            function closeJsonModal() {
                const jsonModal = document.getElementById('json-modal');
                jsonModal.classList.add('hidden');
            }
            
            function copyJsonToClipboard() {
                const jsonContent = document.getElementById('json-content');
                const text = jsonContent.textContent;
                
                navigator.clipboard.writeText(text).then(() => {
                    showUploadNotification('JSON copied to clipboard!', 'success');
                }).catch(err => {
                    console.error('Failed to copy:', err);
                    showUploadNotification('Failed to copy to clipboard', 'error');
                });
            }
            """
