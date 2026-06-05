import random
import time
import os
import json
import cv2
import numpy as np
import pandas as pd
import pytesseract
import sqlite3
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from fpdf import FPDF

# Set the path to the Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Constants
URL = "https://www.cbe.org.eg/en/auctions/egp-t-bills"
USER_AGENTS_FILE = "user_agents.txt"
PROXY_FILE = "Free_Proxy_List.json"
CHROMEDRIVER_PATH = "D:\\Documents\\OngoingProjects\\GalaxyAgent\\chromedriver-win64\\chromedriver.exe"
FONT_PATH = "D:\\Documents\\OngoingProjects\\GalaxyAgent\\DejaVuSans.ttf"  # Full path to the Unicode font file
SCREENSHOT_PATH = "full_page_screenshot.png"  # Path to save the full-page screenshot
FHD_RESOLUTION = (1920, 1080)  # FHD resolution
LOG_FILE = "error_log.txt"  # Path to the error log file
TABLE_OUTPUT_DIR = "extracted_tables"  # Directory to save extracted tables
DB_FILE = "systematic.sqlite3"  # SQLite3 database file

# Load user agents from file
def load_user_agents():
    with open(USER_AGENTS_FILE, "r") as f:
        user_agents = f.read().splitlines()
    return user_agents

# Load proxies from JSON file
def load_proxies():
    with open(PROXY_FILE, "r") as f:
        proxies = json.load(f)
    return proxies

# Choose a random user agent
def get_random_user_agent(user_agents):
    return random.choice(user_agents)

# Choose a random proxy
def get_random_proxy(proxies):
    return random.choice(proxies)

# Log errors to a file
def log_error(error_message):
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.ctime()}: {error_message}\n")

# Take a full-page screenshot using Selenium
def take_full_page_screenshot(url, user_agent, proxy):
    chrome_options = Options()
    chrome_options.add_argument(f"user-agent={user_agent}")
    chrome_options.add_argument(f"--proxy-server={proxy}")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument(f"--window-size={FHD_RESOLUTION[0]},{FHD_RESOLUTION[1]}")

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(url)
        time.sleep(10)  # Wait for JavaScript to load

        # Scroll and take a full-page screenshot
        total_height = driver.execute_script("return document.body.scrollHeight")
        driver.set_window_size(FHD_RESOLUTION[0], total_height)
        driver.save_screenshot(SCREENSHOT_PATH)

    except Exception as e:
        log_error(f"Error with proxy {proxy}: {e}")
        raise e
    finally:
        driver.quit()

# Validate that each table has exactly 5 rows
def validate_table_rows(table):
    # Count the number of rows in the table
    rows = table.strip().split("\n")
    return len(rows) == 5

# Extract tables from the screenshot using OpenCV and Tesseract OCR
def extract_tables_to_dataframe(screenshot_path):
    # Load the screenshot
    image = cv2.imread(screenshot_path)

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply binary thresholding
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

    # Detect horizontal and vertical lines
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))

    horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2)

    # Combine horizontal and vertical lines
    table_mask = cv2.add(horizontal_lines, vertical_lines)

    # Find contours of the tables
    contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Extract and process tables
    dataframes = []
    for i, contour in enumerate(contours):
        x, y, w, h = cv2.boundingRect(contour)
        if w * h > 10000:  # Filter out small contours
            table = image[y:y+h, x:x+w]

            # Use Tesseract OCR to extract text from the table
            table_text = pytesseract.image_to_string(table, config="--psm 6")

            # Validate that the table has exactly 5 rows
            if validate_table_rows(table_text):
                # Convert the text into a Pandas DataFrame
                rows = table_text.strip().split("\n")
                table_data = [row.split() for row in rows]
                df = pd.DataFrame(table_data)

                dataframes.append(df)
            else:
                print(f"Table {i+1} does not have exactly 5 rows. Skipping.")

    return dataframes

# Save DataFrames to SQLite3 database
def save_dataframes_to_sqlite(dataframes):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    for i, df in enumerate(dataframes):
        table_name = f"table_{i+1}"
        df.to_sql(table_name, conn, if_exists="replace", index=False)

    conn.commit()
    conn.close()

# Generate PDF with the extracted tables
def generate_pdf_with_tables(dataframes, output_file="report.pdf"):
    pdf = FPDF()
    pdf.add_page()

    # Add a Unicode font
    pdf.add_font("DejaVuSans", "", FONT_PATH, uni=True)
    pdf.set_font("DejaVuSans", size=12)

    # Add the extracted tables to the PDF
    for df in dataframes:
        pdf.cell(200, 10, txt=df.to_string(), ln=True)
        pdf.ln(10)  # Add space between tables

    pdf.output(output_file)

# Main pipeline
def main():
    user_agents = load_user_agents()
    proxies = load_proxies()

    while True:
        current_time = time.localtime()
        if not (current_time.tm_hour >= 1):  # Start at 1 AM
            print("Script is only active from 1 AM onwards.")
            time.sleep(900)  # Wait 15 minutes
            continue

        user_agent = get_random_user_agent(user_agents)
        proxy = get_random_proxy(proxies)

        try:
            print(f"Fetching page using user-agent: {user_agent} and proxy: {proxy}")
            take_full_page_screenshot(URL, user_agent, proxy)

            if os.path.exists(SCREENSHOT_PATH):
                # Extract tables and convert them to DataFrames
                dataframes = extract_tables_to_dataframe(SCREENSHOT_PATH)
                print(f"Extracted {len(dataframes)} tables from the screenshot.")

                if dataframes:
                    # Save DataFrames to SQLite3 database
                    save_dataframes_to_sqlite(dataframes)
                    print(f"Tables saved to SQLite3 database '{DB_FILE}'.")

                    # Generate PDF with the extracted tables
                    generate_pdf_with_tables(dataframes)
                    print(f"Report generated and saved as 'report.pdf'.")
                else:
                    print("No valid tables found.")
            else:
                print("No screenshot found.")
        except Exception as e:
            print(f"Error: {e}")
            log_error(f"Error with proxy {proxy}: {e}")

        time.sleep(900)  # Wait 15 minutes

# Entry point
if __name__ == "__main__":
    main()