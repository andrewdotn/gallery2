// Note: there's no typescript dependency in package.json, or tsconfig.json yet
import React from 'react';
import { createRoot } from 'react-dom/client';

// Function to get CSRF token from cookies
function getCsrfToken(): string {
  const name = 'csrftoken';
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    const cookiePart = parts.pop();
    if (cookiePart) {
      const cookieValue = cookiePart.split(';').shift();
      return cookieValue || '';
    }
  }
  return '';
}


// CaptionEditor component
function createCaptionEditor(entryId: number, initialCaption: string, htmlCaption: string) {
  // State variables
  let isEditing = false;
  let caption = initialCaption;
  let isSaving = false;
  let error: string | null = null;

  // DOM elements
  let container: HTMLElement | null = null;
  let root: any = null;

  // Event handlers
  function handleEdit() {
    isEditing = true;
    render();
  }

  function handleCancel() {
    caption = initialCaption;
    isEditing = false;
    error = null;
    render();
  }

  async function handleSave() {
    isSaving = true;
    error = null;
    render();

    try {
      const response = await fetch(`/gallery/entry/${entryId}/edit-caption`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ caption }),
      });

      if (response.status !== 200) {
        throw new Error(`${response.status} failed to save caption`);
      }
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to save caption');
      }

      isEditing = false;
      // Update the HTML caption with the new data from the server
      htmlCaption = data.html_caption || htmlCaption;
      // No need to reload the page, just re-render the component
    } catch (err) {
      error = err instanceof Error ? err.message : 'An unknown error occurred';
      render();
    } finally {
      isSaving = false;
      render();
    }
  }

  function handleTextareaChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    caption = e.target.value;
    render();
  }

  // Render function
  function render() {
    if (!root) return;

    root.render(
      isEditing ? renderEditMode() : renderDisplayMode()
    );
  }

  // Render edit mode
  function renderEditMode() {
    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Check for Command+Enter (Mac) or Ctrl+Enter (Windows/Linux)
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        handleSave();
      }
    };

    const textarea = React.createElement('textarea', {
      value: caption,
      onChange: handleTextareaChange,
      onKeyDown: handleKeyDown,
      className: 'form-control mb-2',
      rows: 5,
      disabled: isSaving
    });

    const errorElement = error ? 
      React.createElement('div', { className: 'alert alert-danger mb-2' }, error) : 
      null;

    const saveButton = React.createElement('button', {
      className: 'btn btn-primary btn-sm me-2',
      onClick: handleSave,
      disabled: isSaving
    }, isSaving ? 'Saving...' : 'Save');

    const cancelButton = React.createElement('button', {
      className: 'btn btn-secondary btn-sm',
      onClick: handleCancel,
      disabled: isSaving
    }, 'Cancel');

    const buttonGroup = React.createElement('div', { className: 'btn-group' }, 
      saveButton, 
      cancelButton
    );

    return React.createElement('div', { className: 'caption-editor grow-wrap', 'data-replicated-value': caption },
      textarea,
      errorElement,
      buttonGroup
    );
  }

  // Render display mode
  function renderDisplayMode() {
    const captionDisplay = React.createElement('div', { 
      dangerouslySetInnerHTML: { __html: htmlCaption } 
    });

    const editButton = React.createElement('button', {
      className: 'btn btn-outline-secondary btn-sm mt-2',
      onClick: handleEdit
    }, 'Edit');

    return React.createElement('div', { className: 'caption-display' },
      captionDisplay,
      editButton
    );
  }

  // Initialize
  function init(mountPoint: HTMLElement) {
    container = mountPoint;
    root = createRoot(mountPoint);
    render();
  }

  return { init };
}

function start() {
  // Find all caption containers
  const captionContainers = document.querySelectorAll('.caption');

  captionContainers.forEach(container => {
    const entryId = container.dataset.entryId;
    const htmlCaption = container.innerHTML;
    const rawCaption = container.dataset.rawCaption || '';

    // Create a div to mount React
    const mountPoint = document.createElement('div');
    container.parentNode?.replaceChild(mountPoint, container);

    // Create and initialize the caption editor
    const captionEditor = createCaptionEditor(entryId, rawCaption, htmlCaption);
    captionEditor.init(mountPoint);
  });

  // Handle toggle-hidden checkboxes
  setupHiddenToggleCheckboxes();

  // Handle video play buttons
  setupVideoPlayButtons();
}

