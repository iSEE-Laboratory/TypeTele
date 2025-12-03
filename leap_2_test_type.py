import os
import sys
import numpy as np

from leap_hand_utils.leap_node import LeapNode

HAND_CATEGORY = "leap"

# Reorder index consistent with create script
_REORDER_INDEX = np.array([9, 8, 10, 11, 5, 4, 6, 7, 1, 0, 2, 3, 12, 13, 14, 15])
_INVERSE_INDEX = np.argsort(_REORDER_INDEX)


def _decode_saved(vec: np.ndarray) -> np.ndarray:
    """
    Decode saved format (len=16) back to hardware-required absolute position (radians).
    """
    joints = np.zeros(16, dtype=float)
    joints[_INVERSE_INDEX] = vec
    pos = joints + 3.14159
    return pos


def load_type(type_name: str, category: str = HAND_CATEGORY):
    """
    Load gesture type from TypeLibrary return open / close: np.ndarray (16,)
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.join(current_dir, "TypeLibrary")
    type_library_path = os.path.join(base_path, category)
    
    if not os.path.isdir(type_library_path):
        raise FileNotFoundError(f"Type directory not found: {type_library_path}")
    
    type_file = os.path.join(type_library_path, f"{type_name}.txt")
    if not os.path.exists(type_file):
        raise FileNotFoundError(f"Gesture file not found: {type_file}")
    
    with open(type_file, 'r') as f:
        open_line = f.readline().strip()
        close_line = f.readline().strip()

    def parse_line(line: str):
        """Parse a line of joint values (supports both space-separated and bracketed formats)."""
        line = line.strip().strip('[]')
        parts = [p for p in line.replace(',', ' ').split() if p]
        vals = [float(p) for p in parts]
        if len(vals) != 16:
            raise ValueError(f"Invalid line length (expected 16): {line} -> {len(vals)}")
        return np.array(vals, dtype=float)

    open_vec = parse_line(open_line)
    close_vec = parse_line(close_line)

    return open_vec, close_vec


class LeapTypePlayer:
    """
    Command-line interface for playing back LEAP Hand gesture types.
    
    Allows real-time interpolation between open and close positions using
    keyboard controls ('a' to decrease, 'd' to increase).
    """
    
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.type_name = cfg["type"]["type_name"]
        self.leap_node = None
        self.open_saved = None
        self.close_saved = None
        self.fraction = 0.0  # Current position (0.0 = open, 1.0 = close)
        self.step_size = 0.05  # 5% per step
        
        self._init_leap()
        self._load_type()
        # Send initial open position
        self._apply_fraction(0.0)

    def _init_leap(self):
        try:
            print("Initializing LEAP Hand...")
            self.leap_node = LeapNode(self.cfg["leap_cfg"])
            print("LEAP Hand initialized successfully")
        except Exception as e:
            print(f"Hardware initialization failed: {e}")
            raise

    def _load_type(self):
        try:
            print(f"Loading gesture type: {self.type_name}")
            o, c = load_type(self.type_name, HAND_CATEGORY)
            self.open_saved = o
            self.close_saved = c
            print("Gesture type loaded successfully")
            print(f"  OPEN position:  {o}")
            print(f"  CLOSE position: {c}")
        except Exception as e:
            print(f"Failed to load gesture type '{self.type_name}': {e}")
            raise

    def _apply_fraction(self, frac: float):
        """
        Apply interpolated position to hardware.
        
        Args:
            frac: Interpolation value (0.0 = open, 1.0 = close)
        """
        if self.leap_node is None or self.open_saved is None or self.close_saved is None:
            return
        
        # Clamp fraction to [0.0, 1.0]
        frac = max(0.0, min(1.0, frac))
        self.fraction = frac
        
        # Interpolate between open and close
        interp_saved = self.open_saved * (1 - frac) + self.close_saved * frac
        target_pos = _decode_saved(interp_saved)
        
        # Send to hardware
        self.leap_node.set_leap(target_pos)

    def decrease(self):
        """Decrease interpolation value (move towards open)."""
        new_frac = self.fraction - self.step_size
        new_frac = max(0.0, new_frac)
        self._apply_fraction(new_frac)
        self._print_status()

    def increase(self):
        """Increase interpolation value (move towards close)."""
        new_frac = self.fraction + self.step_size
        new_frac = min(1.0, new_frac)
        self._apply_fraction(new_frac)
        self._print_status()

    def set_fraction(self, frac: float):
        """Set interpolation to specific value."""
        self._apply_fraction(frac)
        self._print_status()

    def _print_status(self):
        """Print current status with visual bar."""
        bar_length = 40
        filled = int(bar_length * self.fraction)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\r[{bar}] {self.fraction:.2f} (0=open, 1=close)", end='', flush=True)

    def print_help(self):
        """Display help information."""
        print("\nAvailable commands:")
        print("  a     - Move towards OPEN (decrease by 5%)")
        print("  d     - Move towards CLOSE (increase by 5%)")
        print("  0     - Jump to OPEN position")
        print("  1     - Jump to CLOSE position")
        print("  help  - Show this help message")
        print("  quit  - Exit program")
        print()

    def run(self):
        """
        Run the command-line interaction loop.
        
        Accepts keyboard commands for controlling the interpolation.
        """
        print("\n" + "="*60)
        print(f"LEAP Gesture Type Player - CLI")
        print(f"Playing: {self.type_name}")
        print("="*60)
        self.print_help()
        self._print_status()
        print()  # New line after initial status

        while True:
            try:
                cmd = input("\nCommand: ").strip().lower()

                if cmd == 'a':
                    self.decrease()
                elif cmd == 'd':
                    self.increase()
                elif cmd == '0':
                    self.set_fraction(0.0)
                elif cmd == '1':
                    self.set_fraction(1.0)
                elif cmd == 'help':
                    self.print_help()
                elif cmd in ['quit', 'exit', 'q']:
                    print("\nExiting...")
                    break
                elif cmd == '':
                    continue
                else:
                    print(f"Unknown command: '{cmd}'. Type 'help' for options")

            except KeyboardInterrupt:
                print("\n\nCtrl+C detected, exiting...")
                break
            except Exception as e:
                print(f"Error: {e}")

        # Clean up
        self.cleanup()

    def cleanup(self):
        """Clean up hardware resources."""
        try:
            if self.leap_node and self.leap_node.free_drag_active:
                print("Disabling free drag mode...")
                self.leap_node.disable_free_drag_mode()
                print("Free drag mode disabled")
        except Exception as e:
            print(f'Failed to disable free drag mode: {e}')


def main():
    if len(sys.argv) > 1:
        name = sys.argv[1]
    else:
        name = "processed_tape"

    cfg = {
        "leap_cfg": {
            "curr_lim": 150,
            "kP": 250,
            "kI": 0,
            "kD": 100
        },
        "type": {
            "type_name": name,
            "category": HAND_CATEGORY
        }
    }
    
    try:
        player = LeapTypePlayer(cfg)
        player.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()