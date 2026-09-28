# Running the browser tests

The browser suite drives the app in Chromium through Playwright. It runs the regression checks, then save/reopen/download lifecycles under the page's normal content-security policy, with the producer tab open and closed. It's separate from the core suite, which needs no browser.

## Setup (once per machine)

A virtual environment keeps Playwright out of your system Python.

**macOS**

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
```

**Windows (PowerShell)**

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
```

(`.venv/` is local to your checkout; don't commit it.)

## Run

```sh
python scripts/check.py --suite browser
```

Results are written to `.checks/`, with a `run-record.json` that records the environment, the commit and the hashes of the tools used. The GitHub workflow runs the same suite automatically on every push.

## What this does and does not cover

It tests the app in **Playwright's Chromium**. It does **not** test the browsers people actually use: installed Edge or Chrome on Windows, Safari or Chrome on macOS. Those need a hands-on check. Open `Point-File-Unit-Converter.html` in each browser, then load, convert, download, save the complete handoff, reopen it and download again, and keep the files produced. That check is still pending; see `docs/CURRENT-STATUS.md`.
