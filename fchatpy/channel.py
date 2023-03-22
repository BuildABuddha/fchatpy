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
        self.mode = ""
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

        :param character: Character that just joined the room. Use the User object class.
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