// Function to create a hidden toggle checkbox component
function createHiddenToggleCheckbox(entryId: string, initialHidden: boolean) {
  // State variables
  let isHidden = initialHidden;
  let isLoading = false;
  let error: string | null = null;

  // DOM elements
  let root: any = null;

  // Event handlers
  async function handleToggle(newHiddenState: boolean) {
    isLoading = true;
    error = null;
    isHidden = newHiddenState; // Optimistically update the UI
    render();

    try {
      const response = await fetch(`/gallery/entry/${entryId}/set_hidden`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ hidden: newHiddenState }),
      });

      if (!response.ok) {
        throw new Error(`Failed to update hidden status: ${response.status}`);
      }

      const data = await response.json();
      console.log(`Entry ${entryId} hidden status updated to: ${data.hidden}`);

      // Update the state to match the server response
      isHidden = data.hidden;
    } catch (err) {
      error = err instanceof Error ? err.message : 'An unknown error occurred';
      // Revert the state on error
      isHidden = !newHiddenState;
    } finally {
      isLoading = false;
      render();
    }
  }

  // Render function
  function render() {
    if (!root) return;

    root.render(renderCheckbox());
  }

  // Render the checkbox
  function renderCheckbox() {
    const checkbox = React.createElement('input', {
      type: 'checkbox',
      checked: isHidden,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => handleToggle(e.target.checked),
      disabled: isLoading,
      className: 'me-2'
    });

    const label = React.createElement('span', {}, 'Hidden');

    const errorElement = error ? 
      React.createElement('div', { className: 'alert alert-danger mt-2 mb-0 p-2' }, error) : 
      null;

    const loadingIndicator = isLoading ?
      React.createElement('span', { className: 'ms-2 spinner-border spinner-border-sm' }) :
      null;

    return React.createElement('div', { className: 'hidden-toggle-container' },
      React.createElement('label', { className: 'd-flex align-items-center' },
        checkbox,
        label,
        loadingIndicator
      ),
      errorElement
    );
  }

  // Initialize
  function init(mountPoint: HTMLElement) {
    root = createRoot(mountPoint);
    render();
  }

  return { init };
}

// Function to setup hidden toggle checkboxes
function setupHiddenToggleCheckboxes() {
  const checkboxes = document.querySelectorAll('.toggle-hidden-checkbox');

  checkboxes.forEach(checkbox => {
    if (!(checkbox instanceof HTMLInputElement)) return;

    const entryId = checkbox.getAttribute('data-entry-id');
    const isHidden = checkbox.checked;

    if (!entryId) return;

    // Get the parent label element
    const label = checkbox.closest('label');
    if (!label) return;

    // Create a div to mount React
    const mountPoint = document.createElement('div');
    label.parentNode?.replaceChild(mountPoint, label);

    // Create and initialize the hidden toggle component
    const hiddenToggle = createHiddenToggleCheckbox(entryId, isHidden);
    hiddenToggle.init(mountPoint);
  });
}

// Function to set up video play buttons
function setupVideoPlayButtons() {
  const playButtons = document.querySelectorAll('.play-video-btn');

  playButtons.forEach(button => {
    if (!(button instanceof HTMLButtonElement)) return;

    button.addEventListener('click', function() {
      const entryId = this.getAttribute('data-entry-id');
      const videoFilename = this.getAttribute('data-video-filename');

      if (!entryId || !videoFilename) return;

      // Find the entry container
      const entryContainer = this.closest('.entry-container');
      if (!entryContainer) return;

      // Find the image element
      const imgElement = entryContainer.querySelector('img.thumbnail');
      if (!imgElement) return;

      // Get the image dimensions to maintain aspect ratio
      const imgWidth = imgElement.width;
      const imgHeight = imgElement.height;

      // Create a video element
      const videoElement = document.createElement('video');
      videoElement.className = 'img-fluid';
      videoElement.controls = true;
      videoElement.autoplay = true;
      videoElement.width = imgWidth;
      videoElement.height = imgHeight;
      videoElement.style.maxWidth = '100%';

      // Create a source element
      const sourceElement = document.createElement('source');
      sourceElement.src = `/gallery/entry/${entryId}/video`;
      sourceElement.type = 'video/quicktime'; // Assuming .mov file

      // Add the source to the video
      videoElement.appendChild(sourceElement);

      // Store a reference to the button for later use
      const playButton = this;

      // Add event listener for when the video ends
      videoElement.addEventListener('ended', function() {
        // Replace the video with the original image
        this.parentNode?.replaceChild(imgElement, this);

        // Show the play button again
        playButton.style.display = '';
      });

      // Replace the image with the video
      imgElement.parentNode?.replaceChild(videoElement, imgElement);

      // Hide the play button
      this.style.display = 'none';
    });
  });
}


// DOMContentLoaded might not fire with an async script
// https://stackoverflow.com/questions/39993676/code-inside-domcontentloaded-event-not-working
if (document.readyState !== "loading") {
  start();
} else {
  document.addEventListener("DOMContentLoaded", start);
}
