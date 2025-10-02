import time
import csv
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options

def setup_driver():
    """Setup Chrome driver with options"""
    chrome_options = Options()
    # Uncomment the line below to run in headless mode (no browser window)
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.maximize_window()
    return driver

def extract_submitted_count(count_text):
    """Extract the current submitted count from text like '125/500'"""
    try:
        if '/' in count_text:
            parts = count_text.split('/')
            current = int(parts[0].strip())
            total = int(parts[1].strip())
            # Return current count and whether it's full
            return current, (current >= total)
        return 0, False
    except:
        return 0, False

def wait_for_table_refresh(driver):
    """Wait for the table to refresh after pagination"""
    try:
        # Wait for any loading overlay to disappear
        WebDriverWait(driver, 10).until_not(
            EC.presence_of_element_located((By.CLASS_NAME, "dataTables_processing"))
        )
        time.sleep(1)  # Additional wait for stability
    except:
        pass

def scrape_current_page(driver):
    """Scrape all problem statements from the current page"""
    problem_statements = []
    
    try:
        # Try both possible table IDs
        table = None
        try:
            # First try with dataTablePS
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table#dataTablePS tbody tr"))
            )
            table = driver.find_element(By.ID, "dataTablePS")
            print("Found table with ID: dataTablePS")
        except:
            # If that fails, try with dataTable
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table#dataTable tbody tr"))
                )
                table = driver.find_element(By.ID, "dataTable")
                print("Found table with ID: dataTable")
            except:
                # Try finding any table with datatable class
                tables = driver.find_elements(By.CSS_SELECTOR, "table.dataTable")
                if tables:
                    table = tables[0]
                    print(f"Found table with class dataTable")
        
        if not table:
            print("Could not find data table")
            return problem_statements
        
        # Wait a bit for complete loading
        time.sleep(2)
        
        # Find all rows in tbody
        rows = table.find_elements(By.CSS_SELECTOR, "tbody tr[role='row']")
        
        print(f"Found {len(rows)} rows on this page")
        
        for row in rows:
            try:
                # Get all cells in the row
                cells = row.find_elements(By.TAG_NAME, "td")
                
                if len(cells) >= 6:  # Ensure we have enough cells
                    # Clean and extract data from each cell
                    row_data = []
                    
                    # Extract text from each cell, handling the specific structure
                    for i, cell in enumerate(cells):
                        cell_text = cell.text.strip()
                        if cell_text and cell_text not in ['…', '...', '']:
                            row_data.append(cell_text)
                    
                    # Check if we have the expected number of columns (should be around 8-9)
                    if len(row_data) >= 6:
                        # Find the submitted count (should be in format XXX/500 or XXX/1000)
                        submitted_text = ""
                        submitted_index = -1
                        
                        for idx, data in enumerate(row_data):
                            if '/' in data and ('500' in data or '1000' in data):  # Some might have different totals
                                submitted_text = data
                                submitted_index = idx
                                break
                        
                        if submitted_text:
                            current_count, is_full = extract_submitted_count(submitted_text)
                            # Only add if less than 200 submissions AND category is Software
                            if current_count < 200 and row_data[3].strip().lower() == "software":
                                print(f"Found Software PS with {current_count} submissions (below 200): {row_data[4] if len(row_data) > 4 else 'Unknown'}")
                                problem_statements.append(row_data)
                
            except Exception as e:
                print(f"Error processing row: {e}")
                continue
    
    except TimeoutException:
        print("Timeout waiting for table to load")
    except Exception as e:
        print(f"Error scraping current page: {e}")
    
    return problem_statements

