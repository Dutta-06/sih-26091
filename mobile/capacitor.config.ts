import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "in.aashaudyami.app",
  appName: "Aashaudyami",
  webDir: "dist",
  android: { backgroundColor: "#F5FAFB" },
  plugins: {
    SplashScreen: { launchShowDuration: 1200, backgroundColor: "#007B8F", showSpinner: false },
    StatusBar: { style: "LIGHT", backgroundColor: "#F5FAFB" },
  },
};

export default config;
