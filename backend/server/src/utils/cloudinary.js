import { v2 as cloudinary } from "cloudinary";
import fs from "fs";

let isConfigured = false;

const configureCloudinary = () => {
  if (!isConfigured) {
    const cloudName = process.env.CLOUDINARY_CLOUD_NAME || process.env.CLOUDINARY_KEY_NAME;
    if (!cloudName || !process.env.CLOUDINARY_API_KEY || !process.env.CLOUDINARY_API_SECRET) {
      throw new Error("Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.");
    }
    cloudinary.config({
      cloud_name: cloudName,
      api_key: process.env.CLOUDINARY_API_KEY,
      api_secret: process.env.CLOUDINARY_API_SECRET,
    });
    isConfigured = true;
  }
};

const uploadoncloudinary = async (localfilepath) => {
  try {
    if (!localfilepath || !fs.existsSync(localfilepath)) return null;
    configureCloudinary();

    const response = await cloudinary.uploader.upload(localfilepath, {
      resource_type: "auto"
    });

    console.log("File uploaded successfully to Cloudinary:", response.secure_url);
    if (fs.existsSync(localfilepath)) fs.unlinkSync(localfilepath);
    return response;
  } catch (error) {
    console.error("Cloudinary upload error:", error.message);
    // Keep the local file available for processing when remote media storage is unavailable.
    return null;
  }
};

export { uploadoncloudinary };