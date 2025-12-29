/**
 * Kanban Board JavaScript
 * HTML5 Drag-and-Drop functionality for task status changes
 * 
 * Uses vanilla JavaScript with HTMX for server communication.
 * No external libraries required.
 */

// ============================================================================
// Drag State Management
// ============================================================================

let draggedElement = null;
let draggedTaskId = null;
let sourceColumn = null;
let sourceStatus = null;

// ============================================================================
// Drag Event Handlers
// ============================================================================

/**
 * Handle drag start event
 * @param {DragEvent} event 
 */
function handleDragStart(event) {
    const card = event.target.closest('.task-card');
    if (!card) return;
    
    // Store drag state
    draggedElement = card;
    draggedTaskId = card.dataset.taskId;
    sourceColumn = card.closest('.kanban-column-body');
    sourceStatus = card.dataset.currentStatus;
    
    // Add dragging class for visual feedback
    card.classList.add('dragging');
    
    // Set drag data
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', draggedTaskId);
    
    // Create custom drag image (optional)
    if (event.dataTransfer.setDragImage) {
        const dragImage = card.cloneNode(true);
        dragImage.style.width = card.offsetWidth + 'px';
        dragImage.style.opacity = '0.8';
        dragImage.style.position = 'absolute';
        dragImage.style.top = '-1000px';
        document.body.appendChild(dragImage);
        event.dataTransfer.setDragImage(dragImage, 20, 20);
        
        // Clean up drag image after drag
        setTimeout(() => dragImage.remove(), 0);
    }
    
    // Highlight valid drop targets
    highlightValidDropTargets(sourceStatus);
}

/**
 * Handle drag end event
 * @param {DragEvent} event 
 */
function handleDragEnd(event) {
    const card = event.target.closest('.task-card');
    if (card) {
        card.classList.remove('dragging');
    }
    
    // Clear all drop target highlights
    clearDropTargetHighlights();
    
    // Reset drag state
    draggedElement = null;
    draggedTaskId = null;
    sourceColumn = null;
    sourceStatus = null;
}

/**
 * Handle drag over event (allows drop)
 * @param {DragEvent} event 
 */
function handleDragOver(event) {
    event.preventDefault();
    
    const column = event.target.closest('.kanban-column-body');
    if (!column) return;
    
    const targetStatus = column.dataset.status;
    
    // Check if drop is valid
    if (isValidTransition(sourceStatus, targetStatus)) {
        event.dataTransfer.dropEffect = 'move';
        column.classList.add('drag-over');
        column.classList.remove('invalid-drop');
    } else {
        event.dataTransfer.dropEffect = 'none';
        column.classList.add('invalid-drop');
        column.classList.remove('drag-over');
    }
}

/**
 * Handle drag leave event
 * @param {DragEvent} event 
 */
function handleDragLeave(event) {
    const column = event.target.closest('.kanban-column-body');
    if (column) {
        // Only remove highlight if we're actually leaving the column
        const relatedTarget = event.relatedTarget;
        if (!column.contains(relatedTarget)) {
            column.classList.remove('drag-over', 'invalid-drop');
        }
    }
}

/**
 * Handle drop event
 * @param {DragEvent} event 
 */
function handleDrop(event) {
    event.preventDefault();
    
    const column = event.target.closest('.kanban-column-body');
    if (!column) return;
    
    // Clear highlight immediately
    column.classList.remove('drag-over', 'invalid-drop');
    
    const targetStatus = column.dataset.status;
    const taskId = event.dataTransfer.getData('text/plain');
    
    // Validate transition
    if (!isValidTransition(sourceStatus, targetStatus)) {
        showErrorToast('Invalid status transition');
        return;
    }
    
    // Same column - no action needed
    if (sourceColumn === column) {
        return;
    }
    
    // Check for personal completed tasks
    if (draggedElement) {
        const isPersonal = draggedElement.dataset.isPersonal === 'true';
        const currentStatus = draggedElement.dataset.currentStatus;
        if (isPersonal && currentStatus === 'completed') {
            showErrorToast('Personal completed tasks cannot be moved');
            return;
        }
    }
    
    // Optimistic UI update - move card immediately
    if (draggedElement) {
        column.appendChild(draggedElement);
        draggedElement.dataset.currentStatus = targetStatus;
        updateColumnCounts();
    }
    
    // Send HTMX request to update server
    moveTaskOnServer(taskId, targetStatus, column);
}

