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
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
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

    def save_wps_to_map(self, map_name: str = 'waypoints_map.html'):
        if 'wp_yaw' not in self.data:
            log.warning('No waypoint_with_yaw in data.')
            return

        wpy_list = self.data['wp_yaw']
        overlaid_list = self.data.get('overlaid', [0] * len(wpy_list))

        latitudes = [wpy[0] for wpy in wpy_list]
        longitudes = [wpy[1] for wpy in wpy_list]
        yaws = [wpy[2] for wpy in wpy_list]

        center = [np.mean(latitudes), np.mean(longitudes)]
        m = folium.Map(location=center, zoom_start=16)

        # Start marker: green play icon
        if latitudes and longitudes:
            folium.Marker(
                location=[latitudes[0], longitudes[0]],
                popup="Start",
                icon=folium.Icon(color="green", icon="play")
            ).add_to(m)

            # End marker: red stop icon
            folium.Marker(
                location=[latitudes[-1], longitudes[-1]],
                popup="End",
                icon=folium.Icon(color="red", icon="stop")
            ).add_to(m)

        # Intermediate waypoints as circle markers with different colors
        for idx, (lat, lon, yaw) in enumerate(zip(latitudes, longitudes, yaws)):
            if idx == 0 or idx == len(latitudes) - 1:
                continue  # Skip start/end
            overlaid = overlaid_list[idx] if idx < len(overlaid_list) else 0
            color = '#1976d2' if overlaid else '#757575'
            folium.CircleMarker(
                location=[lat, lon],
                radius=5,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                popup=f"Yaw: {yaw:.2f}\nOverlaid: {overlaid}"
            ).add_to(m)

        # Polyline for path
        folium.PolyLine(list(zip(latitudes, longitudes)), color="blue", weight=2.5, opacity=1).add_to(m)

        map_path = os.path.join(os.path.dirname(__file__), f'../maps/{map_name}')
        m.save(map_path)
        log.info(f'Waypoints map is saved as {map_path}.')

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

    def save_as_video(self, video_path: str = 'hitl_video.mp4', fps: int = 1):
        n = len(next(iter(self.data.values())))
        height, width = self.data['image'][0].shape[:2]
        fig_height = 1.2 * height  # Extra space for text
        fig_width = 2 * width

        video_writer = cv2.VideoWriter(
            video_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (int(fig_width), int(fig_height))
        )

        for i in tqdm(range(n)):
            img = self.data['image'][i]
            mask = self.data['mask'][i] if 'mask' in self.data else np.zeros_like(img)
            timestamp = self.data['timestamp'][i].decode() if 'timestamp' in self.data else ''
            action = str(self.data['action'][i]) if 'action' in self.data else ''
            overlaid = str(self.data['overlaid'][i]) if 'overlaid' in self.data else ''

            # Prepare mask for display
            if mask.ndim == 2:
                mask_rgb = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
            else:
                mask_rgb = mask

            # Create figure
            fig, axs = plt.subplots(2, 1, figsize=(fig_width / 100, fig_height / 100),
                                    gridspec_kw={'height_ratios': [0.2, 1]})
            fig.subplots_adjust(hspace=0.05, top=0.95, bottom=0.05)

            # Text subplot
            axs[0].axis('off')
            text = f'Time: {timestamp}\nAction: {action}\nOverlaid: {overlaid}'
            axs[0].text(0.5, 0.5, text, ha='center', va='center', fontsize=6, wrap=True)

            # Image+mask subplot
            axs[1].imshow(np.hstack((img, mask_rgb)))
            axs[1].axis('off')

            # Render to numpy array using buffer_rgba
            canvas = FigureCanvas(fig)
            canvas.draw()
            frame = np.frombuffer(canvas.buffer_rgba(), dtype=np.uint8)
            frame = frame.reshape(fig.canvas.get_width_height()[::-1] + (4,))
            frame_rgb = frame[..., :3]  # Drop alpha channel
            plt.close(fig)

            # Resize to match video size
            frame_rgb = cv2.resize(frame_rgb, (int(fig_width), int(fig_height)))
            video_writer.write(cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))

        video_writer.release()


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
        # Usage 1: show logged image, mask and actions
        reader.play()

        # Usage 2: save them as a video
        # reader.save_as_video(video_path='wabash_uptream_hitl.mp4', fps=1)
        # reader.save_as_video(video_path='wabash_downstream_hitl.mp4', fps=1)

        # Usage 3: save waypoints to map
        # reader.save_wps_to_map(map_name='wabash_upstream.html')
        # reader.save_wps_to_map(map_name='wabash_downstream.html')
    except KeyboardInterrupt:
        log.warning("Playback interrupted by user.")
    finally:
        cv2.destroyAllWindows()




