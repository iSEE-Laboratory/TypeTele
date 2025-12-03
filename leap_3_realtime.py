from asr.tencent_asr import AsrServer
from hand_detect.detectFinger import FingerDetector
from retrieve.retrieve import Retrieve
from leap_hand_utils.leap_node import LeapNode

import os
import time
import numpy as np
import cv2

from asr.typing_asr import KeyboardAsrServer

# Joint reordering indices for LEAP Hand consistency
_REORDER_INDEX = np.array([9, 8, 10, 11, 5, 4, 6, 7, 1, 0, 2, 3, 12, 13, 14, 15])
_INVERSE_INDEX = np.argsort(_REORDER_INDEX)

class RealTimeRunner:
    """
    Main loop integrating ASR, Hand Detection, Retrieval, and LEAP Hand control.
    Components run in separate threads/processes managed via start()/stop().
    """
    def __init__(self, cfg: dict):
        self.cfg = cfg

        # Load initial grasp primitive (absolute positions)
        self.category = cfg["type"]["category"]
        self.curr_type = cfg["type"]["type_name"]
        self.open_pos, self.close_pos = self.load_type(self.curr_type)

        # Initialize ASR
        self.asr_type = cfg["asr"].get("type", "typing")
        if self.asr_type == "tencent":
            print("[Info] Tencent ASR enabled.")
            self.asr = AsrServer(cfg["asr"])
        else:
            print("[Info] ASR disabled. Using keyboard input.")
            self.asr = KeyboardAsrServer(cfg["asr"])

        # Initialize other components
        self.finger_detector = FingerDetector(cfg["detector"])
        self.retriever = Retrieve(
            api_key=cfg["retriever"]["api_key"],
            base_url=cfg["retriever"]["base_url"],
            category=self.category
        )
        self.leap_node = LeapNode(self.cfg["leap_cfg"])

    def start(self):
        """Start all components and enter main loop."""
        self.asr.start()
        self.finger_detector.start()
        self.retriever.load_type_library()
        self.retriever.start()
        self.main_loop()

    def stop(self):
        self.asr.stop()
        self.finger_detector.stop()
        self.retriever.stop()
        cv2.destroyAllWindows()

    def change_type(self, new_type: str):
        print(f"[Info] Switching grasp type: {self.curr_type} -> {new_type}")
        self.curr_type = new_type
        self.open_pos, self.close_pos = self.load_type(self.curr_type)

    def load_type(self, type_name: str):
        """Load and decode grasp primitive (open/close poses) from file."""
        def parse_line(line: str):
            line = line.strip().strip('[]')
            parts = [p for p in line.replace(',', ' ').split() if p]
            vals = [float(p) for p in parts]
            if len(vals) != 16:
                raise ValueError(f"Invalid line length for {type_name}: {len(vals)}")
            return np.array(vals, dtype=float)

        def _decode_saved(vec: np.ndarray) -> np.ndarray:
            """Convert saved format to hardware absolute position."""
            joints = np.zeros(16, dtype=float)
            joints[_INVERSE_INDEX] = vec
            return joints + 3.14159
        
        # Resolve file path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        type_file = os.path.join(current_dir, "TypeLibrary", self.category, f"{type_name}.txt")
        
        if not os.path.exists(type_file):
            raise FileNotFoundError(f"Type file not found: {type_file}")
        
        with open(type_file, 'r', encoding='utf-8') as f:
            open_abs = _decode_saved(parse_line(f.readline()))
            close_abs = _decode_saved(parse_line(f.readline()))
            
        return open_abs, close_abs

    def main_loop(self):
        try:
            while True:
                # 1. ASR -> Retrieve
                if self.asr and self.asr.has_new_result():
                    new_query = self.asr.get()
                    if new_query:
                        print(f"[Command] New input: {new_query}")
                        # Direct switch via command
                        if new_query.startswith('/'):
                            try:
                                self.change_type(new_query[1:])
                                continue
                            except Exception as e:
                                print(f"[Error] Failed to switch type: {e}")
                        # Retrieve via LLM
                        self.retriever.retrieve(new_query)

                # 2. Retriever Result -> Switch Type
                if self.retriever.has_new_result():
                    result = self.retriever.get()
                    if result and result != self.curr_type:
                        self.change_type(result)

                # 3. Hand Detection -> Robot Control
                result = self.finger_detector.get()
                if result:
                    ratio, bgr = result
                    
                    # Define masks for finger groups
                    thumb_mask = np.array([0]*12 + [1]*4)
                    index_mask = np.array([1]*4 + [0]*12)
                    middle_mask = np.array([0]*4 + [1]*4 + [0]*8)
                    ring_mask = np.array([0]*8 + [1]*4 + [0]*4)
                    
                    # Interpolate pose based on finger flexion ratios
                    # Note: LEAP Hand typically lacks independent pinky control
                    type_pos = (
                        (self.open_pos * (1 - ratio['thumb']) + self.close_pos * ratio['thumb']) * thumb_mask +
                        (self.open_pos * (1 - ratio['index']) + self.close_pos * ratio['index']) * index_mask +
                        (self.open_pos * (1 - ratio['middle']) + self.close_pos * ratio['middle']) * middle_mask +
                        (self.open_pos * (1 - ratio['ring']) + self.close_pos * ratio['ring']) * ring_mask
                    )

                    self.leap_node.set_leap(type_pos)

                    if bgr is not None:
                        cv2.imshow("Hand Detection", bgr)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break

                time.sleep(0.01)

        except KeyboardInterrupt:
            print("Stopping...")
            self.stop()
            print("Closed.")


def run_leap():
    cfg = {
        "asr": {
            "type": "typing",  # Options: "typing" (keyboard) or "tencent" (API)
            
            # --- Tencent ASR Config ---
            "verbose": True,
            'credentials': {
                'secret_id': "your_secret_id",
                'secret_key': "your_secret_key"
            },
            'audio': {
                'channels': 1,
                'sample_rate': 16000,
                'chunk_duration': 0.1
            },
            'vad': {
                'silence_threshold': 500,
                'min_audio_length': 0.5,
                'max_silence_duration': 2.0
            },
            'tencent': {
                'endpoint': "asr.tencentcloudapi.com",
                'region': "ap-guangzhou",
                'engine_service_type': "16k_zh"
            },
            'test_microphone': True
        },
        "retriever": {
            # --- LLM / Retrieval Config ---
            "api_key": "your_api_key",
            "base_url": "https://api.deepseek.com",
            "category": "leap"
        },
        "detector": {
            "camera": {
                "camera_id": 4,  # Camera index
                "width": 640,
                "height": 480,
                "fps": 30,
                "queue_size": 1
            },
            "hand_type": "Left",
            "selfie": False,
        },
        "type": {
            "type_name": "box",
            "category": "leap"
        },
        "leap_cfg": {
            "curr_lim": 150,
            "kP": 100,
            "kI": 0,
            "kD": 150
        },
    }
    runner = RealTimeRunner(cfg)
    runner.start()


if __name__ == "__main__":
    run_leap()