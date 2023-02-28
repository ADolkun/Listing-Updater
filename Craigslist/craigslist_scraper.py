import re
import requests
import os
import time
import json
import boto3
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

URL = 'https://sfbay.craigslist.org/search/bia?bicycle_type=10&bicycle_type=6&bundleDuplicates=1&condition=20&condition=30&condition=40&condition=50&hasPic=1&max_price=200&min_price=80&postal=94705&purveyor=owner&search_distance=50#search=1~gallery~0~0'

global DATA
DATA = ""

# Set up the Selenium web driver
# def load_page(self,url, page=None): 
#     # Set up the Selenium web driver
#     options = webdriver.ChromeOptions()
#     options.add_argument("--headless") # Run the browser in headless mode to avoid displaying the GUI
#     options.add_argument("--disable-dev-shm-usage") # Disable /dev/shm usage on Linux to prevent crashes
#     options.add_argument("--no-sandbox") # Disable sandbox mode to prevent crashes
#     with webdriver.Chrome(options=options) as driver:
#         page = driver.get(url)

# Use Selenium to scroll down the page until all the results are loaded
#def loadmore(self, driver)
# while True:
#     # Scroll down to the bottom of the page
#     driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
#     time.sleep(1)
    
#     # Check if there are more results to load
#     try:
#         load_more = driver.find_element(By.CLASS_NAME,"loadmore")
#         load_more.click()
#     except NoSuchElementException:
#         break

options = webdriver.ChromeOptions()
options.add_argument("--headless") # Run the browser in headless mode to avoid displaying the GUI
options.add_argument("--disable-dev-shm-usage") # Disable /dev/shm usage on Linux to prevent crashes
options.add_argument("--no-sandbox") # Disable sandbox mode to prevent crashes
driver = webdriver.Chrome(options=options)

page = driver.get(URL)

# Use Selenium to scroll down the page until all the results are loaded
while True:
    # Scroll down to the bottom of the page
    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
    time.sleep(1)
    
    # Check if there are more results to load
    try:
        load_more = driver.find_element(By.CLASS_NAME,"loadmore")
        load_more.click()
    except NoSuchElementException:
        break

# Retrieve the HTML content of the page after it has finished loading
html = driver.page_source

# get the page source and create a BeautifulSoup object
soup = BeautifulSoup(html, 'html.parser')
results = soup.find_all(class_='cl-search-result')
filter_words = ['kids', 'kid', 'children', 'child', 'boys', 'boy', 'girls', 'girl', 'youth', 'fold', 'folding', 'foldable']

#Generate email content by adding all elements as HTML
def generate_email_data(title, price, location, url):
    body = f"<h3>{title}</h3> <p><strong>Location: </strong>{location}</p> <p><strong>Price: </strong>{price}</p> <p><strong>URL: </strong><a href='{url}'>Click Here</a></p>"
    return body

def item_info(result):
    item_price = result.find("span", class_="priceinfo").text
    item_location = result.find("div", class_="meta").text.strip().split("·")[1].strip()
    item_url = result.find("a", class_="titlestring")["href"]
    return [item_price, item_location, item_url]

# Extract information & clean scraped data using filter
def clean_scrape(results, filter_words):
    global DATA
    count = 0
    
    #AWS information
    session = boto3.Session(aws_access_key_id = 'access_key', 
                            aws_secret_access_key='secret_key')
    s3 = session.resource('s3')
    bucket_name = 'craigslistb'
    filename = 'scraped_data.json'
    # Load existing data from S3 if exists
    try:
        obj = s3.Object(bucket_name, filename)
        existing_data = obj.get()['Body'].read().decode('utf-8')
        existing_dict = json.loads(existing_data)
    except:
        existing_dict = {}

    # Extract unique identifiers for each scraped item using item's title
    # Use these to check if a scraped item is new or updated
    item_identifiers = {}

    for result in results:
        item_results = item_info(result)

        item_title = result.find("a", class_="titlestring").text.strip()
        if any(words in item_title.lower() for words in filter_words):
            continue

        item_key = hashlib.md5(item_title.encode('utf-8')).hexdigest()
        item_identifiers[item_key] = item_title

    # Check if each item is new or updated
    for item_key, item_title in item_identifiers.items():
        if item_key not in existing_dict or existing_dict[item_key]['title'] != item_title:
            item_price, item_location, item_url = item_results[0], item_results[1], item_results[2]
            email_body = generate_email_data(item_title, item_price, item_location, item_url)
            existing_dict[item_key] = {'title': item_title, 'price': item_price, 'location': item_location, 'url': item_url}
            DATA += email_body

        count += 1
        # print(count, item_location, item_title, item_price, item_url)

    # Save the updated dictionary as a JSON file on S3
    s3.Object(bucket_name, filename).put(Body=json.dumps(existing_dict))

    print('\n\n\n\n' + str(len(results)))

#Check if an email is valid.
def is_valid_email(email) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def send_email(subject, sender, password, recipient):
    global DATA

    if is_valid_email(sender) and is_valid_email(recipient):
        my_email = sender
        my_password = password
        to_email = recipient

        SMTP_SERVER = 'smtp.gmail.com'
        SMTP_PORT = 587

        message = MIMEMultipart()
        message.attach(MIMEText(DATA, 'html'))
        message['From'] = my_email
        message['To'] = to_email
        message['Subject'] = subject

        # Log in to email server and send message
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(my_email, my_password)
            smtp.send_message(message)
    else:
        print("Invalid emails. Please check the given email addresses")

clean_scrape(results, filter_words)
send_email('Craigslist Scrape', '<sender email>','<sender password>', '<recipient email>')
driver.quit()