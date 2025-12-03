import leap_hand_utils.leap_hand_utils as lhu
from leap_hand_utils.dynamixel_client import *
import numpy as np
import os
import pickle
import time
import threading


class LeapNode:
    def __init__(self, cfg):
        self.cfg = cfg
        self.curr_lim = cfg.get("curr_lim", 200)
        self.kP = cfg.get("kP", 250)
        self.kI = cfg.get("kI", 0)
        self.kD = cfg.get("kD", 100)
        self.init_pos = cfg.get("init_pos", None)

        if self.init_pos is not None:
            self.prdev_pos = self.pos = self.curr_pos = self.init_pos
        else:
            self.prdev_pos = self.pos = self.curr_pos = lhu.allegro_to_LEAPhand(np.zeros(16))

        self.motors = motors = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

        self.dxl_client = DynamixelClient(motors, '/dev/ttyUSB0', 4000000)
        self.dxl_client.connect()

        self.dxl_client.sync_write(motors, np.ones(len(motors)) * 5, 11, 1)
        self.dxl_client.set_torque_enabled(motors, True)
        self.dxl_client.sync_write(motors, np.ones(len(motors)) * self.kP, 84, 2) 
        self.dxl_client.sync_write([0, 4, 8], np.ones(3) * (self.kP * 0.75), 84, 2) 
        self.dxl_client.sync_write(motors, np.ones(len(motors)) * self.kI, 82, 2)  
        self.dxl_client.sync_write(motors, np.ones(len(motors)) * self.kD, 80, 2) 
        self.dxl_client.sync_write([0, 4, 8], np.ones(3) * (self.kD * 0.75), 80, 2)  
        self.dxl_client.sync_write(motors, np.ones(len(motors)) * self.curr_lim, 102, 2)

        self.dxl_client.write_desired_pos(self.motors, self.curr_pos)

        self.free_drag_active = False
        self.free_drag_thread = None
        self.original_curr_lim = self.curr_lim 
        self.original_kP = self.kP
        self.original_kI = self.kI
        self.original_kD = self.kD

    def set_leap(self, pose):
        self.prev_pos = self.curr_pos
        self.curr_pos = np.array(pose)
        self.dxl_client.write_desired_pos(self.motors, self.curr_pos)

    def set_allegro(self, pose):
        pose = lhu.allegro_to_LEAPhand(pose, zeros=False)
        self.prev_pos = self.curr_pos
        self.curr_pos = np.array(pose)
        self.dxl_client.write_desired_pos(self.motors, self.curr_pos)

    def set_ones(self, pose):
        pose = lhu.sim_ones_to_LEAPhand(np.array(pose))
        self.prev_pos = self.curr_pos
        self.curr_pos = np.array(pose)
        self.dxl_client.write_desired_pos(self.motors, self.curr_pos)

    def read_pos(self):
        return self.dxl_client.read_pos()

    def read_vel(self):
        return self.dxl_client.read_vel()

    def read_cur(self):
        return self.dxl_client.read_cur()

    def enable_free_drag_mode(self):
        if self.free_drag_active:
            return
        
        self.filtered_current = self.read_cur()

        self.original_curr_lim = self.curr_lim
        self.curr_lim = 30 
        self.dxl_client.sync_write(self.motors, np.ones(len(self.motors)) * self.curr_lim, 102, 2)

        self.free_drag_active = True
        self.free_drag_thread = threading.Thread(target=self._update_goal_pos_loop)
        self.free_drag_thread.start()

    def disable_free_drag_mode(self):
        if not self.free_drag_active:
            return
        self.free_drag_active = False
        if self.free_drag_thread is not None:
            self.free_drag_thread.join()
        
        self.curr_lim = self.original_curr_lim
        self.dxl_client.sync_write(self.motors, np.ones(len(self.motors)) * self.curr_lim, 102, 2)

        current_pos = self.read_pos()
        self.dxl_client.write_desired_pos(self.motors, current_pos)
        self.free_drag_thread = None

    def _update_goal_pos_loop(self):
        thresholds = np.array([0.05]*16) 
        loop_time = 0

        while self.free_drag_active:
            start_time = time.time()

            current_pos = self.read_pos()
            current_vel = self.read_vel() 
            pos_error = current_pos - self.curr_pos

            delta_pos = np.zeros(16)
            for i in range(16):
                if pos_error[i] > thresholds[i] + 0.05:
                    delta_pos[i] = current_vel[i] * loop_time * 5
                else:
                    delta_pos[i] = current_vel[i] * loop_time

            new_target_pos = current_pos + delta_pos

            pos_diff = np.abs(new_target_pos - self.curr_pos)
            update_mask = pos_diff > thresholds
            updated_positions = np.where(update_mask, new_target_pos, self.curr_pos)

            self.dxl_client.write_desired_pos(self.motors, updated_positions)
            self.curr_pos = updated_positions

            joints = updated_positions - 3.14159
            index = np.array([9, 8, 10, 11, 5, 4, 6, 7, 1, 0, 2, 3, 12, 13, 14, 15])

            inverse_index = np.argsort(index)  
            input_pos = np.array(joints)[inverse_index]

            end_time = time.time()
            loop_time = end_time - start_time