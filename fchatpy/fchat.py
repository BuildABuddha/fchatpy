#!/usr/bin/python
# -*- coding: utf-8 -*-

from ws4py.client.threadedclient import WebSocketClient
import urllib
import urllib.request
import urllib.parse
import json
import time
import logging
import threading


class User(object):
    """
    This object class stores all the information needed to keep track of online users.
    """

    def __init__(self, name, gender, status, message):
        self.name = name
        self.gender = gender
        self.status = status
        self.message = message

    def update(self, status, message):
        self.status = status
        self.message = message


class Channel(object):
    def __init__(self, channel_id, title, num_characters):
        """
        This object class helps you keep track of all the channels.

        NOTICE: Channels have both an "id" and a "title". For public rooms, these will be exactly the same. For private
        rooms, they will have the name of the room as the "title", and the "id" will be a string of numbers and
        characters.

        :param channel_id: Unique ID for the channel.
        :param title: Title of the channel.
        :param num_characters: Number of characters in the room, in integer form.
        """
        self.id = channel_id
        self.title = title
        self.mode = {}
        self.num_characters = num_characters
        self.character_list = []
        self.owner = {}
        self.channel_ops = []
        self.description = {}

    def update(self, channel_id, title, num_characters):
        """
        This command should usually only be used when getting a list of all rooms through either CHA or ORS.

        :param channel_id: ID of the room in string form.
        :param title: Title of the room in string form.
        :param num_characters: Number of characters in the room in int form.
        """
        self.id = channel_id
        self.title = title
        self.num_characters = num_characters

    def joined(self, character):
        """
        To be called when a character joins a room.

        :param character: Character that just joined the room. Use the Character object class.
        """
        if character not in self.character_list:
            self.character_list.append(character)
            self.num_characters += 1

    def left(self, character):
        """
        To be called when a character leaves a room.

        :param character: Character that just left the room. Use the Character object class.
        """
        if character in self.character_list:
            self.character_list.remove(character)
            self.num_characters -= 1

            
