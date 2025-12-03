import cv2
import time
import threading
from queue import Queue, Empty

class Camera:
    def __init__(self, cfg={}):
        self.camera_id = cfg.get("camera_id", 0)
        self.width = cfg.get("width", 640)
        self.height = cfg.get("height", 480)
        self.fps = cfg.get("fps", 30)
        self.queue_size = cfg.get("queue_size", 1)
        
        self.frame_queue = Queue(maxsize=self.queue_size)
        self.stop_event = threading.Event()
        self.capture_thread = None
        self.cap = None
        self.is_running = False
        
    def _capture_frames(self):
        self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_V4L2)
        
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        print(f"Camera started - Resolution: {self.width}x{self.height}, FPS: {self.fps}")
        
        while not self.stop_event.is_set():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except Empty:
                        pass
                self.frame_queue.put(frame)
            else:
                time.sleep(0.01)
        
        if self.cap:
            self.cap.release()
            
    def start(self):
        self.stop_event.clear()
        self.capture_thread = threading.Thread(target=self._capture_frames, daemon=True)
        self.capture_thread.start()
        self.is_running = True
        
    def stop(self):
        self.stop_event.set()
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1.0)
        self.is_running = False
        print("Camera stopped")
        
    def get_frame(self):
        try:
            return self.frame_queue.get(timeout=1.0)
        except Empty:
            return None

def demo_camera():
    camera = Camera({"camera_id": 4, "width": 640, "height": 480, "fps": 30, "queue_size": 1})
    camera.start()
    
    try:
        print("Starting camera feed, press 'q' to exit")
        while True:
            bgr = camera.get_frame()
            if bgr is not None:
                cv2.imshow('Camera Feed', bgr)
            else:
                print("No frame captured")
                time.sleep(0.1)
                
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    finally:
        camera.stop()
        cv2.destroyAllWindows()

# def two_camera():
#     camera1 = Camera({"camera_id": 0})
#     camera2 = Camera({"camera_id": 1})

#     try:
#         camera1.start()
#         camera2.start()

#         print("Starting dual camera feed, press 'q' to exit")

#         while True:
#             frame1 = camera1.get_frame()
#             frame2 = camera2.get_frame()

#             if frame1 is not None:
#                 cv2.imshow('Camera 1', frame1)

#             if frame2 is not None:
#                 cv2.imshow('Camera 2', frame2)
            
#             if cv2.waitKey(1) & 0xFF == ord('q'):
#                 break

#     finally:
#         camera1.stop()
#         camera2.stop()
#         cv2.destroyAllWindows()

if __name__ == "__main__":
    demo_camera()