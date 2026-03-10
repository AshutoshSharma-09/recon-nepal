// API_URL: empty string = relative path (requests go to /api/... on same origin)
// In production, Nginx reverse proxy routes /api/* to the backend container.
// For local dev, Next.js rewrites in next.config.ts proxy /api/* to the backend.
export const API_URL = "";
export const API_KEY = "secret-uploader-token";
