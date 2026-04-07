import platform
from datetime import datetime

class Logger:
    ux = None
    terminal = None
    using_terminal = True


    @staticmethod
    def set_ux(ux):
        Logger.ux = ux

    @staticmethod
    def set_terminal(terminal):
        Logger.terminal = terminal

    @staticmethod
    def set_using_terminal(using: bool):
        Logger.using_terminal = using

    @staticmethod
    def log_message(message: str):
        message = Logger.add_timestamp(message)
        if Logger.ux:
            Logger.ux.log_message(message)

        if Logger.using_terminal:
            Logger.terminal.log_message(message)
        else:
            print(message)

    @staticmethod
    def log_event(event_msg: str):
        event_msg = Logger.add_timestamp(event_msg)
        if Logger.ux:
            Logger.ux.log_event(event_msg)

        if Logger.using_terminal:
            Logger.terminal.log_message(event_msg)
        else:
            print(event_msg)

    @staticmethod
    def log_error(error_msg: str):
        error_msg = "ERROR: " + error_msg
        Logger.log_message(error_msg)


    @staticmethod
    def add_timestamp(message: str):
        if platform.system() == "Windows":
            time = datetime.now().strftime("%#I:%M %p")  # e.g., 2:03 PM
        else:
            time = datetime.now().strftime("%-I:%M %p")  # e.g., 2:03 PM

        return f"[{time}] {message}"
