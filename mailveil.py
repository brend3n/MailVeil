from simple_term_menu import TerminalMenu # Menu
from alive_progress import alive_bar # Progress bar
from imports.mailtm.pymailtm import Account, MailTm, Message # mail.tm API

# Standard libraries
import threading
from typing import List, DefaultDict
from collections import defaultdict
from os import system
import pathlib
import sys
from time import sleep

# Used for partitioning a list of data into chunks for n number of threads
def chunkify(lst: list, n: int):
    # Total number of elements in the list
    l = len(lst)
    # Base size of each chunk
    k = l // n
    # Calculate the number of chunks that need an extra element
    m = l % n
    # Create chunks
    chunks = []
    start = 0
    for i in range(n):
        # Chunks 0 to m-1 will have k+1 elements, others will have k elements
        end = start + (k + 1 if i < m else k)
        chunks.append(lst[start:end])
        start = end
    return chunks

class MailVeil():
  
  db_file_name = ".mailveil_db.txt"
  
  def __init__(self):
    if not pathlib.Path(self.db_file_name).exists():
      print("DB file does not exist so we are making one")
      pathlib.Path(self.db_file_name).touch()
    else:
      print("DB file already exists")
    
    
  def mv_monitor_account(self, account: Account):
    """Keep waiting for new messages and open them in the browser."""
    print("Type Ctrl + C to stop monitoring\n")
    try:
      while True:
          print("\nWaiting for new messages...")
          start = len(account.get_messages())
          while len(account.get_messages()) == start:
              sleep(1)
          print("New message arrived!")
          
                    
          message = account.get_messages()[0]
          msg_to_print = f"""
          From: {message.from_["name"]} ({message.from_["address"]})
          Subject: {message.subject}
          Text: {message.text}
          """
          
          print(msg_to_print)
          
          options = ['Open in web','Back']
          menu = TerminalMenu(options)
          menu_entry = menu.show()      
          
          if options[menu_entry] == 'Back':
            return
          elif options[menu_entry] == 'Open in web':          
            account.get_messages()[0].open_web()
            return
          else:
            return None
    except KeyboardInterrupt:
      print("Done monitoring")
      return
                
  def get_new_email_account(self, email_address=None, password=None) -> None:
    timeout = 10
    
    if not email_address and not password:
      print("Creating account with random email address and password")
    else:
      print(f"Creating account with email address {email_address} and password {password}")
      
    while timeout > 0:
      if not email_address and not password:
        try:
          mt = MailTm()
          account = mt.get_account()
          sleep(1)
        except Exception as e:          
          timeout -= 1          
          print(".", end="",flush=True)
          continue
      else:
        #TODO: This is unsupported at the moment
        try:            
          mt = Account(email_address, password)
          account = mt.get_account()
        except Exception as e:
          timeout -= 1
          print(".", end="",flush=True)
          continue
        
      break
        
    if timeout == 0:
      print("Timed out trying to make new account")    
      return None
    
    print("\n")
    print(f"id: {account.id_}\nemail_address: {account.address}\npassword: {account.password}")
    
    options = ['Monitor for messages','Delete','Back']
    menu = TerminalMenu(options)
    
    while (1):      
      menu_entry = menu.show()      
      if options[menu_entry] == 'Back':
        break
      elif options[menu_entry] == 'Delete':
        delete_res = False
        while(not delete_res):
          try:
            delete_res = account.delete_account()
          except Exception as e:
            print("Error deleting. Retrying")
          sleep(1)
        print("Deleted account", flush=True)
        sleep(1)
        return None
      elif options[menu_entry] == 'Monitor for messages':
        self.mv_monitor_account(account)
      else:
        return None        
    
    print(f"Saving account {account.address}...")
    self._save_account(account)
    return
  
  def _save_account(self, account: Account) -> None:
    with open(self.db_file_name, "a") as f:
      f.write(f"{account.id_},{account.address},{account.password}\n")

  def _load_accounts(self) -> List[str]:            
    with open(self.db_file_name, "r+") as f:
      lines = f.readlines()        
    lines = [line.replace("\n","") for line in lines]      
    return lines 
  
  def _delete_account_from_file(self, account: Account):
    account_strs: List[str] = self._load_accounts()
    found = False
    for acc_str in account_strs:
      if account.address in acc_str:
        # print(f"Found account {account.address} in file\nNow deleting it.")
        account_strs.remove(acc_str)
        found = True
        break
      
    if found == False:
      print(f"Account {account.address} not in file")              
    else:
      with open(self.db_file_name, "w+") as f:
        [f.write(f"{acc}\n") for acc in account_strs]
      print(f"Deleted {account.address} from file")

  def get_all_emails_from_email_addresses(self, bar: alive_bar, accounts: List[str]):
    def target_function(bar, chunk_accounts, list_of_email_objs):
      """
      
      Returns a structure of the form
      
      email_obj: {
      "email_address: str,
      "emails": list[str]
      }
      
      list_of_objs: List[email_obj]
      
      """
      
      for account_info in chunk_accounts:
        account: Account
        id,address,password = tuple(account_info.split(","))            
        timeout = 10
        while timeout > 0:
          try:
            print(f"Getting account {address}")
            account = Account(id,address,password)
            sleep(1)
          except Exception as e:                  
            timeout -= 1                  
            print(".", end="",flush=True)
            continue              
          break
        
        if timeout == 0:
          print("Timed out trying to get account")
          continue
        
        # Try to get messages from MailTM server
        try:
          # Get account from MailTm
          messages_all = account.get_messages()
        except Exception as e:
          print(f"Skipped")
          print(e)
          continue
                        
        messages_parsed = [message for message in messages_all]
        email_obj = {
          "email_address" : account.address,
          "emails" : list(messages_parsed)
        }
        
        # Update email obj list and progress bar
        list_of_email_objs.append(email_obj)
        bar()
        
      return
      
    list_of_emails = [] # Stores our return value of the list of email_objs
    
    # Holds the Thread objects
    threads = []  
    
    num_threads = 10 # Hardcoded for now

    print("Num active accounts: ", len(accounts))

    chunks = chunkify(accounts, num_threads)
  
    # Give each thread webpages
    for i in range(num_threads):
      t = threading.Thread(name=f"Thread {i} with {len(chunks[i])} accounts", target=target_function,args=([bar,chunks[i],list_of_emails]),)
      t.daemon = True 
      threads.append(t)
    
    # Start threads
    print(f"Starting {num_threads} threads.")
    for i in range(num_threads):
      threads[i].start()
    
    # Join threads
    for i in range(num_threads):
      threads[i].join()


    return list_of_emails


  def account_menu(self) -> None:
      
    accounts = self._load_accounts()
    single_account_menu_options: List[str] = []
    
    temp_LUT = defaultdict(dict) # used for getting the id and password after selecting the address from the list
    for line in accounts:
      __id,address,__pw=tuple(line.split(','))
      temp_LUT[address]['id'] = __id 
      temp_LUT[address]['pw'] = __pw
      single_account_menu_options.append(address)
      
    single_account_menu_options.append('Back')    
    single_account_menu = TerminalMenu(single_account_menu_options)
    
    while (1):  
      
      # This is up here because we want to reset it each loop
      account_to_get_boi: List[str] = [] # This list should only contain one string              
      
      system('clear')  
      entry = single_account_menu.show()
      
      if single_account_menu_options[entry] == 'Back':
        return
      else:              
        options = ['Get messages', 'Delete account', 'Back']
        menu = TerminalMenu(options)
        
        while (1):
          system('clear')
          entry_account = menu.show()
          if options[entry_account] == 'Back':
            break # Go back to all accounts
          elif options[entry_account] == 'Delete account':            
            id=temp_LUT[single_account_menu_options[entry]]['id'] or "No id"
            address=single_account_menu_options[entry] or "No address"
            pw=temp_LUT[single_account_menu_options[entry]]['pw'] or "No pw"
            try:
              account: Account = Account(id,address,pw)
            except Exception as e:
              print("Couldnt get account or account already deleted", flush=True)
              # Remove deleted account from structures
              single_account_menu_options.remove(single_account_menu_options[entry])
              single_account_menu = TerminalMenu(single_account_menu_options)              
              temp_LUT.pop(single_account_menu_options[entry], None)
              break              
            delete_res = False
            while(not delete_res):
              try:
                delete_res = account.delete_account()
              except Exception as e:
                print("Error deleting. Retrying",flush=True)
              sleep(1)            
            # Remove deleted account from structures
            temp_LUT.pop(single_account_menu_options[entry], None)
            single_account_menu_options.remove(single_account_menu_options[entry])
            single_account_menu = TerminalMenu(single_account_menu_options)            
            self._delete_account_from_file(account)
            sleep(1)
            break
          elif options[entry_account] == 'Get messages':
            print(f"Reading messages for {single_account_menu_options[entry]}")
            recreated_string_for_function_below=f"{temp_LUT[single_account_menu_options[entry]]['id']},{single_account_menu_options[entry]},{temp_LUT[single_account_menu_options[entry]]['pw']}"
            account_to_get_boi.append(recreated_string_for_function_below) # we have the account information for the selection 
            self.show_emails(email_address=account_to_get_boi)
          else:
            break      
    return          

  # TODO I want to refactor this function a bit. Its kind of hard to read and can be good to split some
  # stuff up because it seems like I should split Account menu stuff from all of the message fetching
  def show_emails(self, show_all_=False, email_address: List[str]=None):
    # Have list of all active email addresses
    account_strs = [] # Holds email addresses with number of emails in them
    accounts = self._load_accounts()
    
    if show_all_ == True: # Get em all
      print("Getting messages for all emails")
      with alive_bar(len(accounts)) as bar:  
        list_of_email_objs = self.get_all_emails_from_email_addresses(bar, accounts)
    else: # Just get one buddy
      with alive_bar(1) as bar:
        list_of_email_objs = self.get_all_emails_from_email_addresses(bar, email_address)
    
    # Creating a new dictionary with 'email_address' as the key and 'emails' as the value
    email_LUT = {item["email_address"]: item["emails"] for item in list_of_email_objs}

    account_strs = [f"{email_obj['email_address']}: {len(email_obj['emails'])}" for email_obj in list_of_email_objs]
    
    # Sort by number of emails
    # TODO
    
    # Menu for each email
    account_strs.append("Back")
    options = account_strs
    menu = TerminalMenu(options)
    
    while (1):
      system('clear') # clear screen
      entry = menu.show()
      
      # Quit scenario
      if options[entry] == "Back":
        return
      else:
        # Extract the email from selected menu choice
        email = str(options[entry]).split(":")[0]
        
        # Lookup emails for that address
        messages: List[Message] = email_LUT[email]        
        
        index = 0 # starting index of messages to look at
        
        # Look at each message
        while (1):   
          system("clear")
          if len(messages) == 0:
              print("No messages for this account")
              break
          else:
            msg_to_print = f"""
            From: {messages[index].from_["name"]} ({messages[index].from_["address"]})
            Subject: {messages[index].subject}
            Text: {messages[index].text}
            """
            
            print(f"Message {index+1}\n\n")
            
            # Show messagemess
            print(msg_to_print)
            
            message_menu_options = ['Next', 'Open in browser', 'Back']
            message_menu = TerminalMenu(message_menu_options)
            message_menu_entry = message_menu.show()
            
            if message_menu_options[message_menu_entry] == 'Next':
              index = (index + 1) % len(messages) if len(messages) > 0 else 0
            elif message_menu_options[message_menu_entry] == 'Back':
              break
            elif message_menu_options[message_menu_entry] == 'Open in browser':
              messages[index].open_web()
            else:
              continue
    return


def main():
    options = ['Get new email address', 'Accounts', 'Get all emails for all adresses', 'Quit']
    menu = TerminalMenu(options)
    
    mv = MailVeil()
    
    while 1:
      system("clear") # clear screen
      menu_entry = menu.show()      
      
      if options[menu_entry] == 'Get new email address':
        mv.get_new_email_account()
      elif options[menu_entry] == 'Accounts':
        mv.account_menu()
      elif options[menu_entry] == 'Get all emails for all adresses':
        mv.show_emails(show_all_=True)
      elif options[menu_entry] == 'Quit':
        return
      else:
        continue

if __name__ == "__main__":
    main()