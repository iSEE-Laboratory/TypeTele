import base64
import json
import os
import threading
import time
from queue import Queue
from collections import deque

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

from tencentcloud.asr.v20190614 import asr_client, models
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile

class AsrServer:
    def __init__(self, cfg=None):
        if cfg is None:
            cfg = self._get_default_config()
        
        self.cfg = cfg
        self.verbose = cfg["verbose"]
        
        self.secret_id = cfg['credentials']['secret_id']
        self.secret_key = cfg['credentials']['secret_key']
        
        self.CHANNELS = cfg['audio']['channels']
        self.RATE = cfg['audio']['sample_rate']
        self.CHUNK_DURATION = cfg['audio']['chunk_duration']
        
        self.SILENCE_THRESHOLD = cfg['vad']['silence_threshold']
        self.MIN_AUDIO_LENGTH = cfg['vad']['min_audio_length']
        self.MAX_SILENCE_DURATION = cfg['vad']['max_silence_duration']
        
        self.audio_queue = Queue()
        self.is_recording = False
        self.is_running = False
        self.current_recording = []
        self.voice_detected = False
        self.silence_start_time = 0
        self.voice_start_time = 0
        
        self.result_queue = Queue(maxsize=1)
        
        self.have_new_result = False
        self._result_lock = threading.Lock()
        
        self.record_thread = None
        self.process_thread = None
        
        self._init_client()

        if cfg.get('test_microphone', True):
            self._test_microphone_volume()
    
    def _get_default_config(self):
        return {
            'credentials': {
                'secret_id': "YOUR_SECRET_ID",
                'secret_key': "YOUR_SECRET_KEY"
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
        }

    def _test_microphone_volume(self) -> int:
        CHUNK = int(self.CHUNK_DURATION * self.RATE)
        CHANNELS = self.CHANNELS
        RATE = self.RATE
        TEST_DURATION = 5

        print("Opening microphone... testing for 5 seconds")
        
        volumes = deque(maxlen=50)
        
        print("=== Microphone Volume Test ===")
        print("Please speak or remain silent in different environments to observe volume changes")
        print("This will help you set an appropriate silence threshold")
        print("-" * 50)
        
        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f"Audio stream status: {status}")
            
            rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))
            volumes.append(rms)
            
            if volumes:
                avg_volume = np.mean(volumes)
                max_volume = np.max(volumes) if volumes else 0
                min_volume = np.min(volumes) if volumes else 0
                
                bar_length = int(rms / 0.01)
                bar = "█" * min(bar_length, 50)
                
                print(f"\rCurrent Volume: {rms:6.3f} |{bar:<50}| Avg: {avg_volume:6.3f} Max: {max_volume:6.3f} Min: {min_volume:6.3f}", end="")

        try:
            with sd.InputStream(
                callback=audio_callback,
                channels=CHANNELS,
                samplerate=RATE,
                blocksize=CHUNK,
                dtype=np.float32
            ):
                print("Microphone ready, starting audio capture...")
                time.sleep(TEST_DURATION)
                
        except sd.PortAudioError as e:
            print(f"Cannot open microphone: {e}")
            print("Please check if the microphone device is available")
            return 0
        
        print("\n" + "=" * 50)
        print("Test finished")
        
        if volumes:
            all_volumes = list(volumes)
            avg_volume = np.mean(all_volumes)
            max_volume = np.max(all_volumes)
            min_volume = np.min(all_volumes)
            
            print(f"Statistics:")
            print(f"  Avg Volume: {avg_volume:.3f}")
            print(f"  Max Volume: {max_volume:.3f}")
            print(f"  Min Volume: {min_volume:.3f}")
            
            suggested_threshold = avg_volume + (max_volume - avg_volume) * 0.3
            
            print(f"\nSuggested silence threshold settings:")
            print(f"  1. Quiet environment: {min_volume * 1.5:.3f}")
            print(f"  2. Normal environment: {suggested_threshold:.3f}")
            print(f"  3. Noisy environment: {max_volume * 0.8:.3f}")
            
            print("\nPlease select a threshold option (1, 2, 3):")
            choice = input("Enter option: ").strip()
            
            if choice == "1":
                selected_threshold = min_volume * 1.5
            elif choice == "2":
                selected_threshold = suggested_threshold
            elif choice == "3":
                selected_threshold = max_volume * 0.8
            else:
                print("Invalid selection, using default normal environment threshold")
                selected_threshold = suggested_threshold
            
            self.SILENCE_THRESHOLD = int(selected_threshold * 120000)
            print(f"Selected threshold: {self.SILENCE_THRESHOLD:.3f}")

        else:
            print("No audio data collected, please check microphone connection")
            self.SILENCE_THRESHOLD = 500
        
    
    def _init_client(self):
        try:
            cred = credential.Credential(self.secret_id, self.secret_key)
            
            httpProfile = HttpProfile()
            httpProfile.endpoint = self.cfg['tencent']['endpoint']
            
            clientProfile = ClientProfile()
            clientProfile.httpProfile = httpProfile
            
            self.client = asr_client.AsrClient(
                cred, 
                self.cfg['tencent']['region'], 
                clientProfile
            )
            
            print("Tencent Cloud ASR client initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Tencent Cloud client: {e}")
            raise e
    
    def _calculate_volume(self, audio_data):
        try:
            if isinstance(audio_data, np.ndarray):
                rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
            else:
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
            return rms
        except Exception as e:
            print(f"Error calculating volume: {e}")
            return 0
    
    def _is_silence(self, audio_data):
        volume = self._calculate_volume(audio_data)
        return volume < self.SILENCE_THRESHOLD
    
    def audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"Audio status warning: {status}")
        
        current_time = time.time()
        is_silent = self._is_silence(indata)

        if not is_silent:
            if not hasattr(self, 'voice_detected') or not self.voice_detected:
                self.voice_detected = True
                self.voice_start_time = current_time
                self.silence_start_time = 0
                if self.verbose:
                    print("Voice detected, starting recording...")
            
            self.current_recording.append(indata.copy())
            self.silence_start_time = 0
            
        else:
            if hasattr(self, 'voice_detected') and self.voice_detected:
                if self.silence_start_time == 0:
                    self.silence_start_time = current_time
                    if self.verbose:
                        print("Silence started...")
                
                silence_duration = current_time - self.silence_start_time
                
                if silence_duration < self.MAX_SILENCE_DURATION:
                    self.current_recording.append(indata.copy())
                else:
                    if self.verbose:
                        print(f"Silence exceeded {self.MAX_SILENCE_DURATION}s, stopping recording")
                    
                    if self.current_recording:
                        audio_data = np.concatenate(self.current_recording, axis=0)
                        total_duration = len(audio_data) / self.RATE
                        
                        if total_duration >= self.MIN_AUDIO_LENGTH:
                            if self.verbose:
                                print(f"Recording finished, duration: {total_duration:.2f}s, sending for recognition...")
                            self.audio_queue.put(audio_data)
                        else:
                            if self.verbose:
                                print(f"Recording too short ({total_duration:.2f}s), discarded")
                    
                    self.current_recording = []
                    self.voice_detected = False
                    self.silence_start_time = 0
                    if self.verbose:
                        print("Waiting for voice input...")
    
    def _record_audio(self):
        if self.verbose:
            print("Starting smart recording detection...")
            print("Waiting for voice input...")
        
        self.voice_detected = False
        self.silence_start_time = 0
        self.current_recording = []
        
        chunk_frames = int(self.RATE * self.CHUNK_DURATION)
        
        try:
            with sd.InputStream(
                samplerate=self.RATE,
                channels=self.CHANNELS,
                dtype='int16',
                blocksize=chunk_frames,
                callback=self.audio_callback
            ):
                while self.is_recording:
                    time.sleep(0.1)
        except Exception as e:
            print(f"Recording error: {e}")
        
        print("Recording thread finished")
    
    def _save_wav_file(self, audio_data, filename):
        try:
            if isinstance(audio_data, np.ndarray):
                if audio_data.dtype != np.int16:
                    audio_data = (audio_data * 32767).astype(np.int16)
                if audio_data.ndim > 1:
                    audio_data = audio_data.flatten()
            else:
                audio_data = np.frombuffer(audio_data, dtype=np.int16)
            
            wavfile.write(filename, self.RATE, audio_data)
        except Exception as e:
            print(f"Failed to save WAV file: {e}")
    
    def _recognize_audio_data(self, audio_data):
        try:
            temp_filename = "temp_audio.wav"
            self._save_wav_file(audio_data, temp_filename)
            
            with open(temp_filename, "rb") as f:
                wav_data = f.read()
            audio_base64 = base64.b64encode(wav_data).decode('utf-8')
            
            req = models.SentenceRecognitionRequest()
            params = {
                "EngSerViceType": self.cfg['tencent']['engine_service_type'],
                "SourceType": 1,
                "VoiceFormat": "wav",
                "UsrAudioKey": f"realtime-{int(time.time())}",
                "Data": audio_base64,
                "DataLen": len(wav_data)
            }
            req.from_json_string(json.dumps(params))
            
            resp = self.client.SentenceRecognition(req)
            
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            
            return resp.Result if resp.Result else ""
            
        except TencentCloudSDKException as err:
            print(f"Recognition request failed: {err}")
            return ""
        except Exception as e:
            print(f"Error during recognition: {e}")
            return ""
    
    def _process_audio(self):
        while self.is_running:
            try:
                if not self.audio_queue.empty():
                    audio_data = self.audio_queue.get(timeout=0.5)
                    
                    if self.verbose:
                        print("Calling Tencent Cloud API for recognition...")
                    result = self._recognize_audio_data(audio_data)
                    if result.strip():
                        if self.verbose:
                            print(f"Recognition Result: {result}")
                        
                        with self._result_lock:
                            if not self.result_queue.empty():
                                try:
                                    self.result_queue.get_nowait()
                                except:
                                    pass
                            
                            self.result_queue.put(result)
                            self.have_new_result = True
                    else:
                        if self.verbose:
                            print("API returned empty result")
                else:
                    time.sleep(0.1)
            except Exception as e:
                if self.is_running:
                    print(f"Error processing audio: {e}")
                time.sleep(0.1)
        
        print("Audio processing thread finished")
    
    def set_silence_threshold(self, threshold):
        self.SILENCE_THRESHOLD = threshold
        print(f"Silence threshold set to: {threshold}")
    
    def set_silence_duration(self, duration):
        self.MAX_SILENCE_DURATION = duration
        print(f"Max silence duration set to: {duration}s")
    
    def start(self):
        if self.is_running:
            print("Speech recognition is already running!")
            return False
        
        print("=== Intelligent Continuous Speech Recognition System ===")
        print("Smart voice segment detection enabled")
        print(f"Silence threshold: {self.SILENCE_THRESHOLD}")
        print(f"Max silence interval: {self.MAX_SILENCE_DURATION}s")
        print(f"Min audio length: {self.MIN_AUDIO_LENGTH}s")
        print("Continuous recording mode: Start on voice, stop on silence")
        print("Avoid sentence fragmentation, maintain speech integrity")
        print("-" * 50)
        
        self.is_recording = True
        self.is_running = True
        
        self.record_thread = threading.Thread(target=self._record_audio, daemon=True)
        self.record_thread.start()
        
        self.process_thread = threading.Thread(target=self._process_audio, daemon=True)
        self.process_thread.start()
        
        print("Real-time speech recognition started!")
        return True
    
    def stop(self):
        print("Stopping recording and processing threads...")
        self.is_recording = False
        self.is_running = False
        
        if self.record_thread and self.record_thread.is_alive():
            print("Waiting for recording thread to finish...")
            self.record_thread.join(timeout=1.0)
            
        if self.process_thread and self.process_thread.is_alive():
            print("Waiting for processing thread to finish...")
            self.process_thread.join(timeout=1.0)
            
        print("Real-time speech recognition stopped")
    
    def get(self):
        try:
            with self._result_lock:
                if self.has_new_result:
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

def main():
    cfg = {
        'verbose': True,
        'credentials': {
            'secret_id': "YOUR_SECRET_ID",
            'secret_key': "YOUR_SECRET_KEY"
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
        }
    }
    
    asr = None
    
    try:
        asr = AsrServer(cfg)
        
        asr.start()
        
        print("\n=== Real-time Speech Recognition Running ===")
        print("Press Ctrl+C to exit")
        
        while True:
            if asr.has_new_result():
                result = asr.get()
                if result:
                    print(f"Speech Recognition: {result}")
            
            time.sleep(0.1)
        
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"Program runtime error: {e}")
    finally:
        print("Cleaning up resources...")
        if asr is not None:
            try:
                asr.stop()
            except Exception as e:
                print(f"Error cleaning up ASR: {e}")
        
        print("Program exited completely")

if __name__ == '__main__':
    main()