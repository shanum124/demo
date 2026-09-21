import mongoose from "mongoose";

const examSchema = new mongoose.Schema(
  {
    examName: { type: String, required: true },
    duration: { type: Number, required: true },
    starttime: { type: String, required: true },
    syllabusText: { type: String },
    syllabusFile: { type: String },
    pyqFiles: [{ type: String }],
    notesFiles: [{ type: String }],
    customInstruction: { type: String },
    strategy: { type: String, default: "" },
    owner: { type: mongoose.Schema.Types.ObjectId, ref: "User" },
  },
  { timestamps: true },
);

export const Exam = mongoose.model("Exam", examSchema);
