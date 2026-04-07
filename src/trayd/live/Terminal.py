import threading
import queue
import os


class Terminal:
    def __init__(self):
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.running = False
        self.clear_terminal = False

    def log_message(self, msg: str):
        self.output_queue.put(msg)

    def start_listen(self):
        if self.clear_terminal:
            os.system("cls")
        self.running = True
        threading.Thread(target=self.listen, daemon=True).start()

    def stop_listen(self):
        self.running = False

    def listen(self):
        try:
            while self.running:
                # wait for input to be consumed
                if not self.input_queue.empty(): 
                    continue
                self.output_all()
                print("----------------------------------")
                user_input = input("Input Command ('ux' for interface)\n > ")
                
                self.input_queue.put(user_input)
                print()

        except (KeyboardInterrupt, EOFError):
            self.running = False
            self.input_queue.put("QUIT")
            return

    def output_all(self):
        if self.clear_terminal:
            os.system("cls")
        while not self.output_queue.empty():
            msg = self.output_queue.get()
            print(msg)
    
    def is_empty(self) -> bool:
        return self.input_queue.empty()

    def query_next(self) -> str:
        return self.input_queue.get()

