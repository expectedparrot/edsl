// Toggle functionality for exception details
function toggleExceptionDetail(header) {
  const detail = header.closest('.exception-detail');
  const content = detail.querySelector('.exception-content');
  const expanded = header.getAttribute('aria-expanded') === 'true';
  
  if (expanded) {
    content.classList.remove('expanded');
    header.setAttribute('aria-expanded', 'false');
  } else {
    content.classList.add('expanded');
    header.setAttribute('aria-expanded', 'true');
  }
}

// Copy code functionality
function copyCode(button) {
  console.log("Copy button clicked");
  
  // Find the code block - look for pre/code elements after the button's parent
  const section = button.closest('div');
  const codeBlock = section.nextElementSibling;
  
  if (codeBlock) {
    // Get the text content
    let textToCopy = '';
    if (codeBlock.tagName === 'PRE') {
      textToCopy = codeBlock.textContent || '';
    } else if (codeBlock.tagName === 'TEXTAREA') {
      textToCopy = codeBlock.value || '';
    }
    
    // Use clipboard API if available, fallback to execCommand
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(textToCopy)
        .then(() => {
          console.log("Text copied to clipboard successfully");
          showCopiedFeedback(button);
        })
        .catch(err => {
          console.error("Failed to copy text: ", err);
          fallbackCopy(textToCopy, button);
        });
    } else {
      fallbackCopy(textToCopy, button);
    }
  } else {
    console.error("Code block not found");
  }
}

// Fallback copy method using document.execCommand
function fallbackCopy(text, button) {
  // Create temporary textarea
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';  // Avoid scrolling to bottom
  document.body.appendChild(textarea);
  textarea.select();
  
  try {
    const successful = document.execCommand('copy');
    if (successful) {
      console.log("Fallback copy successful");
      showCopiedFeedback(button);
    } else {
      console.error("Fallback copy failed");
    }
  } catch (err) {
    console.error("Fallback copy error:", err);
  }
  
  document.body.removeChild(textarea);
}

// Show copied feedback on button
function showCopiedFeedback(button) {
  const originalText = button.textContent;
  button.textContent = 'Copied!';
  button.disabled = true;
  
  setTimeout(() => {
    button.textContent = originalText;
    button.disabled = false;
  }, 2000);
}

// Initialize all headers on page load
document.addEventListener('DOMContentLoaded', function() {
  console.log("DOM loaded, initializing exception toggles");
  
  // Set initial states for all exception contents
  const exceptionContents = document.querySelectorAll('.exception-content');
  console.log(`Found ${exceptionContents.length} exception contents`);
  
  exceptionContents.forEach(content => {
    content.classList.remove('expanded');
  });
  
  // Set aria attributes on headers and add click events
  const exceptionHeaders = document.querySelectorAll('.exception-header');
  console.log(`Found ${exceptionHeaders.length} exception headers`);
  
  exceptionHeaders.forEach(header => {
    header.setAttribute('aria-expanded', 'false');
    
    // Add click listener
    header.addEventListener('click', function(e) {
      console.log("Header clicked, toggling exception detail");
      toggleExceptionDetail(this);
    });
  });
  
  // Set up copy buttons
  const copyButtons = document.querySelectorAll('.copy-button');
  console.log(`Found ${copyButtons.length} copy buttons`);
  
  copyButtons.forEach(button => {
    // Add click listener
    button.addEventListener('click', function(e) {
      console.log("Copy button clicked");
      e.preventDefault();
      e.stopPropagation();
      copyCode(this);
    });
  });
});