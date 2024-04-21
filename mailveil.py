from simple_term_menu import TerminalMenu # Menu
from alive_progress import alive_bar # Progress bar
from imports.mailtm.pymailtm import Account, MailTm # mail.tm API

# Standard libraries
import threading
from typing import List
from os import system
import pathlib
import sys
from time import sleep

# Used for partitioning a list of data into chunks for n number of threads
def chunkify(lst: list,n: int):
    return [lst[i::n] for i in range(n)]

class MailVeil():
  
  db_file_name = ".mailveil_db.txt"
  
  def __init__(self):
    if not pathlib.Path(self.db_file_name).exists():
      print("DB file does not exist so we are making one")
      pathlib.Path(self.db_file_name).touch()
    else:
      print("DB file already exists")
    
  def get_new_email_account(self, email_address=None, password=None) -> Account:    
    success = False
    max_timeout = timeout = 10
  
    while timeout > 0 and not success:
      if not email_address and not password:
        try:
            print("Creating account with random email address and password")
            mt = MailTm()
            account = mt.get_account()
            sleep(1)
        except Exception as e:
            print(f"Could not get new email account\n Error: {e}")
            timeout -= 1
            print(f"Timeout {max_timeout-timeout}/{max_timeout}")
            continue
      else:
        #TODO: This is unsupported at the moment
        try:
            print(f"Creating account with email address {email_address} and password {password}")
            mt = Account(email_address, password)
            account = mt.get_account()
        except Exception as e:
            print(f"Could not get new email account\n Error: {e}")
            timeout -= 1
            print(f"Timeout {max_timeout-timeout}/{max_timeout}")
            continue
        
      success = True
        
    if timeout == 0:
      print("Timed out trying to make new account")    
      return None
    
    print(f"id: {account.id_}\nemail_address: {account.address}\npassword: {account.password}")
    self._save_account(account)
    return account
  
  def _save_account(self, account: Account) -> None:
      with open(self.db_file_name, "a") as f:
        f.write(f"{account.id_},{account.address},{account.password}\n")

  def _load_accounts(self) -> List[Account]:
    
      accounts: List[Account] = []
      
      with open(self.db_file_name, "r+") as f:
        lines = f.readlines()
        
      lines = [line.replace("\n","") for line in lines]
          
      for line in lines:
        id,address,password = tuple(line.split(","))
        
        success = False
        max_timeout = timeout = 10
        while timeout > 0 and not success:
          try:
            account = Account(id,address,password)
            sleep(1)
          except Exception as e:
            print(f"Could not get email account\n Error: {e}")
            timeout -= 1
            print(f"Timeout {max_timeout-timeout}/{max_timeout}")
            continue
        
          success = True
        
        if timeout == 0:
          print("Timed out trying to get accounts")
          return None
        
        accounts.append(account)
        
      return accounts
        

  def get_all_emails_from_email_addresses(self, bar: alive_bar, accounts: List[Account]):
      def target_function(bar, chunk_accounts, list_of_email_objs):
          """
          
          Returns a structure of the form
          
          email_obj: {
          "email_address: str,
          "emails": list[str]
          }
          
          list_of_objs: List[email_obj]
          
          """
          
          for account in chunk_accounts:        
              account: Account    
              # Try to get messages from MailTM server
              try:
                  # Get account from MailTm
                  messages_all = account.get_messages()
              except Exception as e:
                  print(f"Skipped")
                  print(e)
                  continue
                            
              messages_parsed = [message.html for message in messages_all]
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

  def show_emails(self):
      # Have list of all active email addresses
      account_strs = [] # Holds email addresses with number of emails in them
      accounts = self._load_accounts()
  
      print("Getting messages")
      with alive_bar(len(accounts)) as bar:  
          list_of_email_objs = self.get_all_emails_from_email_addresses(bar, accounts)            
      
      # Creating a new dictionary with 'email_address' as the key and 'emails' as the value
      email_LUT = {item["email_address"]: item["emails"] for item in list_of_email_objs}
      
      for email_obj in list_of_email_objs:
          email_address = email_obj["email_address"] 
          email_list = email_obj["emails"]
          
          email_str = f"{email_address}: {len(email_list)}"
          account_strs.append(email_str)
      
      # Sort by number of emails
      # TODO
      
      # Menu for each email
      account_strs.append("Quit")
      options = account_strs
      menu = TerminalMenu(options)
      
      while (1):
          system('clear') # clear screen
          entry = menu.show()
          
          # Quit scenario
          if options[entry] == "Quit":
              return
          else:
              # Extract the email from selected menu choice
              email = str(options[entry]).split(":")[0]
              
              # Lookup emails for that address
              messages = email_LUT[email]
              index = 0 # starting index of messages to look at
              
              # Look at each message
              while (1):                
                  if len(messages) == 0:
                      print("No messages for this account")    
                      break
                  else:
                      # Show message
                      print(messages[index])
                      
                      message_menu_options = ['Next', 'Back', 'Quit']
                      message_menu = TerminalMenu(message_menu_options)
                      message_menu_entry = message_menu.show()
                      
                      if message_menu_options[message_menu_entry] == 'Next':
                          index = (index + 1) % len(messages) if len(messages) > 0 else 0
                      elif message_menu_options[message_menu_entry] == 'Back':
                          break
                      elif message_menu_options[message_menu_entry] == 'Quit':
                          return
                      else:
                          continue
      return


def main():
    options = ['Get new email', 'Show all email addresses', 'Quit']
    menu = TerminalMenu(options)
    
    mv = MailVeil()
    
    while 1:
      menu_entry = menu.show()      
      
      if options[menu_entry] == 'Get new email':
        mv.get_new_email_account()
      elif options[menu_entry] == 'Show all email addresses':
        mv.show_emails()
      elif options[menu_entry] == 'Quit':
        return
      else:
        continue

if __name__ == "__main__":
    main()