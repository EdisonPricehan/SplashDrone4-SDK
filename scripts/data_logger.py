import os
import sys
import h5py
import datetime
import numpy as np
from loguru import logger as log
log.remove()
log.add(sys.stderr, level="INFO")


class DataLogger:
    def __init__(self, data_len: int = 1000):
        """
        Initialize the DataLogger.
        """
        # Define constants
        self.img_height: int = 128
        self.img_width: int = 128
        self.action_dim: int = 4
        self.data_len = data_len

        # Create h5 file
        self.h5file = self.create_log_file()

        # Create datasets in the h5 file
        self.create_datasets()

        # Init variables
        self.index = 0

    def create_log_file(self):
        timestamp_str: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        data_dir: str = os.path.join(os.path.dirname(__file__), '../data')
        os.makedirs(data_dir, exist_ok=True)

        filename: str = f'{data_dir}/data_log_{timestamp_str}.h5'
        h5file = h5py.File(filename, 'w')
        log.info(f'Data will be saved in {filename}')

        return h5file

    def create_datasets(self):
        """
        Create datasets in the h5 file.
        """
        assert self.h5file is not None, 'H5 file is not created yet.'

        self.h5file.create_dataset('timestamp', (self.data_len,), dtype=h5py.string_dtype())
        self.h5file.create_dataset('image', (self.data_len, self.img_height, self.img_width, 3), dtype='uint8')
        self.h5file.create_dataset('action', (self.data_len, self.action_dim), dtype='uint8')
        # TODO log action overlay boolean

    def _update_count_attr(self):
        """
        Update the count attribute in the h5 file.
        """
        if self.h5file is not None:
            self.h5file.attrs['count'] = self.index
            log.info(f'Count attribute updated to {self.index}.')
        else:
            log.warning('H5 file is not created yet, cannot update count attribute.')

    def log_data(self, timestamp: str, image: np.ndarray, action: np.ndarray):
        """
        Log data to the file.
        :param timestamp: The timestamp of the data.
        :param image: The image data.
        :param action: The action taken.
        """
        if self.index >= self.data_len:
            log.warning('Data logger is full, creating new h5 file.')

            # Update count attribute
            self._update_count_attr()
            self.h5file.close()

            # Create a new log file
            self.h5file = self.create_log_file()
            self.create_datasets()
            self.index = 0

        # Log timestamp
        self.h5file['timestamp'][self.index] = timestamp

        # Log image
        if image.shape != (self.img_height, self.img_width, 3):
            log.error(f'Image shape {image.shape} does not match expected shape {(self.img_height, self.img_width, 3)}')
            return
        self.h5file['image'][self.index] = image

        # Log action
        if action.shape != (self.action_dim,):
            log.error(f'Action shape {action.shape} does not match expected shape {(self.action_dim,)}')
            return
        self.h5file['action'][self.index] = action

        self.index += 1
        log.debug(f'Data logged at index {self.index - 1}')

    def close(self):
        """
        Close the h5 file.
        """
        if self.h5file is not None:
            self._update_count_attr()
            self.h5file.close()
            self.index = 0
            log.info('H5 file closed.')
        else:
            log.warning('H5 file is already closed or not created.')
