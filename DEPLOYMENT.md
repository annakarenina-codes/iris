# Deploying IRIS for user testing

Written for a study on three laptops and up to two phones, all talking to one backend on
Railway. Everything here has been checked against the code in this repository.

## What the backend costs, and why it is shaped this way

A check spends about **85% of its time waiting** on OpenAI, Brave and publishers, and about
15% on this machine's processor. That single fact decides the whole configuration:

| measured | value |
|---|---|
| Memory, one process with both models warm | **1005 MB** |
| Local processor work per text check | ~3 s of ~22 s |
| Local processor work per image check | ~6.4 s of OCR on top |
| Slowest post recorded | 195 s (twelve claims) |
| Median post | 46 s |

So IRIS runs as **one process with eight threads**, not several processes. Threads give the
concurrency, because a thread waiting on OpenAI costs nothing. A second process would give
almost none, and would cost another gigabyte, another copy of the article cache, and another
two simultaneous requests aimed at every publisher.

Railway bills what a container actually consumes, per second: **$10/GB/month** of memory and
**$20/vCPU/month**. At roughly 1 GB warm that is about **$0.36/day**, so a Hobby plan's $5
covers a testing fortnight comfortably but not a month of leaving it switched on. A high vCPU
limit is close to free, because you are billed for what is used, not what is allowed — so
give it room and let the encoding and OCR bursts finish quickly.

## 1. Deploy the backend

The backend builds from `iris-backend/Dockerfile`. It installs torch from the CPU index (the
default wheel on PyPI carries a CUDA runtime that no Railway container can use) and downloads
both models at build time, so nobody's first check waits for 190 MB.

1. Create a Railway project from this repository.
2. Service → **Settings** → **Root Directory**: `/iris-backend`. It is a path, with a leading
   slash — not a GitHub URL. This is the one setting the deploy cannot work without: Railway
   finds the Dockerfile inside that folder on its own and builds from it.
3. Optional: **Config File Path** → `/iris-backend/railway.json`. Railway's config file does
   **not** follow the root directory, so it needs the full path from the repository root or it
   is ignored. All it adds is the `/health` check and the restart policy; the deploy works
   without it.
4. Add the variables below.
5. **Settings** → **Networking** → **Generate Domain**. Answer `8080` if it asks for a port.
6. Deploy, then open `https://<your-service>.up.railway.app/health`. It should answer
   `{"status": "ok", ...}` without waking a model.

If Railway cannot see your repositories at all, its GitHub App has not been given access to
them. Go to `github.com/settings/installations` → **Railway** → **Configure**, accept any
pending permission banner, and make sure this repository is selected. Then in Railway, **Add**
→ **GitHub Repository** → **Refresh**. Deploying by pasting a public repo URL works, but that
route does not watch the repository, so pushes will not redeploy on their own.

### Variables

| name | value |
|---|---|
| `OPENAI_API_KEY` | your key |
| `BRAVE_API_KEY` | your key |
| `IRIS_API_TOKEN` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `IRIS_CLAIM_WORKERS` | `3`, or `2` on a small container |

Do **not** set `PORT`; Railway provides it. Leave `IRIS_TRACE_ENABLED` unset — TRACE returns
404 while it is off, and if you do turn it on for a public address it refuses every non-local
request unless `IRIS_TRACE_TOKEN` is also set. `.env.example` lists the rest.

`IRIS_API_TOKEN` is not optional once the address is public. Without it, anyone who finds the
URL can spend your OpenAI and Brave credit.

## 2. Point the clients at it

One command writes the address into all five places that hold it:

```bash
node scripts/set-backend-url.mjs https://your-service.up.railway.app
```

Run it before copying anything to the test machines. It is safe to repeat whenever the
address changes. Note that it sets the Android default too, replacing the `10.0.2.2` emulator
address — which is what you want for a hosted backend, and worth undoing if you go back to
local development.

**The token is deliberately not written by that script, because this repository is public.**
A token committed here is a token anyone can spend. It goes in two places instead, neither of
them tracked by git:

| client | where |
|---|---|
| Chrome | Options → Developer settings → **Access token**, once per laptop. Stays in that browser. |
| Android | `iris.accessToken=YOUR_TOKEN` in `iris-android/local.properties`, which `.gitignore` already covers. The build reads it into `BuildConfig`. |

If you skip both, the clients send no token and a backend with `IRIS_API_TOKEN` set answers
401 — which the panel shows as "This IRIS backend needs an access token."

Setting a hosted address also hides the Android backend card, so participants cannot retype
the server by accident. It reappears on its own whenever the built-in address points at a
development machine again.

## 3. The three laptops

1. Copy the repository folder to the laptop.
2. `chrome://extensions` → turn on **Developer mode** → **Load unpacked** → choose the
   `iris-extension` folder. Not `dist/`: the manifest that Chrome reads is at the top of
   `iris-extension`.
3. Check the toolbar popup shows your Railway address.
4. Select a sentence on a news page, right-click, **Check with IRIS**.

Each unpacked copy gets its own extension ID, so `chrome.storage.sync` does **not** carry
settings between laptops. That is why step 2 of this guide exists: with the address already
in the source, there is nothing to configure on each machine. Chrome shows a developer-mode
warning at every launch; it can be dismissed and does not affect the extension.

The **Backend URL** and the debug checkbox now sit under *Developer settings* on the options
page, folded shut. The privacy note stays visible, because participants should be able to
read what is and is not sent.

## 4. The phone

There is no signing configuration in `app/build.gradle`, so `assembleRelease` produces an
APK that Android will refuse to install. Build the debug one, which is signed automatically:

```bash
cd iris-android && ./gradlew assembleDebug
```

The APK lands at `app/build/outputs/apk/debug/app-debug.apk`. Copy it to the phone and open
it; Android will ask permission to install from this source once. Nothing in the study needs
a release build.

## 5. Running a session

**Warm it first.** Run one check yourself before participants start. The models load on first
use, so whoever goes first otherwise waits an extra 20–40 seconds. If you have enabled
Railway's serverless sleeping, Railway itself documents that the first request after a sleep
can come back as a 502 — leave it switched off during sessions and pause the service between
them instead.

**Expect a slower IRIS than on your laptop.** The 46-second median was measured on twelve
cores. On a two-vCPU container the encoding and OCR portions stretch out; the waiting on
OpenAI and Brave does not.

**What happens when a phone loses signal.** Both clients now give up after 180 seconds and
retry once. The retry is usually fast, because per-claim verdicts are cached on the server, so
the second attempt skips most of the pipeline.

## 6. Changing the backend afterwards

Push to the connected branch and Railway rebuilds. Participants keep the same URL and see
nothing but a gap of about a minute.

Two things are erased by every redeploy, because they live on the container's own disk:
`iris_cache.sqlite3` and `.iris-trace/`. **If you want to keep TRACE records from a session,
attach a Railway volume before it starts.** The verdict cache is only a cache; losing it
costs speed, not results.

## 7. Known limits

- A twelve-claim post takes around 195 seconds. Railway's documented ceiling is 15 minutes,
  but its edge has been reported to cut requests at about 300 seconds, so unusually long posts
  are the ones most likely to need the retry.
- The article cache, the per-publisher request limit and the embedding cache are all held in
  the one process. That is deliberate, and it is why the process count is 1. If you ever raise
  it, raise the publisher limits' scrutiny with it.
- `cleartextTrafficPermitted` is still true in the Android network config. With an https
  address it changes nothing; it means a mistyped `http://` address fails quietly rather than
  loudly.
