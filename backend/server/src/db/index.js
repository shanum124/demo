import mongoose from "mongoose";
import { DB_NAME } from "../../../constants.js";

const connectDB = async () => {
    try {
        const configuredUri = process.env.MONGODB_URI?.trim();
        if (!configuredUri) {
            throw new Error("MONGODB_URI is not configured. Add it to backend/.env before starting the server.");
        }
        let uri = configuredUri;
        if (uri.endsWith("/")) {
            uri = uri.slice(0, -1);
        }
        const connectionInstance = await mongoose.connect(
            `${uri}/${DB_NAME}`
        );
        console.log(`\n MongoDB connected! DB HOST: ${connectionInstance.connection.host}`);
    } catch (error) {
        console.error("MONGODB connection FAILED ", error);
        process.exit(1);
    }
};

export default connectDB;
