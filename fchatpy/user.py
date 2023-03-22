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
