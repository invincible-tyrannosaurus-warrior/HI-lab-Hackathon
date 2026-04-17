import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
    plugins: [react()],
    server: {
        host: "0.0.0.0",
        port: 9999,
        proxy: {
            "/knowledge": "http://localhost:8000",
            "/sources": "http://localhost:8000",
            "/approvals": "http://localhost:8000",
            "/signals": "http://localhost:8000",
        },
    },
});
