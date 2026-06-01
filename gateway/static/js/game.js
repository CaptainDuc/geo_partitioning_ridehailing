const GATEWAY = ""; // Relative to host
const DRIVER_ID = "GAME-DRIVER-1";
const REVALIDATE_INTERVAL = 1500;

class Game {
    constructor() {
        this.player = {
            x: 20, // percentage
            y: 50, // percentage
            speed: 1.5,
            targetX: 20,
            targetY: 50
        };
        this.isRunning = false;
        this.timer = null;
        this.isDragging = false;
        this.keys = {};
        
        this.initDOMElements();
        this.initEventListeners();
        this.updateUI();
        this.gameLoop();
    }

    initDOMElements() {
        this.viewport = document.querySelector('.game-viewport');
        this.playerEl = document.getElementById('player');
        this.shardTargetVal = document.getElementById('shard-target');
        this.cityVal = document.getElementById('current-city');
        this.statusVal = document.getElementById('op-status');
        this.logList = document.getElementById('log-list');
        this.btnToggle = document.getElementById('btn-toggle');
        this.regions = document.querySelectorAll('.region');
    }

    initEventListeners() {
        // Keyboard movement
        window.addEventListener('keydown', (e) => this.keys[e.key.toLowerCase()] = true);
        window.addEventListener('keyup', (e) => this.keys[e.key.toLowerCase()] = false);

        // Dragging
        this.playerEl.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.playerEl.style.cursor = 'grabbing';
        });

        window.addEventListener('mousemove', (e) => {
            if (!this.isDragging) return;
            const rect = this.viewport.getBoundingClientRect();
            this.player.x = ((e.clientX - rect.left) / rect.width) * 100;
            this.player.y = ((e.clientY - rect.top) / rect.height) * 100;
            this.clampPlayer();
        });

        window.addEventListener('mouseup', () => {
            this.isDragging = false;
            this.playerEl.style.cursor = 'grab';
        });

        // Controls
        this.btnToggle.addEventListener('click', () => this.toggleRevalidate());
        document.getElementById('btn-reset').addEventListener('click', () => {
            this.player.x = 20;
            this.player.y = 50;
        });
    }

    clampPlayer() {
        this.player.x = Math.max(0, Math.min(100, this.player.x));
        this.player.y = Math.max(0, Math.min(100, this.player.y));
    }

    getCity(x) {
        return x < 50 ? "Paris" : "London";
    }

    getShard(city) {
        return city === "Paris" ? "EU-West" : "EU-North";
    }

    getLatLng(x, y) {
        const city = this.getCity(x);
        const base = city === "Paris" ? { lat: 48.85, lng: 2.35 } : { lat: 51.5, lng: -0.12 };
        return {
            lat: base.lat + (y - 50) * 0.01,
            lng: base.lng + (x - 50) * 0.01
        };
    }

    gameLoop() {
        if (!this.isDragging) {
            if (this.keys['w'] || this.keys['arrowup']) this.player.y -= this.player.speed;
            if (this.keys['s'] || this.keys['arrowdown']) this.player.y += this.player.speed;
            if (this.keys['a'] || this.keys['arrowleft']) this.player.x -= this.player.speed;
            if (this.keys['d'] || this.keys['arrowright']) this.player.x += this.player.speed;
            this.clampPlayer();
        }

        this.updateUI();
        requestAnimationFrame(() => this.gameLoop());
    }

    updateUI() {
        this.playerEl.style.left = `${this.player.x}%`;
        this.playerEl.style.top = `${this.player.y}%`;

        const city = this.getCity(this.player.x);
        const shard = this.getShard(city);

        this.cityVal.textContent = city;
        this.shardTargetVal.textContent = shard;

        this.regions.forEach(r => {
            const isParis = r.classList.contains('paris');
            if ((isParis && city === 'Paris') || (!isParis && city === 'London')) {
                r.classList.add('active');
            } else {
                r.classList.remove('active');
            }
        });
    }

    toggleRevalidate() {
        if (this.isRunning) {
            this.isRunning = false;
            this.btnToggle.textContent = '🚀 Start Revalidate';
            this.btnToggle.classList.remove('btn-stop');
            clearInterval(this.timer);
            this.appendLog("System paused.", "warning");
        } else {
            this.isRunning = true;
            this.btnToggle.textContent = '🛑 Stop Revalidate';
            this.btnToggle.classList.add('btn-stop');
            this.timer = setInterval(() => this.revalidate(), REVALIDATE_INTERVAL);
            this.appendLog("System active. Monitoring position...", "success");
            this.revalidate();
        }
    }

    async revalidate() {
        const x = Math.round(this.player.x);
        const y = Math.round(this.player.y);
        const city = this.getCity(this.player.x);

        const payload = {
            DriverID: DRIVER_ID,
            City: city,
            PosX: x,
            PosY: y
        };

        try {
            const resp = await fetch('/write', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await resp.json();
            
            if (!resp.ok) {
                this.handleFailure(resp.status, data);
                return;
            }

            this.statusVal.textContent = data.operation || 'Synced';
            this.statusVal.style.color = 'var(--success)';
            
            if (data.status === 'migrated') {
                this.showAlert(`MIGRATED: ${data.from} -> ${data.to}`, 'success');
                this.appendLog(`Record migrated from ${data.from} to ${data.to}`, 'success');
                // Trigger visual transition
                const activeRegion = document.querySelector('.region.active');
                activeRegion.classList.add('region-transition');
                setTimeout(() => activeRegion.classList.remove('region-transition'), 1000);
            } else {
                this.appendLog(`Synced to ${data.routed_to} (${city})`);
            }

        } catch (err) {
            this.handleFailure(503, { error: "Network Error / Shard Unreachable" });
        }
    }

    handleFailure(status, data) {
        this.statusVal.textContent = 'Error: ' + status;
        this.statusVal.style.color = 'var(--danger)';
        
        let msg = data.error || 'Unknown Error';
        this.showAlert(`FAILURE [${status}]: ${msg}`, 'danger');
        this.appendLog(`CRITICAL: ${msg} (Status: ${status})`, 'error');

        // Detailed failure handling visualization
        if (status === 503) {
            this.appendLog("HINT: It seems one of the backend shard nodes is offline.", "warning");
        } else if (status === 404) {
            this.appendLog("HINT: Driver ID not found during migration lookup.", "warning");
        }
    }

    appendLog(msg, type = '') {
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        const time = new Date().toLocaleTimeString();
        entry.textContent = `[${time}] ${msg}`;
        this.logList.prepend(entry);
        
        // Keep logs manageable
        if (this.logList.children.length > 50) {
            this.logList.removeChild(this.logList.lastChild);
        }
    }

    showAlert(msg, type) {
        const overlay = document.getElementById('failure-overlay');
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.textContent = msg;
        overlay.appendChild(alert);
        setTimeout(() => alert.remove(), 4000);
    }
}

// Initialize game
window.addEventListener('load', () => {
    new Game();
});
