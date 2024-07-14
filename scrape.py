
import json
import requests
from flask import Flask
import threading
import re
import os
from bs4 import BeautifulSoup
import csv
import logging
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import schedule
import time

# Configuration
VALID_ENGINES = [
    "CFM56-3B1", "CFM56-3B2", "CFM56-3C1", "CFM56-5A1", "CFM56-5A3",
    "CFM56-5B1", "CFM56-5B3", "CFM56-5B4", "CFM56-5B5", "CFM56-5B6",
    "CFM56-5B7", "CFM56-7B20", "CFM56-7B22", "CFM56-7B24", "CFM56-7B26",
    "CFM56-7B27", "RB211-535E4", "PW2037", "PW2040", "CF6-50",
    "CF6-80A", "CF6-80C2", "CF6-80E1"
]

DESIRED_ENGINES = [
    # CFM56-7B Variations
    "CFM56-7B20", "CFM56-7B22", "CFM56-7B24", "CFM56-7B26", "CFM56-7B27",
    "CFM56-7B/20", "CFM56-7B/22", "CFM56-7B/24", "CFM56-7B/26", "CFM56-7B/27",
    "CFM567B",
    # CFM56-5B Variations
    "CFM56-5B1", "CFM56-5B2", "CFM56-5B3", "CFM56-5B4", "CFM56-5B5", "CFM56-5B6", "CFM56-5B7",
    "CFM56-5B/1", "CFM56-5B/2", "CFM56-5B/3", "CFM56-5B/4", "CFM56-5B/5", "CFM56-5B/6", "CFM56-5B/7",
    "CFM565B",
    # CF6-80C2B Variations
    "CF6-80C2B1", "CF6-80C2B2", "CF6-80C2B3", "CF6-80C2B4", "CF6-80C2B5", "CF6-80C2B6",
    "CF6-80C2B1F", "CF6-80C2B2F", "CF6-80C2B3F", "CF6-80C2B4F", "CF6-80C2B5F", "CF6-80C2B6F",
    "CF680C2B", "CF680C2"
]

CONDITION_PRIORITY = ["NS", "NE", "OH", "SV", "AR", "RP", "Mid-Life"]


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)
TIMEZONE = 'Africa/Khartoum'  # For Sudan time

