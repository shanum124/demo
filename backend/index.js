import dotenv from "dotenv";
import dns from "dns";
import http from "http";
import { Server } from "socket.io";
import connectDB from "./server/src/db/index.js";
import { app } from "./app.js";
import { initSocket } from "./server/src/socket.js";

dotenv.config({ path: "./.env" });

dns.setServers(["1.1.1.1", "8.8.8.8"]);

const server = http.createServer(app);
const io = new Server(server, {
    cors: {
        origin: process.env.CORS_ORIGIN || "*",
        credentials: true
    }
});

app.set("io", io);
initSocket(io);

const port = process.env.PORT || 8002;

connectDB()
    .then(() => {
        server.listen(port, () => {
            console.log(`⚙️ Server is running at port : ${port}`);
        });
    })
    .catch((err) => {
        console.error("MONGO DB connection failed !!! ", err);
    });