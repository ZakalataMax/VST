# VST Work Tools — Usage Guide

How to install, run, and operate VST Work Tools day to day, including the scheduled
daily report. For how the app is built internally, see `CLAUDE.md` instead.

## 1. What you need

- Windows (the app is packaged as a Windows exe; Outlook/Excel automation is
  Windows-only).
- The app itself: either the built `VST.exe`, or Python 3.11+ to run it from source.
- A `.env` file with `ELASTIC_PASS` set — the password for downloading ACS logs from
  Elastic. Ask whoever manages Elastic access for this credential.
- *Optional* — Microsoft Excel installed: enables the native `Pivot` sheet in exported
  reports (skipped automatically if Excel isn't there).
- *Optional* — Microsoft Outlook installed and signed in: required to email reports,
  either manually from the app or via the scheduled daily job. Emailing is skipped
  (not an error) if Outlook isn't set up.

## 2. First-time setup

### 2a. Just running the app (no building)

1. Get `VST.exe` and a `.env` file (from whoever built it, or build it yourself — see
   2b) and put them in the same folder.
2. Open `.env` in a text editor and set `ELASTIC_PASS`. Everything else has sane
   defaults — see `backend/.env.example` for the full list of optional settings
   (recipients, storage paths, thresholds, etc.).
3. Double-click `VST.exe`, or create a desktop shortcut to it.

A `data/` folder is created next to the exe on first run: `data/logs`, `data/csv`,
`data/csv_reports_final`. This is where downloaded logs, parsed CSVs, and exported
reports live.

### 2b. Building `VST.exe` from source

```bat
git clone <repo-url> Parser
cd Parser
git pull                REM if already cloned — always pull latest before building
cd backend
copy .env.example .env
notepad .env            REM fill in ELASTIC_PASS, save and close
build.bat
```

Output: `backend/dist/VST.exe`, with `.env` copied next to it automatically. Re-run
`build.bat` any time `backend/` source changes — it replaces `VST.exe` only and keeps
`dist/data/` (your downloaded logs, parsed CSVs, and reports) untouched.

### 2c. Running from source instead of building (developers)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env    # fill in ELASTIC_PASS
python -m desktop
```

Same behavior as `VST.exe`, using `backend/data/` instead of `backend/dist/data/`.

## 3. Using the app

The app opens on the **Logs** tab.

### Import & Parse

1. Pick a **From**/**To** date range.
2. Click **Import**. Each day downloads from Elastic and is parsed into a CSV
   automatically. The sidebar shows per-day status (not downloaded / partial / full),
   row count, and coverage.
3. Already-complete past days are skipped on re-import; today (or any partial day) is
   always re-downloaded and re-parsed, so re-running Import is safe and cheap.
4. If a day fails (too many malformed lines, or an Elastic query that still hits the
   row cap at the smallest time window), it's reported instead of silently saving
   partial data — re-run Import for that day once the underlying issue is fixed.

### Report

1. Select the day(s) you want in the sidebar — this fills the report **From**/**To**
   range (or type a range in directly).
2. Click **Run** to preview the pivot in the table; **Load more** paginates through
   additional rows.
3. Click **Export** to write a timestamped `.xlsx` file to `data/csv_reports_final/`
   (never overwrites a previous export). The workbook has:
   - `Data` — every row from the query.
   - `Summary` — counts and percentages by transaction result.
   - `Pivot` — a fully built, reconfigurable native Excel PivotTable (only if the
     **Native pivot** checkbox is on and Excel is installed).
4. A report range that has any day without a parsed CSV is blocked and lists which
   day(s) are missing — go back to Import & Parse for those days first.

### Emailing a report manually

Check **Email report** before clicking **Export**. A compose dialog pops up (prefilled
recipients from `REPORT_EMAIL_TO`, editable body) — confirming it sends the exported
file as an attachment via the local, signed-in Outlook app once export finishes.
Uncheck the box to just export without emailing.

### Custom SQL (optional, advanced)

Turn on **Custom SQL** in the Report panel to edit the underlying query directly. It
loads the built-in template on first use. Only a single `SELECT`/`WITH` statement is
allowed — file-access functions and any DDL/DML are rejected.

### Parser tab

A standalone utility unrelated to ACS log parsing: paste a list of numbers to format
them (plain or SQL-quoted) and flag duplicates.

## 4. Running the daily report without the UI

The same download → parse → report → email flow the scheduler uses can be run once by
hand, e.g. to test configuration changes or catch up after an outage:

```bat
dist\VST.exe --auto-report
```

or, running from source:

```bash
python -m desktop --auto-report
```

This opens no window, prints a JSON summary, writes `run-summary-<timestamp>.json` next
to the exported reports, and exits with `0` on success or `1` on failure (missing
parsed days, export failure, or an email send failure all count as failure, but every
other successful part of the run still completes and is recorded in the summary).

Relevant `.env` settings for this job:

- `DAILY_JOB_DOWNLOAD_DAYS` (default 2) — how many trailing days to (re)download/parse.
- `DAILY_JOB_REPORT_DAYS` (default 10) — how many trailing days the exported report
  covers. Older days in this window must already have a parsed CSV on disk from a
  previous run, or the job fails instead of emailing a partial report.
- `REPORT_EMAIL_TO` / `REPORT_EMAIL_SUBJECT` — recipient(s) and subject. Leave
  `REPORT_EMAIL_TO` unset to use the built-in default recipient, or set it to an empty
  value to disable emailing for this job entirely.

## 5. Scheduling the daily report (Windows Task Scheduler)

`backend/run_auto_report.bat` is the entry point meant for the scheduled task. It
always runs the **built** `dist\VST.exe --auto-report` (never from source), appends its
output to `data\auto_report.log`, and sets `REPORT_EMAIL_TO` for the current
recipients — edit that line in the `.bat` file to change who gets the scheduled email
(this overrides `.env` since it's set right before launching the exe).

> Rebuild (`build.bat`) whenever `backend/` source changes — the scheduled task keeps
> running whatever was last built until you do.

Create the task (daily at 07:00; `/it` = only run while a user is logged in, which
Outlook COM automation requires):

```cmd
schtasks /create /tn "VST Daily Report" /tr "\"C:\path\to\backend\run_auto_report.bat\"" /sc daily /st 07:00 /it /f
```

Manage it:

```cmd
schtasks /query /tn "VST Daily Report" /v /fo list   REM inspect current config
schtasks /change /tn "VST Daily Report" /st 08:30     REM change the trigger time
schtasks /run /tn "VST Daily Report"                  REM run right now, on demand
schtasks /change /tn "VST Daily Report" /disable      REM pause
schtasks /change /tn "VST Daily Report" /enable       REM resume
schtasks /delete /tn "VST Daily Report" /f             REM remove entirely
```

From Git Bash, prefix these with `MSYS_NO_PATHCONV=1` (otherwise it mangles the
`/tn`-style flags). If you prefer a GUI, `taskschd.msc` → **Create Task** gives the
same options under **Triggers**/**Actions**, with "Run only when user is logged on"
under **General**.

## 6. Checking results / troubleshooting

- `data\auto_report.log` (next to the exe) — full stdout/stderr of every scheduled or
  manual `--auto-report` run, appended.
- `data\csv_reports_final\run-summary-*.json` — structured result of each
  `--auto-report` run: days downloaded/parsed, dropped-line counts, report path/row
  count, pivot status, email status, and any failures.
- Task Scheduler's **History** tab for "VST Daily Report" — start/stop times and exit
  code (`0` = success).
- `vst-error.log` (next to the exe) — unhandled crash log for the desktop app itself
  (separate from the auto-report log).
- Common issues:
  - Nothing downloads / auth errors → check `ELASTIC_PASS` (and `ELASTIC_USER` if
    non-default) in `.env`.
  - No `Pivot` sheet in exports → Excel isn't installed, or the report has more rows
    than the native-pivot limit; the file still exports fine without it.
  - No email sent → Outlook isn't installed/signed in, or `REPORT_EMAIL_TO` is empty;
    check `email_status` in the run summary for the exact reason.
  - Scheduled task doesn't reflect a recent code change → rebuild with `build.bat`.

## 7. Updating

Pull the latest source and rebuild — this repo's normal workflow is: edit/commit on a
dev machine, then pull and build wherever the exe actually runs.

```bat
git pull
cd backend
build.bat
```