@app.route('/')
def health_check():
    return "Scraper is running", 200

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Utility functions
def get_soup(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        html_content = response.text
        
        logging.info(f"Fetched {len(html_content)} characters from {url}")
        
        # with open('full_page_content.html', 'w', encoding='utf-8') as f:
        #     f.write(html_content)
        # logging.info(f"Full HTML content saved to full_page_content.html")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        if not soup.find('html'):
            logging.error("HTML tag not found in the parsed content")
        if not soup.find('body'):
            logging.error("Body tag not found in the parsed content")
        
        return soup
    except requests.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def get_condition_priority(condition):
    try:
        return CONDITION_PRIORITY.index(condition)
    except ValueError:
        return len(CONDITION_PRIORITY)  # Lowest priority if not in list

def standardize_engine_data(raw_data, source):
    standardized_data = {
        'Engine Mode': 'N/A',
        'Condition': 'N/A',
        'Thrust Rating': 'N/A',
        'TSN': 'N/A',
        'CSN': 'N/A',
        'TSO': 'N/A',
        'CSO': 'N/A',
        'Location': 'N/A',
        'Availability': 'N/A',
        'Documentation': 'N/A',
        'Last Shop Visit': 'N/A',
        'Price': 'N/A',
        'Contact Information': 'N/A',
        'Listing Source': source,
        'Listing Link': 'N/A',
        'Date Found': datetime.now().strftime("%Y-%m-%d"),
        'For Sale': 'Yes'
    }
    
    if source == 'Aeroconnect':
          standardized_data.update({
            'Engine Mode': raw_data.get('Engine Type', 'N/A'),
            'Condition': raw_data.get('Condition', 'N/A'),
            'Location': raw_data.get('Country Location', 'N/A'),
            'Availability': 'Now',
            'Contact Information': f"{raw_data.get('Contact', 'N/A')} - {raw_data.get('Phone', 'N/A')}",
            'Listing Link': raw_data.get('URL', 'N/A'),
            'For Sale': 'Yes'
        })
        
    elif source == 'Locatory':
             standardized_data.update({
            'Engine Mode': raw_data.get('Part Number', 'N/A'),
            'Condition': raw_data.get('Condition', 'N/A'),
            'Location': raw_data.get('Location', 'N/A'),
            'Availability': 'Now',
            'Contact Information': 'Contact through Locatory',
            'Listing Link': raw_data.get('Listing Link', 'N/A'),
            'For Sale': 'Yes'
        })
    elif source == 'MyAirTrade':
        standardized_data.update({
            'Engine Mode': raw_data.get('Model', 'N/A'),
            'Condition': raw_data.get('Condition', 'N/A'),
            'Location': raw_data.get('Location', 'N/A'),
            'Contact Information': f"{raw_data.get('Email', 'N/A')} - {raw_data.get('Phone', 'N/A')}",
            'Listing Link': raw_data.get('Listing Link', 'N/A'),
            'Availability': 'Now',  # Assuming all listed items are available now
        })
    
    return standardized_data
# Aeroconnect scraper functions
def is_engine_for_sale_and_available(row):
    tds = row.find_all('td')
    if len(tds) < 6:
        return False
    available_for = tds[4].text.strip()
    available_date = tds[5].text.strip()
    return available_for.lower() == 'sale' and available_date.lower() == 'now'

def extract_engine_links(soup):
    engine_links = []
    table = soup.find('table', id='engines_table')
    if table:
        rows = table.find('tbody').find_all('tr')
        for row in rows:
            if is_engine_for_sale_and_available(row):
                link = row.find('a', class_='vw_btn')
                if link and 'href' in link.attrs:
                    engine_links.append(link['href'])
    logging.info(f"Extracted {len(engine_links)} engine links for sale and available now")
    return engine_links

def get_owner_info(soup):
    owner_info = {}
    owner_section = soup.find('div', class_='elementor-widget-container', string=lambda t: t and 'Owner Info' in t)
    if owner_section:
        parent_section = owner_section.find_parent('section', class_='elementor-section')
        if parent_section:
            labels_column = parent_section.find('div', class_='line1')
            values_column = parent_section.find('div', class_='line2')
            if labels_column and values_column:
                labels = labels_column.find_all('div', class_='elementor-widget-container')
                values = values_column.find_all('div', class_='elementor-widget-container')
                for label, value in zip(labels, values):
                    key = label.text.strip()
                    if key in ['Phone', 'Additional Phone']:
                        phone_link = value.find('a')
                        val = phone_link['href'].replace('tel:', '') if phone_link and phone_link.has_attr('href') else value.text.strip()
                    else:
                        val = value.text.strip()
                    owner_info[key] = val
    return owner_info

def get_engine_description(soup):
    engine_description = {}
    description_section = soup.find('div', class_='elementor-widget-container', string=lambda t: t and 'Engine Description' in t)
    if description_section:
        parent_section = description_section.find_parent('section', class_='elementor-section')
        if parent_section:
            labels_column = parent_section.find('div', class_='line1')
            values_column = parent_section.find('div', class_='line2')
            if labels_column and values_column:
                labels = labels_column.find_all('div', class_='elementor-widget-container')
                values = values_column.find_all('div', class_='elementor-widget-container')
                for label, value in zip(labels, values):
                    key = label.text.strip()
                    val = value.text.strip()
                    if val:
                        engine_description[key] = val
    return engine_description

def get_engine_details(url):
    soup = get_soup(url)
    if not soup:
        return None
    engine_data = {}
    engine_data.update(get_owner_info(soup))
    engine_data.update(get_engine_description(soup))
    engine_data['Source'] = 'Aeroconnect'
    engine_data['URL'] = url
    return engine_data

def scrape_aeroconnect():
    base_url = "https://www.aeroconnect.com/listings-for-sale-or-lease/engines/cfm56-7b/"
    soup = get_soup(base_url)
    if not soup:
        return []
    engine_links = extract_engine_links(soup)
    standardized_data = []

    for link in engine_links:
        raw_data = get_engine_details(link)
        if raw_data:
            standardized_item = standardize_engine_data(raw_data, 'Aeroconnect')
            standardized_data.append(standardized_item)
    return standardized_data


def fetch_myairtrade_html(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logging.error(f"Error fetching MyAirTrade page: {e}")
        return None

def extract_json_from_html(html_content):
    pattern = r'var listings = (\[.*?\]);'
    match = re.search(pattern, html_content, re.DOTALL)
    if match:
        return match.group(1)
    else:
        logging.error("Could not find listings data in HTML")
        return None

def parse_listings_data(json_string):
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON data: {e}")
        return None

def get_myairtrade_data(url):
    html_content = fetch_myairtrade_html(url)
    if html_content:
        json_string = extract_json_from_html(html_content)
        if json_string:
            return parse_listings_data(json_string)
    return None

def extract_email(contcomm):
    email_match = re.search(r'mailto:(.*?)\?', contcomm)
    return email_match.group(1) if email_match else 'N/A'

def extract_phone(contcomm):
    phone_match = re.search(r'\|\s*(\+[\d\s-]+)', contcomm)
    return phone_match.group(1).strip() if phone_match else 'N/A'

def extract_location(contcomm):
    location_match = re.search(r'located in (.*?)(?:\<|$)', contcomm)
    return location_match.group(1).strip() if location_match else 'N/A'

def extract_condition(contcomm):
    condition_match = re.search(r'(Serviceable|As removed|Overhaul|New)', contcomm, re.IGNORECASE)
    return condition_match.group(1) if condition_match else 'N/A'


def process_myairtrade_listing(listing):
    model = listing['model']
    
    # Check if the engine model is in our desired list
    if not any(model.startswith(engine) for engine in DESIRED_ENGINES):
        return None

    email = extract_email(listing['contcomm'])
    phone = extract_phone(listing['contcomm'])
    location = extract_location(listing['contcomm'])
    condition = extract_condition(listing['contcomm'])

    # Format the availability date
    if listing['ad'] == 'IMM':
        availability = 'Now'
    else:
        try:
            # Assuming the original date is in YYMMDD format
            date_obj = datetime.strptime(listing['ad'], '%y%m%d')
            availability = date_obj.strftime('%d-%m-%Y')
        except ValueError:
            # If the date can't be parsed, use the original value
            availability = listing['ad']

    # Determine if the engine is for sale
    for_sale = 'Yes' if 'S' in listing['at'] else 'No'

    return {
        'Engine Mode': model,
        'Condition': condition,
        'Thrust Rating': 'N/A',
        'TSN': 'N/A',
        'CSN': 'N/A',
        'TSO': 'N/A',
        'CSO': 'N/A',
        'Location': location,
        'Availability': availability,
        'Documentation': 'N/A',
        'Last Shop Visit': 'N/A',
        'Price': 'N/A',
        'Contact Information': f"{email} - {phone}",
        'Phone': phone,
        'Listing Source': 'MyAirTrade',
        'Listing Link': "https://www.myairtrade.com/available/CFM56-7",
        'Date Found': datetime.now().strftime("%d-%m-%Y"),
        'For Sale': for_sale
    }
def scrape_myairtrade():
    url = "https://www.myairtrade.com/available/CFM56-7"
    raw_data = get_myairtrade_data(url)
    if not raw_data:
        logging.error("Failed to fetch MyAirTrade data")
        return []

    standardized_data = []
    for listing in raw_data:
        processed_listing = process_myairtrade_listing(listing)
        if processed_listing:  # Only add the listing if it's not None (i.e., if it passed the filter)
            standardized_data.append(processed_listing)

    logging.info(f"Scraped and standardized {len(standardized_data)} engine listings from MyAirTrade")
    return standardized_data

def scrape_locatory():
    url = "https://www.locatory.com/search/get-result?pn=cfm56&utm_id=&utm_source="
    logging.info(f"Fetching Locatory page: {url}")
    soup = get_soup(url)
    if not soup:
        logging.error("Failed to fetch Locatory page")
        return []

    results_div = soup.find('div', class_='results bg-white')
    if not results_div:
        logging.error("Could not find results div")
        return []

    items = results_div.findChildren("div", class_="grid")
    logging.info(f"Found {len(items)} items on Locatory page")
    
    raw_data = []
    for item in items:
        try:
            # Find the details link
            details_link = item.findChild('a', class_='pointer-events-none')
            
            if not details_link:
                logging.warning("Could not find details link")
                continue
            
            link_url = details_link.get('href', '')
            print("##########################")
            print(link_url)
            print("#######################")
            
            part_number_div = item.find('div', class_='text-grey-1')
            if not part_number_div:
                logging.warning("Could not find part number div")
                continue
            part_number = part_number_div.text.strip().split('#')[-1].strip()
            logging.info(f"Processing part number: {part_number}")
            
            if any(engine in part_number for engine in VALID_ENGINES):
                title_div = item.find('div', class_='text-body-2-mob')
                title = title_div.text.strip() if title_div else "N/A"
                
                info_divs = item.find_all('div', class_='flex xl:flex-col flex-row gap-1 justify-between space-y-2')
                location = condition = quantity = "N/A"
                
                for div in info_divs:
                    label_div = div.find('div', class_=lambda x: x and 'text-grey-1' in x and 'text-body-5-mob' in x)
                    value_div = div.find('div', class_='text-body-4-mob')
                    
                    if label_div and value_div:
                        label = label_div.text.strip()
                        value = value_div.text.strip()
                        
                        if 'Location' in label:
                            location = value
                        elif 'Condition' in label:
                            condition = value
                        elif 'Qty' in label:
                            quantity = value

                raw_data.append({
                    'Part Number': part_number,
                    'Title': title,
                    'Location': location,
                    'Condition': condition,
                    'Quantity': quantity,
                    'Listing Link': link_url  # Add the details link to the raw data
                })
                logging.info(f"Added engine data for part number {part_number}")
            else:
                logging.info(f"Part number {part_number} not in valid engines list")
        except Exception as e:
            logging.error(f"Error processing item: {e}")

    standardized_data = [standardize_engine_data(item, 'Locatory') for item in raw_data]
    logging.info(f"Scraped and standardized {len(standardized_data)} engine listings from Locatory")
    return standardized_data

# Export function
def export_to_csv(data, filename):
    if not data:
        logging.warning("No data to export")
        return

    fieldnames = [
        'Engine Mode', 'Condition', 'Thrust Rating', 'TSN', 'CSN', 'TSO', 'CSO',
        'Location', 'Availability', 'Documentation', 'Last Shop Visit', 'Price',
        'Contact Information', 'Phone', 'Contact', 'Listing Link', 'Listing Source',
        'Date Found', 'For Sale'
    ]

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for item in data:
            writer.writerow({k: item.get(k, 'N/A') for k in fieldnames})

    logging.info(f"Data exported to {filename}") 

RECIPIENT_EMAILS = [
    "momendaoud07@gmail.com",
    "momenfbi123@gmail.com",
    "Ahmed@impoweredlab.com"
]   

def send_email_notification(html_content, attachment_filename=None):
    # Email configuration
    sender_email = "impoweredlab@gmail.com"  # Replace with your Gmail address
    receiver_email = "momenfbi123@gmail.com"  # Replace with the procurement team's email
    password = "yicc hbck atdu dlkm"  # Replace with your Gmail app password

    # Create message
    message = MIMEMultipart("mixed")
    message["Subject"] = f"Engine Scrape Results"
    message["From"] = sender_email
    message["To"] = ", ".join(RECIPIENT_EMAILS)  # Join all recipients with commas

    # Attach HTML content
    html_part = MIMEText(html_content, "html")
    message.attach(html_part)

    # Attach CSV file if provided
    if attachment_filename and os.path.exists(attachment_filename):
        with open(attachment_filename, "rb") as file:
            part = MIMEApplication(file.read(), Name=os.path.basename(attachment_filename))
        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_filename)}"'
        message.attach(part)

    # Create secure connection with server and send email
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender_email, password)
        server.sendmail(sender_email, RECIPIENT_EMAILS, message.as_string())
        server.close()
        logging.info("Email notification sent successfully to all recipients!")
        if attachment_filename:
            logging.info(f"CSV file '{attachment_filename}' was attached to the email.")
        else:
            logging.info("No CSV file was attached to the email.")
    except Exception as e:
        logging.error(f"Error sending email notification: {e}")

