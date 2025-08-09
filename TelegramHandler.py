import logging, threading, telebot, requests, time, sqlite3, re, pandas as pd, numpy as np
from time import sleep
from datetime import datetime as dt
from ebayScraper import Scraper

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(asctime)s - %(message)s", datefmt="%H:%M:%S")


# --- Configure Bot
bot = telebot.TeleBot('')

# --- Configure Selenium
options = Options()

# --- Configure Database
db = sqlite3.connect('ebayTracker.db', check_same_thread=False)
cur = db.cursor()










def toSend_formatter(toSend):
    for i in "\_*[],()~>#+-_=|!.'":
        toSend = toSend.replace(i, f"\\{i}")  # --- Message must be formatted with backslashes for these characters
    return toSend



def TelegramHandler():
    ### ---------------------------------------- START ---------------------------------------- ###
    @bot.message_handler(commands=['start'])
    def start(message):
        """First time users must select this by default, gives opportunity to add userIDs here"""
        bot.send_message(message.chat.id, """😎 I can help track items on ebay, so you don't have to spend hours looking for the perfect price 💸!\n\n/glance [Get the best deals right now!] \n/track [Monitor a new Item] \n/manage [View/Delete existing tracked Items]""")
        cur.execute("SELECT * FROM USER_IDS WHERE ID = ?", (message.chat.id,))
        if not cur.fetchone():
            logging.info(f'New UserID added: {message.chat.id}')
            cur.execute("INSERT INTO USER_IDS VALUES(?)", (message.chat.id,))
            db.commit()
        return
        
    
    
    ### ---------------------------------------- TRACK ---------------------------------------- ###
    @bot.message_handler(commands=['track'])
    def track(message):
        """Prompt users to send Item, Price, Frequency information."""
        bot.send_message(message.chat.id, """📅 Frequency Reference Sheet:\n0 - Sundays\n1 - Daily 10am\n2 - Daily 10am/4pm\n3 - Daily 8am/2pm/8pm""")
        bot.send_message(message.chat.id, """✍🏽 Specify the Item, Target Price and Frequency, seperated by a comma (Be Specific!)\n\nE.g. Pixel 7 Pro 256gb, 600, 1""")
        bot.register_next_step_handler(message, track_handler)  # Tells script that next received message should be routed here
        return
    
    def track_handler(message):
        """Check Legitimacy of Response (Correct formatting/Item exists) and add into Track List""" 
        verify = commands.get(message.text)
        if verify:
            verify(message)  # --- Discretely handles if another command was received during this step
        else:
            response = message.text.split(", ")
            if len(response) != 3 or not response[1].isdigit() or not response[2].isdigit():  # Captures formatting error
                bot.reply_to(message, "🤔 This isn't the correct Format!\n\nPlease enter in this format: ITEM, PRICE, FREQUENCY")
                bot.register_next_step_handler(message, track_handler)
                return
            else:
                bot.reply_to(message, "Verifying Item ...")
                numResults = Scraper(response[0]).item_Scraper(glance=False, dbIngest=False).numResults  # Use Scraper to get itemResults
                if numResults == 0:
                    bot.reply_to(message, f"🤔 Oh No! {response[0]} had no results, maybe try a different wording?")
                    bot.register_next_step_handler(message, track_handler)
                    return

                else:
                    cur.execute("INSERT INTO TRACKED_ITEMS VALUES(?,?,?,?)", (message.chat.id, response[0], int(response[1]), int(response[2])))
                    db.commit()
                    bot.reply_to(message, "🥳 Added to Track List!") 
        
        
        
    ### ---------------------------------------- GLANCE ---------------------------------------- #
    @bot.message_handler(commands=['glance'])
    def glance(message):
        """Allows users to get a quick top 3 match without ingestion"""
        bot.send_message(message.chat.id, """🕵️ Specify the Item & Target Price and get the best 3 matches (Be Specific!)\n\nE.g. Pixel 7 Pro 256gb, 600""")
        bot.register_next_step_handler(message, glance_handler)
        
    def glance_handler(message):
        """Check Legitimacy of Response (Correct formatting/Item exists) and return best 3 matches""" 
        verify = commands.get(message.text)
        if verify:
            verify(message)
        else:
            response = message.text.split(", ")
            if len(response) != 2 or not response[1].isdigit():
                bot.reply_to(message, "🤔 This isn't the correct Format!\n\nPlease enter in this format: ITEM, PRICE")
                bot.register_next_step_handler(message, glance_handler)
                return
            else:
                bot.reply_to(message, "Verifying Item ...")
                scraper = Scraper(response[0])
                scraper.item_Scraper(glance=True, dbIngest=False)
                if scraper.numResults == 0:
                    bot.reply_to(message, f"🤔 Oh No! {response[0]} had no results, maybe try a different wording?")
                    bot.register_next_step_handler(message, glance_handler)
                    return
                else:
                    df = scraper.df  # -- Filter by < Target > 1/2& Target, and <600 Minutes if Auction
                    candidates = df[((df.Price < int(response[1])) & (df.Price >= int(response[1])*0.5)) & ((df.Type == 'Auction') & (df.Minutes < 600) | (df.Type != 'Auction'))].sort_values('Type', ascending=False)[:3]
                    if len(candidates) > 0:
                        for i, row in candidates.iterrows():
                            toSend = 'Buy Now Item found for [£{}]({})'.format(row.Price, row.shortLink) if row.Type != 'Auction' else 'Auction Item found with {} minutes left is currently [£{}]({})'.format(int(row.Minutes), row.Price, row.shortLink)
                            toSend = toSend_formatter(toSend)
                            bot.reply_to(message, toSend, parse_mode='MarkdownV2')
                        return
                    else:
                        bot.reply_to(message, '😔 No Satisfactory matches were found!')
                        return
                    
        
    
    ### ---------------------------------------- MANAGE ---------------------------------------- #
    @bot.message_handler(commands=['manage'])
    def manage(message):
        """Allows users to view and manage their tracked items"""
        userTracked = cur.execute(f"SELECT Item, Price, Frequency FROM TRACKED_ITEMS WHERE ID = {message.chat.id}").fetchall()  # -- Via ID get users trackedItems
        if len(userTracked) == 0:
            bot.send_message(message.chat.id, "You have no tracked items!\n\nUse /track to start tracking")
        else:
            table = "📒 📍NAME 📍PRICE 📍FREQ"
            for i, x in enumerate(userTracked):
                table += f"\n[{i+1}] {x[0]} - £{x[1]} - {x[2]}"
            bot.send_message(message.chat.id, f"{table}\n\nTo modify an Item, type MOD rowNumber\n\nE.g. MOD 1")            
            bot.register_next_step_handler(message, manage_handler, userTracked)
    
    def manage_handler(message, userData):
        """Check Legitimacy of Response (Correct formatting/Item exists), recursively used to verify first MOD action and then secondary DELETE/PRICE/FREQ action""" 
        verify = commands.get(message.text)
        if verify:
            verify(message)
        else:
            response = message.text.split(" ")
            if response[0].lower() != 'delete' and (len(response) !=2 or not response[1].isdigit()):  # If not delete, then checks if second conditions satisfied (otherwise skips straight through)
                bot.reply_to(message, "🤔 This isn't the correct Format!\n\nPlease enter in this format: COMMAND NUMBER. E.g. MOD 3")
                bot.register_next_step_handler(message, manage_handler, userData)
            
            elif response[0].lower() == 'mod' and int(response[1]) <= len(userData):  # -- First activated by MOD, here userData is their trackedItems
                bot.send_message(message.chat.id, """📅 Frequency Reference Sheet:\n0 - Sundays\n1 - Daily 10am\n2 - Daily 10am/4pm\n3 - Daily 8am/2pm/8pm""")
                bot.reply_to(message, "Type FREQ|PRICE number for modifications, and DELETE to remove it\n\nE.g. PRICE 35 or DELETE")
                chosenItem = userData[int(response[1])-1][0]     
                bot.register_next_step_handler(message, manage_handler, chosenItem)
                return
                
            elif response[0].lower() in ['price', 'freq']:  # -- Second activation, here price/freq updates handled
                bot.send_message(message.chat.id, f"🥳 Item {response[0].capitalize()} ammended!")
                col = {'price':'Price','freq':'Frequency'}[response[0].lower()]
                cur.execute(f"UPDATE TRACKED_ITEMS SET {col} = ? WHERE Item = ? AND ID = ?", (response[1], userData, message.chat.id))
                db.commit()
                return
                             
            elif response[0].lower() == 'delete':  # -- Second activation, here item is deleted
                bot.send_message(message.chat.id, f"🥳 Item no longer tracked!")                
                cur.execute(f"DELETE FROM TRACKED_ITEMS WHERE Item = ? AND ID = ?", (userData, message.chat.id))
                db.commit()
                return
            
            else:
                bot.reply_to(message, "🤔 Invalid Format!\n\nPlease enter either DELETE or MOD/PRICE/FREQ Number.")
                bot.register_next_step_handler(message, manage_handler, userData)
    
    commands = {'/start': start, '/glance': glance, '/track': track, '/manage': manage}
    bot.polling(none_stop=True)  # Waits Non-Stop for Messages

if __name__ == "__main__":
  TelegramHandler()
