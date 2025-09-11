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

        self.file_lengths: list[int] = []
        self.file_ranges: list[tuple[int, int]] = []  # [(start_idx, end_idx), ...]

        self.data = self._load_data()

    def _load_data(self):
        """
        Load data from the specified HDF5 files and record per-file lengths/ranges.
        """
        log.info('Loading data from HDF5 files...')
        data = {}
        file_lengths = []

        for filename in self.filenames:
            if not os.path.exists(filename):
                log.error(f'File {filename} does not exist.')
                continue

            with h5py.File(filename, 'r') as h5file:
                # prefer explicit attr 'count' if present; otherwise fall back to len(timestamp)
                default_len = len(h5file['timestamp']) if 'timestamp' in h5file else len(
                    h5file[next(iter(h5file.keys()))])
                count = int(h5file.attrs.get('count', default_len))

                for key in h5file.keys():
                    ds = h5file[key]
                    values = ds[:count] if count is not None else ds[:]
                    if key not in data:
                        data[key] = []
                    data[key].extend(values)

                file_lengths.append(count)

        # build per-file index ranges over the concatenated arrays
        self.file_lengths = file_lengths
        self.file_ranges = []
        start = 0
        for L in file_lengths:
            self.file_ranges.append((start, start + L))
            start += L

        total = sum(file_lengths)
        if total == 0:
            log.error('No records loaded from the provided files.')
        else:
            log.info(f'Loaded {total} records from {len(self.filenames)} files.')

        return data

    def save_wps_to_map(self, map_name: str = 'waypoints_map.html', separate_trajectories: bool = False):
        if 'wp_yaw' not in self.data:
            log.warning('No waypoint_with_yaw in data.')
            return

        wpy_list = self.data['wp_yaw']
        overlaid_list = self.data.get('overlaid', [0] * len(wpy_list))

        # Extract lat/lon/yaw and sanitize
        def _is_num(x):
            try:
                return np.isfinite(float(x))
            except Exception:
                return False

        latitudes = []
        longitudes = []
        yaws = []
        valid_idx = []
        for i, wpy in enumerate(wpy_list):
            if len(wpy) < 2:
                continue
            lat, lon = wpy[0], wpy[1]
            yaw = wpy[2] if len(wpy) > 2 else 0.0
            if _is_num(lat) and _is_num(lon):
                valid_idx.append(i)
                latitudes.append(float(lat))
                longitudes.append(float(lon))
                yaws.append(float(yaw))

        if len(latitudes) == 0:
            log.warning('No valid waypoints (after sanitization) to plot.')
            return

        # Align overlaid_list length to sanitized points
        if len(overlaid_list) != len(wpy_list):
            overlaid_list = [0] * len(wpy_list)
        overlaid_list = [overlaid_list[i] for i in valid_idx]

        center = [float(np.mean(latitudes)), float(np.mean(longitudes))]
        m = folium.Map(location=center, zoom_start=16, control_scale=True)

        # Helper to add one trajectory
        # --- inside save_wps_to_map, replace your add_traj_layer with this ---
        def add_traj_layer(layer_name, lats, lons, yaws_seg, overlaid_seg, color_hex, traj_idx: int):
            if len(lats) < 2:
                return

            fg = folium.FeatureGroup(name=layer_name, show=True)

            # START marker (blue) with numeric ID using BeautifyIcon(number=...)
            def _add_start_with_number(lat, lon, number_str: str):
                try:
                    from folium.plugins import BeautifyIcon
                    folium.Marker(
                        location=[lat, lon],
                        tooltip=f"{layer_name} - Start (#{number_str})",
                        icon=BeautifyIcon(
                            icon_shape='marker',
                            number=number_str,  # <-- use number= (not text=)
                            border_color='blue',
                            text_color='blue',
                            background_color='white'
                        ),
                    ).add_to(fg)
                    return True
                except Exception as e:
                    log.warning(f'BeautifyIcon(number=...) failed; falling back. {e}')
                    return False

            ok = _add_start_with_number(lats[0], lons[0], str(traj_idx + 1))
            if not ok:
                # Fallback: simple blue CircleMarker for Start
                folium.CircleMarker([lats[0], lons[0]],
                                    radius=5, color="blue", fill=True, fill_color="blue",
                                    tooltip=f"{layer_name} - Start (#{traj_idx + 1})").add_to(fg)

            # END marker (orange), no number so we don't risk plugin issues
            folium.CircleMarker([lats[-1], lons[-1]],
                                radius=5, color="orange", fill=True, fill_color="orange",
                                tooltip=f"{layer_name} - End").add_to(fg)

            # Intermediate points: non-overlaid=green, overlaid=red (as requested)
            for idx in range(1, len(lats) - 1):
                overlaid = overlaid_seg[idx] if idx < len(overlaid_seg) else 0
                dot = 'red' if overlaid else 'green'
                folium.CircleMarker(
                    location=[lats[idx], lons[idx]],
                    radius=1,
                    color=dot, fill=True, fill_color=dot, fill_opacity=0.9,
                    popup=f"Yaw: {yaws_seg[idx]:.2f} | Overlaid: {overlaid}",
                ).add_to(fg)

            # Path polyline
            folium.PolyLine(list(zip(lats, lons)), color=color_hex, weight=1.0, opacity=1).add_to(fg)
            fg.add_to(m)

        # Build segments (separate or merged)
        if separate_trajectories and getattr(self, "file_ranges", None):
            from matplotlib import cm, colors as mcolors
            num = max(1, len(self.file_ranges))
            cmap = cm.get_cmap('tab20', num)

            # Map original global indices -> sanitized arrays
            # We need to translate original [0..len(wpy_list)-1] to sanitized [0..len(latitudes)-1]
            orig_to_sanitized = {orig_i: k for k, orig_i in enumerate(valid_idx)}

            any_points = False
            for i, (s, e) in enumerate(self.file_ranges):
                # translate [s:e] through the valid-index map, keep those that exist
                idxs = [orig_to_sanitized[j] for j in range(s, e) if j in orig_to_sanitized]
                if len(idxs) < 2:
                    continue
                any_points = True
                lats_seg = [latitudes[k] for k in idxs]
                lons_seg = [longitudes[k] for k in idxs]
                yaws_seg = [yaws[k] for k in idxs]
                overlaid_seg = [overlaid_list[k] for k in idxs]
                color_hex = mcolors.to_hex(cmap(i))
                layer_name = f"Trajectory {i + 1} ({os.path.basename(self.filenames[i])})"
                add_traj_layer(layer_name, lats_seg, lons_seg, yaws_seg, overlaid_seg, color_hex, traj_idx=i)

            if not any_points:
                log.warning("No drawable per-file segments after sanitization; falling back to merged view.")
                add_traj_layer("All trajectories (merged)", latitudes, longitudes, yaws, overlaid_list, "blue",
                               traj_idx=0)
            else:
                folium.LayerControl(collapsed=False, position='bottomright').add_to(m)
        else:
            add_traj_layer("All trajectories (merged)", latitudes, longitudes, yaws, overlaid_list, "blue", traj_idx=0)

        # Always fit the map to data bounds so it’s visible even if center/zoom was off
        try:
            m.fit_bounds(list(zip(latitudes, longitudes)))
        except Exception:
            pass

        maps_dir = os.path.join(os.path.dirname(__file__), '../maps')
        os.makedirs(maps_dir, exist_ok=True)
        map_path = os.path.join(maps_dir, map_name)
        m.save(map_path)
        log.info(f'Waypoints map is saved as {map_path}.')

    def save_image_with_exif(self, out_dir='../images_exif', mask_out_dir='../masks') -> None:
        """
        Save images with EXIF metadata containing GPS coordinates, as well as corresponding masks if available.

        :param out_dir: image output directory where images will be saved.
        :param mask_out_dir: mask output directory where masks will be saved.
        :return: None
        """
        os.makedirs(out_dir, exist_ok=True)
        os.makedirs(mask_out_dir, exist_ok=True)

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

            # Save corresponding mask if available
            if 'mask' in self.data:
                mask = self.data['mask'][i]
                mask_img = Image.fromarray(mask)
                mask_fname = os.path.join(mask_out_dir, f"{t.decode()}.png")
                mask_img.save(mask_fname, "PNG")

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
    # data_files = [
    #     '../data/data_log_20250630_103652.h5',
    #     '../data/data_log_20250630_103913.h5',
    #     '../data/data_log_20250630_104021.h5',
    #     '../data/data_log_20250630_104128.h5',
    #     '../data/data_log_20250630_104233.h5',
    #     '../data/data_log_20250630_104347.h5',
    #     '../data/data_log_20250630_104454.h5',
    #     '../data/data_log_20250630_104605.h5',
    #     # '../data/data_log_20250630_104720.h5',
    #     # '../data/data_log_20250630_105001.h5',
    # ]

    # Wabash River upstream 07/29
    # data_files = [
    #     '../data/data_log_19691231_190423.h5',
    #     '../data/data_log_19691231_190629.h5',
    #     '../data/data_log_19691231_190751.h5',
    #     '../data/data_log_19691231_190929.h5',
    #     '../data/data_log_19691231_191039.h5',
    #     '../data/data_log_19691231_191152.h5',
    # ]

    # Wabash River downstream 07/29
    # data_files = [
    #     '../data/data_log_20250729_192610.h5',
    #     '../data/data_log_20250729_192904.h5',
    #     '../data/data_log_20250729_193044.h5',
    #     '../data/data_log_20250729_193243.h5',
    #     '../data/data_log_20250729_193428.h5',
    #     '../data/data_log_20250729_193631.h5',
    #     '../data/data_log_20250729_193755.h5',
    # ]

    # Wabash River upstream 09/10
    data_files = [
        '../data/data_log_20250910_143236.h5',  # battery 1
        '../data/data_log_19691231_190334.h5',  # battery 2
        '../data/data_log_20250910_143334.h5',  # battery 3
        '../data/data_log_20250910_150110.h5',  # battery 4
        '../data/data_log_20250910_152547.h5',  # battery 5
    ]

    reader = DataReader(filenames=data_files)

    try:
        # Usage 1: show logged image, mask and actions
        # reader.play()

        # Usage 2: save them as a video
        # reader.save_as_video(video_path='../videos/wabash_uptream_hitl_0729.mp4', fps=1)
        # reader.save_as_video(video_path='../videos/wabash_downstream_hitl_0729.mp4', fps=1)

        # Usage 3: save waypoints to map
        # reader.save_wps_to_map(map_name='wabash_upstream_0729.html')
        # reader.save_wps_to_map(map_name='wabash_downstream_0729.html')
        reader.save_wps_to_map(map_name='wabash_upstream_0910.html', separate_trajectories=True)

        # Usage 4: Save image with exif meta data
        # reader.save_image_with_exif()

    except KeyboardInterrupt:
        log.warning("Playback interrupted by user.")
    finally:
        cv2.destroyAllWindows()
