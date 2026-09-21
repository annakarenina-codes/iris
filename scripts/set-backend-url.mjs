#!/usr/bin/env node
/**
 * Writes the backend address, and optionally the access token, into both clients at once.
 *
 *   node scripts/set-backend-url.mjs https://iris-production.up.railway.app <token>
 *
 * Six files carry one of these values. Three laptops running the extension unpacked each get
 * a different extension ID, so chrome.storage.sync will not carry the address between them,
 * and the Android build has no options screen once a hosted address is set. Editing six files
 * by hand before copying the folder around is how one of them ends up pointing at a laptop
 * that is closed.
 *
 * Run it again whenever the address changes; it rewrites in place and is safe to repeat.
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
  "iris-android/app/src/main/java/com/iris/app/IrisApiClient.java",
];

/** Replaces the quoted value that sits immediately before a `// iris:<marker>` comment. */
function rewrite(text, marker, value) {
  const pattern = new RegExp(
    `("(?:[^"\\\\]|\\\\.)*")([\\s,;]*//\\s*iris:${marker}\\b)`,
    "g",
  );
  let hits = 0;
  const next = text.replace(pattern, (_match, _quoted, tail) => {
    hits += 1;
    return JSON.stringify(value) + tail;
  });
  return { text: next, hits };
}

function main() {
  const [rawUrl, rawToken] = process.argv.slice(2);

  if (!rawUrl) {
    console.error("usage: node scripts/set-backend-url.mjs <backend-url> [access-token]");
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

  const token = (rawToken || "").trim();
  let urlWrites = 0;
  let tokenWrites = 0;

  for (const relative of FILES) {
    const path = join(ROOT, relative);
    const before = readFileSync(path, "utf8");

    let after = before;
    const withUrl = rewrite(after, "backend-url", url);
    after = withUrl.text;
    urlWrites += withUrl.hits;

    if (rawToken !== undefined) {
      const withToken = rewrite(after, "access-token", token);
      after = withToken.text;
      tokenWrites += withToken.hits;
    }

    if (after !== before) {
      writeFileSync(path, after);
      console.log(`  ${relative}`);
    }
  }

  console.log(`\nbackend URL set to ${url} in ${urlWrites} place(s).`);

  if (rawToken === undefined) {
    console.log("No token given, so the token lines were left alone.");
  } else if (token) {
    console.log(`Access token written to ${tokenWrites} place(s).`);
  } else {
    console.log(`Access token cleared in ${tokenWrites} place(s).`);
  }

  if (!local && !token && rawToken === undefined) {
    console.log(
      "\nThis is a hosted address with no token set. Until IRIS_API_TOKEN is set on the\n" +
        "server and passed here, anyone who finds the URL can spend your API credit.",
    );
  }
}

main();
