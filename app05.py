import random
import time
import os
import json
import cv2
import numpy as np
import pandas as pd
import easyocr
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from fpdf import FPDF

# Constants
URL = "https://www.cbe.org.eg/en/auctions/egp-t-bills"
USER_AGENTS_FILE = "user_agents.txt"
PROXY_FILE = "Free_Proxy_List.json"
CHROMEDRIVER_PATH = r"D:\Documents\OngoingProjects\GalaxyAgent\chromedriver-win64\chromedriver.exe"
FONT_PATH = r"D:\Documents\OngoingProjects\GalaxyAgent\DejaVuSans.ttf"  # Full path to the Unicode font file
SCREENSHOT_PATH = "full_page_screenshot.png"  # Path to save the full-page screenshot
PREVIOUS_SCREENSHOT_PATH = "previous_screenshot.png"  # Path to save the previous screenshot
FHD_RESOLUTION = (1920, 1080)  # FHD resolution
LOG_FILE = "error_log.txt"  # Path to the error log file
DB_FILE = "tables.db"  # SQLite3 database file
EMAIL = "your_email@gmail.com"  # Your Gmail address
EMAIL_PASSWORD = "your_email_password"  # Your Gmail password
RECIPIENT_EMAIL = "recipient_email@gmail.com"  # Recipient's email address

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

# Compare two images pixel by pixel
def compare_images(image1_path, image2_path):
    if not os.path.exists(image1_path) or not os.path.exists(image2_path):
        return True  # If either image doesn't exist, consider them different

    image1 = cv2.imread(image1_path)
    image2 = cv2.imread(image2_path)

    if image1 is None or image2 is None:
        return True  # If either image is corrupted, consider them different

    # Resize images to the same dimensions if they differ
    if image1.shape != image2.shape:
        height = min(image1.shape[0], image2.shape[0])
        width = min(image1.shape[1], image2.shape[1])
        image1 = cv2.resize(image1, (width, height))
        image2 = cv2.resize(image2, (width, height))

    difference = cv2.absdiff(image1, image2)
    non_zero_count = np.count_nonzero(difference)

    return non_zero_count > 0  # If there are non-zero differences, images are different

# Extract tables from the screenshot using EasyOCR
def extract_tables_to_dataframe(screenshot_path):
    # Load the screenshot
    image = cv2.imread(screenshot_path)

    # Initialize EasyOCR
    reader = easyocr.Reader(['en'])

    # Perform OCR
    results = reader.readtext(image)

    # Convert OCR results to a DataFrame
    data = []
    for (bbox, text, prob) in results:
        data.append(text)

    df = pd.DataFrame(data, columns=["Text"])
    return [df]  # Return a list of DataFrames for compatibility

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

# Send email with the PDF attachment
def send_email_with_pdf(pdf_path):
    msg = MIMEMultipart()
    msg['From'] = EMAIL
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = "Extracted Tables Report"

    with open(pdf_path, "rb") as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(pdf_path)}')
        msg.attach(part)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL, EMAIL_PASSWORD)
        server.sendmail(EMAIL, RECIPIENT_EMAIL, msg.as_string())
        server.quit()
        print("Email sent successfully.")
    except Exception as e:
        print(f"Error sending email: {e}")
        log_error(f"Error sending email: {e}")

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
                if compare_images(SCREENSHOT_PATH, PREVIOUS_SCREENSHOT_PATH):
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

                        # Send the PDF via email
                        send_email_with_pdf("report.pdf")
                    else:
                        print("No valid tables found.")
                else:
                    print("No changes detected in the screenshot.")
            else:
                print("No screenshot found.")
        except Exception as e:
            print(f"Error: {e}")
            log_error(f"Error with proxy {proxy}: {e}")

        # Save the current screenshot as the previous screenshot for the next comparison
        if os.path.exists(SCREENSHOT_PATH):
            os.replace(SCREENSHOT_PATH, PREVIOUS_SCREENSHOT_PATH)

        time.sleep(900)  # Wait 15 minutes

# Entry point
if __name__ == "__main__":
    main()