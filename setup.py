from setuptools import setup, find_packages

setup(
    name="splashdrone4",
    version="0.1.0",
    description="Python splashdrone4 for SplashDrone4 integration",
    author="Zihan Wang",
    packages=find_packages(),
    scripts=[
        "splashdrone4/keyboard_control.py",
        "splashdrone4/data_logger.py",
        "splashdrone4/data_reader.py",
        "splashdrone4/zmq_interface.py",
        "splashdrone4/zmq_gui.py",
    ],
    install_requires=[
        "numpy",
        "opencv-python",
        "loguru",
        "tqdm",
        "pynput",
        "PySimpleGUI",
        "pyzmq",
        "utm",
        "h5py",
    ],
    python_requires=">=3.10",
)

