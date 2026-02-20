/**
 * Dashboard Real-time Updates via WebSocket
 */

class DashboardWebSocket {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        this.connect();
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/notifications/`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('✓ WebSocket connected');
                this.reconnectAttempts = 0;
                this.onConnected();
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (e) {
                    console.error('Error parsing WebSocket message:', e);
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.onError(error);
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.attemptReconnect();
            };
        } catch (e) {
            console.error('Failed to create WebSocket:', e);
            this.attemptReconnect();
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            setTimeout(() => this.connect(), this.reconnectDelay);
        } else {
            console.error('Max reconnection attempts reached');
        }
    }

    handleMessage(data) {
        const { type, payload } = data;

        switch (type) {
            case 'notification':
                this.handleNotification(payload);
                break;
            case 'submission_result':
                this.handleSubmissionResult(payload);
                break;
            case 'instance_status':
                this.handleInstanceStatus(payload);
                break;
            case 'scoreboard_update':
                this.handleScoreboardUpdate(payload);
                break;
            default:
                console.log('Unknown message type:', type);
        }
    }

    handleNotification(payload) {
        const { title, message, type, priority } = payload;
        
        console.log(`📬 Notification [${type}]: ${title}`);
        
        // Show toast notification
        this.showToast(title, message, type, priority);
        
        // Add to recent activity if it's a submission
        if (type === 'submission' || type === 'violation') {
            this.refreshRecentActivity();
        }
    }

    handleSubmissionResult(payload) {
        const { challenge_name, is_correct, points, is_first_blood } = payload;
        
        if (is_correct) {
            let message = `🎉 Correct! +${points} points`;
            if (is_first_blood) {
                message += ' 🩸 FIRST BLOOD!';
            }
            this.showToast(`Challenge Solved: ${challenge_name}`, message, 'success', 'high');
            
            // Refresh dashboard stats
            this.refreshStats();
        } else {
            this.showToast(`Challenge: ${challenge_name}`, 'Flag incorrect, try again!', 'error', 'normal');
        }
    }

    handleInstanceStatus(payload) {
        const { instance_id, status, challenge_name, message } = payload;
        
        console.log(`🔌 Instance ${instance_id} status: ${status}`);
        
        if (status === 'running') {
            this.showToast(`Instance Started: ${challenge_name}`, 'Your instance is ready!', 'success', 'normal');
        } else if (status === 'error') {
            this.showToast(`Instance Error: ${challenge_name}`, message || 'Failed to start instance', 'error', 'high');
        }
        
        // Refresh instances list
        this.refreshInstances();
    }

    handleScoreboardUpdate(payload) {
        const { team_rank, new_score, rank_change } = payload;
        
        let message = `Your rank: #${team_rank} (Score: ${new_score})`;
        if (rank_change < 0) {
            message += ` ⬆️ Up ${-rank_change}`;
        } else if (rank_change > 0) {
            message += ` ⬇️ Down ${rank_change}`;
        }
        