// ============================================================================
// Server Communication
// ============================================================================

/**
 * Send request to move task to new status
 * @param {string} taskId 
 * @param {string} newStatus 
 * @param {HTMLElement} targetColumn 
 */
function moveTaskOnServer(taskId, newStatus, targetColumn) {
    const url = `/tasks/kanban/move/${taskId}/`;
    const formData = new FormData();
    formData.append('new_status', newStatus);
    
    fetch(url, {
        method: 'POST',
        headers: {
            'X-CSRFToken': window.CSRF_TOKEN,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                throw new Error(extractErrorMessage(text));
            });
        }
        return response.text();
    })
    .then(html => {
        // Update the card with server response
        const card = document.getElementById(`task-card-${taskId}`);
        if (card && html.trim()) {
            // Create a temporary container to parse the HTML
            const temp = document.createElement('div');
            temp.innerHTML = html.trim();
            const newCard = temp.firstElementChild;
            
            if (newCard) {
                card.replaceWith(newCard);
            }
        }
        
        showSuccessToast('Task moved successfully');
        updateColumnCounts();
    })
    .catch(error => {
        console.error('Error moving task:', error);
        showErrorToast(error.message || 'Failed to move task');
        
        // Revert optimistic update - move card back
        revertCardMove(taskId);
    });
}

/**
 * Revert card to original column on error
 * @param {string} taskId 
 */
function revertCardMove(taskId) {
    if (!sourceColumn || !draggedElement) return;
    
    const card = document.getElementById(`task-card-${taskId}`);
    if (card) {
        sourceColumn.appendChild(card);
        card.dataset.currentStatus = sourceStatus;
        updateColumnCounts();
    }
}

// ============================================================================
// UI Helpers
// ============================================================================

/**
 * Highlight valid drop targets based on current status
 * @param {string} currentStatus 
 */
function highlightValidDropTargets(currentStatus) {
    const validTargets = window.VALID_TRANSITIONS[currentStatus] || [];
    
    document.querySelectorAll('.kanban-column-body').forEach(column => {
        const columnStatus = column.dataset.status;
        if (validTargets.includes(columnStatus)) {
            column.style.outline = '2px dashed #6366f1';
            column.style.outlineOffset = '-2px';
        }
    });
}

/**
 * Clear all drop target highlights
 */
function clearDropTargetHighlights() {
    document.querySelectorAll('.kanban-column-body').forEach(column => {
        column.classList.remove('drag-over', 'invalid-drop');
        column.style.outline = '';
        column.style.outlineOffset = '';
    });
}

/**
 * Check if status transition is valid
 * @param {string} fromStatus 
 * @param {string} toStatus 
 * @returns {boolean}
 */
function isValidTransition(fromStatus, toStatus) {
    const validTargets = window.VALID_TRANSITIONS[fromStatus] || [];
    return validTargets.includes(toStatus);
}

/**
 * Update column count badges
 */
function updateColumnCounts() {
    document.querySelectorAll('.kanban-column').forEach(column => {
        const columnBody = column.querySelector('.kanban-column-body');
        const countBadge = column.querySelector('.kanban-column-header span:last-child');
        
        if (columnBody && countBadge) {
            const cardCount = columnBody.querySelectorAll('.task-card').length;
            countBadge.textContent = cardCount;
        }
    });
}

/**
 * Extract error message from HTML response
 * @param {string} html 
 * @returns {string}
 */
function extractErrorMessage(html) {
    const temp = document.createElement('div');
    temp.innerHTML = html;
    return temp.textContent.trim() || 'An error occurred';
}

// ============================================================================
// Toast Notifications
// ============================================================================

/**
 * Show error toast notification
 * @param {string} message 
 */
