import express from "express";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.CLIENT_PORT || 5000;

app.use(express.static(__dirname));

// Fallback for SPA routing in Express 5
app.use((req, res) => {
    res.sendFile(path.join(__dirname, "index.html"));
});

app.listen(PORT, () => {
    console.log(`🚀 PrepOS Frontend running at http://localhost:${PORT}`);
    console.log(`Local mode connects to the Node API at http://127.0.0.1:8002.`);
});
