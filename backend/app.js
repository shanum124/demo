import express from "express";
import cookieParser from "cookie-parser";
import cors from "cors";
import path from "path";
import { fileURLToPath } from "url";
import examRouter from "./server/src/routes/exam.routes.js";
import userRouter from "./server/src/routes/user.routes.js";

const app = express();
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

app.use(cors({
    origin: process.env.CORS_ORIGIN || "*",
    credentials: true
}));

app.use(express.json({ limit: "16mb" }));
app.use(express.urlencoded({ extended: true, limit: "16mb" }));
app.use(cookieParser());

// Serve static frontend files from client directory
app.use(express.static(path.join(__dirname, "client")));
// Serve public uploads
app.use("/public", express.static(path.join(__dirname, "server/public")));

// API Routes
app.use("/api/v1/exams", examRouter);
app.use("/api/v1/users", userRouter);

// Multer and route errors must retain the same JSON contract as controller errors.
app.use((err, req, res, next) => {
    console.error("Unhandled API error:", err);
    const statusCode = err?.code === "LIMIT_FILE_SIZE" ? 413 : (err?.statusCode || err?.status || 500);
    const message = err?.code === "LIMIT_FILE_SIZE"
        ? "Each uploaded document must be 10 MB or smaller."
        : (err?.message || "Unexpected server error.");
    res.status(statusCode).json({ success: false, statusCode, message });
});

export { app };
