// wxt.config.ts
import { defineConfig } from "wxt";
import baseViteConfig from "./vite.config";

import { mergeConfig } from "vite";

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ["@wxt-dev/module-react"],
  srcDir: "src",
  vite: () =>
    mergeConfig(baseViteConfig, {
      // WXT-specific overrides (optional)
    }),
  manifest: {
    // storage: recording state survives MV3 service-worker termination
    // alarms: keepalive while a recording is active
    permissions: ["tabs", "sidePanel", "storage", "alarms"],
    // <all_urls> is a match pattern and belongs in host_permissions ("tabs"
    // covers the API side); keeping it in permissions triggers a load warning.
    host_permissions: ["<all_urls>", "http://127.0.0.1/*"],
    // options_page: "options.html",
    // action: {
    //   default_popup: "popup.html",
    // },
  },
});
