// Robust night mode functionality
(function() {
  'use strict';
  
  function initNightMode() {
    const toggle = document.getElementById('nightModeToggle');
    const body = document.body;
    
    if (!toggle || !body) return;
    
    // Check saved preference
    const savedMode = localStorage.getItem('nightMode') === 'true';
    if (savedMode) {
      body.classList.add('night-mode');
      toggle.classList.add('active');
    }
    
    // Add click handler
    toggle.addEventListener('click', function(e) {
      e.preventDefault();
      body.classList.toggle('night-mode');
      toggle.classList.toggle('active');
      localStorage.setItem('nightMode', body.classList.contains('night-mode'));
    });
  }
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNightMode);
  } else {
    initNightMode();
  }
})();
