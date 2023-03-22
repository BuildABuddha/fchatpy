from fchatpy import FChatClient


# This bot will log into F-Chat and set a status. If it gets a private message, it will echo the message back.
# Remember to set username, password, and character on lines 28-30!

class EchoBot(FChatClient):
    # We don't want PIN, NLN, FLN or STA messages printed to the console. Add in or remove commands as you wish.
    log_filter = ["PIN", "NLN", "FLN", "STA"]

    # Here's all the stuff we want the bot to do first thing when it connects.
    def connect(self):
        super().connect()  # Always call super first!
        self.STA('online',  # Set status on login.
                 "Hello, I am an echo bot. I will echo your messages back to you!")

    # Here's what it should do when it gets a private message.
    def on_PRI(self, character, message):
        super().on_PRI(character, message)  # Always call super first!
        self.PRI(character, message)  # Send message back to character that sent it.


if __name__ == "__main__":
    bot = EchoBot(
        'username',  # Replace with account username
        'password',  # Replace with account password
        'character'  # Replace with name of character
    )

    running = True

    while running:
        try:
            bot.setup()
            bot.run_forever()
        except KeyboardInterrupt or SystemExit:
            bot.logger.exception("Disconnected by user.")
            running = False
        except Exception:
            bot.logger.exception("Unknown exception!")
            bot.terminate_threads()
            running = False
        finally:
            if running and bot:
                bot.reconnect_stagger()
