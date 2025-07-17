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
import folium
import numpy as np
from tqdm import tqdm
from typing import List
from PIL import Image
import piexif
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

    def save_wps_to_map(self, map_name: str = 'waypoints_map.html'):
        if 'wp_yaw' not in self.data:
            log.warning(f'No waypoint_with_yaw in data.')
            return

        # Get waypoints
        wpy_list = self.data['wp_yaw']
        latitudes = [wpy[0] for wpy in wpy_list]
        longitudes = [wpy[1] for wpy in wpy_list]

        # Center map at the mean location
        center = [np.mean(latitudes), np.mean(longitudes)]
        m = folium.Map(location=center, zoom_start=16)

        # Add waypoints as a polyline
        folium.PolyLine(list(zip(latitudes, longitudes)), color="blue", weight=2.5, opacity=1).add_to(m)

        # Mark start (green) and stop (red) waypoints
        if latitudes and longitudes:
            folium.Marker(
                location=[latitudes[0], longitudes[0]],
                popup="Start",
                icon=folium.Icon(color="green", icon="play")
            ).add_to(m)
            folium.Marker(
                location=[latitudes[-1], longitudes[-1]],
                popup="Stop",
                icon=folium.Icon(color="red", icon="stop")
            ).add_to(m)

        # Add small red circles for intermediate waypoints
        for lat, lon in zip(latitudes[1:-1], longitudes[1:-1]):
            folium.CircleMarker(location=[lat, lon], radius=2, color='red').add_to(m)

        # Save to HTML and open in browser
        map_path: str = os.path.join(os.path.dirname(__file__), f'../maps/{map_name}')
        m.save(map_path)
        log.info(f'Waypoints map is saved as {map_path}.')

    def save_image_with_exif(self, out_dir='../images_exif'):
        os.makedirs(out_dir, exist_ok=True)
        for i, (t, img_rgb, wp) in enumerate(zip(self.data['timestamp'], self.data['image'], self.data['wp_yaw'])):
            lat, lon = wp[:2]
            img = Image.fromarray(img_rgb)

            def _deg_to_dms_rational(deg):
                # convert decimal degrees to rational DMS
                d = int(deg)
                m = int((deg - d) * 60)
                s = int((deg - d - m / 60) * 3600)
                return ((d, 1), (m, 1), (s, 1))

            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: b'N' if lat >= 0 else b'S',
                piexif.GPSIFD.GPSLatitude: _deg_to_dms_rational(abs(lat)),
                piexif.GPSIFD.GPSLongitudeRef: b'E' if lon >= 0 else b'W',
                piexif.GPSIFD.GPSLongitude: _deg_to_dms_rational(abs(lon))
            }
            exif_dict = {"GPS": gps_ifd}
            exif_bytes = piexif.dump(exif_dict)

            fname = os.path.join(out_dir, f"{t.decode()}.jpg")
            img.save(fname, "jpeg", exif=exif_bytes)

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

            cv2.waitKey(1000)  # Wait for 1 second


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
    # data_files = [
    #     '../data/data_log_20250628_153349.h5',
    #     '../data/data_log_20250628_153519.h5',
    #     '../data/data_log_20250628_153746.h5',
    #     '../data/data_log_20250628_153901.h5',
    # ]
    # data_files = [
    #     '../data/data_log_20250629_165027.h5',
    #     '../data/data_log_20250629_165126.h5',
    # ]

    # Wabash River upstream 06/30
    # data_files = [
    #     '../data/data_log_20250630_101219.h5',
    #     '../data/data_log_20250630_101532.h5',
    #     '../data/data_log_20250630_101725.h5',
    #     '../data/data_log_20250630_101841.h5',
    #     '../data/data_log_20250630_102007.h5',
    #     '../data/data_log_20250630_102139.h5',
    #     '../data/data_log_20250630_102311.h5',
    #     '../data/data_log_20250630_102431.h5',
    #     '../data/data_log_20250630_102538.h5',
    #     '../data/data_log_20250630_102652.h5',
    # ]

    # Wabash River downstream 06/30
    data_files = [
        '../data/data_log_20250630_103652.h5',
        '../data/data_log_20250630_103913.h5',
        '../data/data_log_20250630_104021.h5',
        '../data/data_log_20250630_104128.h5',
        '../data/data_log_20250630_104233.h5',
        '../data/data_log_20250630_104347.h5',
        '../data/data_log_20250630_104454.h5',
        '../data/data_log_20250630_104605.h5',
        # '../data/data_log_20250630_104720.h5',
        # '../data/data_log_20250630_105001.h5',
    ]

    reader = DataReader(filenames=data_files)

    try:
        reader.play()
        # reader.save_image_with_exif()
        # reader.save_wps_to_map(map_name='wabash_upstream.html')
        # reader.save_wps_to_map(map_name='wabash_downstream.html')
    except KeyboardInterrupt:
        log.warning("Playback interrupted by user.")
    finally:
        cv2.destroyAllWindows()




