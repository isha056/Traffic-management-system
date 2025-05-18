/**
 * Main JavaScript for Traffic Management System
 */

// Initialize tooltips and popovers when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Enable tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Enable popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    const popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Handle navigation active states
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
    
    // Socket.IO global connection handler (if available)
    if (typeof io !== 'undefined') {
        // Global connection status indicator
        const connectionStatusIndicator = document.getElementById('connection-status');
        const socket = io();
        
        socket.on('connect', function() {
            console.log('Connected to server');
            if (connectionStatusIndicator) {
                connectionStatusIndicator.classList.remove('text-danger');
                connectionStatusIndicator.classList.add('text-success');
                connectionStatusIndicator.textContent = 'Connected';
            }
        });
        
        socket.on('disconnect', function() {
            console.log('Disconnected from server');
            if (connectionStatusIndicator) {
                connectionStatusIndicator.classList.remove('text-success');
                connectionStatusIndicator.classList.add('text-danger');
                connectionStatusIndicator.textContent = 'Disconnected';
            }
        });
    }
    
    // Global notification system
    window.showNotification = function(message, type = 'info', duration = 5000) {
        // Create notification container if it doesn't exist
        let notificationContainer = document.getElementById('notification-container');
        
        if (!notificationContainer) {
            notificationContainer = document.createElement('div');
            notificationContainer.id = 'notification-container';
            notificationContainer.style.position = 'fixed';
            notificationContainer.style.top = '10px';
            notificationContainer.style.right = '10px';
            notificationContainer.style.zIndex = '9999';
            document.body.appendChild(notificationContainer);
        }
        
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show`;
        notification.role = 'alert';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        // Add notification to container
        notificationContainer.appendChild(notification);
        
        // Initialize Bootstrap alert
        const bsAlert = new bootstrap.Alert(notification);
        
        // Auto-dismiss after duration
        setTimeout(() => {
            bsAlert.close();
        }, duration);
    };
    
    // Format date and time globally
    window.formatDateTime = function(dateString) {
        const date = new Date(dateString);
        return date.toLocaleString();
    };
    
    // Format number with commas for thousands
    window.formatNumber = function(number) {
        return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    };
    
    // Handle form validation globally
    const forms = document.querySelectorAll('.needs-validation');
    
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            
            form.classList.add('was-validated');
        }, false);
    });
    
    // Add dark mode toggle functionality if present
    const darkModeToggle = document.getElementById('dark-mode-toggle');
    
    if (darkModeToggle) {
        // Check for saved theme preference or respect OS preference
        const prefersDarkScheme = window.matchMedia('(prefers-color-scheme: dark)');
        const storedTheme = localStorage.getItem('theme');
        
        if (storedTheme === 'dark' || (!storedTheme && prefersDarkScheme.matches)) {
            document.body.classList.add('dark-mode');
            darkModeToggle.checked = true;
        }
        
        // Listen for toggle changes
        darkModeToggle.addEventListener('change', function() {
            if (this.checked) {
                document.body.classList.add('dark-mode');
                localStorage.setItem('theme', 'dark');
            } else {
                document.body.classList.remove('dark-mode');
                localStorage.setItem('theme', 'light');
            }
        });
    }
    
    // Initialize any charts with default settings
    if (typeof Chart !== 'undefined') {
        // Set default options for all charts
        Chart.defaults.font.family = "'Segoe UI', 'Helvetica Neue', 'Arial', sans-serif";
        Chart.defaults.color = '#6c757d';
        Chart.defaults.responsive = true;
        Chart.defaults.maintainAspectRatio = false;
    }
    
    // Print page functionality
    const printButtons = document.querySelectorAll('.btn-print');
    
    printButtons.forEach(button => {
        button.addEventListener('click', function() {
            window.print();
        });
    });
    
    // Scroll to top button
    const scrollTopButton = document.getElementById('scroll-top-btn');
    
    if (scrollTopButton) {
        // Show button when user scrolls down
        window.onscroll = function() {
            if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
                scrollTopButton.style.display = 'block';
            } else {
                scrollTopButton.style.display = 'none';
            }
        };
        
        // Scroll to top when button is clicked
        scrollTopButton.addEventListener('click', function() {
            document.body.scrollTop = 0; // For Safari
            document.documentElement.scrollTop = 0; // For Chrome, Firefox, IE and Opera
        });
    }
});
