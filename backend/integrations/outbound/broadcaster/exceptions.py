class BroadcasterError(Exception):
    """
    `status_code`: codi HTTP de la resposta de Broadcaster, si n'hi ha.
    `user_message`: motiu que pot veure l'usuari (traduït), si l'error és de les dades de l'SMS.
    """

    def __init__(self, message="", status_code=None, user_message=None):
        super().__init__(message)
        self.status_code = status_code
        self.user_message = user_message
