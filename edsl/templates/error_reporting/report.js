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
    const textarea = button.parentElement.querySelector('textarea');
    textarea.select();
    document.execCommand('copy');
    
    // Show "Copied!" feedback
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
    // Set initial states for all exception contents
    const exceptionContents = document.querySelectorAll('.exception-content');
    exceptionContents.forEach(content => {
      content.classList.remove('expanded');
    });
    
    // Set aria attributes on headers and add click events
    const exceptionHeaders = document.querySelectorAll('.exception-header');
    exceptionHeaders.forEach(header => {
      header.setAttribute('aria-expanded', 'false');
      header.addEventListener('click', function() {
        toggleExceptionDetail(this);
      });
    });
    
    // Make section headings collapsible if needed
    const sectionHeadings = document.querySelectorAll('.section h3');
    sectionHeadings.forEach(heading => {
      const content = heading.nextElementSibling;
      
      if (content && content.classList.contains('collapsible-content')) {
        heading.classList.add('collapsible-heading');
        
        // Add click event
        heading.addEventListener('click', function() {
          const isCollapsed = content.style.maxHeight === '0px';
          
          if (isCollapsed) {
            content.style.maxHeight = content.scrollHeight + 'px';
            heading.classList.add('expanded');
          } else {
            content.style.maxHeight = '0px';
            heading.classList.remove('expanded');
          }
        });
        
        // Initialize as expanded
        content.style.maxHeight = content.scrollHeight + 'px';
      }
    });
  });