# Website Change Detector (Beginner Python Project)

A small website that checks public web pages and stores a new version only when the cleaned page text changes.

## What it can do

- Add a public website with a name and check interval.
- Check a website immediately with the **Check now** button.
- Save page text in a local SQLite database.
- Ignore some common noise such as scripts, styles, timestamps, and long random tokens.
- Show a dashboard with website status.
- View saved versions and a simple text difference between the newest two snapshots.
- Run repeated checks while the Python app is running.

## 1. Install Python

Install Python 3.10 or newer from https://www.python.org/downloads/

On Windows, tick **Add Python to PATH** during installation.

## 2. Open the project folder

Open Command Prompt or the terminal in this folder.

## 3. Install the packages

```bash
python -m pip install -r requirements.txt
```

## 4. Start the website

```bash
python app.py
```

You should see a local address in the terminal. Open:

http://127.0.0.1:5000

Keep the terminal open while using the website. Press `Ctrl + C` in the terminal to stop it.

## How the code works (simple explanation)

- `app.py` contains the Python logic.
- `templates/index.html` is the main dashboard page.
- `templates/history.html` shows saved versions and text changes.
- `static/style.css` controls the colours, spacing, and layout.
- `changes.db` is created automatically and stores websites and snapshots.

### Main functions in `app.py`

- `create_tables()` makes the database tables.
- `fetch_page()` downloads a public page.
- `clean_page_text()` removes some page noise.
- `check_website()` compares the latest text hash and saves a snapshot only when it changes.
- `background_checker()` repeats checks while the app is running.

## Important beginner-version limits

This is a learning project, not a production monitoring service.

- It uses ordinary HTTP requests, not a headless browser. Some JavaScript-heavy websites may not work.
- It does not yet save screenshots, send email/Telegram/Discord alerts, or offer a visual region picker.
- The background checker wakes up every minute and checks saved pages. The selected interval is saved and shown in the UI, but per-website scheduling is a future improvement.
- The app avoids automatically following redirects and blocks non-public IP addresses, but a real public service needs stronger URL/redirect protections, a proper job queue, rate limiting, and careful security testing.
- The app does not save website login credentials. Only monitor public pages you are allowed to access, and avoid checking a site too frequently.

## Easy improvements to try

1. Change the purple colours in `static/style.css`.
2. Add a keyword-only monitoring option.
3. Add email alerts when the status becomes `Changed`.
4. Use Playwright later to support JavaScript-rendered pages and screenshots.
5. Improve scheduling so each website is checked at its selected interval.
