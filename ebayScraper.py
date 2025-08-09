import logging, threading, telebot, requests, time, sqlite3, re, pandas as pd, numpy as np
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from time import sleep
from datetime import datetime as dt
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(asctime)s - %(message)s", datefmt="%H:%M:%S")



# --- Configure Selenium
options = Options()

# --- Configure Database
db = sqlite3.connect('', check_same_thread=False)
cur = db.cursor()










class Scraper:
    def __init__(self, item):
        self.START = time.time()
        self.END = 0
        self.item = item.replace(' ', '-')
        self.numResults = None
        self.df = None
        self.userID = None
        self.userItem = item
        
    def total_price(self, x):
        """Retrieves both Item & Postage Price (by £) and returns total"""
        prices = [float(i) for i in re.findall(r'£(\d+\.+\d*)', x)]
        return np.round(sum(prices), 2)
    
    def convert_into_hours(self, x):
        """If exist, return time left in minutes"""
        minutes = 0
        try:
            x = x.split('\n')
            timeLeft = x[x.index('Time left') +1]
            for i in ['d', 'h', 'm']:
                a = re.findall(f'(\d+){i}', timeLeft)  # Looks for numbers before d,h,m
                if i == 'd' and a:
                    minutes += int(a[0]) * 24 * 60
                if i == 'h' and a:
                    minutes += int(a[0]) * 60
                if i == 'm' and a:
                    minutes += int(a[0])
            return minutes 
        except ValueError:  # Only interested where Time left exists
            return None

    def item_Scraper(self, glance, dbIngest):
        """Scrape item metadata"""
        driver = webdriver.Firefox(options=options)
        driver.get('https://www.ebay.co.uk/sch/i.html?_nkw={}'.format(self.item))
        logging.info(f'{self.item} succesfully searched')
        
        nums = (driver.find_elements(By.CLASS_NAME, 'srp-controls__count-heading'))[0].text        
        self.numResults = int(re.findall(r'(\d+) results', nums)[0])  # -- Number of relevant results (Stored in Class)  
        data = [s.text for s in driver.find_elements(By.CLASS_NAME, 's-item')]  # Item details
        links = [s.get_attribute('href') for s in driver.find_elements(By.CLASS_NAME, 's-item__link')]  # Item hyperlinks
        driver.quit()
        logging.info(f'{self.item} metadata retrieved')
        
        self.END = time.time() - self.START
        if glance:
            logging.info(f'{self.item} metadata manipulation beginning ...')
            self.item_manipulation(data, links, dbIngest)  # --- Allows for scraperCall without adding to
        return self
        
        
    def item_manipulation(self, data, links, dbIngest):
        """Clean retreived data"""
        df = pd.DataFrame({'Metadata':data, 'Hyperlink':links})
        df['Type'] = np.select([df['Metadata'].str.lower().str.contains('buy it now'), df['Metadata'].str.lower().str.contains('time left'), df['Metadata'].str.lower().str.contains('best offer')], ['buy it now', 'auction', 'buy it now'], None)
        df['Item_ID'] = df['Hyperlink'].apply(lambda x: int(re.findall(r'itm/(\d+)', x)[0]) if x else None)
        df['Name'] = df['Metadata'].apply(lambda x: x.split('\n')[0] if x else None)
        df['Minutes'] = df['Metadata'].apply(self.convert_into_hours)
        df['Price'] = df['Metadata'].apply(self.total_price)
        df['shortLink'] = df['Item_ID'].apply(lambda x: 'https://www.ebay.co.uk/itm/{}'.format(x))
        df['Status'] = 1
        df['userID'] = self.userID
        df['userItem'] = self.userItem

                
        if self.numResults < len(df):  # First two always seem to be irrelevant
            df = df[2:(2+self.numResults)]
        else:
            df = df[2:]
        self.df = df
        self.END = time.time() - self.START
        logging.info(f'{self.item} metadata manipulation complete')
        
        if dbIngest:
            logging.info(f'{self.item} database ingestion beginning ...')
            self.ingestion()
        
    def ingestion(self):
        cur.execute("UPDATE TRACKED_LIST SET Status=0 WHERE userID=? AND userItem=?", (self.userID, self.userItem))
        db.commit()  # -- Set existing Status=0, as they'll be overwritten for stillActive
        
        toIngest = [tuple(row) for row in self.df[['userID','userItem','Name','Item_ID','Type','Minutes','Price','Hyperlink','shortLink','Metadata','Status']].values]
        cur.executemany("INSERT OR REPLACE INTO TRACKED_LIST (userID, userItem, Name, Item_ID, Type, Minutes, Price, Hyperlink, shortLink, Metadata, Status) VALUES (?,?,?,?,?,?,?,?,?,?,?)", toIngest)
        db.commit()  # --- Batch insert all newlyTracked
        
        logging.info('Data Ingested')        










response = #sys.argv[1]
vals = {'Type1':[3], 'Type2':[0,1,2], 'Type3':[3], 'Type4':[2], 'Type5':[3]}.get(response)
toScrape = cur.execute(f"SELECT * FROM TRACKED_ITEMS WHERE Frequency IN ({','.join('?'*len(vals))}) ORDER BY ID", vals).fetchall()                


def sendOff(entry):
    scraper = Scraper(entry[1])  # Pass ItemName
    scraper.userID = entry[0]
    scraper.item_Scraper(glance=True, dbIngest=True)
    
    df = scraper.df  # --- Filter by: >1/2*£tgt, <£tgt and <600mins for Auction
    candidates = df[((df.Price < int(entry[2])) & (df.Price >= int(entry[2])*0.5)) & ((df.Type == 'Auction') & (df.Minutes < 600) | (df.Type != 'Auction'))].sort_values('Type', ascending=False)[:3]
    
    if len(candidates) > 0:
        for i, row in candidates.iterrows():
            toSend = 'Buy Now Item found for [£{}]({})'.format(row.Price, row.shortLink) if row.Type != 'Auction' else 'Auction Item found with {} minutes left is currently [£{}]({})'.format(int(row.Minutes), row.Price, row.shortLink)
            toSend = toSend_formatter(toSend)
            bot.send_message(entry[0], toSend, parse_mode='MarkdownV2')
    else:
        bot.send_message(entry[0], f"😔 No Satisfactory matches were found for '{entry[1]}'!")

for entry in toScrape:
    sendOff(entry)

