from fchatpy import fchat

"""
This bot does absolutely nothing but connect to F-Chat and display all the messages you're getting. 
The absolute bare minimum.
"""


class SimpleBot(fchat.FChatClient):
    log_filter = []     # We want to see all messages.
    log_pings = True    # We're also going to show our own outgoing pings.


if __name__ == "__main__":
    bot = SimpleBot('ws://chat.f-list.net:8722',    # test server: 8722, public server: 9722
                    'username',                     # Replace with account username
                    'password',                     # Replace with account password
                    'character')                    # Replace with character to log in with
    bot.setup()             # Get our ticket and prepare to connect
    bot.connect()           # Log onto F-Chat
    bot.run_forever()       # Keep the program running until stopped with ctrl + c
