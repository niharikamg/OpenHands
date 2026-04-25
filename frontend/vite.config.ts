/// <reference types="vitest" />
/// <reference types="vite-plugin-svgr/client" />
import { existsSync, statSync } from "node:fs";
import path from "node:path";
import { defineConfig, loadEnv } from "vite";
import viteTsconfigPaths from "vite-tsconfig-paths";
import svgr from "vite-plugin-svgr";
import { reactRouter } from "@react-router/dev/vite";
import { configDefaults } from "vitest/config";
import tailwindcss from "@tailwindcss/vite";

const FRONTEND_SRC_ROOT = path.resolve(__dirname, "src");
const AGENT_SERVER_GUI_SRC_ROOT = path.resolve(
  __dirname,
  "node_modules/@openhands/agent-server-gui/src",
);
const MODULE_CANDIDATE_SUFFIXES = [
  "",
  ".ts",
  ".tsx",
  ".js",
  ".jsx",
  ".json",
  "/index.ts",
  "/index.tsx",
  "/index.js",
  "/index.jsx",
  "/index.json",
];

const resolveSharedFrontendModule = (source: string) => {
  if (!source.startsWith("#/")) {
    return null;
  }

  const [relativePath, query = ""] = source.slice(2).split("?");
  const querySuffix = query ? `?${query}` : "";

  for (const root of [FRONTEND_SRC_ROOT, AGENT_SERVER_GUI_SRC_ROOT]) {
    const basePath = path.join(root, relativePath);
    for (const suffix of MODULE_CANDIDATE_SUFFIXES) {
      const candidate = `${basePath}${suffix}`;
      if (existsSync(candidate) && statSync(candidate).isFile()) {
        return `${candidate}${querySuffix}`;
      }
    }
  }

  return null;
};

export default defineConfig(({ mode }) => {
  const {
    VITE_BACKEND_HOST = "127.0.0.1:3000",
    VITE_USE_TLS = "false",
    VITE_FRONTEND_PORT = "3001",
    VITE_INSECURE_SKIP_VERIFY = "false",
  } = loadEnv(mode, process.cwd());

  const USE_TLS = VITE_USE_TLS === "true";
  const INSECURE_SKIP_VERIFY = VITE_INSECURE_SKIP_VERIFY === "true";
  const PROTOCOL = USE_TLS ? "https" : "http";
  const WS_PROTOCOL = USE_TLS ? "wss" : "ws";

  const API_URL = `${PROTOCOL}://${VITE_BACKEND_HOST}/`;
  const WS_URL = `${WS_PROTOCOL}://${VITE_BACKEND_HOST}/`;
  const FE_PORT = Number.parseInt(VITE_FRONTEND_PORT, 10);

  return {
    plugins: [
      {
        name: "agent-server-gui-shared-module-fallback",
        enforce: "pre",
        resolveId(source) {
          return resolveSharedFrontendModule(source);
        },
      },
      !process.env.VITEST && reactRouter(),
      viteTsconfigPaths(),
      svgr(),
      tailwindcss(),
    ],
    optimizeDeps: {
      include: [
        // Pre-bundle ALL dependencies to prevent runtime optimization and page reloads
        // These are discovered during initial app load:
        "posthog-js",
        "@tanstack/react-query",
        "react-hot-toast",
        "i18next",
        "i18next-http-backend",
        "i18next-browser-languagedetector",
        "react-i18next",
        "axios",
        "prop-types",
        "react-is",
        "@uidotdev/usehooks",
        "react-icons/fa6",
        "react-icons/fa",
        "clsx",
        "tailwind-merge",
        "@heroui/react",
        "lucide-react",
        "@microlink/react-json-view",
        "socket.io-client",
        "@mswjs/socket.io-binding",
        "socket.io-parser",
        "engine.io-parser",
        // These are discovered when launching conversations:
        "react-icons/vsc",
        "react-icons/lu",
        "react-icons/di",
        "react-icons/io5",
        "react-icons/io", // Added to prevent runtime optimization
        "@monaco-editor/react",
        "react-textarea-autosize",
        "react-markdown",
        "remark-gfm",
        "remark-breaks",
        "react-syntax-highlighter",
        "react-syntax-highlighter/dist/esm/styles/prism",
        "react-syntax-highlighter/dist/esm/styles/hljs",
        // Terminal dependencies - added to prevent runtime optimization
        "@xterm/addon-fit",
        "@xterm/xterm",
        "@xterm/xterm/css/xterm.css",
      ],
    },
    server: {
      port: FE_PORT,
      host: true,
      allowedHosts: true,
      proxy: {
        "/api": {
          target: API_URL,
          changeOrigin: true,
          secure: !INSECURE_SKIP_VERIFY,
        },
        "/ws": {
          target: WS_URL,
          ws: true,
          changeOrigin: true,
          secure: !INSECURE_SKIP_VERIFY,
        },
        "/socket.io": {
          target: WS_URL,
          ws: true,
          changeOrigin: true,
          secure: !INSECURE_SKIP_VERIFY,
          // rewriteWsOrigin: true,
        },
      },
      watch: {
        ignored: ["**/node_modules/**", "**/.git/**"],
      },
    },
    ssr: {
      noExternal: ["react-syntax-highlighter"],
    },
    clearScreen: false,
    test: {
      environment: "jsdom",
      setupFiles: ["vitest.setup.ts"],
      exclude: [...configDefaults.exclude, "tests"],
      coverage: {
        reporter: ["text", "json", "html", "lcov", "text-summary"],
        reportsDirectory: "coverage",
        include: ["src/**/*.{ts,tsx}"],
      },
    },
  };
});
