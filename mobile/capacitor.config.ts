import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "in.arambh.advisor",
  appName: "Arambh",
  webDir: "dist",
  android: { backgroundColor: "#FBF7EF" },
  plugins: {
    SplashScreen: { launchShowDuration: 1200, backgroundColor: "#0F5132", showSpinner: false },
    StatusBar: { style: "LIGHT", backgroundColor: "#FBF7EF" },
  },
};

export default config;
