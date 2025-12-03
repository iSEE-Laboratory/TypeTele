# <p align="center">TypeTele (CoRL 2025)</p>

### <p align="center">Yuhao Lin\*, Yi-Lin Wei\*, Haoran Liao, Mu Lin, Chengyi Xing, Hao Li, <br>Dandan Zhang, Mark Cutkosky, Wei-Shi Zheng</p>

#### <p align="center">[![Project Page](https://img.shields.io/badge/Project-Page-blue)](https://isee-laboratory.github.io/TypeTele/) [![arXiv](https://img.shields.io/badge/arXiv-2507.01857-b31b1b.svg)](https://arxiv.org/abs/2507.01857)
### Official repository of paper "TypeTele: Releasing Dexterity in Teleoperation by Dexterous Manipulation Types".

TypeTele is a type-guided teleoperation system that transcends the morphological constraints of traditional hand retargeting. By leveraging an MLLM-assisted retrieval module and a diverse Dexterous Manipulation Type Library, TypeTele maps human intent to stable, functional robot postures. TypeTele simplifies the teleoperation process, delivering higher success rates with reduced execution time. Its intuitive design minimizes the learning cost, allowing users to rapidly master the system and begin data collection immediately.

<p align="center">
  <img src="assets/overview.png" style="max-width:100%; height:auto;">
</p>

## Features

- Dexterous manipulation type library for robot-exclusive actions
- MLLM-assisted type retrieval for natural language command interpretation
- Real-time hand gesture tracking and mapping
- Extensible framework for various dexterous hands
- Support for both keyboard and voice command inputs

## Installation

### Prerequisites

- Python 3.10
- Conda (recommended for environment management)

### Environment Setup

We recommend creating a virtual environment using conda:

```bash
conda create -n typetele python=3.10 -y
conda activate typetele
```

Install required packages:

```bash
pip install -r requirements.txt
```

## Usage

### 1. Creating/Recording Grasp Types

To create and save new grasp types to the TypeLibrary:

```bash
python leap_1_create_type.py
```

Follow the command-line interface to:
- Record open position (`ro`)
- Record close position (`rc`)
- Save the gesture to file (`save`)
- Other commands: `reset`, `help`, `quit`

Saved types will be stored in `TypeLibrary/leap/` directory.

### 2. Testing Grasp Types

To test and interact with saved grasp types:

```bash
python leap_2_test_type.py [type_name]
```

Controls:
- `a`: Move towards OPEN position (decrease by 5%)
- `d`: Move towards CLOSE position (increase by 5%)
- `0`: Jump to OPEN position
- `1`: Jump to CLOSE position

If no type name is provided, it defaults to "processed_tape".

### 3. Real-time Teleoperation

For real-time teleoperation with hand tracking:

First, configure your API keys in leap_3_realtime.py:
- LLM API key for type retrieval
- (Optional) Tencent ASR credentials for voice input

```bash
python leap_3_realtime.py
```

By default, the system uses keyboard input for commands. To enable voice recognition, change the ASR type in the configuration section.

Controls:
- Type natural language commands for grasp type retrieval
- Use hand gestures for fine-grained control
- `/type_name` for direct type switching

## Hardware Configuration

### LEAP Hand Communication

The DynamixelClient in leap_node.py uses "/dev/ttyUSB0" as the default serial port. For Windows users:
- Check Device Manager for the COM port
- Modify the port in leap_node.py accordingly (e.g., "COM1")

### Camera Setup

Default camera settings:
- In Camera.py, the capture method uses: `cv2.VideoCapture(self.camera_id, cv2.CAP_V4L2)`
- Default camera ID varies across systems:
  - External default config gives ID 4
  - `.get()` method defaults to ID 0
  - Demo in Camera.py uses ID 4
  
Adjust the camera ID in the configuration according to your setup.

## Project Structure

```
TypeTele/
├── TypeLibrary/              # Dexterous manipulation type library
│   └── leap/                 # LEAP Hand specific types
├── asr/                      # Automatic Speech Recognition modules
│   ├── tencent_asr.py        # Tencent Cloud ASR implementation
│   └── typing_asr.py         # Keyboard-based ASR alternative
├── hand_detect/              # Hand detection and tracking
│   ├── Camera.py             # Camera interface
│   ├── SingleHandDetetor.py  # Hand landmark detection
│   └── detectFinger.py       # Finger state estimation
├── leap_hand_utils/          # LEAP Hand utility functions
├── retrieve/                 # MLLM-based type retrieval
├── leap_1_create_type.py     # Type creation script
├── leap_2_test_type.py       # Type testing script
└── leap_3_realtime.py        # Real-time teleoperation
```

## Contributing

We welcome contributions to extend TypeTele! Please feel free to submit issues and pull requests.

## Citation

If you use TypeTele in your research, please cite our paper:

```bibtex
@article{lin2025typetele,
  title={TypeTele: Releasing Dexterity in Teleoperation by Dexterous Manipulation Types},
  author={Lin, Yuhao and Wei, Yi-Lin and Liao, Haoran and Lin, Mu and Xing, Chengyi and Li, Hao and Zhang, Dandan and Cutkosky, Mark and Zheng, Wei-Shi},
  journal={arXiv preprint arXiv:2507.01857},
  year={2025}
}
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.