/**
 * Video streaming functionality for Traffic Management System
 */

document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the dashboard page with video elements
    const videoFeed = document.getElementById('video-feed');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const loadingIndicator = document.getElementById('loading-indicator');
    const violationAlert = document.getElementById('violation-alert');
    
    if (!videoFeed || !startBtn || !stopBtn) {
        return; // Not on the dashboard page
    }
    
    // Socket.IO connection for real-time updates
    console.log('Initializing Socket.IO connection...');
    const socket = io();
    let isStreaming = false;
    
    // Socket connection event handlers
    socket.on('connect', function() {
        console.log('Socket.IO connected successfully');
    });
    
    socket.on('disconnect', function() {
        console.log('Socket.IO disconnected');
        if (isStreaming) {
            // Show error notification
            if (window.showNotification) {
                window.showNotification('Connection to server lost. Video stream interrupted.', 'warning');
            }
        }
    });
    
    socket.on('connect_error', function(error) {
        console.error('Socket.IO connection error:', error);
    });
    
    // Handle start button click
    startBtn.addEventListener('click', function() {
        if (isStreaming) return;
        
        // Show loading indicator
        loadingIndicator.classList.remove('d-none');
        
        // Get video source from the dropdown
        const videoSourceSelect = document.getElementById('video-source');
        const videoSource = videoSourceSelect ? videoSourceSelect.value : 'my.mp4';
        
        // Make API call to start processing
        fetch('/start_processing', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `video_path=${videoSource}`
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                console.log('Video processing started successfully');
                isStreaming = true;
                startBtn.disabled = true;
                stopBtn.disabled = false;
                
                // Hide loading indicator after a short delay
                setTimeout(() => {
                    loadingIndicator.classList.add('d-none');
                }, 1000);
                
                // Show notification
                if (window.showNotification) {
                    window.showNotification('Video processing started successfully', 'success');
                }
            } else {
                console.error('Failed to start video processing:', data.message);
                loadingIndicator.classList.add('d-none');
                
                // Show error notification
                if (window.showNotification) {
                    window.showNotification('Error: ' + data.message, 'danger');
                }
            }
        })
        .catch(error => {
            console.error('Error starting video processing:', error);
            loadingIndicator.classList.add('d-none');
            
            // Show error notification
            if (window.showNotification) {
                window.showNotification('Error connecting to server', 'danger');
            }
        });
    });
    
    // Handle stop button click
    stopBtn.addEventListener('click', function() {
        if (!isStreaming) return;
        
        fetch('/stop_processing', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                console.log('Video processing stopped');
                isStreaming = false;
                startBtn.disabled = false;
                stopBtn.disabled = true;
                
                // Reset video feed to placeholder
                videoFeed.src = 'https://via.placeholder.com/800x450?text=Press+Start+to+Begin+Stream';
                
                // Show notification
                if (window.showNotification) {
                    window.showNotification('Video processing stopped', 'info');
                }
            } else {
                console.error('Failed to stop video processing:', data.message);
                
                // Show error notification
                if (window.showNotification) {
                    window.showNotification('Error: ' + data.message, 'danger');
                }
            }
        })
        .catch(error => {
            console.error('Error stopping video processing:', error);
            
            // Show error notification
            if (window.showNotification) {
                window.showNotification('Error connecting to server', 'danger');
            }
        });
    });
    
    // Handle incoming frames from Socket.IO
    socket.on('frame_update', function(data) {
        console.log('Received frame update');
        if (data.frame) {
            console.log('Setting video frame source');
            videoFeed.src = 'data:image/jpeg;base64,' + data.frame;
        } else {
            console.warn('Received frame update without frame data');
        }
        
        // Update vehicle counts
        updateVehicleCounts(data.vehicle_counts);
        
        // Update violation counts
        updateViolationCounts(data.violations);
    });
    
    // Update vehicle counts in the UI
    function updateVehicleCounts(counts) {
        if (!counts) return;
        
        // Update individual counts
        const vehicleTypes = ['car', 'truck', 'bus', 'motorcycle', 'bicycle'];
        let totalCount = 0;
        
        vehicleTypes.forEach(type => {
            const countElement = document.getElementById(`${type}-count`);
            if (countElement) {
                const count = counts[type] || 0;
                countElement.textContent = count;
                totalCount += count;
            }
        });
        
        // Update total count
        const totalElement = document.getElementById('total-count');
        if (totalElement) {
            totalElement.textContent = totalCount;
        }
    }
    
    // Update violation counts in the UI
    function updateViolationCounts(violations) {
        if (!violations) return;
        
        // Update violation counters
        const violationTypes = ['speeding', 'red_light', 'wrong_way', 'illegal_parking', 'no_helmet'];
        
        violationTypes.forEach(type => {
            const countElement = document.getElementById(`${type}-count`);
            if (countElement) {
                countElement.textContent = violations[type] || 0;
            }
        });
        
        // Calculate total violations
        const totalViolations = Object.values(violations).reduce((sum, count) => sum + count, 0);
        const totalElement = document.getElementById('total-violations');
        if (totalElement) {
            totalElement.textContent = totalViolations;
        }
        
        // Show violation alert if there are new violations
        if (totalViolations > 0 && violationAlert) {
            violationAlert.classList.add('show-alert');
            setTimeout(() => {
                violationAlert.classList.remove('show-alert');
            }, 3000);
        }
    }
});
