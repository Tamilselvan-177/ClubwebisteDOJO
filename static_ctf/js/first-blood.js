/**
 * First Blood Animation System
 * Triggers when a challenge is solved first
 * Inspired by Stranger Things - Dark, neon, cinematic
 */

class FirstBloodAnimator {
    constructor() {
        this.isAnimating = false;
        this.soundEnabled = localStorage.getItem('sound-enabled') !== 'false';
        this.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    /**
     * Trigger the First Blood animation
     * @param {Object} data - Event data containing playerName, challengeName, teamColor
     */
    async triggerFirstBlood(data) {
        if (this.isAnimating || this.reducedMotion) return;
        
        this.isAnimating = true;
        
        // 1. VHS distortion effect
        await this.vhsDistortion();
        
        // 2. Lockdown screen
        await this.screenLockdown();
        
        // 3. Create blood crack effect
        await this.createBloodCrack(data);
        
        // 4. Ring/Impact effect
        await this.ringEffect();
        
        // 5. Cinematic reveal with text animation
        await this.cinematicReveal(data);
        
        // 6. Particle explosion
        this.particleExplosion();
        
        // 7. Screen glitch
        await this.screenGlitch();
        
        // 8. Return to normal
        await this.screenRestore();
        
        this.isAnimating = false;
        
        // Update leaderboard
        this.updateLeaderboard();
    }

    /**
     * VHS distortion effect at start
     */
    async vhsDistortion() {
        const vhs = document.createElement('div');
        vhs.style.position = 'fixed';
        vhs.style.top = '0';
        vhs.style.left = '0';
        vhs.style.width = '100%';
        vhs.style.height = '100%';
        vhs.style.zIndex = '9995';
        vhs.style.pointerEvents = 'none';
        vhs.style.background = `
            repeating-linear-gradient(
                0deg,
                rgba(255, 0, 0, 0.03),
                rgba(255, 0, 0, 0.03) 1px,
                transparent 1px,
                transparent 2px
            )
        `;
        vhs.style.animation = 'vhsScanlines 0.15s linear infinite';
        vhs.style.mixBlendMode = 'overlay';
        document.body.appendChild(vhs);

        return new Promise(resolve => setTimeout(resolve, 600));
    }

    /**
     * Ring/Impact effect from center
     */
    async ringEffect() {
        const rings = 3;
        for (let i = 0; i < rings; i++) {
            const ring = document.createElement('div');
            ring.style.position = 'fixed';
            ring.style.top = '50%';
            ring.style.left = '50%';
            ring.style.width = '100px';
            ring.style.height = '100px';
            ring.style.border = '3px solid #ff0000';
            ring.style.borderRadius = '50%';
            ring.style.transform = 'translate(-50%, -50%)';
            ring.style.zIndex = '9996';
            ring.style.pointerEvents = 'none';
            ring.style.boxShadow = '0 0 20px #ff0000';
            ring.style.animation = `ringExpand 0.8s ease-out forwards`;
            ring.style.animationDelay = `${i * 0.15}s`;
            document.body.appendChild(ring);

            setTimeout(() => ring.remove(), 1200);
        }

        return new Promise(resolve => setTimeout(resolve, 600));
    }

    /**
     * Enhanced screen glitch effect
     */
    async screenGlitch() {
        const body = document.body;
        body.style.animation = 'screenGlitch 0.6s ease-out forwards';

        return new Promise(resolve => setTimeout(resolve, 600));
    }

    /**
     * Lock down the screen with dimming and rumble
     */
    async screenLockdown() {
        const overlay = document.createElement('div');
        overlay.id = 'first-blood-overlay';
        overlay.style.position = 'fixed';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.zIndex = '9998';
        overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
        overlay.style.backdropFilter = 'blur(4px)';
        overlay.style.animation = 'fadeIn 0.3s ease-out';
        overlay.style.pointerEvents = 'none';
        document.body.appendChild(overlay);

        // Play rumble sound
        if (this.soundEnabled) {
            this.playSound('rumble');
        }

        // Camera shake
        this.cameraShake(3, 0.3);

        return new Promise(resolve => setTimeout(resolve, 500));
    }

    /**
     * Create animated blood crack effect
     */
    async createBloodCrack(data) {
        const container = document.createElement('div');
        container.id = 'first-blood-container';
        container.style.position = 'fixed';
        container.style.top = '0';
        container.style.left = '0';
        container.style.width = '100%';
        container.style.height = '100%';
        container.style.zIndex = '9999';
        container.style.display = 'flex';
        container.style.alignItems = 'center';
        container.style.justifyContent = 'center';
        container.style.pointerEvents = 'none';
        document.body.appendChild(container);

        // Create SVG crack
        const svg = this.createCrackSVG();
        container.appendChild(svg);

        // Animate crack lines
        const paths = svg.querySelectorAll('path');
        paths.forEach((path, index) => {
            const length = path.getTotalLength();
            path.style.strokeDasharray = length;
            path.style.strokeDashoffset = length;
            path.style.animation = `crackDraw 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) forwards`;
            path.style.animationDelay = `${index * 0.1}s`;
        });

        // Blood particle effects from crack
        await this.bloodSpill(container);

        // Add splatter effects on screen
        await this.bloodSplatter(container);

        return new Promise(resolve => setTimeout(resolve, 1200));
    }

    /**
     * Create SVG crack pattern
     */
    createCrackSVG() {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', '100%');
        svg.setAttribute('height', '100%');
        svg.setAttribute('viewBox', '0 0 1920 1080');
        svg.setAttribute('preserveAspectRatio', 'xMidYMid slice');
        
        // Center crack
        const mainCrack = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        mainCrack.setAttribute('d', 'M960,0 Q950,200 945,540 Q940,900 960,1080');
        mainCrack.setAttribute('stroke', '#ff0000');
        mainCrack.setAttribute('stroke-width', '4');
        mainCrack.setAttribute('fill', 'none');
        mainCrack.setAttribute('filter', 'drop-shadow(0 0 10px #ff0000)');
        
        // Left cracks
        const leftCrack1 = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        leftCrack1.setAttribute('d', 'M945,540 L700,450 L650,650');
        leftCrack1.setAttribute('stroke', '#ff4444');
        leftCrack1.setAttribute('stroke-width', '2');
        leftCrack1.setAttribute('fill', 'none');
        leftCrack1.setAttribute('filter', 'drop-shadow(0 0 5px #ff0000)');
        
        // Right cracks
        const rightCrack1 = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        rightCrack1.setAttribute('d', 'M945,540 L1220,450 L1270,650');
        rightCrack1.setAttribute('stroke', '#ff4444');
        rightCrack1.setAttribute('stroke-width', '2');
        rightCrack1.setAttribute('fill', 'none');
        rightCrack1.setAttribute('filter', 'drop-shadow(0 0 5px #ff0000)');
        
        svg.appendChild(mainCrack);
        svg.appendChild(leftCrack1);
        svg.appendChild(rightCrack1);
        
        return svg;
    }

    /**
     * Animate blood spilling from crack - ENHANCED
     */
    async bloodSpill(container) {
        const dropCount = 60;
        
        for (let i = 0; i < dropCount; i++) {
            const drop = document.createElement('div');
            
            const size = 1 + Math.random() * 3;
            drop.style.width = size + 'px';
            drop.style.height = size + 'px';
            drop.style.position = 'absolute';
            drop.style.borderRadius = '50%';
            drop.style.backgroundColor = '#ff0000';
            drop.style.boxShadow = `0 0 ${4 + Math.random() * 8}px #ff0000`;
            
            drop.style.left = `calc(50% + ${(Math.random() - 0.5) * 150}px)`;
            drop.style.top = '50%';
            drop.style.opacity = '0.9';
            
            const xOffset = (Math.random() - 0.5) * 600;
            const yOffset = Math.random() * 800 + 100;
            const duration = 1.2 + Math.random() * 0.6;
            const rotation = Math.random() * 360;
            
            drop.style.animation = `bloodDrop ${duration}s ease-in forwards`;
            drop.style.setProperty('--x-offset', `${xOffset}px`);
            drop.style.setProperty('--y-offset', `${yOffset}px`);
            drop.style.setProperty('--rotation', rotation);
            drop.style.animationDelay = `${i * 0.015}s`;
            
            container.appendChild(drop);
            
            // Remove after animation
            setTimeout(() => drop.remove(), (duration + 0.3) * 1000);
        }

        return new Promise(resolve => setTimeout(resolve, 1000));
    }

    /**
     * Create blood splatter effects on screen
     */
    async bloodSplatter(container) {
        const splatterCount = 20;
        
        for (let i = 0; i < splatterCount; i++) {
            setTimeout(() => {
                // Weighted distribution - more splatters on edges
                let x, y;
                if (Math.random() < 0.6) {
                    // Edges and corners
                    const edge = Math.floor(Math.random() * 4);
                    if (edge === 0) x = Math.random() * 20; // Left
                    else if (edge === 1) x = 80 + Math.random() * 20; // Right
                    else if (edge === 2) y = Math.random() * 20; // Top
                    else y = 80 + Math.random() * 20; // Bottom
                    
                    if (!x) x = Math.random() * 100;
                    if (!y) y = Math.random() * 100;
                } else {
                    // Random anywhere
                    x = Math.random() * 100;
                    y = Math.random() * 100;
                }
                
                const size = 40 + Math.random() * 180;
                const rotation = Math.random() * 360;
                
                const splatter = document.createElement('div');
                splatter.style.position = 'fixed';
                splatter.style.left = x + '%';
                splatter.style.top = y + '%';
                splatter.style.width = size + 'px';
                splatter.style.height = size + 'px';
                splatter.style.zIndex = '9997';
                splatter.style.pointerEvents = 'none';
                splatter.style.transform = `translate(-50%, -50%) rotate(${rotation}deg)`;
                
                // SVG splatter shape
                const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                svg.setAttribute('viewBox', '0 0 100 100');
                svg.setAttribute('width', '100%');
                svg.setAttribute('height', '100%');
                svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
                
                // Create splatter blob with irregular edges
                const splatterPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                const splatPattern = this.generateSplatPattern();
                splatterPath.setAttribute('d', splatPattern);
                splatterPath.setAttribute('fill', '#ff0000');
                splatterPath.setAttribute('opacity', '0.7');
                splatterPath.setAttribute('filter', 'drop-shadow(0 0 6px #ff0000)');
                
                svg.appendChild(splatterPath);
                
                // Add secondary splatters (smaller)
                if (Math.random() > 0.4) {
                    for (let j = 0; j < 2 + Math.floor(Math.random() * 2); j++) {
                        const secondaryPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                        const smallPattern = this.generateSplatPattern();
                        const offsetX = (Math.random() - 0.5) * 40;
                        const offsetY = (Math.random() - 0.5) * 40;
                        const scale = 0.4 + Math.random() * 0.4;
                        
                        secondaryPath.setAttribute('d', smallPattern);
                        secondaryPath.setAttribute('fill', '#cc0000');
                        secondaryPath.setAttribute('opacity', `${0.4 + Math.random() * 0.4}`);
                        secondaryPath.setAttribute('transform', `translate(${offsetX}, ${offsetY}) scale(${scale})`);
                        
                        svg.appendChild(secondaryPath);
                    }
                }
                
                splatter.appendChild(svg);
                
                splatter.style.animation = `splatterAppear 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards, splatterFade 2s ease-in forwards`;
                splatter.style.animationDelay = `${i * 0.06}s, ${i * 0.06 + 1.8}s`;
                
                container.appendChild(splatter);
                
                // Remove after animation
                setTimeout(() => splatter.remove(), 5000);
            }, i * 80);
        }

        return new Promise(resolve => setTimeout(resolve, 1000));
    }

    /**
     * Generate random splat pattern
     */
    generateSplatPattern() {
        const numPoints = 8 + Math.floor(Math.random() * 4);
        let path = 'M 50,50';
        
        for (let i = 0; i < numPoints; i++) {
            const angle = (i / numPoints) * Math.PI * 2;
            const radius = 30 + Math.random() * 20;
            const x = 50 + Math.cos(angle) * radius;
            const y = 50 + Math.sin(angle) * radius;
            
            // Add variance for irregular splat
            const nextAngle = ((i + 1) / numPoints) * Math.PI * 2;
            const nextRadius = 30 + Math.random() * 20;
            const nextX = 50 + Math.cos(nextAngle) * nextRadius;
            const nextY = 50 + Math.sin(nextAngle) * nextRadius;
            
            path += ` Q ${x + (Math.random() - 0.5) * 10},${y + (Math.random() - 0.5) * 10} ${nextX},${nextY}`;
        }
        
        path += ' Z';
        return path;
    }

    /**
     * Cinematic text reveal
     */
    async cinematicReveal(data) {
        const escapeHtml = (value) => String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');

        const safePlayer = escapeHtml(data.playerName);
        const safeChallenge = escapeHtml(data.challengeName);
        const safeTeam = escapeHtml(data.teamName);
        const safePoints = Number.isFinite(Number(data.points)) ? Number(data.points) : 0;

        const textContainer = document.createElement('div');
        textContainer.style.position = 'fixed';
        textContainer.style.top = '0';
        textContainer.style.left = '0';
        textContainer.style.width = '100%';
        textContainer.style.height = '100%';
        textContainer.style.zIndex = '10000';
        textContainer.style.display = 'flex';
        textContainer.style.alignItems = 'center';
        textContainer.style.justifyContent = 'center';
        textContainer.style.pointerEvents = 'none';
        textContainer.innerHTML = `
            <div class="text-center" style="animation: textEntrance 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;">
                <div class="text-7xl font-black mb-6 text-red-600" style="
                    text-shadow: 0 0 40px #ff0000, 0 0 80px #ff4444, 0 0 120px #cc0000;
                    animation: neonGlow 1.5s ease-in-out infinite;
                    letter-spacing: 4px;
                ">
                    🩸 FIRST BLOOD 🩸
                </div>
                <div class="text-4xl font-display text-red-400 glitch mb-6" data-text="${safePlayer} has conquered ${safeChallenge}" style="
                    text-shadow: 0 0 20px #ff0000;
                    animation: glitch 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
                ">
                    ${safePlayer} has conquered ${safeChallenge}
                </div>
                <div class="text-2xl text-red-300 mt-6 font-mono" style="
                    animation: flicker 0.1s infinite;
                    text-shadow: 0 0 10px #ff0000;
                    letter-spacing: 1px;
                ">
                    Team: <span class="font-bold text-red-500">${safeTeam}</span> • <span class="text-yellow-400">+${safePoints} pts</span>
                </div>
            </div>
        `;
        document.body.appendChild(textContainer);

        // Play synth bass
        if (this.soundEnabled) {
            this.playSound('synth-drop');
        }

        // Glitch effect
        this.glitchText(textContainer.querySelector('.glitch'));

        // Multiple thunder flashes
        this.thunderFlash();
        setTimeout(() => this.thunderFlash(), 200);
        setTimeout(() => this.thunderFlash(), 600);

        return new Promise(resolve => setTimeout(resolve, 2500));
    }

    /**
     * Glitch text effect
     */
    glitchText(element) {
        const text = element.getAttribute('data-text');
        let iteration = 0;
        
        const interval = setInterval(() => {
            element.textContent = text
                .split('')
                .map((char, index) => {
                    if (index < iteration) return char;
                    return Math.random() > 0.8 ? String.fromCharCode(33 + Math.floor(Math.random() * 94)) : char;
                })
                .join('');
            
            if (iteration >= text.length) {
                clearInterval(interval);
            }
            iteration++;
        }, 20);
    }

    /**
     * Thunder/lightning flash effect
     */
    thunderFlash() {
        const flash = document.createElement('div');
        flash.style.position = 'fixed';
        flash.style.top = '0';
        flash.style.left = '0';
        flash.style.width = '100%';
        flash.style.height = '100%';
        flash.style.zIndex = '10001';
        flash.style.pointerEvents = 'none';
        flash.style.backgroundColor = '#00ffff';
        flash.style.opacity = '0';
        flash.style.animation = 'thunderFlash 0.1s ease-out';
        document.body.appendChild(flash);

        setTimeout(() => flash.remove(), 100);
    }

    /**
     * Spawn atmospheric particles - ENHANCED
     */
    spawnParticles() {
        const container = document.getElementById('first-blood-container');
        if (!container) return;

        const particleCount = 80;
        
        for (let i = 0; i < particleCount; i++) {
            const particle = document.createElement('div');
            particle.className = 'absolute rounded-full';
            
            const type = Math.random();
            const size = Math.random() * 4 + 1;
            
            particle.style.width = size + 'px';
            particle.style.height = size + 'px';
            
            if (type < 0.3) {
                // Red blood particles
                particle.style.backgroundColor = '#ff0000';
                particle.style.boxShadow = '0 0 8px #ff0000, 0 0 16px #ff4444';
            } else if (type < 0.5) {
                // Cyan glow
                particle.style.backgroundColor = '#00ffff';
                particle.style.boxShadow = '0 0 10px #00ffff, 0 0 20px #0088ff';
            } else if (type < 0.7) {
                // Magenta spores
                particle.style.backgroundColor = '#ff00ff';
                particle.style.boxShadow = '0 0 8px #ff00ff, 0 0 16px #ff0088';
            } else {
                // Yellow sparks
                particle.style.backgroundColor = '#ffff00';
                particle.style.boxShadow = '0 0 10px #ffff00, 0 0 20px #ffaa00';
            }

            particle.style.left = '50%';
            particle.style.top = '50%';
            
            // Random direction for explosion
            const angle = (Math.random() * Math.PI * 2);
            const velocity = 5 + Math.random() * 10;
            const xVel = Math.cos(angle) * velocity;
            const yVel = Math.sin(angle) * velocity;
            
            const duration = 1.5 + Math.random() * 1.5;
            const delay = Math.random() * 0.1;
            
            particle.style.animation = `particleExplode ${duration}s ease-out forwards`;
            particle.style.setProperty('--vx', xVel);
            particle.style.setProperty('--vy', yVel);
            particle.style.animationDelay = delay + 's';
            particle.style.opacity = '1';
            
            container.appendChild(particle);
            setTimeout(() => particle.remove(), (duration + delay + 0.5) * 1000);
        }
    }

    /**
     * Enhanced particle explosion from center
     */
    particleExplosion() {
        const container = document.createElement('div');
        container.style.position = 'fixed';
        container.style.top = '0';
        container.style.left = '0';
        container.style.width = '100%';
        container.style.height = '100%';
        container.style.zIndex = '9997';
        container.style.pointerEvents = 'none';
        document.body.appendChild(container);

        const explosionCount = 150;
        
        for (let i = 0; i < explosionCount; i++) {
            const particle = document.createElement('div');
            
            const size = Math.random() * 6 + 2;
            const type = Math.random();
            
            particle.style.position = 'absolute';
            particle.style.width = size + 'px';
            particle.style.height = size + 'px';
            particle.style.borderRadius = '50%';
            particle.style.top = '50%';
            particle.style.left = '50%';
            particle.style.pointerEvents = 'none';
            
            if (type < 0.4) {
                particle.style.backgroundColor = '#ff0000';
                particle.style.boxShadow = '0 0 10px #ff0000';
            } else if (type < 0.7) {
                particle.style.backgroundColor = '#ff4444';
                particle.style.boxShadow = '0 0 8px #ff4444';
            } else {
                particle.style.backgroundColor = '#ffaa00';
                particle.style.boxShadow = '0 0 12px #ffaa00';
            }
            
            const angle = (Math.random() * Math.PI * 2);
            const distance = 100 + Math.random() * 400;
            const vx = Math.cos(angle) * distance;
            const vy = Math.sin(angle) * distance;
            const duration = 1 + Math.random() * 1.5;
            const delay = Math.random() * 0.2;
            
            particle.style.animation = `explosionParticle ${duration}s cubic-bezier(0.25, 0.46, 0.45, 0.94) forwards`;
            particle.style.setProperty('--vx', vx);
            particle.style.setProperty('--vy', vy);
            particle.style.animationDelay = delay + 's';
            
            container.appendChild(particle);
            setTimeout(() => particle.remove(), (duration + delay + 0.5) * 1000);
        }

        setTimeout(() => container.remove(), 4000);
    }

    /**
     * Restore screen to normal
     */
    async screenRestore() {
        const overlay = document.getElementById('first-blood-overlay');
        const container = document.getElementById('first-blood-container');
        
        if (overlay) {
            overlay.style.animation = 'fadeOut 0.8s ease-out forwards';
            setTimeout(() => overlay.remove(), 800);
        }
        
        if (container) {
            container.style.animation = 'fadeOut 1s ease-out forwards';
            setTimeout(() => container.remove(), 1000);
        }

        return new Promise(resolve => setTimeout(resolve, 1000));
    }

    /**
     * Camera shake effect
     */
    cameraShake(intensity, duration) {
        const body = document.body;
        const startTime = Date.now();
        
        const shake = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / (duration * 1000), 1);
            
            if (progress < 1) {
                const amount = intensity * (1 - progress);
                body.style.transform = `translate(${(Math.random() - 0.5) * amount}px, ${(Math.random() - 0.5) * amount}px)`;
                requestAnimationFrame(shake);
            } else {
                body.style.transform = 'translate(0, 0)';
            }
        };
        
