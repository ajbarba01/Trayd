class Logger:
    log = True

    @staticmethod
    def log_message(*args, **kwargs):
        if Logger.log:
            print(*args, **kwargs)

    @staticmethod
    def log_error(*args, **kwargs):
        Logger.log_message("ERROR:", *args, **kwargs)
