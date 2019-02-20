# fchatpy
A python library to create bots and chat clients for the F-Chat websocket. This library is still in heavy development, don't expect a bug-free experience quite yet.

This does NOT have a GUI (yet). So unless you're planning on making one yourself, I would not use this to do your chatting on. However, it's pretty easy to make simple bots with this library, if that's what you're looking for. 

This library supports nearly every F-Chat command available. So you should be able to do everything a non-chatop can do. 

## How to install:

In bash, type the following:

```
git clone https://github.com/BuildABuddha/fchatpy.git
sudo python3 setup.py install
```

If you're on Windows, I'd recommend installing it with an IDE such as PyCharm. 

## How to use:

The F-Chat websocket sends and receives messages to/from every user. Each message has a "command" attached to each one. For example, if a message has the "MSG" command attached to it, that means that command is related to a message sent in a channel. If it has the "PRI" command, then it's a private message sent between two users. 

For a list of commands sent to you by the server, go to: https://wiki.f-list.net/F-Chat_Server_Commands

For a list of commands sent to the server by you, go to: https://wiki.f-list.net/F-Chat_Client_Commands

The majority of the functions in fchat.py either send these commands to the server, or automatically run when these commands are received from the server. In the examples folder, the echobot.py file shows an example of how this can be used. In that case, it logs in, sets a status, and when a private message is received, it echos the message back to whoever sent it. 

If you want to know what a specific command for something is, or what arguments a command uses, check the documentation for that command in the fchat.py file. 
