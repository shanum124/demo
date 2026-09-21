import mongoose from "mongoose";

const chatSchema = new mongoose.Schema(
    {
        exam: {
            type: mongoose.Schema.Types.ObjectId,
            ref: "Exam",
            required: true
        },
        user: {
            type: mongoose.Schema.Types.ObjectId,
            ref: "User",
            required: true
        },
        sender: {
            type: String,
            enum: ["user", "model"],
            required: true
        },
        message: {
            type: String,
            required: true
        }
    },
    { timestamps: true }
);

export const Chat = mongoose.model("Chat", chatSchema);
