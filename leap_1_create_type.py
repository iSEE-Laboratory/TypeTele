import os
import numpy as np

from leap_hand_utils.leap_node import LeapNode

# Hand category for type library organization
HAND_CATEGORY = "leap"

class LeapCreateType:
    """
    Command-line interface for recording LEAP Hand gesture types.
    
    This class manages the recording of open and close positions for hand gestures
    and saves them to the TypeLibrary for later use in teleoperation tasks.
    """
    
    def __init__(self, cfg):
        """
        Initialize the gesture recorder.
        
        Args:
            cfg (dict): Configuration dictionary containing 'leap_cfg' with hardware parameters
        """
        self.cfg = cfg
        self.leap_node = None
        self.open_pos = None  # First line (open position)
        self.close_pos = None  # Second line (close position)
        self.init_leap()

    def init_leap(self):
        """Initialize hardware node and enable free drag mode."""
        print("Initializing LEAP Hand...")
        self.leap_node = LeapNode(self.cfg["leap_cfg"])
        self.leap_node.enable_free_drag_mode()
        print("LEAP Hand entered free drag mode")

    def _get_current_leap_pos(self):
        """Read current 16 joint positions and convert to save format."""
        current_pos = self.leap_node.read_pos()  # Raw 16-length position
        joints = current_pos - 3.14159
        reorder_index = np.array([9, 8, 10, 11, 5, 4, 6, 7, 1, 0, 2, 3, 12, 13, 14, 15])
        inverse_index = np.argsort(reorder_index)
        reordered = np.array(joints)[inverse_index]
        return reordered

    def record_open(self):
        """Record the open position of the gesture."""
        pos = self._get_current_leap_pos()
        self.open_pos = pos
        print("OPEN position recorded:")
        print(pos)

    def record_close(self):
        """Record the close position of the gesture."""
        pos = self._get_current_leap_pos()
        self.close_pos = pos
        print("CLOSE position recorded:")
        print(pos)

    def save_data(self):
        """
        Save recorded gesture data to file.
        
        Prompts user for gesture name and saves both open and close positions
        to TypeLibrary/<HAND_CATEGORY>/<gesture_name>.txt
        """
        if self.open_pos is None or self.close_pos is None:
            print("Error: Please record both OPEN (ro) and CLOSE (rc) positions first")
            return

        type_name = input("Enter gesture name: ").strip()
        if not type_name:
            print("Gesture name cannot be empty")
            return

        # Directory structure: TypeLibrary/<HAND_CATEGORY>/
        base_dir = 'TypeLibrary'
        save_dir = os.path.join(base_dir, HAND_CATEGORY)
        os.makedirs(save_dir, exist_ok=True)
        
        save_path = os.path.join(save_dir, f'{type_name}.txt')
        
        # Check if file already exists
        if os.path.exists(save_path):
            confirm = input(f"Gesture '{type_name}' already exists. Overwrite? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Save cancelled")
                return

        # Save as space-separated values, one line per position
        with open(save_path, 'w') as f:
            f.write(' '.join(map(str, self.open_pos)) + '\n')
            f.write(' '.join(map(str, self.close_pos)) + '\n')

        print(f"Gesture saved to: {save_path}")

    def reset_positions(self):
        """Reset all recorded positions."""
        self.open_pos = None
        self.close_pos = None
        print("All recordings reset")

    def print_help(self):
        """Display help information with available commands."""
        print("\nAvailable commands:")
        print("  ro     - Record OPEN position (first line)")
        print("  rc     - Record CLOSE position (second line)")
        print("  save   - Save gesture to file")
        print("  reset  - Reset all recordings")
        print("  help   - Display this help message")
        print("  quit   - Exit program")
        print()

    def run(self):
        """
        Run the command-line interaction loop.
        
        Main loop that processes user commands until quit is requested.
        Handles KeyboardInterrupt gracefully and cleans up resources on exit.
        """
        print("\n" + "="*60)
        print("LEAP Gesture Type Recorder - CLI")
        print("="*60)
        self.print_help()

        while True:
            try:
                cmd = input("\nEnter command (type 'help' for options): ").strip().lower()

                if cmd == 'ro':
                    self.record_open()
                elif cmd == 'rc':
                    self.record_close()
                elif cmd == 'save':
                    self.save_data()
                elif cmd == 'reset':
                    self.reset_positions()
                elif cmd == 'help':
                    self.print_help()
                elif cmd in ['quit', 'exit', 'q']:
                    print("Exiting...")
                    break
                elif cmd == '':
                    continue
                else:
                    print(f"Unknown command: '{cmd}'. Type 'help' for available commands")

            except KeyboardInterrupt:
                print("\n\nCtrl+C detected, exiting...")
                break
            except Exception as e:
                print(f"Error: {e}")

        # Clean up resources
        self.cleanup()

    def cleanup(self):
        """Clean up hardware resources and disable free drag mode."""
        try:
            if self.leap_node and self.leap_node.free_drag_active:
                print("Disabling free drag mode...")
                self.leap_node.disable_free_drag_mode()
                print("Free drag mode disabled")
        except Exception as e:
            print(f'Failed to disable free drag mode: {e}')


def main():
    """
    Main entry point for the LEAP gesture recorder.
    
    Initializes hardware configuration and starts the interactive CLI.
    """
    cfg = {
        "leap_cfg": {
            "curr_lim": 120,
            "kP": 150,
            "kI": 0,
            "kD": 50
        }
    }
    
    recorder = LeapCreateType(cfg)
    recorder.run()


if __name__ == '__main__':
    main()