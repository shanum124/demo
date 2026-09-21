import mongoose from "mongoose";

const mockTestSchema = new mongoose.Schema(
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
        questions: [
            {
                question: { type: String, required: true },
                options: [{ type: String, required: true }],
                answer: { type: String, required: true }, // e.g. "A", "B", "C", "D"
                explanation: { type: String, default: "" }
            }
        ],
        score: {
            type: Number,
            default: 0
        },
        completed: {
            type: Boolean,
            default: false
        }
    },
    { timestamps: true }
);

export const MockTest = mongoose.model("MockTest", mockTestSchema);