def click_next_page(driver):
    """Click the next page button. Returns False if no more pages are available."""
    try:
        # Small wait to let pagination render
        time.sleep(1)

        # Debug info
        try:
            all_buttons = driver.find_elements(By.CSS_SELECTOR, "li.paginate_button")
            print(f"Found {len(all_buttons)} pagination buttons")
        except:
            pass

        try:
            next_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "dataTable_next"))
            )
            print("Found Next button element")

            # 🔑 Key Fix: Always check if it's disabled
            classes = next_button.get_attribute("class") or ""
            print(f"Next button classes: {classes}")
            if "disabled" in classes:
                print("Next button is disabled - reached last page")
                return False

            # Scroll into view
            driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
            time.sleep(1)

            # Method 1: Anchor tag inside the LI
            try:
                next_link = next_button.find_element(By.TAG_NAME, "a")
                print("Found anchor tag inside Next button")
                driver.execute_script("arguments[0].click();", next_link)
                print("Successfully clicked Next button")
                time.sleep(3)
                return True
            except Exception as e:
                print(f"Could not click anchor tag: {e}")

            # Method 2: XPath
            try:
                next_link = driver.find_element(By.XPATH, "//li[@id='dataTable_next']/a")
                parent = next_link.find_element(By.XPATH, "..")
                if "disabled" in parent.get_attribute("class"):
                    print("Next button is disabled - reached last page")
                    return False
                driver.execute_script("arguments[0].click();", next_link)
                print("Successfully clicked Next button using XPath")
                time.sleep(3)
                return True
            except Exception as e2:
                print(f"XPath method failed: {e2}")

            # Method 3: Direct click LI (double-check class again just in case)
            if "disabled" in next_button.get_attribute("class"):
                print("Next button is disabled - reached last page")
                return False
            driver.execute_script("arguments[0].click();", next_button)
            print("Clicked li element directly")
            time.sleep(3)
            return True

        except TimeoutException:
            print("Timeout waiting for Next button")

            # Alternative: Link text
            try:
                next_link = driver.find_element(By.LINK_TEXT, "Next")
                parent = next_link.find_element(By.XPATH, "..")
                if "disabled" in parent.get_attribute("class"):
                    print("Next button is disabled - reached last page")
                    return False
                driver.execute_script("arguments[0].click();", next_link)
                print("Clicked Next using link text")
                time.sleep(3)
                return True
            except:
                print("Could not find Next link by text")

            # Last resort: CSS selector
            try:
                next_link = driver.find_element(By.CSS_SELECTOR, "a.page-link[aria-controls='dataTable']")
                parent = next_link.find_element(By.XPATH, "..")
                if "disabled" in parent.get_attribute("class"):
                    print("Next button is disabled - reached last page")
                    return False
                driver.execute_script("arguments[0].click();", next_link)
                print("Clicked Next using CSS selector")
                time.sleep(3)
                return True
            except:
                print("CSS selector method failed")

        except Exception as e:
            print(f"Error finding Next button: {e}")

        return False

    except Exception as e:
        print(f"Error in click_next_page: {e}")
        import traceback
        traceback.print_exc()
        return False
    
def get_clean_headers():
    """Return clean headers for the CSV"""
    return [
        'S.No.',
        'Organization',
        'Problem Statement Title',
        'Category',
        'PS Number',
        'Submitted Idea(s) Count',
        'Theme',
        'Deadline for Idea Submission'
    ]

def get_pagination_info(driver):
    """Get current pagination information"""
    try:
        info_element = driver.find_element(By.CSS_SELECTOR, ".dataTables_info")
        info_text = info_element.text
        print(f"Current page info: {info_text}")
        
        # Extract the total number of entries and current position
        match = re.search(r'Showing (\d+) to (\d+) of (\d+) entries', info_text)
        if match:
            start = int(match.group(1))
            end = int(match.group(2))
            total_entries = int(match.group(3))
            print(f"Entries: {start}-{end} of {total_entries}")
            return info_text, total_entries, end
        
        # Alternative pattern
        match = re.search(r'of (\d+) entries', info_text)
        if match:
            total_entries = int(match.group(1))
            print(f"Total entries: {total_entries}")
            return info_text, total_entries, 0
        
        return info_text, 0, 0
    except Exception as e:
        print(f"Error getting pagination info: {e}")
        return "", 0, 0

