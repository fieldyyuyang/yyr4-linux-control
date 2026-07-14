class ManagementError(Exception):
    pass

class ProtocolError(ManagementError):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code

class SocketError(ManagementError):
    pass
