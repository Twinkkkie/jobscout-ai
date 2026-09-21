import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "ai.jobscout.app",
  appName: "JobScout AI",
  webDir: "dist",
  server: {
    androidScheme: "https"
  }
};

export default config;
