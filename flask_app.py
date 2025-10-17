from flask import Flask, request, render_template, redirect, url_for, jsonify, send_from_directory
import subprocess
import uuid
import os
import threading
import time
from datetime import date, timedelta
from pathlib import Path

app = Flask(__name__)

# --- In-memory job store (for simplicity) ---
# In a production app, you would use a database or Redis for this.
JOBS = {}
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

def run_scraper_task(job_id: str, cmd: list):
    """This function runs in a separate thread."""
    try:
        # Update job status to 'running'
        JOBS[job_id]['status'] = 'running'
        start_time = time.time()
        
        # Run the subprocess
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,  # Don't raise exception on non-zero exit code
            encoding='utf-8'
        )

        # Check for errors after the process completes
        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        # Find the JSON output file created by the script
        files = sorted(OUTPUT_DIR.glob(f"web_{job_id}_*.json"))
        if not files:
            raise FileNotFoundError("Scraper ran but did not produce an output file.")
        
        # Collect PDFs generated during this job window
        pdf_dir = OUTPUT_DIR / "pdfs"
        pdfs = []
        if pdf_dir.exists():
            for p in sorted(pdf_dir.glob("*.pdf")):
                try:
                    if p.stat().st_mtime >= start_time - 1:
                        pdfs.append(p.name)
                except Exception:
                    continue

        # Update job status to 'completed'
        JOBS[job_id].update({
            'status': 'completed',
            'output_file': files[-1].name,
            'pdfs': pdfs
        })

    except Exception as e:
        # Update job status to 'failed'
        JOBS[job_id].update({
            'status': 'failed',
            'error': str(e)
        })

@app.route("/", methods=["GET"])
def index():
    """Renders the main form with dropdown options."""
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Minimal sample options; extend as needed
    states = [
        "Delhi",
        "Maharashtra",
        "Karnataka",
    ]
    districts_by_state = {
        "Delhi": ["New Delhi", "South East", "Central"],
        "Maharashtra": ["Mumbai", "Pune"],
        "Karnataka": ["Bengaluru", "Mysuru"],
    }
    complexes_by_district = {
        "New Delhi": ["Tis Hazari", "Patiala House", "Rouse Avenue"],
        "South East": ["Saket Courts"],
        "Central": ["Karkardooma"],
        "Mumbai": ["Fort", "Dindoshi"],
        "Pune": ["Shivajinagar"],
        "Bengaluru": ["City Civil Court", "Mayo Hall"],
        "Mysuru": ["Mysuru Court Complex"],
    }

    return render_template(
        "index.html",
        today=today.isoformat(),
        tomorrow=tomorrow.isoformat(),
        states=states,
        districts_by_state=districts_by_state,
        complexes_by_district=complexes_by_district,
    )

@app.route("/run", methods=["POST"])
def run_job():
    """Starts a new scraping job."""
    job_id = uuid.uuid4().hex[:10]

    # Build the command from form data
    cmd = [
        "python", "main.py", "--causelist",
        "--state", request.form.get("state"),
        "--district", request.form.get("district"),
        "--complex", request.form.get("complex"),
        "--date", request.form.get("date"),
        "--output", f"web_{job_id}",
        "--headless", # Always run in headless mode from the web app
        "--download-pdf" # Always download PDFs
    ]
    # Force PDFs regardless of checkbox; keep UI checkbox for future use

    # Initialize job in our store
    JOBS[job_id] = {'status': 'pending', 'command': ' '.join(cmd)}

    # Start the scraper in a background thread
    thread = threading.Thread(target=run_scraper_task, args=(job_id, cmd))
    thread.start()

    # Redirect user to the status page
    return redirect(url_for('get_status', job_id=job_id))

@app.route("/status/<job_id>")
def get_status(job_id: str):
    """Renders the status page for a given job."""
    job = JOBS.get(job_id)
    if not job:
        return "Job not found", 404
    return render_template("status.html", job_id=job_id, job=job)

@app.route("/api/status/<job_id>")
def api_status(job_id: str):
    """Returns the job status as JSON (for potential JS polling)."""
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)

@app.route("/outputs/<path:filename>")
def serve_output(filename: str):
    """Serves generated files (JSON, PDFs) from the outputs directory."""
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(port=8080, debug=True)