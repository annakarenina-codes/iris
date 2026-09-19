import { copyFile, mkdir, rm } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(scriptDir, "..");
const distDir = join(projectRoot, "dist");

const files = [
  "manifest.json",
  "popup.html",
  "popup.css",
  "popup.js",
  "options.html",
  "options.css",
  "options.js",
  "assets/iris-logo.png",
  "assets/iris-logo-mark.png",
  "assets/icon16.png",
  "assets/icon32.png",
  "assets/icon48.png",
  "assets/icon128.png",
  "src/background.js",
  "src/content.js",
  "src/content.css"
];

await rm(distDir, { recursive: true, force: true });

for (const file of files) {
  const source = join(projectRoot, file);
  const target = join(distDir, file);
  await mkdir(dirname(target), { recursive: true });
  await copyFile(source, target);
}

console.log("IRIS extension bundle written to dist/");
