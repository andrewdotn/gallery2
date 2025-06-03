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

    return React.createElement('div', { className: 'caption-editor' },
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
  const captionContainers = document.querySelectorAll('.entry-container .col-md-3 > div:last-child');

  captionContainers.forEach(container => {
    // Get the entry ID from the img src attribute in the same entry container
    const entryContainer = container.closest('.entry-container');
    if (!entryContainer) return;

    const imgElement = entryContainer.querySelector('img.thumbnail');
    if (!imgElement) return;

    const imgSrc = imgElement.getAttribute('src');
    if (!imgSrc) return;

    // Extract entry ID from the URL
    const match = imgSrc.match(/entry\/(\d+)\/thumbnail/);
    if (!match) return;

    const entryId = parseInt(match[1], 10);
    const htmlCaption = container.innerHTML;
    const rawCaption = container.getAttribute('data-raw-caption') || '';

    // Create a div to mount React
    const mountPoint = document.createElement('div');
    container.parentNode?.replaceChild(mountPoint, container);

    // Create and initialize the caption editor
    const captionEditor = createCaptionEditor(entryId, rawCaption, htmlCaption);
    captionEditor.init(mountPoint);
  });




}


// DOMContentLoaded might not fire with an async script
// https://stackoverflow.com/questions/39993676/code-inside-domcontentloaded-event-not-working
if (document.readyState !== "loading") {
  start();
} else {
  document.addEventListener("DOMContentLoaded", start);
}