class FChatClient(WebSocketClient):
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG)
    logger = logging.getLogger("fchat")
    log_filter = {}

    def __init__(self, url, account, password, character, client_name="Python FChat Library"):
        """
        This object class is the main meat and potatoes of this library. Calling this will initialize a client to
        connect one character to the F-Chat websocket.

        :param url: URL of the websocket. Should be either 'ws://chat.f-list.net:9722' for the public server or
        'ws://chat.f-list.net:8722' for the test server.
        :param account: Your account's username.
        :param password: Your account's password.
        :param character: The character you want to log in to.
        :param client_name: Default set to "Python FChat Library".
        """
        WebSocketClient.__init__(self, url)
        self.account = account
        self.password = password
        self.character_name = character
        self.client_name = client_name

        self.outgoing_pump_running = True
        self.connection_test_running = True
        self.log_pings = False

        self.operators = []
        self.server_vars = {}
        self.users = {}  # Dictionary of online users. Key is username (lower case), object type is "User".
        self.channels = {}
        self.friends = []
        self.ignored_users = []
        self.outgoing_buffer = []

        self.message_delay = 1
        self.ticket_time = 0
        self.ticket = ''
        self.last_ping_time = time.time()

        self.buffer_lock = threading.Lock()
        self.reconnect = threading.Thread(target=self.connection_test, args=())
        self.outgoing_thread = threading.Thread(target=self.outgoing_pump, args=())

        # We want to initialize these variables only if they don't already exist.
        try:
            self.reconnect_delay = self.reconnect_delay
            self.reconnect_attempt = self.reconnect_attempt
        except AttributeError or NameError:
            self.reconnect_delay = 1
            self.reconnect_attempt = 0

    def setup(self):
        """
        This function should be called before connecting to the websocket. It will get a ticket for connecting and
        start up some required threads. It will also initialize some values.

        :return: True if able to get a ticket, False if unable to get a ticket.
        """

        if self.get_ticket() is None:
            return False
        else:
            # self.outgoing_thread = OutgoingPumpThread(self)
            self.outgoing_thread.setDaemon(True)
            self.outgoing_thread.start()

            self.reconnect_delay = 1
            self.reconnect_attempt = 0
            # self.reconnect = PingTestThread(self)
            self.reconnect.setDaemon(True)
            self.reconnect.start()

            return True

    def connect(self):
        """
        This function is called first thing whenever we're connected. If you want to do something like set your status
        or join rooms immediately upon joining F-Chat, you will do it by overriding this function.
        """

        super().connect()
        time.sleep(3)  # We should give the client some time to initialize before trying to do stuff.

    def get_ticket(self):
        """
        Will request a ticket from F-List.net. This ticket is required to connect to the websocket.

        :return: If successful, returns ticket. If not successful, returns None.
        """

        if self.ticket and time.time() - self.ticket_time < 30 * 60:
            return self.ticket
        else:
            self.logger.info("Fetching ticket ...")
            self.ticket_time = time.time()

            data = {'account': self.account, 'password': self.password}
            data_enc = urllib.parse.urlencode(data)
            data_enc = data_enc.encode("UTF-8")

            response = urllib.request.urlopen('https://www.f-list.net/json/getApiTicket.php', data_enc)
            text = response.read()
            text_parsed = json.loads(text.decode("UTF-8"))

            if 'ticket' in text_parsed:
                self.ticket = text_parsed['ticket']
                return self.ticket
            else:
                self.logger.error(text_parsed['error'])
                return None

    def outgoing_pump(self):
        while self.outgoing_pump_running:
            if len(self.outgoing_buffer):
                self.send_one()
                time.sleep(self.message_delay)
            else:
                time.sleep(0.01)

    def connection_test(self):
        while self.connection_test_running:
            if time.time() - self.last_ping_time > 90:
                self.logger.info("Didn't get a ping in time. Restarting.")
                self.close_connection()
                break
            else:
                time.sleep(1)

    def terminate_threads(self):
        """
        This function should be called whenever we close our client, so that threads can safely end.
        """
        try:
            if self.outgoing_thread.isAlive:
                self.outgoing_thread.running = False
        except AttributeError:
            pass

        try:
            if self.reconnect.isAlive:
                self.reconnect.running = False
        except AttributeError:
            pass

    def opened(self):
        """
        Automatically called when we successfully connect to the server. Resets reconnect delays, and sends sends an
        IDN message.
        """
        self.reconnect_delay = 1
        self.reconnect_attempt = 0
        self.logger.info("Connected!")
        self.IDN(self.character_name)

    def closed(self, code, reason=None):
        """
        Automatically  called when the client is closed. Terminates threads and logs reason for closing.

        :param code:
        :param reason:
        """
        self.logger.info("Closing (" + str(code) + ", " + str(reason) + ")!")
        self.terminate_threads()
        super().closed(code, reason)

    def received_message(self, m):
        """
        Called automatically whenever a message is received from the F-Chat websocket. The first three letters will be
        the command given by the message. Everything after it will be the data in JSON form.

        :param m: Message received, UTF-8 encoded, in JSON form.
        """

        msg = m.data.decode("UTF-8")
        command = msg[:3]
        try:
            json_string = msg[4:]
            data = json.loads(json_string)
        except:
            data = {}

        # Print everything not filtered out by log_filter to the logger.
        if command not in self.log_filter:
            self.logger.debug("<< %s %s" % (command, data))

        # Call the function for the command. There's probably a better way to do this, but this is at least stable, and
        # multiple if/else string checks like this are actually not very time intensive in python.
        if command == "ADL":  # Chatops list
            self.on_ADL(data['ops'])

        elif command == "AOP":  # Chatops promotion
            self.on_AOP(data['character'])

        elif command == "BRO":  # Admin broadcast
            self.on_BRO(data['message'])

        elif command == "CDS":  # Channel description change
            self.on_CDS(data['channel'], data['description'])

        elif command == "CHA":  # Public channels list
            self.on_CHA(data['channels'])

        elif command == "CIU":  # Channel invite
            self.on_CIU(data['sender'], data['title'], data['name'])

        elif command == "CBU":  # User banned from channel
            self.on_CBU(data['operator'], data['channel'], data['character'])

        elif command == "CKU":  # User kicked from channel
            self.on_CKU(data['operator'], data['channel'], data['character'])

        elif command == "COA":  # Channel op promotion
            self.on_COA(data['character'], data['channel'])

        elif command == "COL":  # Channel ops list
            self.on_COL(data['channel'], data['oplist'])

        elif command == "CON":  # Number of connected users
            self.on_CON(data['count'])

        elif command == "COR":  # Channel op demotion
            self.on_COR(data['character'], data['channel'])

        elif command == "CSO":  # Channel owner promotion
            self.on_CSO(data['character'], data['channel'])

        elif command == "CTU":  # Channel temp ban
            self.on_CTU(data['operator'], data['channel'], data['length'], data['character'])

        elif command == "DOP":  # Chatops demotion
            self.on_DOP(data['character'])

        elif command == "ERR":  # Error notification
            self.on_ERR(data['message'], data['number'])

        elif command == "FKS":  # Search results
            self.on_FKS(data['characters'], data['kinks'])

        elif command == "FLN":  # User disconnected
            self.on_FLN(data['character'])

        elif command == "HLO":  # Hello command
            self.on_HLO(data['message'])

        elif command == "ICH":  # Initial channel data
            self.on_ICH(data['users'], data['channel'], data['mode'])

        elif command == "IDN":  # Identification successful
            self.on_IDN(data['character'])

        elif command == "JCH":  # User joined channel
            self.on_JCH(data['character'], data['channel'], data['title'])

        elif command == "KID":  # Kink data
            self.on_KID(data['type'], data['message'], data['key'], data['value'])

        elif command == "LCH":  # User left channel
            self.on_LCH(data['channel'], data['character'])

        elif command == "LIS":  # Online characters list
            self.on_LIS(data['characters'])

        elif command == "NLN":  # User connected
            self.on_NLN(data['identity'], data['gender'], data['status'])

        elif command == "IGN":  # Ignore list
            if data['action'] == 'init':
                self.on_IGN(data['action'], characters=data['characters'])
            elif data['action'] == 'add' or data['action'] == 'delete':
                self.on_IGN(data['action'], character=data['character'])

        elif command == "FRL":  # Friends list
            self.on_FRL(data['characters'])

        elif command == "ORS":  # Private channels list
            self.on_ORS(data['channels'])

        elif command == "PIN":  # Ping from server
            self.on_PIN()

        elif command == "PRD":  # Profile data
            self.on_PRD(data['type'], data['message'], data['key'], data['value'])

        elif command == "PRI":  # Private message
            self.on_PRI(data['character'], data['message'])

        elif command == "MSG":  # Message in channel
            self.on_MSG(data['character'], data['message'], data['channel'])

        elif command == "LRP":  # Ad in channel
            self.on_LRP(data['channel'], data['message'], data['character'])

        elif command == "RLL":  # Dice roll results
            if data['type'] == 'dice':
                self.on_RLL(data['channel'], data['type'], data['character'], data['message'], results=data['results'],
                            rolls=data['rolls'], endresult=data['endresult'])
            elif data['type'] == 'bottle':
                self.on_RLL(data['channel'], data['type'], data['character'], data['message'], target=data['target'])

        elif command == "RMO":  # Room ad mode changed
            self.on_RMO(data['mode'], data['channel'])

        elif command == "RTB":  # Real-time bridge
            if data['type'] in ["trackadd", "trackrem", "friendadd", "friendremove", "friendrequest"]:
                self.on_RTB(data['type'], name=data['name'])
            elif data['type'] == 'note':
                self.on_RTB(data['type'], sender=data['sender'], note_id=data['id'], subject=data['subject'])

        elif command == "SFC":  # Alert admins and chatops
            self.on_SFC(data)  # TODO: Add more inputs

        elif command == "STA":  # User changes status
            self.on_STA(data['status'], data['character'], data['statusmsg'])

        elif command == "SYS":  # Message generated by server
            if 'channel' in data:
                self.on_SYS(data['message'], channel=data['channel'])
            else:
                self.on_SYS(data['message'])

        elif command == "TPN":  # User typing status
            self.on_TPN(data['character'], data['status'])

        elif command == "UPT":  # Server up-time
            self.on_UPT(data['time'], data['starttime'], data['startstring'], data['accepted'], data['channels'],
                        data['users'], data['maxusers'])

        elif command == "VAR":  # Server variables
            self.on_VAR(data['variable'], data['value'])

    def send_message(self, cmd, data):
        """
        Despite the name, this doesn't immediately send out a message. Instead, it adds a message to be sent to the
        websocket to a queue. This message will be sent out with the send_one() function.

        :param cmd: The command to be given out, in the form of a string. Ex: "PRI"
        :param data: The data for the message in dict form. Ex: {"message": "Hello, world!", "recipient": "John Doe"}
        """
        self.buffer_lock.acquire()
        self.outgoing_buffer.append((cmd, json.dumps(data)))
        self.buffer_lock.release()

    def send_one(self):
        """
        Used to send the next message in the outgoing_buffer queue to the websocket. This is called in a periodic manner
        to prevent violation of the websocket's anti-spam timer.
        """
        self.buffer_lock.acquire()
        cmd, data = self.outgoing_buffer.pop(0)
        if (cmd != "PIN") or self.log_pings:
            self.logger.debug(">> %s %s" % (cmd, data))  # Logs every outgoing message except pings.
        self.send(cmd + " " + data)
        self.buffer_lock.release()

    def add_user(self, user):
        self.users[user.name.lower()] = user

    def remove_user(self, user):
        # for channel in self.channels:
        #     channel.left(user)

        for channel in self.channels:
            self.channels[channel].left(user)

        del self.users[user.name.lower()]

    def user_exists_by_name(self, user_name):
        return user_name.lower() in self.users

    def get_user_by_name(self, name):
        try:
            return self.users[name.lower()]
        except KeyError:
            return None

    def add_channel(self, channel):
        # self.channels.append(channel)

        self.channels[channel.id.lower()] = channel

    def channel_exists_by_id(self, channel_id):
        return channel_id.lower() in self.channels.keys()
        # is_found = False
        #
        # # for channel in self.channels:
        # #     if channel.id == channel_id:
        # #         is_found = True
        #
        # for channel in self.channels:
        #     if self.channels[channel] == channel_id.lower():
        #         is_found = True
        #
        # # return channel_id in self.channels
        # return is_found

    def get_channel_by_id(self, channel_id):
        # for channel in self.channels:
        #     if channel.id == channel_id:
        #         return channel

        try:
            return self.channels[channel_id.lower()]
        except KeyError:
            return None

        # return None

    def reconnect_stagger(self):
        self.terminate_threads()
        self.logger.info("Trying to reconnect in %d seconds (attempt number %d) ..." % (
            self.reconnect_delay, self.reconnect_attempt))
        time.sleep(self.reconnect_delay)
        if self.reconnect_delay < 120:
            self.reconnect_delay *= 2
        self.reconnect_attempt += 1

    """
    --- EVENT HANDLERS ---
    These functions will be called automatically when they are sent to us from the server. You should never have to call
    these yourself, however, you may override them in a child class. If you do, I would recommend calling super first so
    you don't break something important.
    """

    def on_ADL(self, ops):
        """
        Sends the client the current list of chatops.

        :param ops: Array of chat operator names.
        """
        pass

    def on_AOP(self, character):
        """
        The given character has been promoted to chatop.

        :param character: Name of character promoted to chat operator.
        """
        pass

    def on_BRO(self, message):
        """
        Incoming admin broadcast.

        :param message: Message broadcast by chat admin.
        """
        pass

    def on_CDS(self, channel, description):
        """
        Alerts the client that that the channel's description has changed. This is sent whenever a client sends a JCH to
        the server.

        :param channel: ID of channel getting its description changed.
        :param description: Description for the channel.
        """
        if self.channel_exists_by_id(channel):
            self.get_channel_by_id(channel).description = description
        else:
            self.logger.error("Error: Got CDS message from a channel we don't know!")

    def on_CHA(self, channels):
        """
        Sends the client a list of all public channels.
        NOTE: For public channels, ID and name are the same!

        :param channels: Array of channel dictionaries with keys {"Name", "Mode", "Characters"}.
            * "Name" is both the ID and the official name of the channel.
            * "Mode" is an enum of type "chat", "ads", or "both".
            * "Characters" is an integer representing the current population.
        """

        for channel in channels:
            if not self.channel_exists_by_id(channel['name']):
                self.add_channel(Channel(channel['name'], channel['name'], channel['characters']))
                self.get_channel_by_id(channel['name']).mode = channel['mode']
            else:
                self.get_channel_by_id(channel['name']).update(channel['name'], channel['name'], channel['characters'])

    def on_CIU(self, sender, title, name):
        """
        Invites a user to a channel.

        :param sender: Name of character sending the invite.
        :param title: The display name for the room. (ex: "Sex Driven LFRP" or "Test Room")
        :param name: The channel ID. (ex: "Sex Driven LFRP" or "ADH-c7fc4c15c858dd76d860")
        """
        pass

    def on_CBU(self, operator, channel, character):
        """
        Removes a user from a channel, and prevents them from re-entering.

        :param operator: Channel operator giving the command.
        :param channel: ID of channel the character is getting removed from.
        :param character: Name of the character getting removed.
        """
        pass

    def on_CKU(self, operator, channel, character):
        """
        Kicks a user from a channel.

        :param operator: Channel operator giving the command.
        :param channel: ID of the channel the character is getting kicked from.
        :param character: Name of the character getting kicked.
        """

        if self.channel_exists_by_id(channel):
            self.get_channel_by_id(channel).left(self.get_user_by_name(character))
        else:
            self.logger.error("Error: Got CKU message from a channel we don't know!")

    def on_COA(self, character, channel):
        """
        Promotes a user to channel operator.

        :param character: Name of character getting promoted.
        :param channel: ID of the channel the character is now operator of.
        """

        if self.channel_exists_by_id(channel):
            self.get_channel_by_id(channel).channel_ops.append(character)
        else:
            self.logger.error("Error: Got COA message from a channel we don't know!")

    def on_COL(self, channel, oplist):
        """
        Gives a list of channel ops. Sent in response to JCH.

        :param channel: ID of the channel.
        :param oplist: Array of channel operator names.

        Note: First name in oplist will be the owner. If no owner, will be "".
        """

        if oplist[0]:
            self.get_channel_by_id(channel).owner = oplist[0]

        for operator in oplist:
            if operator:
                self.get_channel_by_id(channel).channel_ops.append(operator)

    def on_CON(self, count):
        """
        After connecting and identifying you will receive a CON command, giving the number of connected users to the
        network.

        :param count: Integer for number of connected users.
        """
        pass

    def on_COR(self, character, channel):
        """
        Removes a channel operator.

        :param character: Name of character getting removed.
        :param channel: ID/name of the channel.
        """

        if self.channel_exists_by_id(channel):
            self.get_channel_by_id(channel).channel_ops.remove(character)
        else:
            self.logger.error("Error: Got COR message from a channel we don't know!")

    def on_CSO(self, character, channel):
        """
        Sets the owner of the current channel to the character provided.

        :param character: Name of the character who now owns the channel.
        :param channel: ID/name of the channel.
        """

        if self.channel_exists_by_id(channel):
            self.get_channel_by_id(channel).owner = self.get_user_by_name(character)
        else:
            self.logger.error("Error: Got CSO message from a channel we don't know!")

    def on_CTU(self, operator, channel, length, character):
        """
        Temporarily bans a user from the channel for 1-90 minutes. A channel timeout.

        :param operator: Name of operator giving the command.
        :param channel: ID/name of the channel.
        :param length: Integer for number of minutes user is timed out.
        :param character: Name of the character being given the timeout.
        """

        if self.channel_exists_by_id(channel):
            self.get_channel_by_id(channel).left(self.get_user_by_name(character))
        else:
            self.logger.error("Error: Got CTU message from a channel we don't know!")

    def on_DOP(self, character):
        """
        The given character has been stripped of chatop status.

        :param character: Name of the character stripped of chat operator status.
        """
        pass

    def on_ERR(self, message, number):
        """
        Indicates that the given error has occurred.

        :param message: Error message given from server.
        :param number: Integer representing error number.
        """
        pass

    def on_FKS(self, characters, kinks):
        """
        Sent by as a response to the client's FKS command, containing the results of the search.

        :param characters: Array of character names from search result.
        :param kinks: Array of kink IDs from the search result.
        """
        pass

    def on_FLN(self, character):
        """
        Sent by the server to inform the client a given character went offline.

        :param character: Name of character that went offline.
        """

        user = self.get_user_by_name(character)

        if not user:
            logging.warning("Error, got FLN for user not in our list: %s" % character)
            return

        self.remove_user(user)

    def on_HLO(self, message):
        """
        Server hello command. Tells which server version is running and who wrote it.

        :param message: Message sent from the server.
        """
        pass

    def on_ICH(self, users, channel, mode):
        """

        :param users: Array of objects with the syntax {'identity'}
        :param channel: ID/name of channel.
        :param mode: Current mode for the channel. Can be "ads", "chat", or "both".
        """

        room = self.get_channel_by_id(channel)
        room.num_characters = 0

        for user in users:
            user = self.get_user_by_name(user['identity'])
            room.joined(user)

    def on_IDN(self, character):
        """
        Used to inform the client their identification is successful, and handily sends their character name along with
        it.

        :param character: Name of your own character that just joined.
        """
        pass

    def on_JCH(self, character, channel, title):
        """
        Indicates the given user has joined the given channel. This may also be the client's character.

        :param character: Character that just joined with syntax {"Identity"}.
        :param channel: ID of the channel. Same as title if public, but not if private.
        :param title: Name of the channel.
        """

        name = character['identity']

        if name.lower() == self.character_name.lower():
            # Hey, this person is us! We should check if we know this channel yet or not.
            if not self.channel_exists_by_id(channel):
                self.add_channel(Channel(channel, title, 0))

        self.get_channel_by_id(channel).joined(self.get_user_by_name(character['identity']))

    def on_KID(self, kid_type, message, key, value):
        """
        Kinks data in response to a KIN client command.

        :param kid_type: Enum of either "start", "custom", or "end".
        :param message: Message sent by server.
        :param key: Integer value. Not sure what this is yet.
        :param value: Integer value. Not sure what this is yet.
        """
        pass

    #
    def on_LCH(self, channel, character):
        """
        An indicator that the given character has left the channel. This may also be the client's character.

        :param channel: ID for the channel.
        :param character: Name of the character that's left.
        """

        self.get_channel_by_id(channel).left(self.get_user_by_name(character))

    def on_LIS(self, characters):
        """
        Sends an array of all the online characters and their gender, status, and status message.

        :param characters: Array of character arrays with format ["Name", "Gender", "Status", "Status Message"].
        """

        for user in characters:
            self.add_user(User(user[0], user[1], user[2], user[3]))

    def on_NLN(self, identity, gender, status):
        """
        A user connected.

        :param identity: Character name for user connected.
        :param gender: Gender of character connected.
        :param status: Enum for status. Should always be "online" since they just joined.
        """

        if not self.user_exists_by_name(identity):
            self.add_user(User(identity, gender, status, ''))

    def on_IGN(self, action, character=None, characters=None):
        """
        Handles the ignore list.

        :param action: String indicating what the message is telling us. Possible values may be:
            init: Sends the initial ignore list. Uses characters:[string] to send an array of character names.
            add: Acknowledges the addition of a character to the ignore list. Uses character:"string".
            delete: Acknowledges the deletion of a character from the ignore list. Uses character:"string".
        :param character: Variable used when action is 'add' or 'delete'. The name of the character.
        :param characters: Variable used when action is 'init'. Array of character names in ignore list.
        """
        if action == 'init' and characters:
            self.ignored_users = characters
        elif action == 'add' and character:
            self.ignored_users.append(character)
        elif action == 'delete' and character:
            self.ignored_users.remove(character)

    def on_FRL(self, characters):
        """
        Initial friends list.

        :param characters: Array of names of characters in friends list.
        """
        self.friends = characters

    def on_ORS(self, channels):
        """
        Gives a list of open private rooms.

        :param channels: Array of channel dictionaries with keys {"Name", "Characters", "Title"}.
            Name: ID of private room. Usually a string of random numbers and letters.
            Characters: Integer value for number of characters in the room.
            Title: Actual name of the room.
        """

        for channel in channels:
            if not self.channel_exists_by_id(channel['title']):
                self.add_channel(Channel(channel['name'], channel['title'], channel['characters']))
            else:
                self.get_channel_by_id(channel['title']).update(channel['name'], channel['title'],
                                                                channel['characters'])

    def on_PIN(self):
        """
        Ping command from the server, requiring a response, to keep the connection alive.
        """
        self.PIN()
        # self.reconnect.reset()
        self.last_ping_time = time.time()

    def on_PRD(self, prd_type, message, key, value):
        """
        Profile data commands sent in response to a PRO client command.

        :param prd_type: Enumerator of type "start", "info", "select", and "end".
        :param message: Message sent by the server.
        :param key: Integer. Not sure what this does.
        :param value: Integer. Not sure what this does.
        """
        pass

    def on_PRI(self, character, message):
        """
        A private message is received from another user.

        :param character: Name of the character sending the message.
        :param message: Message sent by the character.
        """
        pass

    def on_MSG(self, character, message, channel):
        """
        A message is received from a user in a channel.

        :param character: Name of the character sending the message.
        :param message: Message sent by the character.
        :param channel: ID of the channel.
        """
        pass

    def on_LRP(self, channel, message, character):
        """
        A roleplay ad is received from a user in a channel.

        :param channel: ID of the channel being sent the message.
        :param message: Message being sent to the channel.
        :param character: Name of the character sending the message.
        """
        pass

    def on_RLL(self, channel, rll_type, character, message, results=None, rolls=None, endresult=None, target=None):
        """
        Rolls dice or spins the bottle.

        :param channel: ID of channel the roll is happening in.
        :param rll_type: Enumerator of type "dice" or "bottle".
        :param character: Name of the character who called the command.
        :param message: The message the client should print.
        :param results: Optional 'dice' variable. Array of ints for the result for each dice.
        :param rolls: Optional 'dice' variable. An array of dice sets and added numbers.
        :param endresult: Optional 'dice' variable. The sum of all results as a single int.
        :param target: Optional 'bottle' variable. The name of who was selected.
        """
        pass

    def on_RMO(self, mode, channel):
        """
        Change room mode to accept chat, ads, or both.

        :param mode: Enumerator of type "chat", "ads", or "both".
        :param channel: ID of the channel being changed.
        """
        pass

    def on_RTB(self, rtb_type, name=None, sender=None, note_id=None, subject=None):
        """
        Real-time bridge. Indicates the user received a note or message, right at the very moment this is received.

        :param rtb_type: Enum of either "trackadd", "trackrem", "friendadd", "friendremove", "friendrequest", or "note".
        :param name: Optional variable for 'trackadd', 'trackrem', 'friendadd', 'friendremove', or 'friendrequest'. Name
        of the character involved.
        :param sender: Optional variable for 'note'. Name of the sender of the note.
        :param note_id: Optional variable for 'note'. Integer ID for the note, used to link to the contents of the note.
        :param subject: Optional variable for 'note'. Subject title for the note received.
        """
        pass

    def on_SFC(self, data):
        """
        Alerts admins and chatops (global moderators) of an issue.
        Note: Since I don't think any global mods will use this client, and it's kind of complicated,  I'm not going to
        bother with this one.

        :param data: Raw data (use only if other params do not work).
        :return:
        """
        pass

    def on_STA(self, status, character, statusmsg):
        """
        A user changed their status.

        :param status: Enumerator of type "online", "looking", "busy", "dnd", "idle", and "away".
        :param character: Name of the character setting their message.
        :param statusmsg: The custom message set by the character.
        """
        user = self.get_user_by_name(character)
        if user:
            user.update(status, statusmsg)

    def on_SYS(self, message, channel=None):
        """
        An informative autogenerated message from the server. This is also the way the server responds to some commands,
        such as RST, CIU, CBL, COL, and CUB. The server will sometimes send this in concert with a response command, as
        with SFC, COA, and COR.

        :param channel: Optional argument. ID of the channel, if the notice is related to one.
        :param message: Message sent by the server.
        """
        pass

    def on_TPN(self, character, status):
        """
        A user informs you of his typing status.

        :param character: Name of the character sending the message.
        :param status: Enumerator of type "clear", "paused", and "typing".
        """
        pass

    def on_UPT(self, current_time, start_time, start_string, accepted, channels, users, max_users):
        """

        :param current_time: POSIX timestamp of the current time.
        :param start_time: POSIX timestamp of when the server was last started.
        :param start_string: Human-readable timestamp of when the server was last started.
        :param accepted: How many connections have been accepted since last start.
        :param channels: How many channels the server recognizes.
        :param users: How many users are currently connected.
        :param max_users: The peak count of online users since last restart.
        """
        pass

    def on_VAR(self, variable, value):
        """
        Variables the server sends to inform the client about server variables.

        :param variable: Name of the variable being sent.
        :param value: The value of the variable being sent.
        """
        self.server_vars[variable] = value

        # fine tune outgoing message pump
        if variable == 'msg_flood':
            delay = float(value) * 2.5
            self.logger.debug("Fine tuned outgoing message delay to %f." % delay)
            # Increase the value by 150%, just to be safe!
            # self.outgoing_thread.set_delay(delay)
            self.message_delay = delay

    """
    --- CLIENT COMMANDS ---
    These commands are used to send messages to the server. There really shouldn't be a reason to override any of these.
    In addition, many of these are admin, chat operator, or channel operator commands. Please avoid trying to use 
    commands that you do not have the rights to use. 
    """

    def ACB(self, character):
        """
        --- This command requires chat op or higher. ---
        Request a character's account be banned from the server.

        :param character: Character to be banned.
        """
        data = {'character': character}
        self.send_message("ACB", data)

    def AOP(self, character):
        """
        --- This command is admin only. ---
        Promotes a user to be a chatop (global moderator).

        :param character: Character to be promoted.
        """
        data = {'character': character}
        self.send_message("AOP", data)

    def AWC(self, character):
        """
        --- This command requires chat op or higher. ---
        Requests a list of currently connected alts for a characters account.

        :param character: Character to search for alts of.
        """
        data = {'character': character}
        self.send_message("AWC", data)

    def BRO(self, message):
        """
        --- This command is admin only. ---
        Broadcasts a message to all connections.

        :param message: Message to broadcast.
        """
        data = {'message': message}
        self.send_message("BRO", data)

    def CBL(self, channel):
        """
        --- This command requires channel op or higher. ---
        Request the channel banlist.

        :param channel: The channel ID you want the banlist for.
        """
        data = {'channel': channel}
        self.send_message("CBL", data)

    def CBU(self, character, channel):
        """
        --- This command requires channel op or higher. ---
        Bans a character from a channel.

        :param character: Character to be banned from the room.
        :param channel:  The ID for the channel you want the character banned from.
        """
        data = {'character': character, 'channel': channel}
        self.send_message("CBU", data)

    def CCR(self, channel):
        """
        Create a private, invite-only channel.

        :param channel: The name for the channel you want to create.
        """
        data = {'channel': channel}
        self.send_message("CCR", data)

    def CDS(self, channel, description):
        """
        --- This command requires channel op or higher. ---
        Changes a channel's description.

        :param channel: Channel ID for
        :param description:
        """
        data = {'channel': channel, 'description': description}
        self.send_message("CDS", data)

    def CHA(self):
        """
        Request a list of all public channels.
        """
        self.send_message("CHA", {})

    def CIU(self, channel, character):
        """
        --- This command requires channel op or higher. ---
        Sends an invitation for a channel to a user.

        :param channel: ID for the channel you're sending a request for.
        :param character: Name of the character you're sending the request to.
        """
        data = {'channel': channel, 'character': character}
        self.send_message("CIU", data)

    def CKU(self, channel, character):
        """
        --- This command requires channel op or higher. ---
        Kicks a user from a channel.

        :param channel: ID for the channel you're kicking someone from.
        :param character: Name of the character you're kicking.
        """
        data = {'channel': channel, 'character': character}
        self.send_message("CKU", data)

    def COA(self, channel, character):
        """
        --- This command requires channel op or higher. ---
        Request a character be promoted to channel operator

        :param channel: ID for channel.
        :param character: Name of the promoted character.
        """
        data = {'channel': channel, 'character': character}
        self.send_message("COA", data)

    def COL(self, channel):
        """
        Requests the list of channel ops (channel moderators).

        :param channel: ID for the channel.
        """
        data = {'channel': channel}
        self.send_message("COL", data)

    def COR(self, channel, character):
        """
        --- This command requires channel op or higher. ---
        Demotes a channel operator (channel moderator) to a normal user.

        :param channel: Channel ID
        :param character: Character getting demoted.
        """
        data = {'channel': channel, 'character': character}
        self.send_message("COR", data)

    def CRC(self, channel):
        """
        --- This command is admin only. ---
        Creates an official channel.

        :param channel: Channel name, I assume?
        """
        data = {'channel': channel}
        self.send_message("CRC", data)

    def CSO(self, character, channel):
        """
        --- This command requires channel op or higher. ---
        Set a new channel owner.

        :param character: Name of character
        :param channel: ID of channel
        """
        data = {'character': character, 'channel': channel}
        self.send_message("CSO", data)

    def CTU(self, channel, character, length):
        """
        --- This command requires channel op or higher. ---
        Temporarily bans a user from the channel for 1-90 minutes. A channel timeout.

        :param channel: Channel ID
        :param character: Character to be banned
        :param length: Length of time in minutes
        """
        data = {'channel': channel, 'character': character, 'length': length}
        self.send_message("STU", data)

    def CUB(self, channel, character):
        """
        --- This command requires channel op or higher. ---
        Unbans a user from a channel.

        :param channel: Channel ID
        :param character: Character to be unbanned
        """
        data = {'channel': channel, 'character': character}
        self.send_message("CUB", data)

    def DOP(self, character):
        """
        --- This command is admin only. ---
        Demotes a chatop (global moderator).

        :param character: Character to be demoted.
        """
        data = {'character': character}
        self.send_message("DOP", data)
        pass

    def FKS(self, kinks, genders, orientations, languages, furryprefs, roles):
        """
        Search for characters fitting the user's selections. Kinks is required, all other parameters are optional.

        Raw sample:
        FKS {
        "kinks":["523","66"],
        "genders":["Male","Maleherm"],
        "orientations":["Gay","Bi - male preference","Bisexual"],
        "languages":["Dutch"],
        "furryprefs":["Furs and / or humans","Humans ok, Furries Preferred","No humans, just furry characters"],
        roles:["Always dominant", "Usually dominant"]
        }

        :param kinks: identified by kinkids, available here, along with the full list of other parameters.
                        http://www.f-list.net/json/chat-search-getfields.json?ids=true
        :param genders: can be any of "Male", "Female", "Transgender", "Herm", "Shemale", "Male-Herm", "Cunt-boy",
                        "None"
        :param orientations:can be any of "Straight", "Gay", "Bisexual", "Asexual", "Unsure", "Bi - male preference",
                        "Bi - female preference", "Pansexual", "Bi-curious"
        :param languages: can be any of "Dutch", "English", "French", "Spanish", "German", "Russian", "Chinese",
                        "Japanese", "Portuguese", "Korean", "Arabic", "Italian", "Swedish", "Other"
        :param furryprefs: can be any of "No furry characters, just humans", "No humans, just furry characters",
                        "Furries ok, Humans Preferred", "Humans ok, Furries Preferred", "Furs and / or humans"
        :param roles: can be any of "Always dominant", "Usually dominant", "Switch", "Usually submissive",
                        "Always submissive", "None"
        """
        # TODO: Finish writing FKS command.
        self.logger.debug("Warning: FKS command not supported yet!")
        pass

    def IDN(self, character):
        """
        This command is used to identify with the server.
        If you send any commands before identifying, you will be disconnected.

        :param character: Name of character you're logging in as.
        """
        data = {'account': self.account,
                'character': character,
                'ticket': self.ticket,
                'cname': self.client_name,
                'cversion': '0.1.0',
                'method': 'ticket'}

        self.send_message("IDN", data)

    def IGN(self, action, character):
        """
        A multi-faceted command to handle actions related to the ignore list. The server does not actually handle much
        of the ignore process, as it is the client's responsibility to block out messages it receives from the server
        if that character is on the user's ignore list.

        :param action: Enum with the following options...
            add: adds the character to the ignore list
            delete: removes the character from the ignore list
            notify: notifies the server that character sending a PRI has been ignored
            list: returns full ignore list. Does not take 'character' parameter.
        :param character: Character involved in the action. If action = "list", either leave blank or use None.
        """

        if action == "list":
            data = {"action": action}
        else:
            data = {"action": action, "character": character}

        self.send_message("IGN", data)

    def JCH(self, channel):
        """
        Send a channel join request.

        :param channel: Channel ID
        """
        self.send_message("JCH", {'channel': channel})

    def KIC(self, channel):
        """
        --- This command requires chat op or higher. ---
        Deletes a channel from the server.Private channel owners can destroy their own channels, but it isn't officially
        supported to do so.

        :param channel: ID of channel.
        """
        self.send_message("KIC", {'channel': channel})

    def KIK(self, character):
        """
        --- This command requires chat op or higher. ---
        Request a character be kicked from the server.

        :param character: Name of character being kicked.
        """
        self.send_message("KIK", {'character': character})

    def KIN(self, character):
        """
        Request a list of a user's kinks.

        :param character: Name of character.
        """
        self.send_message("KIN", {'character': character})

    def LCH(self, channel):
        """
        Request to leave a channel.

        :param channel: ID of channel
        """
        self.send_message("LCH", {'channel': channel})

    def LRP(self, channel, message):
        """
        Sends a chat ad to all other users in a channel.

        :param channel: ID of channel
        :param message: Message to be sent
        """
        data = {'channel': channel, 'message': message}
        self.send_message("LRP", data)

    def MSG(self, channel, message):
        """
        Sends a message to all other users in a channel.

        :param channel: Channel ID
        :param message: Message to be sent
        """
        data = {'channel': channel, 'message': message.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")}
        self.send_message("MSG", data)

    def ORS(self):
        """
        Request a list of open private rooms.
        """
        self.send_message("ORS", {})

    def PIN(self):
        """
        Sends a ping response to the server. These requests usually come every 30 seconds. Failure to respond means
        disconnection. Sending multiple pings within 10 seconds will also disconnect you.
        """
        self.send_message("PIN", {})

    def PRI(self, recipient, message):
        """
        Sends a private message to another user.

        :param recipient: Name of character receiving message
        :param message: Message to be sent
        """
        data = {'recipient': recipient, 'message': message.replace("&lt;", "<").replace("&gt;", ">")}
        self.send_message("PRI", data)

    def PRO(self, character):
        """
        Requests some of the profile tags on a character, such as Top/Bottom position and Language Preference.

        :param character: Name of character you're getting tags of
        """
        self.send_message("PRO", {'character': character})

    def RLL(self, channel, dice):
        """
        Roll dice or spin the bottle.

        :param channel: ID of channel
        :param dice: Enum of the following values:
                    bottle: selects one person in the room, other than the person sending the command.
                    #d##: rolls # dice with ## sides, each.
                    #d##+#d##: rolls more than one size of dice.
                    #d##+###: adds a number (###) to the roll.
        """
        data = {'channel': channel, 'dice': dice}
        self.send_message("RLL", data)
        pass

    def RLD(self):
        """
        I have no idea how this command is used. It's chat-op only anyway so idgaf.
        """
        pass

    def RMO(self, channel, mode):
        """
        --- This command requires channel op or higher. ---
        Change room mode to accept chat, ads, or both.

        :param channel: ID of channel
        :param mode: Enum of following values:
                    chat: Show only MSG.
                    ads: Show only LRP.
                    both: Show MSG and LRP.
        """
        data = {'channel': channel, 'mode': mode}
        self.send_message("RMO", data)

    def RST(self, channel, status):
        """
        --- This command requires channel op or higher. ---
        Sets a private room's status to closed or open. ("private" or "public")

        :param channel: ID of channel
        :param status: Enum of following values:
                        private: Only those who are invited can join!
                        public: Anybody can join!
        """
        data = {'channel': channel, 'status': status}
        self.send_message("RST", data)

    def RWD(self, character):
        """
        --- This command is admin only. ---
        Rewards a user, setting their status to 'crown' until they change it or log out.

        :param character:
        """
        self.send_message("RWD", {'character': character})

    def SFC(self, action, report, character):
        """
        Alerts admins and chatops (global moderators) of an issue.

        The webclients also upload logs and have a specific formatting to "report".
        It is suspected that third-party clients cannot upload logs.

        :param action: the type of SFC. The client will always send "report".
        :param report: The user's complaint
        :param character: The character being reported
        """
        # TODO: Finish SFC command.
        self.logger.debug("Warning: SFC command not supported yet!")
        pass

    def STA(self, status, statusmsg):
        """
        Request a new status be set for your character.

        :param status: Valid values are "online", "looking", "busy", "dnd", "idle", and "away"
        :param statusmsg: Status message to be set
        """
        data = {'status': status, 'statusmsg': statusmsg}
        self.send_message("STA", data)

    def TMO(self, character, timeout_time, reason):
        """
        --- This command requires chat op or higher. ---
        Times out a user for a given amount minutes.

        :param character: Character to be timed out
        :param timeout_time: Duration of timeout in minutes, from 1 to 90
        :param reason: Reason for timeout
        """
        pass

    def TPN(self, character, status):
        """
        "User ___ is typing/stopped typing/has entered text" for private messages.

        It is assumed a user is no longer typing after a private message has been sent, so there is no need to send a
        TPN of clear with it.

        :param character: Character that you're typing to.
        :param status: Enum of "clear", "paused", and "typing".
        """
        data = {'character': character, 'status': status}
        self.send_message("TPN", data)

    def UNB(self, character):
        """
        --- This command requires chat op or higher. ---
        Unbans a character's account from the server.

        :param character: Character to be unbanned
        """
        self.send_message("UNB", {'character': character})

    def UPT(self):
        """
        Requests info about how long the server has been running, and some stats about usage.
        """
        self.send_message("UPT", {})

    """
    --- JSON ENDPOINT COMMANDS ---
    These commands access F-List's JSON data. Most JSON commands require a ticket, which can be fetched with the 
    get_ticket() function. These commands will return the JSON data retrieved in the form of a dictionary object, which
    can be further broken down into useful information. Be careful not to spam these commands!
    """

    @staticmethod
    def send_JSON_request(url, data=None):
        if data is None:
            data = {}
        data_enc = urllib.parse.urlencode(data)
        data_enc = data_enc.encode("UTF-8")

        response = urllib.request.urlopen(url, data_enc)
        return json.loads(response.read().decode("UTF-8"))

    def get_character_profile_data(self, name):
        return self.send_JSON_request(
            'https://www.f-list.net/json/api/character-data.php',
            {
                'account': self.account,
                'ticket': self.get_ticket(),
                'name': name
            }
        )

    def get_character_friends(self, name):
        return self.send_JSON_request(
            'https://www.f-list.net/json/api/character-friends.php',
            {
                'account': self.account,
                'ticket': self.get_ticket(),
                'name': name
            }
        )

    def get_character_images(self, name):
        return self.send_JSON_request(
            'https://www.f-list.net/json/api/character-images.php',
            {
                'account': self.account,
                'ticket': self.get_ticket(),
                'name': name
            }
        )

    def get_character_memo(self, name):
        return self.send_JSON_request(
            'https://www.f-list.net/json/api/character-memo-get2.php',
            {
                'account': self.account,
                'ticket': self.get_ticket(),
                'target': name
            }
        )

    def save_character_memo(self, name, memo):
        return self.send_JSON_request(
            'https://www.f-list.net/json/api/character-memo-get2.php',
            {
                'account': self.account,
                'ticket': self.get_ticket(),
                'target_name': name
            }
        )

    def get_friend_bookmark_list(self, bookmarklist=False, friendlist=False, requestlist=False, requestpending=False):
        data = {"account": self.account,
                "ticket": self.get_ticket()}

        if bookmarklist:
            data['bookmarklist'] = 'true'
        if friendlist:
            data['friendlist'] = 'true'
        if requestlist:
            data['requestlist'] = 'true'
        if requestpending:
            data['requestpending'] = 'true'

        return self.send_JSON_request('https://www.f-list.net/json/api/friend-list.php', data)

    def get_friend_list(self):
        return self.get_friend_bookmark_list(friendlist=True)['friendlist']

    def get_bookmark_list(self):
        return self.get_friend_bookmark_list(bookmarklist=True)['bookmarklist']

    def get_friend_request_list(self):
        return self.get_friend_bookmark_list(requestlist=True)['requestlist']

    def get_friend_pending_list(self):
        return self.get_friend_bookmark_list(requestpending=True)['requestpending']

    def add_bookmark(self, name):
        return self.send_JSON_request(
            'https://www.f-list.net/json/api/bookmark-add.php',
            {
                'account': self.account,
                'ticket': self.get_ticket(),
                'name': name
            }
        )

    def remove_bookmark(self, name):
        return self.send_JSON_request(
            'https://www.f-list.net/json/api/bookmark-remove.php',
            {
                'account': self.account,
                'ticket': self.get_ticket(),
                'name': name
            }
        )

    def remove_friend(self, source_name, dest_name):
        return self.send_JSON_request(
            'https://www.f-list.net/json/api/friend-remove.php',
            {
                "account": self.account,
                "ticket": self.get_ticket(),
                "source_name": source_name,
                "dest_name": dest_name
            }
        )

    def accept_friend_request(self, request_id):
        return self.send_JSON_request(
            'https://www.f-list.net/json/api/request-accept.php',
            {
                "account": self.account,
                "ticket": self.get_ticket(),
                "request_id": request_id
            }
        )

    def deny_friend_request(self, request_id):
        return self.send_JSON_request(
            'https://www.f-list.net/json/api/request-deny.php',
            {
                "account": self.account,
                "ticket": self.get_ticket(),
                "request_id": request_id
            }
        )

    def cancel_friend_request(self, request_id):
        return self.send_JSON_request(
            'https://www.f-list.net/json/api/request-cancel.php',
            {
                "account": self.account,
                "ticket": self.get_ticket(),
                "request_id": request_id
            }
        )

    def send_friend_request(self, source, target):
        return self.send_JSON_request(
            'https://www.f-list.net/json/api/request-send2.php',
            {
                "account": self.account,
                "ticket": self.get_ticket(),
                "source": source,
                "target": target
            }
        )
