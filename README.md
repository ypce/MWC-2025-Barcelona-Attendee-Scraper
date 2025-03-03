# MWC Barcelona 2025 Attendee Scraper

This tool automatically scrapes attendee information from the MWC Barcelona 2025 event website. It allows you to search for attendees based on various criteria and save the results to CSV files.

## Features

- Search for attendees by name/keyword
- Filter by attendee interest
- Filter by company main activity
- Batch processing of multiple filter combinations
- Automatic retry and error handling
- Detailed logging

## Prerequisites

- Python 3.7+
- Playwright for Python
- A valid MWC Barcelona 2025 account

## Installation

1. Clone this repository
2. Install the required dependencies:

```bash
pip install playwright asyncio
python -m playwright install
```

## Configuration

The scraper requires three input files in the same directory:

1. `letters.txt` - Keywords or name fragments to search for (one per line)
2. `interests.txt` - Interest categories to filter by (one per line)
3. `company_activities.txt` - Company activities to filter by (one per line)

## Environment Variables

Set the following environment variables with your MWC Barcelona login credentials:

```bash
# On Linux/Mac
export MWC_USERNAME="your_email@example.com"
export MWC_PASSWORD="your_password"

# On Windows (Command Prompt)
set MWC_USERNAME=your_email@example.com
set MWC_PASSWORD=your_password

# On Windows (PowerShell)
$env:MWC_USERNAME="your_email@example.com"
$env:MWC_PASSWORD="your_password"
```

## Usage

Run the script with:

```bash
python mwc_scraper.py
```

Optional arguments:
- `--debug`: Enable additional debug output

## Output

The script generates:

1. Individual CSV files for each search combination
2. A master log file (`mwc_scraper_master_log.csv`) tracking all operations

Each CSV contains attendee information including:
- Name
- Job Title
- Company
- Event
- Profile URL
- Interest
- Company Activity

## Error Handling

If the script encounters errors, it will:
1. Log the error in the master log file
2. Create a `terminate_signal.txt` file with error information
3. Attempt to recover and continue with the next combination when possible

## Notes

- The script remembers which combinations it has already processed, so it can be safely restarted if interrupted.
- All found attendees are added to each combination's output file, even if they were found in previous combinations.
- The script will automatically handle login and session management.

## Legal Considerations

Ensure you comply with MWC Barcelona's terms of service and have appropriate access rights before using this tool. This scraper is intended for legitimate data collection purposes only.