def main():
    """Main function to orchestrate the scraping"""
    url = "https://sih.gov.in/sih2025PS"
    
    print("Starting SIH Problem Statement Scraper...")
    print("=" * 50)
    print("Looking for problem statements with < 200 submissions")  # CHANGED HERE
    print("=" * 50)
    
    # Setup driver
    driver = setup_driver()
    
    try:
        # Navigate to the website
        print(f"Navigating to {url}")
        driver.get(url)
        
        # Wait for initial page load
        print("Waiting for page to load...")
        time.sleep(5)
        
        # Try to set the table to show more entries per page
        try:
            # Look for the dropdown to show more entries
            length_selector = driver.find_element(By.NAME, "dataTablePS_length")
            from selenium.webdriver.support.ui import Select
            select = Select(length_selector)
            select.select_by_value("100")  # Show 100 entries per page
            time.sleep(2)
            print("Set to show 100 entries per page")
        except:
            print("Could not change entries per page setting")
        
        all_problem_statements = []
        page_count = 1
        last_end_position = 0
        consecutive_failures = 0
        
        # Increased limit to ensure we get all pages
        while page_count <= 20:  # CHANGED HERE - increased from 10 to 20
            print(f"\n{'='*50}")
            print(f"Scraping page {page_count}...")
            print("-" * 30)
            
            # Get pagination info
            info, total, current_end = get_pagination_info(driver)
            
            # Check if we've reached all entries
            if total > 0 and current_end >= total:
                print(f"Reached all {total} entries")
                # Still scrape this last page
                current_ps = scrape_current_page(driver)
                if current_ps:
                    all_problem_statements.extend(current_ps)
                    print(f"Found {len(current_ps)} problem statements with < 200 submissions on this page")
                break
            
            # Check if we're stuck on the same position
            if current_end > 0 and current_end == last_end_position:
                consecutive_failures += 1
                print(f"No progress in pagination (attempt {consecutive_failures}), trying once more...")
                if consecutive_failures >= 3:
                    print("Failed to progress after 3 attempts, stopping...")
                    break
            else:
                consecutive_failures = 0
            
            last_end_position = current_end
            
            # Scrape current page
            current_ps = scrape_current_page(driver)
            
            if current_ps:
                all_problem_statements.extend(current_ps)
                print(f"Found {len(current_ps)} problem statements with < 200 submissions on this page")  # CHANGED HERE
                print(f"Total found so far: {len(all_problem_statements)}")
            else:
                print("No problem statements with < 200 submissions on this page")  # CHANGED HERE
            
            # Try to go to next page
            if not click_next_page(driver):
                print("\nReached the last page or unable to navigate further")
                break
            
            page_count += 1
            
            # Add a small delay to avoid overwhelming the server
            time.sleep(1)
        
        # Save to CSV
        if all_problem_statements:
            csv_filename = "sih_problem_statements_under_200.csv"  # CHANGED HERE
            
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write headers
                writer.writerow(get_clean_headers())
                
                # Write data
                for ps in all_problem_statements:
                    # Ensure we have exactly 8 columns
                    while len(ps) < 8:
                        ps.append('')
                    writer.writerow(ps[:8])  # Take only first 8 columns
            
            print(f"\n{'=' * 50}")
            print(f"Scraping completed successfully!")
            print(f"Total problem statements found with < 200 submissions: {len(all_problem_statements)}")  # CHANGED HERE
            print(f"Data saved to: {csv_filename}")
            print("=" * 50)
        else:
            print("\nNo problem statements found with submissions less than 200")  # CHANGED HERE
    
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Wait before closing
        input("\nPress Enter to close the browser...")
        # Close the driver
        driver.quit()
        print("Driver closed.")

if __name__ == "__main__":
    main()
