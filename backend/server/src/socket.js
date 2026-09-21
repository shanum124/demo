import jwt from "jsonwebtoken";
import { User } from "./models/user.model.js";
import { Exam } from "./models/exam.model.js";
import { Chat } from "./models/chat.model.js";
import { getGeminiChatStream } from "./utils/gemini.js";

export const initSocket = (io) => {
    // Authenticate socket connection
    io.use(async (socket, next) => {
        try {
            let guestUser = await User.findOne({ username: "guest" });
            if (!guestUser) {
                try {
                    guestUser = await User.create({
                        username: "guest",
                        email: "guest@example.com",
                        password: "guestpassword123"
                    });
                } catch (e) {
                    // Bulletproof fallbacks
                    guestUser = await User.findOne({ email: "guest@example.com" });
                    if (!guestUser) {
                        guestUser = await User.findOne();
                    }
                    if (!guestUser) {
                        const randomId = Math.floor(Math.random() * 10000);
                        guestUser = await User.create({
                            username: `guest_${randomId}`,
                            email: `guest_${randomId}@example.com`,
                            password: "guestpassword123"
                        });
                    }
                }
            }

            const token = socket.handshake.auth?.token || socket.handshake.query?.token;
            if (!token) {
                socket.user = guestUser;
                return next();
            }

            let decoded;
            try {
                decoded = jwt.verify(token, process.env.ACCESS_TOKEN_SECRET);
            } catch {
                socket.user = guestUser;
                return next();
            }

            const user = await User.findById(decoded._id).select("-password");
            socket.user = user || guestUser;
            next();
        } catch (err) {
            console.error("Socket authentication unavailable:", err.message);
            next(new Error("Authentication service is temporarily unavailable."));
        }
    });

    io.on("connection", (socket) => {
        const user = socket.user;
        console.log(`⚡ Client authenticated via Socket: ${socket.id} (User: ${user.username})`);

        socket.on("join-exam", (examId) => {
            socket.join(examId);
            console.log(`👤 User ${user.username} joined exam room: ${examId}`);
        });

        socket.on("send-message", async ({ examId, message }) => {
            if (!examId || !message) {
                socket.emit("chat-stream-error", { error: "Exam ID and Message are required." });
                return;
            }

            try {
                // Find exam for context
                const exam = await Exam.findOne({ _id: examId, owner: user._id });
                if (!exam) {
                    socket.emit("chat-stream-error", { error: "Exam context not found." });
                    return;
                }

                // Fetch past chat history
                const pastChats = await Chat.find({ exam: examId, user: user._id })
                    .sort({ createdAt: 1 })
                    .limit(20);

                // Save user message first
                const userChatMessage = await Chat.create({
                    exam: examId,
                    user: user._id,
                    sender: "user",
                    message: message
                });

                // Let the frontend know the user message is saved and we're starting to stream the AI response
                socket.emit("chat-message-saved", userChatMessage);
                socket.emit("chat-stream-start");

                let fullAiResponse = "";

                // Get the response through ai_services.
                const resultStream = await getGeminiChatStream(exam.syllabusText, pastChats, message, user._id, exam._id);

                for await (const chunk of resultStream) {
                    const chunkText = chunk.choices[0]?.delta?.content || "";
                    if (chunkText) {
                        fullAiResponse += chunkText;
                        socket.emit("chat-stream-chunk", { text: chunkText });
                    }
                }

                // Save model message in database
                const modelChatMessage = await Chat.create({
                    exam: examId,
                    user: user._id,
                    sender: "model",
                    message: fullAiResponse
                });

                // Emit end event with the final database record
                socket.emit("chat-stream-end", modelChatMessage);

            } catch (error) {
                console.error("Socket error processing AI chat:", error);

                // Fallback in case the AI service or database is unavailable.
                try {
                    const fallbackMessage = "I encountered an issue processing your request. Please check that ai_services is running and try again.";
                    const modelChatMessage = await Chat.create({
                        exam: examId,
                        user: user._id,
                        sender: "model",
                        message: fallbackMessage
                    });

                    socket.emit("chat-stream-chunk", { text: fallbackMessage });
                    socket.emit("chat-stream-end", modelChatMessage);
                } catch (dbErr) {
                    socket.emit("chat-stream-error", { error: "Database or processing error: " + error.message });
                }
            }
        });

        socket.on("disconnect", () => {
            console.log(`🔌 Client disconnected: ${socket.id}`);
        });
    });
};
