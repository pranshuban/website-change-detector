# Website Change Detector
# A small beginner-friendly Flask project.
# It checks public web pages, stores versions in SQLite, and shows text changes.

from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import hashlib
import difflib
import re
import threading
import time
from urllib.parse import urlparse
import ipaddress
import socket

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

DATABASE = "changes.db"
CHECK_EVERY_SECONDS = 60
MAX_PAGE_SIZE = 2 * 1024 * 1024  # Do not download pages larger than 2 MB.


def connect_db():
    """Open a connection to our small local SQLite database."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():
    """Create the tables the first time the app runs."""
    with connect_db() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS websites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                interval_minutes INTEGER NOT NULL DEFAULT 60,
                last_checked TEXT,
                status TEXT NOT NULL DEFAULT 'Not checked yet',
                last_hash TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                website_id INTEGER NOT NULL,
                page_text TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                FOREIGN KEY (website_id) REFERENCES websites (id)
            )
        """)


def is_public_url(url):
    """
    Basic safety check: only allow public HTTP/HTTPS website URLs.
    This is a learning-project safeguard, not a complete production security system.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False

    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
        for address in addresses:
            ip_text = address[4][0]
            ip = ipaddress.ip_address(ip_text)
            if not ip.is_global:
                return False
    except (socket.gaierror, ValueError):
        return False

    return True


def clean_page_text(html):
    """Turn HTML into readable text and remove common changing/noisy elements."""
    soup = BeautifulSoup(html, "html.parser")

    # These parts often change without meaning anything important.
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    # Remove common timestamp, advertisement, and counter elements.
    noisy_words = re.compile(
        r"(timestamp|time-stamp|ad-container|advertisement|cookie-banner|"
        r"visitor-count|view-count|random-token)",
        re.IGNORECASE
    )
    for tag in soup.find_all(True):
        tag_id = tag.get("id", "")
        tag_classes = " ".join(tag.get("class", []))
        if noisy_words.search(str(tag_id) + " " + tag_classes):
            tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    # Replace common date/time strings and long random-looking tokens.
    text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", "[TIME]", text)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "[DATE]", text)
    text = re.sub(r"\b[A-Za-z0-9_-]{24,}\b", "[TOKEN]", text)

    return text.strip()


def fetch_page(url):
    """Download a page and return its cleaned text."""
    if not is_public_url(url):
        raise ValueError("Please enter a public website URL beginning with http:// or https://.")

    headers = {"User-Agent": "BeginnerWebsiteChangeDetector/1.0"}
    response = requests.get(
        url,
        headers=headers,
        timeout=15,
        allow_redirects=False,
        stream=True
    )

    # Do not follow redirects automatically; this keeps the starter safer.
    if response.is_redirect:
        raise ValueError("This website redirected the request. Try its final HTTPS URL.")

    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        raise ValueError("This starter version only checks HTML or plain-text pages.")

    page_bytes = b""
    for chunk in response.iter_content(chunk_size=8192):
        page_bytes += chunk
        if len(page_bytes) > MAX_PAGE_SIZE:
            raise ValueError("This page is too large for the beginner version (limit: 2 MB).")

    encoding = response.encoding or "utf-8"
    html = page_bytes.decode(encoding, errors="replace")
    return clean_page_text(html)


def check_website(website_id):
    """Check one website and save a snapshot only when its text changes."""
    with connect_db() as connection:
        website = connection.execute(
            "SELECT * FROM websites WHERE id = ?", (website_id,)
        ).fetchone()

    if website is None:
        return

    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        page_text = fetch_page(website["url"])
        page_hash = hashlib.sha256(page_text.encode("utf-8")).hexdigest()

        with connect_db() as connection:
            if website["last_hash"] != page_hash:
                connection.execute(
                    """INSERT INTO snapshots (website_id, page_text, content_hash, checked_at)
                       VALUES (?, ?, ?, ?)""",
                    (website_id, page_text, page_hash, checked_at)
                )
                new_status = "Changed" if website["last_hash"] else "OK"
                connection.execute(
                    """UPDATE websites
                       SET last_checked = ?, status = ?, last_hash = ?
                       WHERE id = ?""",
                    (checked_at, new_status, page_hash, website_id)
                )
            else:
                connection.execute(
                    "UPDATE websites SET last_checked = ?, status = 'OK' WHERE id = ?",
                    (checked_at, website_id)
                )

    except Exception as error:
        # Show a short error in the dashboard instead of crashing the app.
        with connect_db() as connection:
            connection.execute(
                "UPDATE websites SET last_checked = ?, status = ? WHERE id = ?",
                (checked_at, "Error: " + str(error)[:100], website_id)
            )


def background_checker():
    """Check saved websites repeatedly in the background."""
    while True:
        with connect_db() as connection:
            websites = connection.execute("SELECT id FROM websites").fetchall()

        for website in websites:
            check_website(website["id"])
            time.sleep(1)  # A tiny pause so we do not hammer websites.

        time.sleep(CHECK_EVERY_SECONDS)


@app.route("/")
def index():
    with connect_db() as connection:
        websites = connection.execute(
            "SELECT * FROM websites ORDER BY id DESC"
        ).fetchall()

    total = len(websites)
    changed = sum(1 for site in websites if site["status"] == "Changed")
    errors = sum(1 for site in websites if str(site["status"]).startswith("Error"))

    return render_template(
        "index.html",
        websites=websites,
        total=total,
        changed=changed,
        errors=errors
    )


@app.route("/add", methods=["POST"])
def add_website():
    name = request.form.get("name", "").strip()
    url = request.form.get("url", "").strip()
    interval = request.form.get("interval", "60")

    if not name or not url:
        flash("Please enter both a website name and URL.", "error")
        return redirect(url_for("index"))

    try:
        interval = int(interval)
        if interval < 15 or interval > 1440:
            raise ValueError
    except ValueError:
        flash("The interval must be between 15 minutes and 24 hours.", "error")
        return redirect(url_for("index"))

    if not is_public_url(url):
        flash("Enter a valid public website URL, such as https://example.com.", "error")
        return redirect(url_for("index"))

    with connect_db() as connection:
        connection.execute(
            "INSERT INTO websites (name, url, interval_minutes) VALUES (?, ?, ?)",
            (name, url, interval)
        )
        new_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Do the first check immediately so the user sees a result straight away.
    check_website(new_id)
    flash("Website added! Its first check is complete.", "success")
    return redirect(url_for("index"))


@app.route("/check/<int:website_id>", methods=["POST"])
def check_now(website_id):
    check_website(website_id)
    flash("Check finished.", "success")
    return redirect(url_for("index"))


@app.route("/delete/<int:website_id>", methods=["POST"])
def delete_website(website_id):
    with connect_db() as connection:
        connection.execute("DELETE FROM snapshots WHERE website_id = ?", (website_id,))
        connection.execute("DELETE FROM websites WHERE id = ?", (website_id,))
    flash("Website removed.", "success")
    return redirect(url_for("index"))


@app.route("/history/<int:website_id>")
def history(website_id):
    with connect_db() as connection:
        website = connection.execute(
            "SELECT * FROM websites WHERE id = ?", (website_id,)
        ).fetchone()
        snapshots = connection.execute(
            "SELECT * FROM snapshots WHERE website_id = ? ORDER BY id DESC",
            (website_id,)
        ).fetchall()

    if website is None:
        flash("That website could not be found.", "error")
        return redirect(url_for("index"))

    # Compare the newest two versions to create a simple text diff.
    difference = []
    if len(snapshots) >= 2:
        old_lines = snapshots[1]["page_text"].split()
        new_lines = snapshots[0]["page_text"].split()
        difference = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile="Previous version",
            tofile="Latest version",
            lineterm=""
        ))

    return render_template(
        "history.html",
        website=website,
        snapshots=snapshots,
        difference=difference
    )


if __name__ == "__main__":
    create_tables()

    # Start one background checker when running the app directly.
    checker = threading.Thread(target=background_checker, daemon=True)
    checker.start()

    app.run(debug=True, use_reloader=False)
