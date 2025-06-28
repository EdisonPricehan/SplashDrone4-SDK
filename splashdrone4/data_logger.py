# data_logger.py: Log flight info to HDF5 files.
# Copyright (C) <2025>  <Zihan Wang>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import os
import sys
import h5py
import datetime
import numpy as np
from loguru import logger as log
log.remove()
log.add(sys.stderr, level="INFO")

from splashdrone4.constants import IMG_HEIGHT, IMG_WIDTH, ACTION_DIM


class DataLogger:
    def __init__(self, data_len: int = 1000):
        """
        Initialize the DataLogger.
        """
        # Define constants
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
        self.h5file.create_dataset('wp_yaw', (self.data_len, 3), dtype=np.float32)
        self.h5file.create_dataset('timestamp', (self.data_len,), dtype=h5py.string_dtype())
        self.h5file.create_dataset('image', (self.data_len, IMG_HEIGHT, IMG_WIDTH, 3), dtype='uint8')
        self.h5file.create_dataset('mask', (self.data_len, IMG_HEIGHT, IMG_WIDTH), dtype='uint8')
        self.h5file.create_dataset('action', (self.data_len, ACTION_DIM), dtype='uint8')
        self.h5file.create_dataset('overlaid', (self.data_len, 1), dtype=np.bool_)

    def _update_count_attr(self):
        """
        Update the count attribute in the h5 file.
        """
        if self.h5file is not None:
            self.h5file.attrs['count'] = self.index
            log.info(f'Count attribute updated to {self.index}.')
        else:
            log.warning('H5 file is not created yet, cannot update count attribute.')

    def log_data(
            self,
            timestamp: str,
            wp_yaw: np.ndarray,
            image: np.ndarray,
            mask: np.ndarray,
            action: np.ndarray,
            overlaid: bool,
    ):
        """
        Log data to the file.
        :param timestamp: The timestamp of the data.
        :param wp_yaw: GPS waypoint with yaw.
        :param image: The image data.
        :param mask: The segmented water mask.
        :param action: The action taken.
        :param overlaid: Whether RL policy action is overlaid by human.
        """
        if self.index >= self.data_len:
            log.warning('Current h5 file is full, creating new h5 file.')

            # Update count attribute
            self._update_count_attr()
            self.h5file.close()

            # Create a new log file
            self.h5file = self.create_log_file()
            self.create_datasets()
            self.index = 0

        # Log timestamp
        self.h5file['timestamp'][self.index] = timestamp

        # Log gps with yaw
        if wp_yaw.shape != (3,):
            log.error(f'Waypoint with yaw expects 3-tuple (lat, lon, yaw), given dim: {wp_yaw.shape}')
            return
        self.h5file['wp_yaw'][self.index] = wp_yaw

        # Log image
        if image.shape != (IMG_HEIGHT, IMG_WIDTH, 3):
            log.error(f'Image shape {image.shape} does not match expected shape {(IMG_HEIGHT, IMG_WIDTH, 3)}')
            return
        self.h5file['image'][self.index] = image

        if mask.shape != (IMG_HEIGHT, IMG_WIDTH):
            log.error(f'Image shape {mask.shape} does not match expected shape {(IMG_HEIGHT, IMG_WIDTH)}')
            return
        self.h5file['mask'][self.index] = mask

        # Log action
        if action.shape != (ACTION_DIM,):
            log.error(f'Action shape {action.shape} does not match expected shape {(ACTION_DIM,)}')
            return
        self.h5file['action'][self.index] = action

        # Log action overlay boolean
        if not isinstance(overlaid, bool):
            log.error(f'Action overlay should be a boolean type, given type {type(overlaid)}')
            return
        self.h5file['overlaid'][self.index] = overlaid

        log.debug(f'Data logged at index {self.index}')
        self.index += 1

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