        this.showToast('Scoreboard Updated', message, 'info', 'normal');
        this.refreshScoreboard();
    }

    showToast(title, message, type = 'info', priority = 'normal') {
        const toast = document.createElement('div');
        
        const colors = {
            success: 'bg-green-500/20 border-green-500/50 text-green-400',
            error: 'bg-blue-500/20 border-blue-500/50 text-blue-400',
            info: 'bg-blue-500/20 border-blue-500/50 text-blue-400',
            warning: 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400'
        };
        
        const icons = {
            success: '✓',
            error: '✗',
            info: 'ℹ',
            warning: '⚠'
        };
        
        toast.className = `fixed top-4 right-4 max-w-sm ${colors[type] || colors.info} border rounded-lg p-4 backdrop-blur-md shadow-lg z-50 animate-slide-in`;

        const wrapper = document.createElement('div');
        wrapper.className = 'flex items-start gap-3';

        const iconSpan = document.createElement('span');
        iconSpan.className = 'text-xl';
        iconSpan.textContent = icons[type] || icons.info;

        const textContainer = document.createElement('div');
        textContainer.className = 'flex-1';
        const titleEl = document.createElement('h4');
        titleEl.className = 'font-bold';
        titleEl.textContent = String(title || '');
        const msgEl = document.createElement('p');
        msgEl.className = 'text-sm opacity-90';
        msgEl.textContent = String(message || '');
        textContainer.appendChild(titleEl);
        textContainer.appendChild(msgEl);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'ml-2 opacity-70 hover:opacity-100 transition';
        closeBtn.textContent = '×';
        closeBtn.addEventListener('click', () => {
            if (toast.parentElement) {
                toast.remove();
            }
        });

        wrapper.appendChild(iconSpan);
        wrapper.appendChild(textContainer);
        wrapper.appendChild(closeBtn);
        toast.appendChild(wrapper);
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.animation = 'slide-out 0.3s ease-out forwards';
                setTimeout(() => toast.remove(), 300);
            }
        }, 5000);
    }

    refreshStats() {
        // Fetch updated stats via AJAX
        fetch('/dojo/api/dashboard-stats/')
            .then(r => r.json())
            .then(data => this.updateStats(data))
            .catch(e => console.error('Failed to refresh stats:', e));
    }

    refreshScoreboard() {
        // Fetch updated scoreboard
        fetch('/dojo/api/dashboard-scoreboard/')
            .then(r => r.json())
            .then(data => this.updateScoreboard(data))
            .catch(e => console.error('Failed to refresh scoreboard:', e));
    }

    refreshInstances() {
        // Fetch updated instances
        fetch('/dojo/api/instances/')
            .then(r => r.json())
            .then(data => this.updateInstances(data))
            .catch(e => console.error('Failed to refresh instances:', e));
    }

    refreshRecentActivity() {
        // Fetch recent submissions
        fetch('/dojo/api/submissions/my_submissions/?limit=10')
            .then(r => r.json())
            .then(data => this.updateRecentActivity(data))
            .catch(e => console.error('Failed to refresh activity:', e));
    }

    updateStats(data) {
        // Update DOM elements with new stats
        const elements = {
            score: document.querySelector('[data-stat="score"]'),
            solved: document.querySelector('[data-stat="solved"]'),
            instances: document.querySelector('[data-stat="instances"]'),
            rank: document.querySelector('[data-stat="rank"]')
        };

        Object.entries(elements).forEach(([key, el]) => {
            if (el && data[key] !== undefined) {
                el.textContent = data[key];
                el.classList.add('animate-pulse');
                setTimeout(() => el.classList.remove('animate-pulse'), 500);
            }
        });
    }

    updateScoreboard(data) {
        const scoreboard = document.querySelector('[data-component="scoreboard"]');
        if (scoreboard && data.teams) {
            // Update scoreboard with new data
            console.log('Updating scoreboard with', data.teams.length, 'teams');
        }
    }

    updateInstances(data) {
        const instancesList = document.querySelector('[data-component="instances"]');
        if (instancesList && data.results) {
            console.log('Updating instances with', data.results.length, 'instances');
        }
    }

    updateRecentActivity(data) {
        const activity = document.querySelector('[data-component="activity"]');
        if (activity && data.results) {
            console.log('Updating recent activity with', data.results.length, 'submissions');
        }
    }

    onConnected() {
        console.log('✓ WebSocket connection established');
        // Notify user
        this.showToast('Connected', 'Real-time updates enabled', 'success', 'low');
    }

    onError(error) {
        console.error('WebSocket connection error:', error);
        this.showToast('Connection Error', 'Real-time updates disconnected', 'error', 'high');
    }

    close() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Initialize WebSocket on page load
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('[data-dashboard]')) {
        window.dashboardWS = new DashboardWebSocket();
    }
});

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slide-in {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slide-out {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }

    .animate-slide-in {
        animation: slide-in 0.3s ease-out forwards;
    }

    @keyframes pulse {
        0%, 100% {
            opacity: 1;
        }
        50% {
            opacity: 0.5;
        }
    }

    .animate-pulse {
        animation: pulse 0.6s ease-in-out;
    }
`;
document.head.appendChild(style);
