eCourts Cause List Scraper & Web UI
This project provides a set of tools to automatically download "cause lists" (daily court schedules) and look up case information from the Indian eCourts services portal. It includes a powerful command-line interface for automation and a simple web application for ease of use.

The scraper is built using Python and the Playwright library to handle modern, JavaScript-heavy websites.

Features
Dual Interface: Access the scraper via a simple web form or a flexible command-line tool.

Cause List Downloader: Fetch the complete cause list for a specific court complex on a given date.

PDF Archiving: Automatically download and save all individual judge cause list PDFs.

Structured Data Output: All scraped information is saved in a clean, machine-readable JSON format.

Robust Scraping: Uses modern web automation that can handle complex, dynamic websites.

Project Structure
The project is organized into a core scraping script, a web wrapper, and template files.

.
├── main.py               # The core CLI scraper script
├── flask_app.py          # The Flask web application wrapper
├── templates/
│   ├── index.html        # HTML for the main web form
│   └── status.html       # HTML for the job status page
└── outputs/              # Folder for generated results (auto-created)
    ├── some_result.json
    └── pdfs/
        └── some_causelist.pdf
Setup and Installation
Follow these steps to get the project running on your local machine.

1. Prerequisites
Python 3.8 or newer.

2. Create a Virtual Environment
It is highly recommended to use a virtual environment to keep dependencies isolated.

Bash

# Create the environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
3. Install Dependencies
Install the required Python libraries from the terminal.

Bash

pip install flask playwright
4. Install Browser Binaries
Playwright requires browser binaries to function. This command will download them (this may take a few minutes).

Bash

playwright install
Usage
You can run the tool in two ways: through the easy-to-use web application or the powerful command-line interface.

Method 1: Running the Web Application (Recommended)
This method starts a local web server with a user-friendly form.

Start the server:

Bash

python flask_app.py
Open your browser: Navigate to http://127.0.0.1:8080.

Fill the form: Enter the State, District, and Court Complex, select a date, and click "Fetch Cause List". You will be redirected to a status page that updates automatically until the job is complete.

Method 2: Using the Command-Line Interface (CLI)
This is ideal for automation and scripting. Run main.py with arguments directly from your terminal.

Example: Download a Cause List
This command fetches the cause list for Tis Hazari, Delhi for a specific date and downloads all associated PDFs.

Bash

python main.py --causelist --state "Delhi" --district "New Delhi" --complex "Tis Hazari" --date "2025-10-20" --download-pdf
--causelist: Specifies the action to download a cause list.

--date: Use YYYY-MM-DD format. You can also use --today or --tomorrow.

--download-pdf: Optional flag to save the PDF files.

Output Files
All results are saved in the outputs/ directory, which is created automatically.

JSON Files: A file named web_... .json or ecourts_... .json contains the structured data from the scrape.

JSON

{
  "invoked_at": "2025-10-17T20:30:00.123456",
  "date_checked": "2025-10-20",
  "result": {
    "cause_list": {
      "state": "Delhi",
      "district": "New Delhi",
      "complex": "Tis Hazari",
      "date": "2025-10-20",
      "judges": [
        {
          "judge_text": "Hon'ble Judge A. K. Singh",
          "pdf_link": "https://.../link_to.pdf",
          "downloaded_pdf": "outputs\\pdfs\\2025-10-20_Tis Hazari_Honble Judge A K Singh.pdf"
        }
      ]
    }
  }
}
PDF Files: If --download-pdf is used, all cause list PDFs are saved in the outputs/pdfs/ sub-directory.

Troubleshooting
No Files Generated: The most common reason for this is that the selected date is too far in the future. Court cause lists are typically published only 1-2 days in advance. If you choose a date a week from now, the website will have no data, and the script will produce an empty result.

Solution: Try running the script with --today or for the next working day (e.g., Monday if today is Friday).