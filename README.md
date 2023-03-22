# fchatpy
A python library to create bots and chat clients for the F-Chat websocket. This library is still in heavy development, don't expect a bug-free experience quite yet.

This does NOT have a GUI. So unless you're planning on making one yourself, I would not use this to do your chatting on. However, it's pretty easy to make simple bots with this library, if that's what you're looking for. 

This library supports nearly every F-Chat command available. So you should be able to do everything a non-chatop can do. 

## How to install:

In bash, type the following:

```
pip install -i https://test.pypi.org/simple/ FChatPy==0.3.0
```

If you're on Windows, I'd recommend installing it with an IDE such as PyCharm. 

## How to use:

The F-Chat websocket sends and receives messages to/from every user. Each message has a three letter "command" attached to each one, followed by a JSON object of some kind. For example, if a message has the "MSG" command attached to it, that means that command is related to a message sent in a channel. If it has the "PRI" command, then it's a private message sent between two users. 

For a list of commands sent to you by the server, go to: https://wiki.f-list.net/F-Chat_Server_Commands

For a list of commands sent to the server by you, go to: https://wiki.f-list.net/F-Chat_Client_Commands

The majority of the functions in client.py either send these commands to the server, or automatically run when these commands are received from the server. By overriding the "on_XXX" functions, you can program how your client responds to these events. For example, let's write a simple bot that just echos private messages sent to it.

```python
from fchatpy import FChatClient

class EchoBot(FChatClient):    
    def on_PRI(self, character, message):
        super().on_PRI(character, message)
        self.PRI(character, message)

if __name__ == "__main__":
    bot = EchoBot('username', 'password', 'character')
    bot.setup()
    bot.run_forever()
```

As you can see, the way you create a bot is by treating the FChatClient class like an abstract class (even though it's technically not one...) and override any function you want to add features to. In this case, we override the function on_PRI, which is called whenever we get a private message. 

Once you've created your new class, you initialize it with three variables: your username, your password, and the name of the character you're using. 

If you want to know what a specific command for something is, or what arguments a command uses, check the documentation for that command in the fchat.py file.