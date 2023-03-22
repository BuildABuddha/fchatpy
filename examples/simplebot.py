from fchatpy import FChatClient

"""
This bot does absolutely nothing but connect to F-Chat and display all the messages you're getting. 
The absolute bare minimum.
"""


class SimpleBot(FChatClient):
    log_filter = []     # We want to see all messages.
    log_pings = True    # We're also going to show our own outgoing pings.


if __name__ == "__main__":

    bot = SimpleBot(
        'username',  # Replace with account username
        'password',  # Replace with account password
        'character'  # Replace with name of character
    )

    bot.setup()             # Get our ticket and prepare to connect
    bot.run_forever()       # Keep the program running until stopped with ctrl + c
