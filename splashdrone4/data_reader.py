# data_reader.py: Read and play flight info from HDF5 files.
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
import cv2
from tqdm import tqdm
from typing import List
from loguru import logger as log
log.remove()
log.add(sys.stderr, level="INFO")


class DataReader:
    def __init__(self, filenames: List[str]):
        """
        Initialize the DataReader with a list of filenames.
        :param filenames: List of HDF5 file paths to read data from.
        """
        self.filenames = filenames
        if len(filenames) == 0:
            log.error('No filenames provided for DataReader.')
            raise ValueError('Filenames list cannot be empty.')

        self.data = self._load_data()

    def _load_data(self):
        """
        Load data from the specified HDF5 files.
        """
        log.info('Loading data from HDF5 files...')
        data = {}

        for filename in self.filenames:
            if not os.path.exists(filename):
                log.error(f'File {filename} does not exist.')
                continue

            with h5py.File(filename, 'r') as h5file:
                count = h5file.attrs.get('count', len(h5file['timestamp']))

                for key in h5file.keys():
                    dataset = h5file[key]
                    if count is not None:
                        values = dataset[:count]
                    else:
                        values = dataset[:]
                    if key not in data:
                        data[key] = []
                    data[key].extend(values)

        log.info(f'Loaded {len(next(iter(data.values())))} records from {len(self.filenames)} files.')
        return data

    def play(self):
        """
        Play the logged data by displaying images and printing actions.
        """
        log.info(f'All keys: {self.data.keys()}')

        n = len(next(iter(self.data.values())))
        for i in tqdm(range(n)):
            if 'image' in self.data:
                img_bgr = cv2.cvtColor(self.data['image'][i], cv2.COLOR_RGB2BGR)
                cv2.imshow('Image', img_bgr)
            if 'mask' in self.data:
                cv2.imshow('Mask', self.data['mask'][i])
            timestamp = self.data['timestamp'][i].decode() if 'timestamp' in self.data else None
            wp_yaw = self.data['wp_yaw'][i] if 'wp_yaw' in self.data else None
            action = self.data['action'][i] if 'action' in self.data else None
            overlaid = self.data['overlaid'][i] if 'overlaid' in self.data else None
            log.info(f'Timestamp: {timestamp}, Action: {action}, WP-Yaw: {wp_yaw}, Overlaid: {overlaid}')

            cv2.waitKey(1000)


if __name__ == "__main__":
    # Example usage
    # data_files = ['../data/data_log_20250618_160611.h5',
    #               '../data/data_log_20250618_160627.h5',
    #               '../data/data_log_20250618_160636.h5',
    #               '../data/data_log_20250618_160658.h5']
    # data_files = ['../data/data_log_20250618_163702.h5',
    #               '../data/data_log_20250618_163712.h5',
    #               '../data/data_log_20250618_163718.h5',
    #               '../data/data_log_20250618_163724.h5']
    # data_files = [
    #     '../data/data_log_20250620_141941.h5',
    #     '../data/data_log_20250620_142103.h5',
    #     '../data/data_log_20250620_142153.h5',
    #     '../data/data_log_20250620_142237.h5',
    # ]
    data_files = [
        '../data/data_log_20250628_153349.h5',
        '../data/data_log_20250628_153519.h5',
        '../data/data_log_20250628_153746.h5',
        '../data/data_log_20250628_153901.h5',
    ]

    reader = DataReader(filenames=data_files)

    try:
        reader.play()
    except KeyboardInterrupt:
        log.warning("Playback interrupted by user.")
    finally:
        cv2.destroyAllWindows()




