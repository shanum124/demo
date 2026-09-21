/**
 * PrepOS API & WebSocket Gateway Service
 * Manages Auth, REST Endpoints, Socket.IO Streaming, and Multi-Environment Switching
 */

(function(window) {
    "use strict";

    const STORAGE_KEY_ENV = "prepos_selected_env";
    const STORAGE_KEY_TOKEN = "accessToken";
    const STORAGE_KEY_USER = "prepos_current_user";

    const ENVIRONMENTS = {
        local: { name: "Local Server", base: "http://127.0.0.1:8002" },
        render: { name: "Live Render Cloud", base: "https://prep-os-live.onrender.com" },
        demo: { name: "Intelligent Demo Mode", base: "demo" }
    };

    class ApiGateway {
        constructor() {
            this.currentEnv = localStorage.getItem(STORAGE_KEY_ENV) || "local";
            this.socket = null;
            this.activeExamId = null;
        }

        setEnvironment(envKey) {
            if (ENVIRONMENTS[envKey]) {
                this.currentEnv = envKey;
                localStorage.setItem(STORAGE_KEY_ENV, envKey);
                if (this.socket) {
                    this.socket.disconnect();
                    this.socket = null;
                }
            }
        }

        getBaseUrl() {
            const configuredBase = ENVIRONMENTS[this.currentEnv]?.base || "";
            // The frontend can be served by the API (8002) or by `npm run client`
            // (5000). In the latter case, relative API URLs mistakenly target the
            // static-file server, so always use the actual Node API endpoint.
            if (this.currentEnv === "local" && window.location.port === "8002") return "";
            return configuredBase;
        }

        getToken() {
            return sessionStorage.getItem(STORAGE_KEY_TOKEN) || localStorage.getItem(STORAGE_KEY_TOKEN);
        }

        setToken(token) {
            if (token) {
                sessionStorage.setItem(STORAGE_KEY_TOKEN, token);
                localStorage.setItem(STORAGE_KEY_TOKEN, token);
            } else {
                sessionStorage.removeItem(STORAGE_KEY_TOKEN);
                localStorage.removeItem(STORAGE_KEY_TOKEN);
            }
        }

        getUser() {
            try {
                return JSON.parse(sessionStorage.getItem(STORAGE_KEY_USER) || localStorage.getItem(STORAGE_KEY_USER));
            } catch {
                return null;
            }
        }

        setUser(user) {
            if (user) {
                const str = JSON.stringify(user);
                sessionStorage.setItem(STORAGE_KEY_USER, str);
                localStorage.setItem(STORAGE_KEY_USER, str);
            } else {
                sessionStorage.removeItem(STORAGE_KEY_USER);
                localStorage.removeItem(STORAGE_KEY_USER);
            }
        }

        async request(endpoint, options = {}) {
            const isDemo = this.currentEnv === "demo";
            if (isDemo) {
                return this.handleDemoRequest(endpoint, options);
            }

            const baseUrl = this.getBaseUrl();
            const url = `${baseUrl}${endpoint}`;
            const token = this.getToken();

            const headers = Object.assign({}, options.headers || {});
            if (token) {
                headers["Authorization"] = `Bearer ${token}`;
            }
            if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
                headers["Content-Type"] = "application/json";
            }

            try {
                const res = await fetch(url, Object.assign({}, options, { headers }));
                const raw = await res.text();
                let data;
                try {
                    data = raw ? JSON.parse(raw) : {};
                } catch {
                    return {
                        success: false,
                        statusCode: res.status,
                        message: `Server returned an invalid response for ${endpoint}. Check that the Node API is running on port 8002.`
                    };
                }
                if (!res.ok && data.success !== false) {
                    return Object.assign({}, data, {
                        success: false,
                        statusCode: res.status,
                        message: data.message || data.detail || `Request failed with status ${res.status}.`
                    });
                }
                return data;
            } catch (err) {
                console.warn(`API error at ${endpoint}:`, err);
                // Auto fallback to demo response if network failed
                return {
                    success: false,
                    networkError: true,
                    message: "Cannot connect to server. Try switching to Live Render or Intelligent Demo Mode."
                };
            }
        }

        /* ── Authentication Endpoints ── */
        async login(username, password) {
            const payload = username.includes("@") ? { email: username, password } : { username, password };
            const res = await this.request("/api/v1/users/login", {
                method: "POST",
                body: JSON.stringify(payload)
            });
            if (res.success && res.data) {
                this.setToken(res.data.accessToken);
                this.setUser(res.data.user);
            }
            return res;
        }

        async register(username, email, password) {
            const res = await this.request("/api/v1/users/register", {
                method: "POST",
                body: JSON.stringify({ username, email, password })
            });
            return res;
        }

        async guestLogin() {
            if (this.currentEnv === "demo") {
                const guestUser = { _id: "demo_guest_id", username: "Guest Scholar", email: "guest@adaptive.ai" };
                this.setToken("demo_jwt_token");
                this.setUser(guestUser);
                return { success: true, data: { user: guestUser, accessToken: "demo_jwt_token" } };
            }

            const res = await this.request("/api/v1/users/guest-login", {
                method: "POST"
            });
            if (res.success && res.data) {
                this.setToken(res.data.accessToken);
                this.setUser(res.data.user);
                return res;
            }

            // If local/remote server is down, auto-fallback to Demo Mode
            if (res.networkError) {
                console.warn("Server offline, auto-falling back to Demo Mode");
                this.setEnvironment("demo");
                const guestUser = { _id: "demo_guest_id", username: "Guest Scholar", email: "guest@adaptive.ai" };
                this.setToken("demo_jwt_token");
                this.setUser(guestUser);
                return {
                    success: true,
                    isFallbackDemo: true,
                    data: { user: guestUser, accessToken: "demo_jwt_token" },
                    message: "Local backend not running. Switched to Intelligent Demo Mode automatically!"
                };
            }
            return res;
        }

        async getMe() {
            return await this.request("/api/v1/users/me");
        }

        async logout() {
            try {
                await this.request("/api/v1/users/logout", { method: "POST" });
            } catch {}
            this.setToken(null);
            this.setUser(null);
            if (this.socket) {
                this.socket.disconnect();
                this.socket = null;
            }
        }

        /* ── Exam Endpoints ── */
        async listExams() {
            const res = await this.request("/api/v1/exams/list");
            if (res.networkError) {
                return await this.handleDemoRequest("/api/v1/exams/list");
            }
            return res;
        }

        async setupExam(formData) {
            return await this.request("/api/v1/exams/setup", {
                method: "POST",
                body: formData
            });
        }

        async getStrategy(examId) {
            return await this.request(`/api/v1/exams/strategy/${examId}`);
        }

        async solveDoubt(examId, doubt) {
            return await this.request(`/api/v1/exams/doubt/${examId}`, {
                method: "POST",
                body: JSON.stringify({ doubt })
            });
        }

        async getMockTest(examId) {
            return await this.request(`/api/v1/exams/mock/${examId}`);
        }

        async submitMockScore(examId, score) {
            return await this.request(`/api/v1/exams/mock/${examId}/submit`, {
                method: "POST",
                body: JSON.stringify({ score })
            });
        }

        async getChatHistory(examId) {
            return await this.request(`/api/v1/exams/chat/${examId}`);
        }

        loadSocketClient(socketUrl) {
            if (window.io) return Promise.resolve();
            if (this.socketClientPromise) return this.socketClientPromise;

            this.socketClientPromise = new Promise((resolve, reject) => {
                const script = document.createElement("script");
                script.src = `${socketUrl}/socket.io/socket.io.js`;
                script.async = true;
                script.onload = () => window.io ? resolve() : reject(new Error("Socket.IO client did not initialize."));
                script.onerror = () => reject(new Error("Unable to load the Socket.IO client from the Node API."));
                document.head.appendChild(script);
            }).catch(error => {
                this.socketClientPromise = null;
                throw error;
            });
            return this.socketClientPromise;
        }

        /* ── Real-Time Streaming Socket.IO Integration ── */
        initSocket(examId, callbacks = {}) {
            this.activeExamId = examId;
            const token = this.getToken();

            if (this.currentEnv === "demo") {
                // Demo streaming simulator
                return {
                    sendMessage: (message) => this.simulateStreamingChat(message, callbacks),
                    disconnect: () => {}
                };
            }

            const socketUrl = this.getBaseUrl() || window.location.origin;

            if (this.socket) {
                this.socket.disconnect();
            }

            let disconnected = false;
            const pendingMessages = [];
            const connect = () => {
                if (disconnected || !window.io) return;
                this.socket = window.io(socketUrl, {
                    auth: { token },
                    query: { token },
                    transports: ["websocket", "polling"]
                });

                this.socket.on("connect", () => {
                    console.log("⚡ Socket connected:", this.socket.id);
                    this.socket.emit("join-exam", examId);
                    pendingMessages.splice(0).forEach(message => {
                        this.socket.emit("send-message", { examId, message });
                    });
                });

                this.socket.on("connect_error", error => {
                    if (callbacks.onError) callbacks.onError({ error: error.message || "Unable to connect to chat." });
                });

                this.socket.on("chat-message-saved", msg => {
                    if (callbacks.onMessageSaved) callbacks.onMessageSaved(msg);
                });

                this.socket.on("chat-stream-start", () => {
                    if (callbacks.onStreamStart) callbacks.onStreamStart();
                });

                this.socket.on("chat-stream-chunk", chunk => {
                    const text = typeof chunk === "string" ? chunk : chunk?.text;
                    if (text && callbacks.onStreamChunk) callbacks.onStreamChunk(text);
                });

                this.socket.on("chat-stream-end", () => {
                    if (callbacks.onStreamEnd) callbacks.onStreamEnd();
                });

                this.socket.on("chat-stream-error", err => {
                    if (callbacks.onError) callbacks.onError(err);
                });

            };

            if (window.io) {
                connect();
            } else {
                this.loadSocketClient(socketUrl).then(connect).catch(error => {
                    if (!disconnected && callbacks.onError) callbacks.onError({ error: error.message });
                });
            }

            return {
                sendMessage: (message) => {
                    if (this.socket?.connected) {
                        this.socket.emit("send-message", { examId, message });
                    } else {
                        pendingMessages.push(message);
                    }
                },
                disconnect: () => {
                    disconnected = true;
                    pendingMessages.length = 0;
                    if (this.socket) this.socket.disconnect();
                }
            };
        }

        simulateStreamingChat(message, callbacks) {
            const userMsg = { sender: "user", message, createdAt: new Date() };
            if (callbacks.onMessageSaved) callbacks.onMessageSaved(userMsg);
            if (callbacks.onStreamStart) callbacks.onStreamStart();

            // Intelligent simulated academic response
            let sampleAnswer = `### Conceptual Analysis & Solution\n\nRegarding your question on **${message.slice(0, 40)}**:\n\n1. **Core Principle**: In operating systems, resource allocation and synchronization must satisfy mutual exclusion, progress, and bounded waiting.\n2. **Diagnostic Insight**: Based on your recent question attempts, you've shown strong mastery in CPU scheduling, but Deadlock Avoidance and Bankers Algorithm remain an active focus.\n3. **Recommended Next Step**: Review the **Critical Section Problem** and practice with semaphore invariant proofs before advancing to multi-resource deadlock state checks.\n\n\`\`\`c\n// Safe state check idiom\nwhile (count < num_processes) {\n    if (!finish[p] && need[p] <= available) {\n        available += allocation[p];\n        finish[p] = true;\n    }\n}\n\`\`\``;

            const chunks = sampleAnswer.split(" ");
            let i = 0;
            const interval = setInterval(() => {
                if (i < chunks.length) {
                    if (callbacks.onStreamChunk) callbacks.onStreamChunk((i > 0 ? " " : "") + chunks[i]);
                    i++;
                } else {
                    clearInterval(interval);
                    if (callbacks.onStreamEnd) callbacks.onStreamEnd();
                }
            }, 35);
        }

        /* ── Standalone Offline Demo Handler ── */
        handleDemoRequest(endpoint, options) {
            return new Promise(resolve => {
                setTimeout(() => {
                    if (endpoint.includes("/users/guest-login") || endpoint.includes("/users/login")) {
                        const user = { _id: "demo_guest_id", username: "Guest Scholar", email: "guest@adaptive.ai" };
                        this.setToken("demo_token");
                        this.setUser(user);
                        resolve({ success: true, data: { user, accessToken: "demo_token" } });
                    } else if (endpoint.includes("/exams/list")) {
                        resolve({
                            success: true,
                            data: [{
                                _id: "demo_exam_os",
                                examName: "Operating Systems — CS301 Final Exam",
                                duration: 18,
                                starttime: "09:00",
                                strategy: JSON.stringify(this.getDemoStrategy())
                            }]
                        });
                    } else if (endpoint.includes("/exams/doubt")) {
                        resolve({
                            success: true,
                            data: {
                                answer: `### Deep Academic Explanation\n\n**Concept Overview**:\nYour question touches an essential part of system concurrency.\n\n- **Step 1: Invariant Verification**: Confirm that critical section guarantees mutual exclusion without busy waiting when hardware atomic primitives (e.g. Test-and-Set, Compare-and-Swap) are leveraged.\n- **Step 2: Safe Sequence Construction**: When Available $\\ge$ Need, process can terminate and return allocated resources to system pool.\n- **Step 3: Edge Cases**: Check for starvation and priority inversion.`
                            }
                        });
                    } else {
                        resolve({ success: true, data: {} });
                    }
                }, 200);
            });
        }

        getDemoStrategy() {
            return {
                summary: "Master Operating Systems across 5 foundational phases with high-yield focus on Process Scheduling, Concurrency & Banker's Deadlock Avoidance.",
                milestones: [
                    { title: "Phase 1: Process Concepts & Scheduling", description: "PCB, context switching, FCFS, SJF, and Round Robin scheduling." },
                    { title: "Phase 2: Concurrency, Semaphores & Deadlocks", description: "Critical section problem, Mutex, Semaphores, and Banker's Algorithm." },
                    { title: "Phase 3: Memory Management & Paging", description: "Address translation, MMU, TLB, and Virtual Memory paging." },
                    { title: "Phase 4: Page Replacement & Virtual Memory", description: "FIFO, LRU, Optimal, and Belady's Anomaly." },
                    { title: "Phase 5: File Systems, I/O & Final Review", description: "File allocation methods, disk scheduling (SCAN, C-LOOK) and PYQs." }
                ],
                schedule: [
                    { day: "Day 1", durationHours: 3.5, topic: "Process Fundamentals & State Transitions", tasks: ["Review PCB and Process States", "Context Switching Mechanics", "Solve 5 numericals on FCFS & SJF"] },
                    { day: "Day 2", durationHours: 4.0, topic: "CPU Scheduling Algorithms & Criteria", tasks: ["Round Robin time quantum selection", "Multilevel Feedback Queue", "Compare Gantt charts for PYQ 2023"] },
                    { day: "Day 3", durationHours: 4.0, topic: "Synchronization Primitives", tasks: ["Peterson's Algorithm proof", "Binary vs Counting Semaphores", "Classic Readers-Writers solution"] },
                    { day: "Day 4", durationHours: 3.5, topic: "Deadlock Avoidance & Banker's Algo", tasks: ["Resource Allocation Graph cycles", "Banker's Algorithm safe sequence matrix", "Deadlock detection & recovery"] },
                    { day: "Day 5", durationHours: 3.0, topic: "Memory Paging & Address Translation", tasks: ["Logical to physical address translation", "TLB hit ratio & Effective Access Time", "Paging vs Segmentation"] }
                ],
                tips: [
                    "SJF minimizes average waiting time among non-preemptive algorithms.",
                    "Always verify Need = Max - Allocation before running Banker's Algorithm safety check.",
                    "Belady's Anomaly never occurs in stack-based algorithms like LRU and OPT."
                ]
            };
        }
    }

    window.apiGateway = new ApiGateway();

})(window);
