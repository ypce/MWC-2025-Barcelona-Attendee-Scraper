import asyncio
import csv
import os
import sys
import time
import argparse
from playwright.async_api import async_playwright

# Import the exit handler function
try:
    from exit_handler import create_exit_flag_file
except ImportError:
    # Define a simple version if the file doesn't exist
    def create_exit_flag_file(error=False):
        print("Creating exit signal file...")
        with open("terminate_signal.txt", "w") as f:
            status = "error" if error else "complete"
            f.write(f"{status}: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("Exit signal created. Exiting...")
        time.sleep(1)

# Generate dynamic output filename based on parameters
def generate_output_filename(attendee_name=None, interest=None, company_activity=None):
    """Generate a filename based on provided parameters with auto-enumeration"""
    base_name = "mwc_barcelona_2025_attendees"
    
    # If attendee name and/or interest are provided, use them in the filename
    if attendee_name or interest or company_activity:
        parts = []
        if attendee_name:
            # Clean attendee name for filename
            clean_name = attendee_name.lower()
            clean_name = ''.join(c if c.isalnum() or c == ' ' else '-' for c in clean_name)
            clean_name = clean_name.replace(' ', '-')
            parts.append(clean_name)
        if interest:
            # Clean interest for filename (remove special characters)
            interest_str = str(interest).lower()
            interest_str = ''.join(c if c.isalnum() or c == ' ' else '-' for c in interest_str)
            interest_str = interest_str.replace(' ', '-')
            # Remove any consecutive hyphens
            while '--' in interest_str:
                interest_str = interest_str.replace('--', '-')
            parts.append(interest_str)
        if company_activity:
            # Clean company activity for filename
            activity_str = str(company_activity).lower()
            activity_str = ''.join(c if c.isalnum() or c == ' ' else '-' for c in activity_str)
            activity_str = activity_str.replace(' ', '-')
            # Remove any consecutive hyphens
            while '--' in activity_str:
                activity_str = activity_str.replace('--', '-')
            parts.append(activity_str)
        
        base_name = "-".join(parts)
    
    # Find the next available file number
    counter = 1
    while True:
        filename = f"{base_name}-{counter}.csv"
        if not os.path.exists(filename):
            return filename
        counter += 1

async def login_to_mwc(page, username, password):
    """Handle the login process"""
    print("Logging in...")
    await page.goto("https://www.mwcbarcelona.com/mymwc")
    
    # Remove cookie consent if present
    await page.evaluate("""() => {
        const banner = document.getElementById('onetrust-consent-sdk');
        if (banner) banner.remove();
        document.querySelectorAll('.onetrust-pc-dark-filter').forEach(el => el.remove());
        document.body.style.overflow = 'auto';
    }""")
    
    # Fill the form
    await page.fill('input[type="email"]', username)
    await page.fill('input[type="password"]', password)
    
    # Click login button with JS (more reliable)
    await page.evaluate("""() => {
        const loginButton = document.getElementById('login-button');
        if (loginButton) loginButton.click();
    }""")
    
    # Wait for navigation to dashboard with reduced timeout
    try:
        await page.wait_for_url("**/mymwc/home*", timeout=10000)
        print("Login successful!")
        return True
    except Exception as e:
        print(f"Login error: {e}")
        return False

async def set_search_filter(page, search_term):
    """Set the search filter in the search input"""
    print(f"Setting search filter to '{search_term}'...")
    
    # Focus on the search input
    await page.focus('#find-attendees-search-bar')
    
    # Clear the existing text (backspace multiple times)
    try:
        # First try to get the current value
        current_value = await page.evaluate("""() => {
            const searchInput = document.querySelector('#find-attendees-search-bar');
            return searchInput ? searchInput.value : '';
        }""")
        
        # Clear the field by pressing backspace multiple times
        if current_value:
            print(f"Clearing existing search text: '{current_value}'")
            for _ in range(len(current_value)):
                await page.press('#find-attendees-search-bar', 'Backspace')
            await page.wait_for_timeout(500)
    except Exception as e:
        print(f"Error clearing search field: {e}")
        # Fallback to fill method
        await page.fill('#find-attendees-search-bar', '')
    
    # Type the search term character by character
    await page.type('#find-attendees-search-bar', search_term, delay=50)
    
    # Press Enter key to trigger search
    await page.press('#find-attendees-search-bar', 'Enter')
    
    # Click outside the input field to ensure the filter sticks
    await page.evaluate("""() => {
        // Click on the body or another element outside the search input
        document.body.click();
    }""")
    
    # Allow time for search results to load
    await page.wait_for_timeout(1500)
    return True

async def select_interest_filter(page, interest_value):
    """Set the interest filter dropdown"""
    if not interest_value:
        print("No interest filter specified, skipping...")
        return True
        
    print(f"Setting interest filter to '{interest_value}'...")
    
    success = await page.evaluate(f"""(interestValue) => {{
        // Find the Attendee Interest dropdown (second select)
        const selects = Array.from(document.querySelectorAll('select'));
        if (selects.length >= 2) {{
            const interestSelect = selects[1]; // Second select (Attendee Interest)
            
            // Find the option with the specified value
            const options = Array.from(interestSelect.options);
            const targetOption = options.find(option => 
                option.value === interestValue || 
                option.textContent.trim().toLowerCase() === interestValue.toLowerCase()
            );
            
            if (targetOption) {{
                // Set the value and trigger change event
                interestSelect.value = targetOption.value;
                interestSelect.dispatchEvent(new Event('change', {{ bubbles: true }}));
                console.log('Selected interest filter: ' + targetOption.textContent);
                return true;
            }} else {{
                console.log('Interest option not found: ' + interestValue);
                return false;
            }}
        }}
        
        console.log('Interest select element not found');
        return false;
    }}""", interest_value)
    
    if success:
        print("Interest filter applied successfully")
    else:
        print("Failed to apply interest filter")
    
    # Wait for filter to apply
    await page.wait_for_timeout(1000)
    return success

async def select_company_activity_filter(page, activity_value):
    """Set the company main activity filter dropdown"""
    if not activity_value:
        print("No company activity filter specified, skipping...")
        return True
        
    print(f"Setting company activity filter to '{activity_value}'...")
    
    success = await page.evaluate(f"""(activityValue) => {{
        // Find the Company Main Activity dropdown (fourth select)
        const selects = Array.from(document.querySelectorAll('select'));
        if (selects.length >= 4) {{
            const activitySelect = selects[3]; // Fourth select (Company Main Activity)
            
            // Find the option with the specified value
            const options = Array.from(activitySelect.options);
            const targetOption = options.find(option => 
                option.value === activityValue || 
                option.textContent.trim().toLowerCase() === activityValue.toLowerCase()
            );
            
            if (targetOption) {{
                // Set the value and trigger change event
                activitySelect.value = targetOption.value;
                activitySelect.dispatchEvent(new Event('change', {{ bubbles: true }}));
                console.log('Selected company activity filter: ' + targetOption.textContent);
                return true;
            }} else {{
                console.log('Company activity option not found: ' + activityValue);
                return false;
            }}
        }}
        
        console.log('Company activity select element not found');
        return false;
    }}""", activity_value)
    
    if success:
        print("Company activity filter applied successfully")
    else:
        print("Failed to apply company activity filter")
    
    # Wait for filter to apply
    await page.wait_for_timeout(1000)
    return success

async def scrape_combination(page, attendee_name, interest, company_activity, processed_urls):
    """Scrape attendees for a specific combination of filters"""
    
    # Generate dynamic output filename
    output_file = generate_output_filename(attendee_name, interest, company_activity)
    print(f"Using output file: {output_file}")
    
    # Initialize CSV file if it doesn't exist already
    if not os.path.exists(output_file):
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Name', 'Job Title', 'Company', 'Event', 'Profile URL', 'Interest', 'Company Activity']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            print(f"Created new output file: {output_file}")
    
    total_attendees = 0
    
    try:
        # Navigate to the search page if not already there
        current_url = page.url
        if "search" not in current_url:
            print("Navigating to attendee search page...")
            await page.goto("https://www.mwcbarcelona.com/mymwc/search", wait_until="networkidle")
            await page.wait_for_timeout(2000)  # Increased wait time
            
        # Select MWC Barcelona 2025 from the dropdown
        print("Selecting MWC Barcelona 2025 event filter...")
        await page.wait_for_selector('select', state='visible', timeout=5000)
        
        await page.evaluate("""() => {
            const selects = Array.from(document.querySelectorAll('select'));
            for (const select of selects) {
                const options = Array.from(select.options);
                const targetOption = options.find(option => 
                    option.textContent.includes('MWC Barcelona 2025')
                );
                
                if (targetOption) {
                    select.value = targetOption.value;
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                    console.log('Selected MWC Barcelona 2025');
                    return;
                }
            }
        }""")
        
        # Wait for the filter to take effect
        await page.wait_for_timeout(1000)
        
        # First reset all filters to ensure clean state
        print("Resetting all filters before applying new ones...")
        
        # Clear the search field first (important)
        try:
            await page.fill('#find-attendees-search-bar', '')
            await page.press('#find-attendees-search-bar', 'Enter')
            await page.wait_for_timeout(500)
        except Exception as e:
            print(f"Error clearing search field: {e}")
        
        # Apply interest filter if provided
        if interest:
            await select_interest_filter(page, interest)
            await page.wait_for_timeout(1000)  # Wait after changing filters
        
        # Apply company activity filter if provided
        if company_activity:
            await select_company_activity_filter(page, company_activity)
            await page.wait_for_timeout(1000)  # Wait after changing filters
        
        # Apply the search filter LAST, after all other filters have been set
        filter_success = await set_search_filter(page, attendee_name)
        if not filter_success:
            print(f"Could not set search filter for '{attendee_name}'. Skipping this combination.")
            return 0
            
        # Process all pages for the search results
        page_num = 1
        
        while True:
            print(f"Processing search results for '{attendee_name}' with interest '{interest}' and company activity '{company_activity}', page {page_num}...")
            
            # Wait to stabilize content
            await page.wait_for_timeout(2000)  # Increased wait time
            
            # Extract attendee information
            print("Extracting attendee information...")
            attendees = await page.evaluate("""() => {
                const attendees = [];
                const attendeeItems = document.querySelectorAll('ul.flex.flex-wrap.items-left.my-4 > li');
                
                for (const item of attendeeItems) {
                    try {
                        // Get the main anchor element that contains attendee info
                        const mainAnchor = item.querySelector('a');
                        let profileUrl = 'N/A';
                        
                        // Extract the profile URL from the main anchor tag
                        if (mainAnchor && mainAnchor.hasAttribute('href')) {
                            const href = mainAnchor.getAttribute('href');
                            // Create absolute URL from relative path
                            profileUrl = new URL(href, window.location.origin).href;
                        }
                        
                        // Extract text elements within the anchor
                        const paragraphs = item.querySelectorAll('p');
                        
                        // Initialize with empty values
                        let name = 'N/A';
                        let jobTitle = 'N/A';
                        let company = 'N/A';
                        let event = 'N/A';
                        
                        // Extract name from the element with text-lg class
                        const nameEl = item.querySelector('p.text-lg.font-medium');
                        if (nameEl) name = nameEl.textContent.trim();
                        
                        // Get all paragraphs with font-medium class (typically contains job title)
                        const jobTitleEls = Array.from(item.querySelectorAll('p.font-medium'))
                            .filter(el => el !== nameEl && el.textContent.trim() !== '');
                        
                        if (jobTitleEls.length > 0) {
                            jobTitle = jobTitleEls[0].textContent.trim();
                        }
                        
                        // Company is usually in the p with style="overflow-wrap: anywhere;"
                        const companyEl = item.querySelector('p[style*="overflow-wrap"]');
                        if (companyEl) company = companyEl.textContent.trim();
                        
                        // Event is in the p with font-bold class
                        const eventEl = item.querySelector('p.font-bold');
                        if (eventEl) event = eventEl.textContent.trim();
                        
                        attendees.push({
                            name: name,
                            jobTitle: jobTitle,
                            company: company,
                            event: event,
                            profileUrl: profileUrl
                        });
                    } catch (e) {
                        console.error('Error processing attendee:', e);
                    }
                }
                
                return attendees;
            }""")
            
            print(f"Found {len(attendees)} attendees on page {page_num}")
            
            # Check if we have attendees
            if len(attendees) == 0:
                print(f"WARNING: No attendees found on this page!")
                print(f"Completed scraping for this combination - no results found!")
                return total_attendees
            
            # Write to CSV, skipping already processed URLs
            new_attendees_count = 0
            
            with open(output_file, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['Name', 'Job Title', 'Company', 'Event', 'Profile URL', 'Interest', 'Company Activity']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                for attendee in attendees:
                    # Instead of skipping, we'll just log that we've seen this person before
                    if attendee['profileUrl'] in processed_urls:
                        print(f"Note: {attendee['name']} was also found in previous combinations")
                    
                    # Debug log
                    print(f"Writing new attendee: {attendee['name']}")
                    
                    # Get human-readable names for the filters
                    interest_display = "N/A"
                    company_activity_display = "N/A"
                    
                    if interest:
                        # Try to get the text description if numeric value was provided
                        if interest.isdigit():
                            interest_display = await page.evaluate(f"""(interestId) => {{
                                const selects = Array.from(document.querySelectorAll('select'));
                                if (selects.length >= 2) {{
                                    const interestSelect = selects[1];
                                    const option = Array.from(interestSelect.options).find(opt => opt.value === interestId);
                                    return option ? option.textContent.trim() : interestId;
                                }}
                                return interestId;
                            }}""", interest)
                        else:
                            interest_display = interest
                    
                    if company_activity:
                        # Try to get the text description if numeric value was provided
                        if company_activity.isdigit():
                            company_activity_display = await page.evaluate(f"""(activityId) => {{
                                const selects = Array.from(document.querySelectorAll('select'));
                                if (selects.length >= 4) {{
                                    const activitySelect = selects[3];
                                    const option = Array.from(activitySelect.options).find(opt => opt.value === activityId);
                                    return option ? option.textContent.trim() : activityId;
                                }}
                                return activityId;
                            }}""", company_activity)
                        else:
                            company_activity_display = company_activity
                    
                    writer.writerow({
                        'Name': attendee['name'],
                        'Job Title': attendee['jobTitle'],
                        'Company': attendee['company'],
                        'Event': attendee['event'],
                        'Profile URL': attendee['profileUrl'],
                        'Interest': interest_display,
                        'Company Activity': company_activity_display
                    })
                    
                    processed_urls.add(attendee['profileUrl'])
                    new_attendees_count += 1
            
            total_attendees += new_attendees_count
            print(f"Added {new_attendees_count} new attendees on page {page_num}")
            
            # Check if there's a next page button and click it
            print("Checking for next page...")
            next_button_exists = await page.evaluate("""() => {
                const nextLinks = Array.from(document.querySelectorAll('a.underline.text-lg, a[href="#find-attendees-search-bar"]'))
                    .filter(a => a.textContent.trim() === 'Next');
                
                if (nextLinks.length > 0) {
                    nextLinks[0].click();
                    return true;
                }
                return false;
            }""")
            
            if next_button_exists:
                print(f"Navigating to next page...")
                await page.wait_for_timeout(2000)  # Increased wait time
                page_num += 1
            else:
                print(f"No 'Next' link found. Completed all pages for this combination.")
                print(f"Total attendees scraped for this combination: {total_attendees}")
                return total_attendees
                
    except Exception as e:
        print(f"Error during scraping combination: {e}")
        print(f"Continuing to next combination...")
        return total_attendees

async def run_all_combinations():
    """Run the scraper for all combinations from the input files"""
    
    # Read input files
    try:
        with open('letters.txt', 'r', encoding='utf-8') as f:
            letters = [line.strip() for line in f if line.strip()]
        
        with open('interests.txt', 'r', encoding='utf-8') as f:
            interests = [line.strip() for line in f if line.strip()]
        
        with open('company_activities.txt', 'r', encoding='utf-8') as f:
            company_activities = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading input files: {e}")
        create_exit_flag_file(error=True)
        return
    
    print(f"Loaded {len(letters)} letters, {len(interests)} interests, and {len(company_activities)} company activities")
    print(f"Total combinations to process: {len(letters) * len(interests) * len(company_activities)}")
    
    # Create a master CSV to track all combinations
    master_file = "mwc_scraper_master_log.csv"
    with open(master_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Letter', 'Interest', 'Company Activity', 'Output File', 'Attendees Found', 'Status', 'Timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
    
    # Track processed URLs to record duplicate findings, but we'll still add all entries
    processed_urls = set()
    
    # Load previously seen URLs from existing CSV files if any (for logging purposes only)
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv') and f != master_file]
    for csv_file in csv_files:
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'Profile URL' in row and row['Profile URL'] != 'N/A':
                        processed_urls.add(row['Profile URL'])
        except Exception as e:
            print(f"Error loading URLs from {csv_file}: {e}")
    
    print(f"Loaded {len(processed_urls)} previously seen URLs (will still add all attendees to new combinations)")
    
    # Keep track of completed combinations
    completed_combinations = []
    
    # Try to load completed combinations from log file if it exists
    if os.path.exists(master_file):
        try:
            with open(master_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['Status'] == 'Completed':
                        completed_combinations.append((row['Letter'], row['Interest'], row['Company Activity']))
        except Exception as e:
            print(f"Error loading completed combinations: {e}")
    
    print(f"Loaded {len(completed_combinations)} previously completed combinations")
    
    # Get login credentials from environment variables
    username = os.environ.get('MWC_USERNAME')
    password = os.environ.get('MWC_PASSWORD')
    
    # Check if credentials are available
    if not username or not password:
        print("ERROR: Login credentials not found in environment variables.")
        print("Please set MWC_USERNAME and MWC_PASSWORD environment variables.")
        create_exit_flag_file(error=True)
        return
    
    browser = None
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(viewport={'width': 1280, 'height': 900})
            page = await context.new_page()
            
            # Login using credentials from environment variables
            login_success = await login_to_mwc(page, username, password)
            
            if not login_success:
                print("Failed to login. Aborting.")
                if browser:
                    await browser.close()
                create_exit_flag_file(error=True)
                return
            
            # Process all combinations
            combination_count = 0
            total_combinations = len(letters) * len(interests) * len(company_activities)
            
            print("IMPORTANT: All attendees will be added to each combination's output file, even if they were found in previous runs.")
            
            for letter in letters:
                for interest in interests:
                    for company_activity in company_activities:
                        combination_count += 1
                        print(f"\n--- Processing combination {combination_count}/{total_combinations} ---")
                        print(f"Letter: '{letter}', Interest: '{interest}', Company Activity: '{company_activity}'")
                        
                        # Skip if already completed
                        if (letter, interest, company_activity) in completed_combinations:
                            print(f"Skipping already completed combination")
                            continue
                        
                        # Generate output filename for this combination
                        output_file = generate_output_filename(letter, interest, company_activity)
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                        
                        try:
                            # Update master log - Started
                            with open(master_file, 'a', newline='', encoding='utf-8') as csvfile:
                                fieldnames = ['Letter', 'Interest', 'Company Activity', 'Output File', 'Attendees Found', 'Status', 'Timestamp']
                                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                                writer.writerow({
                                    'Letter': letter,
                                    'Interest': interest,
                                    'Company Activity': company_activity,
                                    'Output File': output_file,
                                    'Attendees Found': 0,
                                    'Status': 'Started',
                                    'Timestamp': timestamp
                                })
                                
                            # Add delay before starting scraping to ensure page is ready
                            await page.wait_for_timeout(2000)
                            
                            # Run scraper for this combination
                            attendees_found = await scrape_combination(page, letter, interest, company_activity, processed_urls)
                            
                            # Update master log - Completed
                            with open(master_file, 'a', newline='', encoding='utf-8') as csvfile:
                                fieldnames = ['Letter', 'Interest', 'Company Activity', 'Output File', 'Attendees Found', 'Status', 'Timestamp']
                                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                                writer.writerow({
                                    'Letter': letter,
                                    'Interest': interest,
                                    'Company Activity': company_activity,
                                    'Output File': output_file,
                                    'Attendees Found': attendees_found,
                                    'Status': 'Completed',
                                    'Timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                                })
                            
                            # Add to completed combinations
                            completed_combinations.append((letter, interest, company_activity))
                            
                            # Important: Don't clear processed_urls between combinations
                            # We're just tracking them for informational purposes now
                            
                        except Exception as e:
                            print(f"Error processing combination: {e}")
                            
                            # Update master log - Error
                            with open(master_file, 'a', newline='', encoding='utf-8') as csvfile:
                                fieldnames = ['Letter', 'Interest', 'Company Activity', 'Output File', 'Attendees Found', 'Status', 'Timestamp']
                                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                                writer.writerow({
                                    'Letter': letter,
                                    'Interest': interest,
                                    'Company Activity': company_activity,
                                    'Output File': output_file,
                                    'Attendees Found': 0,
                                    'Status': f'Error: {str(e)[:100]}',
                                    'Timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                                })
                            
                            # Reload the page to recover from errors
                            try:
                                await page.goto("https://www.mwcbarcelona.com/mymwc/search", wait_until="networkidle")
                                await page.wait_for_timeout(3000)
                            except Exception as nav_error:
                                print(f"Error navigating after failure: {nav_error}")
                                # Try to create a new page if navigation fails
                                try:
                                    await page.close()
                                    page = await context.new_page()
                                    await page.goto("https://www.mwcbarcelona.com/mymwc/search", wait_until="networkidle")
                                    await page.wait_for_timeout(3000)
                                except Exception as new_page_error:
                                    print(f"Error creating new page: {new_page_error}")
                                    # Last resort - create a new context
                                    try:
                                        await context.close()
                                        context = await browser.new_context(viewport={'width': 1280, 'height': 900})
                                        page = await context.new_page()
                                        
                                        # Re-login if needed
                                        login_success = await login_to_mwc(page, username, password)
                                        
                                        if not login_success:
                                            print("Failed to re-login. Continuing to next combination...")
                                    except Exception as context_error:
                                        print(f"Fatal error recreating context: {context_error}")
                                        break
            
            print("\n--- Scraping Complete ---")
            print(f"Total combinations processed: {len(completed_combinations)}/{total_combinations}")
            print(f"Total URLs seen across all combinations: {len(processed_urls)}")
            print(f"Master log saved to: {master_file}")
            
            # Close the browser
            if browser:
                await browser.close()
                
            # Signal to the wrapper script to terminate with success
            print("Creating exit signal file...")
            create_exit_flag_file()
            print("Exit signal created. Exiting...")
    
    except Exception as e:
        print(f"Critical error during processing: {e}")
        if browser:
            try:
                await browser.close()
            except:
                pass
        # Signal to terminate with error
        print("Creating exit signal file due to error...")
        create_exit_flag_file(error=True)
        print("Exit signal created. Exiting...")
        return

# Main entry point
if __name__ == "__main__":
    # Add command line arguments
    parser = argparse.ArgumentParser(description='Scrape MWC Barcelona 2025 attendees for all combinations')
    parser.add_argument('--debug', action='store_true', help='Enable additional debug output')
    args = parser.parse_args()
    
    # Run the scraper with all combinations and handle any errors
    try:
        asyncio.run(run_all_combinations())
    except Exception as e:
        print(f"Unexpected error: {e}")
        # Signal to terminate with error
        create_exit_flag_file(error=True)