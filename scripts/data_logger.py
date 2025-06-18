import h5py
import datetime
import numpy as np
from loguru import logger as log


class DataLogger:
    def __init__(self, init_data_len: int = 1000):
        """
        Initialize the DataLogger.
        """
        self.filename = filename
        self.init_data_len = init_data_len
        self.data = {
            'timestamp': [],
            'image': [],
            'action': []
        }
        self.index = 0

    def log_data(self, timestamp: str, image: np.ndarray, action: np.ndarray):
        """
        Log data to the file.
        :param timestamp: The timestamp of the data.
        :param image: The image data.
        :param action: The action taken.
        """
        self.data['timestamp'].append(timestamp)
        self.data['image'].append(image)
        self.data['action'].append(action)