#!/usr/bin/env node
/**
 * Writes the backend address into every client file that holds it.
 *
 *   node scripts/set-backend-url.mjs https://iris-production.up.railway.app
 *
 * The address is not a secret, so it lives in the source. The access token is, and this
 * repository is public, so the token is deliberately NOT handled here:
 *
 *   - Chrome:  type it once per laptop under Options -> Developer settings. It stays in
 *              that browser's storage.
 *   - Android: put `iris.accessToken=...` in iris-android/local.properties, which git
 *              ignores. The build reads it into BuildConfig.
 *
 * Run this again whenever the address changes; it rewrites in place and is safe to repeat.
 */

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

const FILES = [
  "iris-extension/src/background.js",
  "iris-extension/src/content.js",
  "iris-extension/popup.js",
  "iris-extension/options.js",
  "iris-android/app/src/main/java/com/iris/app/IrisPrefs.java",
];

/** Replaces the quoted value that sits immediately before a `// iris:backend-url` comment. */
function rewrite(text, value) {
  const pattern = /("(?:[^"\\]|\\.)*")([\s,;]*\/\/\s*iris:backend-url\b)/g;
  let hits = 0;
  const next = text.replace(pattern, (_match, _quoted, tail) => {
    hits += 1;
    return JSON.stringify(value) + tail;
  });
  return { text: next, hits };
}

function main() {
  const [rawUrl, extra] = process.argv.slice(2);

  if (!rawUrl) {
    console.error("usage: node scripts/set-backend-url.mjs <backend-url>");
    process.exit(1);
  }

  if (extra) {
    console.error("This script takes the URL only. The access token is kept out of the");
    console.error("repository on purpose -- see the comment at the top of this file.");
    process.exit(1);
  }

  const url = rawUrl.trim().replace(/\/+$/, "");

  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    console.error(`"${url}" is not a URL. It needs the scheme too, as in https://example.com`);
    process.exit(1);
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    console.error("The backend URL has to be http or https.");
    process.exit(1);
  }

  const local = ["localhost", "127.0.0.1", "10.0.2.2"].includes(parsed.hostname);
  if (parsed.protocol === "http:" && !local) {
    console.error(`Refusing to write ${url}: a hosted backend has to be https, or every`);
    console.error("check a participant runs travels their network in the clear.");
    process.exit(1);
  }

  let written = 0;

  for (const relative of FILES) {
    const path = join(ROOT, relative);
    const before = readFileSync(path, "utf8");
    const { text, hits } = rewrite(before, url);
    written += hits;

    if (text !== before) {
      writeFileSync(path, text);
      console.log(`  ${relative}`);
    }
  }

  console.log(`\nBackend URL set to ${url} in ${written} place(s).`);

  if (!local) {
    console.log("\nThe token is separate, and is not written by this script:");
    console.log("  Chrome   Options -> Developer settings -> Access token, on each laptop");
    console.log("  Android  iris.accessToken=... in iris-android/local.properties");
  }
}

main();
