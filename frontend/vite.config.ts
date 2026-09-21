import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["brand-icon.svg"],
      manifest: {
        name: "JobScout AI",
        short_name: "JobScout",
        description: "AI-powered international remote job search",
        theme_color: "#d94d79",
        background_color: "#fffafb",
        display: "standalone",
        start_url: "/",
        scope: "/",
        icons: [
          {
            src: "/brand-icon.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any maskable"
          }
        ]
      }
    })
  ],
  server: {
    port: 5173
  }
});
