/**
 * Adaptive Cognitive Modeling Engine (DKT + BKT + Performance Prediction)
 * Part of the Adaptive Learning Intelligence System
 */

(function(window) {
    "use strict";

    // Default concept profiles for common engineering subjects (e.g., Operating Systems)
    const DEFAULT_CONCEPTS = [
        { id: "c_proc_mgmt", name: "Process Concepts & PCB", unit: "Unit 1", baseline: 0.65, prerequisites: [] },
        { id: "c_cpu_sched", name: "CPU Scheduling Algorithms", unit: "Unit 1", baseline: 0.50, prerequisites: ["c_proc_mgmt"] },
        { id: "c_sync_mutex", name: "Mutex, Semaphores & Concurrency", unit: "Unit 2", baseline: 0.45, prerequisites: ["c_proc_mgmt"] },
        { id: "c_deadlock", name: "Deadlock Avoidance & Banker's Algo", unit: "Unit 2", baseline: 0.35, prerequisites: ["c_sync_mutex"] },
        { id: "c_mem_paging", name: "Paging & Address Translation", unit: "Unit 3", baseline: 0.55, prerequisites: [] },
        { id: "c_virt_mem", name: "Virtual Memory & Page Replacement", unit: "Unit 3", baseline: 0.40, prerequisites: ["c_mem_paging"] },
        { id: "c_file_sys", name: "File Allocation & Directory Structures", unit: "Unit 4", baseline: 0.70, prerequisites: [] },
        { id: "c_disk_sched", name: "Disk Scheduling (SCAN, C-LOOK)", unit: "Unit 4", baseline: 0.60, prerequisites: ["c_file_sys"] }
    ];

    class CognitiveModel {
        constructor(examId = "default_exam") {
            this.examId = examId;
            this.concepts = new Map();
            this.attemptHistory = [];
            this.bktParams = {
                prior: 0.4,       // P(L0)
                learn: 0.18,      // P(T) - transition probability
                guess: 0.20,      // P(G) - guess probability
                slip: 0.10        // P(S) - slip probability
            };
            this.loadState();
        }

        initializeConceptsFromSyllabus(syllabusText, milestones = []) {
            // If already initialized with attempts, keep existing probabilities
            if (this.concepts.size > 0 && this.attemptHistory.length > 0) return;

            this.concepts.clear();

            // Extract topics from milestones or default
            let extracted = [];
            if (milestones && milestones.length > 0) {
                milestones.forEach((m, idx) => {
                    const id = `c_phase_${idx + 1}`;
                    extracted.push({
                        id: id,
                        name: m.title || `Milestone ${idx + 1}`,
                        unit: `Phase ${idx + 1}`,
                        baseline: 0.5,
                        prerequisites: idx > 0 ? [`c_phase_${idx}`] : []
                    });
                });
            }

            const list = extracted.length >= 4 ? extracted : DEFAULT_CONCEPTS;
            list.forEach(item => {
                this.concepts.set(item.id, {
                    ...item,
                    mastery: item.baseline || 0.5,
                    attemptsCount: 0,
                    correctCount: 0,
                    lastAttemptTimestamp: null,
                    trend: "neutral" // "improving", "declining", "neutral"
                });
            });

            this.saveState();
        }

        recordAttempt({ conceptId, isCorrect, timeTakenSec = 45, difficulty = "medium", questionText = "" }) {
            let concept = this.concepts.get(conceptId);
            if (!concept) {
                // Find closest match or assign to first available
                const keys = Array.from(this.concepts.keys());
                conceptId = keys[0] || "c_general";
                if (!this.concepts.has(conceptId)) {
                    this.concepts.set(conceptId, {
                        id: conceptId,
                        name: "General Concepts",
                        unit: "Core",
                        mastery: 0.5,
                        attemptsCount: 0,
                        correctCount: 0,
                        prerequisites: []
                    });
                }
                concept = this.concepts.get(conceptId);
            }

            const prevMastery = concept.mastery;
            const { learn, guess, slip } = this.bktParams;

            // Bayesian Knowledge Tracing posterior update
            let pL_given_obs;
            if (isCorrect) {
                pL_given_obs = (prevMastery * (1 - slip)) / ((prevMastery * (1 - slip)) + ((1 - prevMastery) * guess));
            } else {
                pL_given_obs = (prevMastery * slip) / ((prevMastery * slip) + ((1 - prevMastery) * (1 - guess)));
            }

            // Probability of mastery transition after practice
            let updatedMastery = pL_given_obs + (1 - pL_given_obs) * learn;

            // Difficulty adjustment weight
            if (difficulty === "hard" && isCorrect) updatedMastery = Math.min(1.0, updatedMastery + 0.05);
            if (difficulty === "easy" && !isCorrect) updatedMastery = Math.max(0.05, updatedMastery - 0.08);

            // Bound between 0.05 and 0.99
            updatedMastery = Math.max(0.05, Math.min(0.99, updatedMastery));

            // Update concept stats
            concept.mastery = updatedMastery;
            concept.attemptsCount += 1;
            if (isCorrect) concept.correctCount += 1;
            concept.lastAttemptTimestamp = Date.now();
            concept.trend = updatedMastery > prevMastery ? "improving" : updatedMastery < prevMastery ? "declining" : "neutral";

            // Record to time-series sequence history
            const record = {
                timestamp: Date.now(),
                conceptId,
                conceptName: concept.name,
                isCorrect: Boolean(isCorrect),
                prevMastery: Number(prevMastery.toFixed(3)),
                newMastery: Number(updatedMastery.toFixed(3)),
                timeTakenSec,
                difficulty,
                questionPreview: questionText ? questionText.slice(0, 60) + "..." : ""
            };

            this.attemptHistory.push(record);
            if (this.attemptHistory.length > 50) this.attemptHistory.shift();

            this.saveState();
            return {
                concept,
                updatedMastery,
                delta: updatedMastery - prevMastery,
                historyLength: this.attemptHistory.length
            };
        }

        getConceptMasteryList() {
            if (this.concepts.size === 0) {
                this.initializeConceptsFromSyllabus("");
            }
            return Array.from(this.concepts.values()).map(c => ({
                id: c.id,
                name: c.name,
                unit: c.unit,
                masteryPct: Math.round(c.mastery * 100),
                status: c.mastery >= 0.75 ? "Mastered" : c.mastery >= 0.45 ? "Learning" : "Critical Gap",
                attempts: c.attemptsCount,
                accuracy: c.attemptsCount > 0 ? Math.round((c.correctCount / c.attemptsCount) * 100) : 0,
                trend: c.trend,
                prerequisites: c.prerequisites || []
            }));
        }

        getWeakTopics(threshold = 0.50) {
            const list = this.getConceptMasteryList();
            return list.filter(c => c.masteryPct < threshold * 100)
                       .sort((a, b) => a.masteryPct - b.masteryPct);
        }

        predictPerformance(roadmapProgressPct = 0) {
            const concepts = this.getConceptMasteryList();
            if (concepts.length === 0) return { predictedScore: 65, lowerBound: 58, upperBound: 72, riskLevel: "Moderate" };

            // Average concept mastery weight (70%) + Roadmap completion weight (30%)
            const avgMastery = concepts.reduce((acc, c) => acc + c.masteryPct, 0) / concepts.length;
            const recentAttempts = this.attemptHistory.slice(-10);
            const recentAccuracy = recentAttempts.length > 0
                ? (recentAttempts.filter(a => a.isCorrect).length / recentAttempts.length) * 100
                : avgMastery;

            const compositeScore = (avgMastery * 0.55) + (recentAccuracy * 0.25) + (roadmapProgressPct * 0.20);
            const predictedScore = Math.min(98, Math.max(25, Math.round(compositeScore)));

            // Margin of error based on sample size
            const sampleSize = this.attemptHistory.length;
            const margin = Math.max(4, Math.round(15 / Math.sqrt(Math.max(1, sampleSize))));

            // Dropout / Blindspot risk
            let riskLevel = "Low";
            const criticalGapsCount = concepts.filter(c => c.masteryPct < 40).length;
            if (criticalGapsCount >= 3 || predictedScore < 45) {
                riskLevel = "High";
            } else if (criticalGapsCount >= 1 || predictedScore < 65) {
                riskLevel = "Moderate";
            }

            return {
                predictedScore,
                lowerBound: Math.max(10, predictedScore - margin),
                upperBound: Math.min(100, predictedScore + margin),
                averageMastery: Math.round(avgMastery),
                recentAccuracy: Math.round(recentAccuracy),
                riskLevel,
                criticalGapsCount
            };
        }

        getSequenceTrajectory() {
            return this.attemptHistory.map((att, i) => ({
                index: i + 1,
                concept: att.conceptName,
                correct: att.isCorrect,
                mastery: Math.round(att.newMastery * 100),
                timeTaken: att.timeTakenSec
            }));
        }

        saveState() {
            try {
                const data = {
                    concepts: Array.from(this.concepts.entries()),
                    attemptHistory: this.attemptHistory
                };
                localStorage.setItem(`adaptive_cognitive_${this.examId}`, JSON.stringify(data));
            } catch (e) {
                console.warn("Could not persist cognitive state to localStorage", e);
            }
        }

        loadState() {
            try {
                const raw = localStorage.getItem(`adaptive_cognitive_${this.examId}`);
                if (raw) {
                    const parsed = JSON.parse(raw);
                    if (parsed.concepts) {
                        this.concepts = new Map(parsed.concepts);
                    }
                    if (parsed.attemptHistory) {
                        this.attemptHistory = parsed.attemptHistory;
                    }
                }
            } catch (e) {
                console.warn("Could not load cognitive state", e);
            }
        }

        reset() {
            this.concepts.clear();
            this.attemptHistory = [];
            try {
                localStorage.removeItem(`adaptive_cognitive_${this.examId}`);
            } catch {}
            this.initializeConceptsFromSyllabus("");
        }
    }

    // Export to global scope
    window.CognitiveModel = CognitiveModel;

})(window);