# send_email_notification(email_content, filename if new_engines else None)

import json
import os
from datetime import datetime

STORAGE_FILE = 'engine_data_storage.json'

def generate_unique_id(engine):
    # Combine multiple fields to create a unique identifier
    unique_fields = [
        engine.get('Engine Mode', ''),
        engine.get('ESN', ''),  # If available
        engine.get('Location', ''),
        engine.get('Contact', ''),
        engine.get('Listing Source', ''),
        engine.get('Condition', '')
    ]
    return '_'.join(str(field) for field in unique_fields if field)

def save_data(data):
    with open(STORAGE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_data():
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, 'r') as f:
            return json.load(f)
    return {}

def compare_and_update(new_data):
    stored_data = load_data()
    
    # Convert to sets for easy comparison
    new_ids = set(generate_unique_id(engine) for engine in new_data)
    stored_ids = set(stored_data.keys())
    
    # Identify new and removed engines
    new_engine_ids = new_ids - stored_ids
    removed_engine_ids = stored_ids - new_ids
    
    # Prepare updates
    updates = {
        'Aeroconnect': [],
        'Locatory': [],
        'MyAirTrade': []
    }
    
    # Process new engines
    for engine in new_data:
        unique_id = generate_unique_id(engine)
        if unique_id in new_engine_ids:
            updates[engine['Listing Source']].append(engine)
    
    # Update stored data
    new_stored_data = {generate_unique_id(engine): engine for engine in new_data}
    save_data(new_stored_data)
    
    return updates, list(removed_engine_ids)