        shake();
    }

    /**
     * Play sound effects
     */
    playSound(type) {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        
        if (type === 'rumble') {
            // Low frequency rumble
            const osc = audioContext.createOscillator();
            const gain = audioContext.createGain();
            
            osc.connect(gain);
            gain.connect(audioContext.destination);
            
            osc.frequency.value = 40;
            gain.gain.setValueAtTime(0.3, audioContext.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
            
            osc.start(audioContext.currentTime);
            osc.stop(audioContext.currentTime + 0.3);
        } else if (type === 'synth-drop') {
            // Synth bass drop
            const osc = audioContext.createOscillator();
            const gain = audioContext.createGain();
            const filter = audioContext.createBiquadFilter();
            
            osc.connect(filter);
            filter.connect(gain);
            gain.connect(audioContext.destination);
            
            osc.type = 'square';
            osc.frequency.setValueAtTime(220, audioContext.currentTime);
            osc.frequency.exponentialRampToValueAtTime(110, audioContext.currentTime + 0.3);
            
            gain.gain.setValueAtTime(0.2, audioContext.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
            
            osc.start(audioContext.currentTime);
            osc.stop(audioContext.currentTime + 0.3);
        }
    }

    /**
     * Update leaderboard with crown icon
     */
    updateLeaderboard() {
        const leaderboardRows = document.querySelectorAll('[data-team-rank="1"]');
        leaderboardRows.forEach(row => {
            const crownIcon = row.querySelector('.first-blood-crown');
            if (!crownIcon) {
                const crown = document.createElement('span');
                crown.className = 'first-blood-crown ml-2 animate-bounce';
                crown.textContent = '👑';
                row.querySelector('.team-name')?.appendChild(crown);
            }
        });
    }

    /**
     * Listen for first blood events via WebSocket
     */
    listenForFirstBlood() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws/first-blood/`);

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'first_blood') {
                this.triggerFirstBlood({
                    playerName: data.player_name,
                    challengeName: data.challenge_name,
                    teamName: data.team_name,
                    points: data.points,
                    teamColor: data.team_color
                });
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const animator = new FirstBloodAnimator();
    
    // Listen for events if on scoreboard/dashboard
    if (document.body.classList.contains('has-scoreboard')) {
        animator.listenForFirstBlood();
    }
    
    // Store globally for testing
    window.firstBloodAnimator = animator;
});