function showErrorToast(message) {
    const toast = document.getElementById('error-toast');
    const messageEl = document.getElementById('error-message');
    
    if (toast && messageEl) {
        messageEl.textContent = message;
        toast.classList.remove('hidden');
        
        // Auto-hide after 5 seconds
        setTimeout(() => hideErrorToast(), 5000);
    }
}

/**
 * Hide error toast
 */
function hideErrorToast() {
    const toast = document.getElementById('error-toast');
    if (toast) {
        toast.classList.add('hidden');
    }
}

/**
 * Show success toast notification
 * @param {string} message 
 */
function showSuccessToast(message) {
    const toast = document.getElementById('success-toast');
    const messageEl = document.getElementById('success-message');
    
    if (toast && messageEl) {
        messageEl.textContent = message;
        toast.classList.remove('hidden');
        
        // Auto-hide after 3 seconds
        setTimeout(() => hideSuccessToast(), 3000);
    }
}

/**
 * Hide success toast
 */
function hideSuccessToast() {
    const toast = document.getElementById('success-toast');
    if (toast) {
        toast.classList.add('hidden');
    }
}

// ============================================================================
// Keyboard Accessibility
// ============================================================================

/**
 * Initialize keyboard support for drag-and-drop
 */
function initKeyboardSupport() {
    document.querySelectorAll('.task-card').forEach(card => {
        card.setAttribute('tabindex', '0');
        
        card.addEventListener('keydown', (event) => {
            // Space or Enter to initiate drag mode
            if (event.key === ' ' || event.key === 'Enter') {
                event.preventDefault();
                toggleDragMode(card);
            }
            
            // Arrow keys to move between columns in drag mode
            if (card.classList.contains('keyboard-dragging')) {
                handleKeyboardMove(event, card);
            }
            
            // Escape to cancel drag mode
            if (event.key === 'Escape') {
                cancelKeyboardDrag(card);
            }
        });
    });
}

/**
 * Toggle keyboard drag mode for a card
 * @param {HTMLElement} card 
 */
function toggleDragMode(card) {
    if (card.classList.contains('keyboard-dragging')) {
        cancelKeyboardDrag(card);
    } else {
        card.classList.add('keyboard-dragging', 'ring-2', 'ring-indigo-500');
        showSuccessToast('Use arrow keys to move, Enter to confirm, Escape to cancel');
    }
}

/**
 * Handle keyboard movement in drag mode
 * @param {KeyboardEvent} event 
 * @param {HTMLElement} card 
 */
function handleKeyboardMove(event, card) {
    const columns = Array.from(document.querySelectorAll('.kanban-column-body'));
    const currentColumn = card.closest('.kanban-column-body');
    const currentIndex = columns.indexOf(currentColumn);
    
    let targetColumn = null;
    
    if (event.key === 'ArrowRight' && currentIndex < columns.length - 1) {
        targetColumn = columns[currentIndex + 1];
    } else if (event.key === 'ArrowLeft' && currentIndex > 0) {
        targetColumn = columns[currentIndex - 1];
    } else if (event.key === 'Enter' && targetColumn !== currentColumn) {
        // Confirm the move
        event.preventDefault();
        card.classList.remove('keyboard-dragging', 'ring-2', 'ring-indigo-500');
        return;
    }
    
    if (targetColumn) {
        event.preventDefault();
        const currentStatus = card.dataset.currentStatus;
        const targetStatus = targetColumn.dataset.status;
        
        if (isValidTransition(currentStatus, targetStatus)) {
            targetColumn.appendChild(card);
            card.dataset.currentStatus = targetStatus;
            moveTaskOnServer(card.dataset.taskId, targetStatus, targetColumn);
        } else {
            showErrorToast('Invalid status transition');
        }
    }
}

/**
 * Cancel keyboard drag mode
 * @param {HTMLElement} card 
 */
function cancelKeyboardDrag(card) {
    card.classList.remove('keyboard-dragging', 'ring-2', 'ring-indigo-500');
}

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Kanban JS initialized');
    
    // Initialize keyboard accessibility
    initKeyboardSupport();
    
    // Update counts on page load
    updateColumnCounts();
});

// Re-initialize after HTMX swaps
document.body.addEventListener('htmx:afterSwap', function(event) {
    initKeyboardSupport();
    updateColumnCounts();
});