import schedule
import time
from datetime import datetime
import logging

# Import your existing functions here
# from your_module import scrape_aeroconnect, scrape_locatory, scrape_myairtrade, compare_and_update, export_to_csv, send_email_notification

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
def get_color_coded_status(source, count):
    if count > 0:
        return f'<span style="color: green;">{source}: Status: Update; {count} new engines</span>'
    else:
        return f'<span style="color: red;">{source}: Status: No updates; 0 new engines</span>'

def get_update_summary(updates, removed_count):
    summary = []
    for source, engines in updates.items():
        summary.append(get_color_coded_status(source, len(engines)))
    
    summary.append(f"Removed: {removed_count} engines removed")
    return summary

def run_scraper():
    logging.info("Starting engine data scraping...")
    
    all_engine_data = []
    
    aeroconnect_data = scrape_aeroconnect()
    all_engine_data.extend(aeroconnect_data)
    
    locatory_data = scrape_locatory()
    all_engine_data.extend(locatory_data)
    
    myairtrade_data = scrape_myairtrade()
    all_engine_data.extend(myairtrade_data)
    
    if all_engine_data:
        updates, removed_engines = compare_and_update(all_engine_data)
        summary = get_update_summary(updates, len(removed_engines))
        
        # Prepare email content
        email_content = "<h2>Engine Scrape Results:</h2><ul>"
        for status in summary:
            email_content += f"<li>{status}</li>"
        email_content += f"</ul><p>Scrape Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        
        # Prepare CSV with only new engines
        new_engines = [engine for engines in updates.values() for engine in engines]
        if new_engines:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"new_engines_{timestamp}.csv"
            export_to_csv(new_engines, filename)
            
            try:
                # Send email with attachment
                send_email_notification(email_content, filename)
            finally:
                # Delete the CSV file, regardless of whether the email was sent successfully
                if os.path.exists(filename):
                    os.remove(filename)
                    logging.info(f"Deleted CSV file: {filename}")
                else:
                    logging.warning(f"CSV file not found for deletion: {filename}")
        else:
            # Send email without attachment
            send_email_notification(email_content)
        
        logging.info(f"Scrape completed. {len(new_engines)} new engines found, {len(removed_engines)} engines removed.")
    else:
        logging.warning("No engine data scraped from any source")

    logging.info("Scraping process completed")

def schedule_scraper(run_times):
    schedule.clear()

    for run_time in run_times:
        schedule.every().day.at(run_time).do(run_scraper)
        logging.info(f"Scheduled scraping for {run_time}")

if __name__ == "__main__":
     # Start the Flask app in a separate thread
    threading.Thread(target=run_flask, daemon=True).start()

    run_times = ["04:00","18:50"]  # Example: Run twice a day at 8 AM and 8 PM
    
    schedule_scraper(run_times)
    
    logging.info("Scraper scheduled. Running continuously...")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute