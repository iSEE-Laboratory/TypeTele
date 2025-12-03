import sys
import time
import threading
from queue import Queue, Empty
from pynput import keyboard
import os

class KeyboardAsrServer:
    def __init__(self, cfg=None):
        self.cfg = cfg or {}
        self.verbose = cfg.get("verbose", True) if cfg else True
        
        self.is_running = False
        self.input_thread = None
        
        self.result_queue = Queue(maxsize=1)
        self._result_lock = threading.Lock()
        self.have_new_result = False
        
        self.input_buffer = ""
        self.pynput_char_queue = Queue(maxsize=10)
        self.keyboard_listener = None
        
        print("=== Keyboard Input Mode ===")
        print("Enter commands in the terminal, press Enter to send")
        print("Type 'quit' or 'exit' to exit")
        print("=" * 30)
    
    def on_release(self, key):
        if not self.is_running:
            return
            
        char = None
        try:
            char = key.char
        except AttributeError:
            if key == keyboard.Key.enter:
                char = '\n'
            elif key == keyboard.Key.backspace:
                char = '\x7f'
            elif key == keyboard.Key.esc:
                char = '\x03'
                
        if char is not None:
            try:
                self.pynput_char_queue.put_nowait(char)
            except Empty:
                pass

    def _input_loop(self):
        print("Keyboard input ready, start typing commands...")
        
        self.keyboard_listener = keyboard.Listener(
            on_release=self.on_release,
            daemon=True
        )
        self.keyboard_listener.start()
        
        while self.is_running:
            char = None
            try:
                char = self.pynput_char_queue.get_nowait()
            except Empty:
                pass
            
            if char is not None:
                if char == '\n':
                    if self.input_buffer.strip():
                        text = self.input_buffer.strip()
                        self.input_buffer = ""
                        
                        if text.lower() in ['quit', 'exit']:
                            print(f"\nExit command detected: {text}")
                            self.is_running = False
                            break
                        
                        self._put_result(text)
                        print(f"\nCommand sent: {text}")
                        print("Enter next command: ", end="", flush=True)
                    else:
                        print("\nContinue typing: ", end="", flush=True)
                
                elif char == '\x7f':
                    if self.input_buffer:
                        self.input_buffer = self.input_buffer[:-1]
                        print('\b \b', end='', flush=True)
                
                elif char == '\x03':
                    print("\nCtrl+C received, exiting...")
                    self.is_running = False
                    break
                
                else:
                    self.input_buffer += char
                    print(char, end='', flush=True)
            
            time.sleep(0.01)
            
        if self.keyboard_listener and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()

    def _put_result(self, text):
        with self._result_lock:
            if not self.result_queue.empty():
                try:
                    self.result_queue.get_nowait()
                except:
                    pass
            
            self.result_queue.put(text)
            self.have_new_result = True
    
    def start(self):
        if self.is_running:
            if self.verbose:
                print("Keyboard input is already running")
            return True
        
        self.is_running = True
        
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self.input_thread.start()
        
        if self.verbose:
            print("Keyboard input started")
        
        return True
    
    def stop(self):
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.input_thread and self.input_thread.is_alive():
            self.input_thread.join(timeout=1.0)
        
        if self.verbose:
            print("Keyboard input stopped")
    
    def get(self):
        try:
            with self._result_lock:
                if self.have_new_result:
                    result = self.result_queue.get_nowait()
                    self.have_new_result = False
                    return result
                return None
        except:
            return None
    
    def has_new_result(self):
        with self._result_lock:
            return self.have_new_result
    
    def is_running_status(self):
        return self.is_running
    
    def __del__(self):
        self.stop()


# import sys
# import time
# import threading
# from queue import Queue
# import select
# import termios
# import tty
# import os

# class KeyboardAsrServer:
#     def __init__(self, cfg=None):
#         self.cfg = cfg or {}
#         self.verbose = cfg.get("verbose", True) if cfg else True
        
#         self.is_running = False
#         self.input_thread = None
        
#         self.result_queue = Queue(maxsize=1)
#         self._result_lock = threading.Lock()
#         self.have_new_result = False
        
#         self.input_buffer = ""
        
#         print("=== Keyboard Input Mode ===")
#         print("Enter commands in the terminal, press Enter to send")
#         print("Type 'quit' or 'exit' to exit")
#         print("=" * 30)
    
#     def _non_blocking_input(self):
#         try:
#             if select.select([sys.stdin], [], [], 0.1)[0]:
#                 return sys.stdin.read(1)
#             return None
#         except:
#             return None
    
#     def _input_loop(self):
#         print("Keyboard input ready, start typing commands...")
        
#         old_settings = termios.tcgetattr(sys.stdin)
#         try:
#             tty.setcbreak(sys.stdin.fileno())
            
#             while self.is_running:
#                 char = self._non_blocking_input()
                
#                 if char:
#                     if char == '\n':
#                         if self.input_buffer.strip():
#                             text = self.input_buffer.strip()
#                             self.input_buffer = ""
                            
#                             if text.lower() in ['quit', 'exit']:
#                                 print(f"\nExit command detected: {text}")
#                                 self.is_running = False
#                                 break
                            
#                             self._put_result(text)
#                             print(f"\nCommand sent: {text}")
#                             print("Enter next command: ", end="", flush=True)
#                         else:
#                             print("\nContinue typing: ", end="", flush=True)
                    
#                     elif char == '\x7f':
#                         if self.input_buffer:
#                             self.input_buffer = self.input_buffer[:-1]
#                             print('\b \b', end='', flush=True)
                    
#                     elif char == '\x03':
#                         print("\nCtrl+C received, exiting...")
#                         self.is_running = False
#                         break
                    
#                     else:
#                         self.input_buffer += char
#                         print(char, end='', flush=True)
                
#                 time.sleep(0.01)
                
#         finally:
#             termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
#     def _put_result(self, text):
#         with self._result_lock:
#             if not self.result_queue.empty():
#                 try:
#                     self.result_queue.get_nowait()
#                 except:
#                     pass
            
#             self.result_queue.put(text)
#             self.have_new_result = True
    
#     def start(self):
#         if self.is_running:
#             if self.verbose:
#                 print("Keyboard input is already running")
#             return True
        
#         self.is_running = True
        
#         self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
#         self.input_thread.start()
        
#         if self.verbose:
#             print("Keyboard input started")
        
#         return True
    
#     def stop(self):
#         if not self.is_running:
#             return
        
#         self.is_running = False
        
#         if self.input_thread and self.input_thread.is_alive():
#             self.input_thread.join(timeout=1.0)
        
#         if self.verbose:
#             print("Keyboard input stopped")
    
#     def get(self):
#         try:
#             with self._result_lock:
#                 if self.have_new_result:
#                     result = self.result_queue.get_nowait()
#                     self.have_new_result = False
#                     return result
#                 return None
#         except:
#             return None
    
#     def has_new_result(self):
#         with self._result_lock:
#             return self.have_new_result
    
#     def is_running_status(self):
#         return self.is_running
    
#     def __del__(self):
#         self.stop()