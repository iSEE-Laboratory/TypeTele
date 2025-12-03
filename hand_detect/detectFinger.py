from .Camera import Camera
from .SingleHandDetetor import SingleHandDetector
import cv2
import numpy as np
import time
from scipy import stats
import threading
from queue import Queue
import json
import os

class FingerDetector:
    def __init__(self, cfg):
        self.hand_type = cfg.get("hand_type", "Right")
        self.selfie = cfg.get("selfie", True)
        
        self.cam = None
        self.detector = None
        self.cam = Camera(cfg["camera"])
        # self.cam.start()
        self.detector = SingleHandDetector(hand_type=self.hand_type, selfie=False)
        
        self.open_mean_angles = None
        self.closed_mean_angles = None
        self.angle_range = None
        self.is_calibrated = False
        
        self.result_queue = Queue(maxsize=1)
        
        self.running = False
        self.detection_thread = None
 
    def _detection_loop(self):
        while self.running:
            try:
                bgr = self.cam.get_frame()
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                _, joint_pos, keypoint_2d, _ = self.detector.detect(rgb=rgb)
                
                if joint_pos is not None:
                    bgr = self.detector.draw_skeleton_on_image(bgr, keypoint_2d, style="default")

                    thumb_vec = joint_pos[4] - joint_pos[0]
                    thumb_vec[0] = thumb_vec[2] = 0
                    thumb_length = np.linalg.norm(thumb_vec)
                    index_vec = joint_pos[8] - joint_pos[0]
                    index_length = np.linalg.norm(index_vec)
                    middle_vec = joint_pos[12] - joint_pos[0]
                    middle_length = np.linalg.norm(middle_vec)
                    ring_vec = joint_pos[16] - joint_pos[0]
                    ring_length = np.linalg.norm(ring_vec)
                    pinky_vec = joint_pos[20] - joint_pos[0]
                    pinky_length = np.linalg.norm(pinky_vec)

                    thumb_ratio = np.clip((thumb_length - 0.02) / (0.09 - 0.02), 0.0, 1.0)
                    index_ratio = np.clip((index_length - 0.09) / (0.17 - 0.09), 0.0, 1.0)
                    middle_ratio = np.clip((middle_length - 0.09) / (0.18 - 0.09), 0.0, 1.0)
                    ring_ratio = np.clip((ring_length - 0.07) / (0.17 - 0.07), 0.0, 1.0)
                    pinky_ratio = np.clip((pinky_length - 0.08) / (0.14 - 0.08), 0.0, 1.0)

                    finger_ratios = {
                        'thumb': 1 - thumb_ratio,
                        'index': 1 - index_ratio,
                        'middle': 1 - middle_ratio,
                        'ring': 1 - ring_ratio,
                        'pinky': 1 - pinky_ratio
                    }

                    if not self.result_queue.empty():
                        try:
                            self.result_queue.get_nowait()
                        except:
                            pass
                    
                    self.result_queue.put((finger_ratios, bgr))
                
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Detection loop error: {e}")
                time.sleep(0.1)
    
    def start(self):
        if self.running:
            print("Detection is already running!")
            return False
        
        if self.cam is None:
            self.cam = Camera()
        self.cam.start()
        
        if self.detector is None:
            self.detector = SingleHandDetector(hand_type=self.hand_type, selfie=self.selfie)
        
        self.running = True
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()
        
        print("Real-time detection started!")
        return True
    
    def stop(self):
        self.running = False
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=1.0)
        print("Real-time detection stopped!")
    
    def get(self):
        try:
            return self.result_queue.get_nowait()
        except:
            return None
    
    def is_running(self):
        return self.running
    
    def __del__(self):
        self.stop()