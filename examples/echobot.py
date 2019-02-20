from fchatpy import fchat
from ws4py.exc import WebSocketException

# This bot will log into F-Chat and set a status. If it gets a private message, it will echo the message back. 
# Remember to set username, password, and character on lines 28-30!

class EchoBot(fchat.FChatClient):

    # We don't want PIN, NLN, FLN or STA messages printed to the console. Add in or remove commands as you wish.
    log_filter = {"PIN", "NLN", "FLN", "STA"}

    # Here's all the stuff we want the bot to do first thing when it connects.
    def connect(self):
        super().connect()   # Always call super first!
        self.STA('online',  # Set status on login.
                 "Hello, I am an echo bot. I will echo your messages back to you!")

    # Here's what it should do when it gets a private message.
    def on_PRI(self, character, message):
        super().on_PRI(character, message)  # Always call super first!
        self.PRI(character, message)        # Send message back to character that sent it.


if __name__ == "__main__":
    running = True
    while running:
        bot = EchoBot('ws://chat.f-list.net:8722',  # test server: 8722, public server: 9722
                      'username',                   # Replace with account username
                      'password',                   # Replace with account password
                      'character')                  # Replace with character to log in with
        bot.logger.info("Connecting ...")
        try:
            bot.setup()
            bot.connect()
            bot.run_forever()
        except KeyboardInterrupt:   # Use ctrl + c to close the client from the command line.
            bot.logger.exception("Disconnected by user.")
            running = False
        except WebSocketException as e:
            bot.logger.exception("WebSocket Exception!")
        except ConnectionError as e:
            bot.logger.error("Could not connect to server!")
        except Exception:
            bot.logger.exception("Unknown exception!")
        finally:
            bot.close()
            if running:
                bot.reconnect_stagger()
