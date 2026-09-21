import express from "express";
import {
    setupExam,
    getStrategy,
    getChats,
    getDoubts,
    getMockTest,
    submitMockTestScore,
    getExamsList
} from "../controllers/exam.controller.js";
import { upload } from "../middlewares/multer.middleware.js";
import { verifyJWT } from "../middlewares/auth.middleware.js";

const router = express.Router();

// Apply JWT verification middleware to all exam routes
router.use(verifyJWT);

router.route("/list").get(getExamsList);

router.route("/setup").post(
    upload.fields([
        {
            name: "syllabus",
            maxCount: 1
        },
        {
            name: "pyq",
            maxCount: 3
        },
        {
            name: "attachment",
            maxCount: 3
        }
    ]),
    setupExam
);

router.route("/strategy/:examId").get(getStrategy);
router.route("/chat/:examId").get(getChats);
router.route("/doubt/:examId").post(getDoubts);
router.route("/mock/:examId").get(getMockTest);
router.route("/mock/:examId/submit").post(submitMockTestScore);

export default router;
