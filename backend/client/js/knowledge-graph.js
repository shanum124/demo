/**
 * Interactive Knowledge Graph Engine (Prerequisite & Concept Dependency Modeling)
 * Part of the Adaptive Learning Intelligence System
 */

(function(window) {
    "use strict";

    class KnowledgeGraph {
        constructor(canvasId, options = {}) {
            this.canvas = document.getElementById(canvasId);
            if (!canvasId || !this.canvas) return;
            this.ctx = this.canvas.getContext("2d");
            this.options = Object.assign({
                nodeRadius: 28,
                springLength: 140,
                repulsion: 3000,
                damping: 0.88,
                onNodeSelect: null
            }, options);

            this.nodes = [];
            this.links = [];
            this.selectedNode = null;
            this.hoveredNode = null;
            this.draggedNode = null;

            // Pan & Zoom
            this.transform = { x: 0, y: 0, scale: 1.0 };
            this.isPanning = false;
            this.panStart = { x: 0, y: 0 };

            this.animationFrameId = null;
            this.isRunning = false;

            this.initCanvasSize();
            this.bindEvents();
        }

        initCanvasSize() {
            const rect = this.canvas.parentElement.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;
            const width = rect.width || 800;
            const height = rect.height || 520;

            this.canvas.width = width * dpr;
            this.canvas.height = height * dpr;
            this.canvas.style.width = `${width}px`;
            this.canvas.style.height = `${height}px`;

            this.ctx.resetTransform?.();
            this.ctx.scale(dpr, dpr);
            this.width = width;
            this.height = height;

            if (this.transform.x === 0 && this.transform.y === 0) {
                this.transform.x = width / 2;
                this.transform.y = height / 2;
            }
        }

        setGraphData(conceptsList = []) {
            if (!conceptsList || conceptsList.length === 0) return;

            // Create nodes
            const total = conceptsList.length;
            this.nodes = conceptsList.map((c, i) => {
                // Arrange in layers or circle initially
                const angle = (i / total) * Math.PI * 2;
                const radius = 160 + (i % 2) * 50;
                return {
                    id: c.id,
                    name: c.name,
                    unit: c.unit || "Core",
                    masteryPct: c.masteryPct || 50,
                    status: c.status || "Learning",
                    prerequisites: c.prerequisites || [],
                    x: Math.cos(angle) * radius,
                    y: Math.sin(angle) * radius,
                    vx: 0,
                    vy: 0,
                    radius: this.options.nodeRadius
                };
            });

            // Create links based on prerequisites
            this.links = [];
            this.nodes.forEach(targetNode => {
                (targetNode.prerequisites || []).forEach(prereqId => {
                    const sourceNode = this.nodes.find(n => n.id === prereqId);
                    if (sourceNode) {
                        this.links.push({
                            source: sourceNode,
                            target: targetNode
                        });
                    }
                });
            });

            // Check prerequisite breaches
            this.nodes.forEach(node => {
                node.hasPrereqBreach = false;
                if (node.masteryPct < 45) {
                    // Critical gap itself
                    node.hasPrereqBreach = true;
                } else {
                    const prereqNodes = (node.prerequisites || []).map(pid => this.nodes.find(n => n.id === pid)).filter(Boolean);
                    if (prereqNodes.some(pn => pn.masteryPct < 45)) {
                        node.hasPrereqBreach = true;
                    }
                }
            });

            this.startSimulation();
        }

        startSimulation() {
            if (this.isRunning) return;
            this.isRunning = true;
            let iterations = 0;

            const tick = () => {
                if (!this.isRunning) return;
                this.updatePhysics();
                this.render();

                // Run physics for 250 frames or while dragging
                iterations++;
                if (iterations < 250 || this.draggedNode) {
                    this.animationFrameId = requestAnimationFrame(tick);
                } else {
                    this.isRunning = false;
                    this.render(); // final static render
                }
            };
            this.animationFrameId = requestAnimationFrame(tick);
        }

        updatePhysics() {
            const { springLength, repulsion, damping } = this.options;

            // Repulsion between all node pairs
            for (let i = 0; i < this.nodes.length; i++) {
                for (let j = i + 1; j < this.nodes.length; j++) {
                    const a = this.nodes[i];
                    const b = this.nodes[j];
                    let dx = b.x - a.x;
                    let dy = b.y - a.y;
                    let dist = Math.sqrt(dx * dx + dy * dy) || 1;

                    if (dist < 400) {
                        const force = repulsion / (dist * dist);
                        const fx = (dx / dist) * force;
                        const fy = (dy / dist) * force;
                        a.vx -= fx;
                        a.vy -= fy;
                        b.vx += fx;
                        b.vy += fy;
                    }
                }
            }

            // Spring attraction along links
            for (let link of this.links) {
                const a = link.source;
                const b = link.target;
                let dx = b.x - a.x;
                let dy = b.y - a.y;
                let dist = Math.sqrt(dx * dx + dy * dy) || 1;
                let displacement = dist - springLength;
                let force = displacement * 0.04;
                let fx = (dx / dist) * force;
                let fy = (dy / dist) * force;

                a.vx += fx;
                a.vy += fy;
                b.vx -= fx;
                b.vy -= fy;
            }

            // Center gravity pull
            for (let node of this.nodes) {
                if (node === this.draggedNode) continue;
                node.vx -= node.x * 0.015;
                node.vy -= node.y * 0.015;

                node.vx *= damping;
                node.vy *= damping;
                node.x += node.vx;
                node.y += node.vy;
            }
        }

        render() {
            const ctx = this.ctx;
            ctx.clearRect(0, 0, this.width, this.height);

            ctx.save();
            ctx.translate(this.transform.x, this.transform.y);
            ctx.scale(this.transform.scale, this.transform.scale);

            // Draw subtle background grid
            this.drawGrid(ctx);

            // Draw links
            this.drawLinks(ctx);

            // Draw nodes
            this.drawNodes(ctx);

            ctx.restore();
        }

        drawGrid(ctx) {
            const gridSpacing = 44;
            const size = 1600;

            // Ambient central purple nebula glow
            const nebula = ctx.createRadialGradient(0, 0, 20, 0, 0, 650);
            nebula.addColorStop(0, "rgba(139, 92, 246, 0.12)");
            nebula.addColorStop(0.5, "rgba(99, 102, 241, 0.05)");
            nebula.addColorStop(1, "transparent");
            ctx.fillStyle = nebula;
            ctx.fillRect(-size, -size, size * 2, size * 2);

            // Subtle dot matrix / grid
            ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
            ctx.lineWidth = 1;

            ctx.beginPath();
            for (let x = -size; x <= size; x += gridSpacing) {
                ctx.moveTo(x, -size);
                ctx.lineTo(x, size);
            }
            for (let y = -size; y <= size; y += gridSpacing) {
                ctx.moveTo(-size, y);
                ctx.lineTo(size, y);
            }
            ctx.stroke();
        }

        drawLinks(ctx) {
            for (let link of this.links) {
                const s = link.source;
                const t = link.target;

                const isConnectedToSelected = this.selectedNode &&
                    (this.selectedNode.id === s.id || this.selectedNode.id === t.id);

                let strokeStyle = "rgba(139, 92, 246, 0.32)";
                let lineWidth = 1.6;

                if (this.selectedNode) {
                    if (isConnectedToSelected) {
                        strokeStyle = "#8B5CF6";
                        lineWidth = 2.6;
                    } else {
                        strokeStyle = "rgba(255, 255, 255, 0.06)";
                    }
                }

                ctx.strokeStyle = strokeStyle;
                ctx.lineWidth = lineWidth;

                // Calculate edge cutoff at circle radius
                const dx = t.x - s.x;
                const dy = t.y - s.y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                const ux = dx / dist;
                const uy = dy / dist;

                const startX = s.x + ux * s.radius;
                const startY = s.y + uy * s.radius;
                const endX = t.x - ux * (t.radius + 6);
                const endY = t.y - uy * (t.radius + 6);

                ctx.beginPath();
                ctx.moveTo(startX, startY);
                ctx.lineTo(endX, endY);
                ctx.stroke();

                // Draw directed arrow head
                this.drawArrowHead(ctx, endX, endY, Math.atan2(dy, dx), strokeStyle);
            }
        }

        drawArrowHead(ctx, x, y, angle, color) {
            const headLen = 8;
            ctx.save();
            ctx.fillStyle = color;
            ctx.translate(x, y);
            ctx.rotate(angle);
            ctx.beginPath();
            ctx.moveTo(0, 0);
            ctx.lineTo(-headLen, -headLen / 2.2);
            ctx.lineTo(-headLen, headLen / 2.2);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
        }

        drawNodes(ctx) {
            for (let node of this.nodes) {
                const isSelected = this.selectedNode && this.selectedNode.id === node.id;
                const isHovered = this.hoveredNode && this.hoveredNode.id === node.id;

                let strokeColor = "#10B981"; // Mastered (Emerald)
                let glowColor = "rgba(16, 185, 129, 0.25)";
                if (node.masteryPct < 45) {
                    strokeColor = "#F43F5E"; // Critical gap (Neon Rose)
                    glowColor = "rgba(244, 63, 94, 0.35)";
                } else if (node.masteryPct < 75) {
                    strokeColor = "#F59E0B"; // Learning (Warm Amber)
                    glowColor = "rgba(245, 158, 11, 0.25)";
                }

                // Halo glow if selected, hovered, or prerequisite breach
                if (isSelected || isHovered || node.hasPrereqBreach) {
                    ctx.beginPath();
                    const haloRadius = node.radius + (isSelected ? 9 : isHovered ? 7 : 6);
                    ctx.arc(node.x, node.y, haloRadius, 0, Math.PI * 2);
                    ctx.fillStyle = node.hasPrereqBreach
                        ? "rgba(244, 63, 94, 0.35)"
                        : isSelected ? "rgba(139, 92, 246, 0.4)" : "rgba(6, 182, 212, 0.25)";
                    ctx.fill();
                }

                // 3D Glass Radial Node Background
                ctx.beginPath();
                ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
                const grad = ctx.createRadialGradient(
                    node.x - node.radius * 0.3,
                    node.y - node.radius * 0.3,
                    2,
                    node.x,
                    node.y,
                    node.radius
                );
                grad.addColorStop(0, "#1E2644");
                grad.addColorStop(0.7, "#111628");
                grad.addColorStop(1, "#0A0D1A");
                ctx.fillStyle = grad;
                ctx.fill();

                // Glowing border ring
                ctx.lineWidth = isSelected ? 3.5 : 2.5;
                ctx.strokeStyle = isSelected ? "#A78BFA" : strokeColor;
                ctx.stroke();

                // Mastery percentage inside node
                ctx.fillStyle = "#FFFFFF";
                ctx.font = "700 12px 'JetBrains Mono', monospace";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(`${node.masteryPct}%`, node.x, node.y);

                // Node Title label beneath circle
                ctx.fillStyle = isSelected ? "#FFFFFF" : isHovered ? "#E2E8F0" : "#94A3B8";
                ctx.font = `${isSelected ? "700" : "600"} 11px 'Plus Jakarta Sans', sans-serif`;
                ctx.fillText(this.truncate(node.name, 24), node.x, node.y + node.radius + 15);

                // Prerequisite Breach Warning Icon
                if (node.hasPrereqBreach) {
                    ctx.fillStyle = "#F43F5E";
                    ctx.beginPath();
                    ctx.arc(node.x + node.radius - 3, node.y - node.radius + 3, 7, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.fillStyle = "#FFFFFF";
                    ctx.font = "bold 9px 'JetBrains Mono', monospace";
                    ctx.fillText("!", node.x + node.radius - 3, node.y - node.radius + 3);
                }
            }
        }

        truncate(text, maxLen) {
            return text.length > maxLen ? text.slice(0, maxLen - 2) + ".." : text;
        }

        bindEvents() {
            // Mouse Drag & Pan
            this.canvas.addEventListener("mousedown", e => {
                const pos = this.getCanvasPos(e);
                const clickedNode = this.getNodeAt(pos.x, pos.y);

                if (clickedNode) {
                    this.draggedNode = clickedNode;
                    this.selectedNode = clickedNode;
                    if (this.options.onNodeSelect) this.options.onNodeSelect(clickedNode);
                    this.startSimulation();
                } else {
                    this.isPanning = true;
                    this.panStart = { x: e.clientX - this.transform.x, y: e.clientY - this.transform.y };
                }
            });

            window.addEventListener("mousemove", e => {
                if (this.isPanning) {
                    this.transform.x = e.clientX - this.panStart.x;
                    this.transform.y = e.clientY - this.panStart.y;
                    this.render();
                } else if (this.draggedNode) {
                    const pos = this.getCanvasPos(e);
                    this.draggedNode.x = pos.x;
                    this.draggedNode.y = pos.y;
                    this.draggedNode.vx = 0;
                    this.draggedNode.vy = 0;
                    this.render();
                } else {
                    // Hover check
                    const rect = this.canvas.getBoundingClientRect();
                    if (e.clientX >= rect.left && e.clientX <= rect.right &&
                        e.clientY >= rect.top && e.clientY <= rect.bottom) {
                        const pos = this.getCanvasPos(e);
                        const hovered = this.getNodeAt(pos.x, pos.y);
                        if (hovered !== this.hoveredNode) {
                            this.hoveredNode = hovered;
                            this.canvas.style.cursor = hovered ? "pointer" : "grab";
                            this.render();
                        }
                    }
                }
            });

            window.addEventListener("mouseup", () => {
                this.isPanning = false;
                this.draggedNode = null;
                this.canvas.style.cursor = "default";
            });

            // Zoom Wheel
            this.canvas.addEventListener("wheel", e => {
                e.preventDefault();
                const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
                const newScale = Math.min(2.5, Math.max(0.4, this.transform.scale * zoomFactor));

                const rect = this.canvas.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;

                this.transform.x = mouseX - (mouseX - this.transform.x) * (newScale / this.transform.scale);
                this.transform.y = mouseY - (mouseY - this.transform.y) * (newScale / this.transform.scale);
                this.transform.scale = newScale;

                this.render();
            }, { passive: false });

            // Window resize
            window.addEventListener("resize", () => {
                this.initCanvasSize();
                this.render();
            });
        }

        getCanvasPos(e) {
            const rect = this.canvas.getBoundingClientRect();
            const clientX = e.clientX - rect.left;
            const clientY = e.clientY - rect.top;
            return {
                x: (clientX - this.transform.x) / this.transform.scale,
                y: (clientY - this.transform.y) / this.transform.scale
            };
        }

        getNodeAt(x, y) {
            for (let i = this.nodes.length - 1; i >= 0; i--) {
                const node = this.nodes[i];
                const dx = x - node.x;
                const dy = y - node.y;
                if (Math.sqrt(dx * dx + dy * dy) <= node.radius + 6) {
                    return node;
                }
            }
            return null;
        }

        resetView() {
            this.transform = {
                x: this.width / 2,
                y: this.height / 2,
                scale: 1.0
            };
            this.render();
        }

        zoomIn() {
            this.transform.scale = Math.min(2.5, this.transform.scale * 1.2);
            this.render();
        }

        zoomOut() {
            this.transform.scale = Math.max(0.4, this.transform.scale * 0.8);
            this.render();
        }
    }

    window.KnowledgeGraph = KnowledgeGraph;

})(window);
