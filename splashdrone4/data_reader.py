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
from branca.element import Element
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

        # Post-process known singleton-shaped series like 'overlaid' (bool stored as (N,1))
        def _scalarize_singletons(seq):
            out = []
            for v in seq:
                try:
                    if isinstance(v, np.ndarray):
                        # If it's a single value array, extract the scalar
                        if v.size == 1:
                            out.append(v.reshape(-1)[0].item() if hasattr(v.reshape(-1)[0], 'item') else v.reshape(-1)[0])
                            continue
                    # generic 1-length containers (e.g., lists/tuples)
                    if hasattr(v, '__len__') and not isinstance(v, (bytes, bytearray, np.bytes_)):
                        try:
                            if len(v) == 1:
                                out.append(v[0])
                                continue
                        except TypeError:
                            pass
                except Exception:
                    pass
                out.append(v)
            return out

        if 'overlaid' in data:
            data['overlaid'] = _scalarize_singletons(data['overlaid'])

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

        # Hide default controls (zoom, layers, attribution)
        css_hide = Element("""
        <style>
        .leaflet-control-zoom,
        .leaflet-control-layers,
        .leaflet-control-attribution { display: none !important; }
        </style>
        """)
        m.get_root().html.add_child(css_hide)

        # Determine yaw units (radians vs degrees) from sanitized yaws
        def _yaw_is_radians(ylist):
            vals = [abs(v) for v in ylist if np.isfinite(v)]
            if not vals:
                return True
            return max(vals) <= 2 * np.pi * 1.05
        yaw_in_radians = _yaw_is_radians(yaws)

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

            # Helper: add a yaw-oriented elongated arrow at a point using a filled polygon (triangle)
            def _add_yaw_arrow(lat, lon, yaw_value, color='black', length_m: float = 8.0, base_width_m: float = 4.0):
                try:
                    yaw_deg = float(np.degrees(yaw_value) if yaw_in_radians else yaw_value)
                    if not np.isfinite(yaw_deg):
                        return

                    # Convert small meter offsets to lat/lon near the given latitude
                    R = 6378137.0  # Earth radius in meters
                    lat_rad = np.radians(lat)

                    def _offset_latlon(d_north_m: float, d_east_m: float):
                        dlat = (d_north_m / R) * (180.0 / np.pi)
                        dlon = (d_east_m / (R * np.cos(lat_rad))) * (180.0 / np.pi)
                        return lat + dlat, lon + dlon

                    # Interpret yaw as heading degrees from North, clockwise (common navigation convention)
                    th = np.radians(yaw_deg)
                    # Unit vectors in meters: along-heading (north/east components)
                    u_n = np.cos(th)
                    u_e = np.sin(th)
                    # Perpendicular to the left of heading
                    v_n = -np.sin(th)
                    v_e =  np.cos(th)

                    # Triangle points: tip ahead, base at the waypoint with given width
                    tip = _offset_latlon(length_m * u_n, length_m * u_e)
                    base_left = _offset_latlon(0.5 * base_width_m * v_n, 0.5 * base_width_m * v_e)
                    base_right = _offset_latlon(-0.5 * base_width_m * v_n, -0.5 * base_width_m * v_e)

                    folium.Polygon(
                        locations=[tip, base_left, base_right],
                        color=color,
                        weight=1,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.9,
                    ).add_to(fg)
                except Exception as e:
                    log.warning(f"Failed to add yaw arrow polygon: {e}")

            # Intermediate points: non-overlaid=green, overlaid=red (as requested)
            for idx in range(0, len(lats)):
                overlaid = overlaid_seg[idx] if idx < len(overlaid_seg) else 0
                dot = 'red' if overlaid else 'green'
                # Keep the dot for visibility
                folium.CircleMarker(
                    location=[lats[idx], lons[idx]],
                    radius=1,
                    color=dot, fill=True, fill_color=dot, fill_opacity=0.9,
                    popup=f"Yaw: {yaws_seg[idx]:.2f} | Overlaid: {overlaid}",
                ).add_to(fg)
                # Add yaw arrow on top (longer and wider to emphasize direction)
                _add_yaw_arrow(lats[idx], lons[idx], yaws_seg[idx], color='#202020', length_m=2.0, base_width_m=1.0)

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

    def save_image_with_exif(self, out_dir='../images_exif', mask_out_dir='../masks', per_trajectory: bool = False, trajectory_key: str = 'trajectory_id', trajectory_name: str | None = None) -> None:
        """
        Save images with EXIF metadata containing GPS coordinates, as well as corresponding masks if available.

        :param out_dir: image output directory where images will be saved.
        :param mask_out_dir: mask output directory where masks will be saved.
        :param per_trajectory: if True, create subfolders per trajectory and place images/masks accordingly.
        :param trajectory_key: dataset key in self.data that contains trajectory identifiers (per frame). Used when per_trajectory is True and trajectory_name is not provided.
        :param trajectory_name: optional constant trajectory folder name to use for all frames (overrides trajectory_key when provided).
        :return: None
        """
        def _sanitize(name: str) -> str:
            safe = ''.join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in name)
            return safe.strip('._') or 'traj'

        os.makedirs(out_dir, exist_ok=True)
        os.makedirs(mask_out_dir, exist_ok=True)

        # Helper to compute destination subdirs for a given index
        def _resolve_subdirs(i: int):
            if not per_trajectory:
                return out_dir, mask_out_dir
            # Determine trajectory label
            if trajectory_name:
                traj_label = trajectory_name
            elif trajectory_key in self.data:
                val = self.data[trajectory_key][i]
                if isinstance(val, (bytes, bytearray, np.bytes_)):
                    traj_label = val.decode(errors='ignore')
                else:
                    traj_label = str(val)
            else:
                # fallback: try to infer from file_ranges (which file the index belongs to)
                traj_idx = None
                for fi, (start, end) in enumerate(self.file_ranges):
                    if start <= i < end:
                        traj_idx = fi
                        break
                if traj_idx is not None:
                    base = os.path.splitext(os.path.basename(self.filenames[traj_idx]))[0]
                    traj_label = base
                else:
                    # last resort: prefix of timestamp
                    t = self.data.get('timestamp', [b'unknown'])[i]
                    t_str = t.decode() if isinstance(t, (bytes, bytearray, np.bytes_)) else str(t)
                    traj_label = t_str[:15]
            traj_label = _sanitize(traj_label)
            img_dir = os.path.join(out_dir, traj_label)
            msk_dir = os.path.join(mask_out_dir, traj_label)
            os.makedirs(img_dir, exist_ok=True)
            os.makedirs(msk_dir, exist_ok=True)
            return img_dir, msk_dir

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

            cur_out_dir, cur_mask_dir = _resolve_subdirs(i)

            t_str = t.decode() if isinstance(t, (bytes, bytearray, np.bytes_)) else str(t)
            fname = os.path.join(cur_out_dir, f"{t_str}.jpg")
            img.save(fname, "jpeg", exif=exif_bytes)

            # Save corresponding mask if available
            if 'mask' in self.data:
                mask = self.data['mask'][i]
                mask_img = Image.fromarray(mask)
                mask_fname = os.path.join(cur_mask_dir, f"{t_str}.png")
                mask_img.save(mask_fname, "PNG")

    def save_intervention_rate_pdf(
            self,
            steps: int = 50,
            pdf_path: str = '../figures/intervention_rate.pdf',
            fig_width: float = 7.0,
            fig_height: float = 2.0,
            include_overall: bool = True,
            show: bool = False,
    ) -> None:
        """
        Plot the intervention rate (from the `overlaid` indicator) as a moving average and save as a PDF.
        No trajectory separation; the plot is compact in height for double-column insertion in papers.

        :param steps: Window length (in steps/frames) for moving average calculation.
        :param pdf_path: Output path for the PDF figure.
        :param fig_width: Figure width in inches (use ~7 for double-column width).
        :param fig_height: Figure height in inches (keep small to be short in height).
        :param include_overall: If True, draw a dashed horizontal line for overall intervention rate.
        :param show: If True, display the figure in an interactive window (useful for debugging).
        :return: None
        """
        if 'overlaid' not in self.data:
            log.warning('No "overlaid" key in data; cannot plot intervention rate.')
            return

        # Convert to a clean 0/1 numpy array
        raw = self.data['overlaid']
        def _to01(v):
            try:
                if isinstance(v, (bytes, bytearray, np.bytes_)):
                    s = v.decode(errors='ignore').strip().lower()
                    return 1.0 if s in ('1', 'true', 'yes', 'y') else 0.0
                if isinstance(v, (np.bool_, bool)):
                    return 1.0 if v else 0.0
                if isinstance(v, (int, np.integer, float, np.floating)):
                    return 1.0 if float(v) != 0.0 else 0.0
                # Fallback to string interpretation
                s = str(v).strip().lower()
                return 1.0 if s in ('1', 'true', 'yes', 'y') else 0.0
            except Exception:
                return 0.0
        x = np.array([_to01(v) for v in raw], dtype=float)

        n = len(x)
        if n == 0:
            log.warning('Empty "overlaid" array; nothing to plot.')
            return
        if steps <= 0:
            steps = 1
        steps = min(steps, n)

        # Moving average using convolution (centered window via 'same')
        kernel = np.ones(steps, dtype=float) / float(steps)
        ma = np.convolve(x, kernel, mode='same')
        overall = float(np.mean(x)) if include_overall else None

        # Prepare figure (short height)
        import matplotlib as mpl
        mpl.rcParams.update({'pdf.fonttype': 42, 'ps.fonttype': 42})  # embed fonts as TrueType for vector editors
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))

        ax.plot(ma, color='tab:red', linewidth=1.5, label=f'MA (window={steps})')
        if include_overall:
            ax.hlines(overall, 0, n - 1, colors='tab:blue', linestyles='dashed', linewidth=1.0,
                      label=f'Overall={overall:.2f}')

        ax.set_xlim(0, n - 1)
        ax.set_ylim(0, 0.6)
        # Keep y-axis (spine) on the left, but place tick labels on the right side of that axis (inside plot)
        ax.set_ylabel('')
        ax.set_xlabel('')
        ax.yaxis.set_ticks_position('left')
        ax.spines['left'].set_visible(True)
        ax.spines['right'].set_visible(False)
        # Move tick labels to the inside (right side of the left spine) using a negative pad
        # Increase the negative padding and shorten tick length to avoid label/tick overlap
        ax.tick_params(axis='y', which='both', labelleft=True, labelright=False, pad=-18, direction='in', length=2)
        ax.grid(True, which='both', linestyle='--', linewidth=0.4, alpha=0.6)
        leg = ax.legend(loc='upper right', fontsize=8, frameon=False)
        if leg is not None:
            leg.set_title('Intervention Rate vs Step')
            try:
                leg._legend_box.align = 'left'
            except Exception:
                pass

        # Slightly lift the lowest y-tick label to avoid overlapping with the x-axis
        try:
            import matplotlib.transforms as mtransforms
            yticks = ax.get_yticks()
            if len(yticks) > 0:
                y0 = float(np.min(yticks))
                for lbl, y in zip(ax.get_yticklabels(), yticks):
                    if np.isclose(y, y0):
                        # move label up by 8 points in display coords (increase to avoid x-axis conflict)
                        offset = mtransforms.ScaledTranslation(0, 8/72.0, fig.dpi_scale_trans)
                        lbl.set_transform(lbl.get_transform() + offset)
                        break
        except Exception:
            pass

        # Clean look for publication
        ax.spines['top'].set_visible(False)

        # Ensure output directory exists
        out_dir = os.path.dirname(pdf_path) or '.'
        os.makedirs(out_dir, exist_ok=True)

        # Remove all external margins around the figure
        try:
            fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        except Exception:
            pass
        fig.tight_layout(pad=0.0)
        fig.savefig(pdf_path, format='pdf', bbox_inches='tight', pad_inches=0)
        log.info(f'Intervention rate plot saved to {pdf_path}')
        if show:
            plt.show()
        plt.close(fig)

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
            if 'image_nadir' in self.data:
                img_nadir_bgr = cv2.cvtColor(self.data['image_nadir'][i], cv2.COLOR_RGB2BGR)
                cv2.imshow('Image Nadir', img_nadir_bgr)
            if 'mask' in self.data:
                cv2.imshow('Mask', self.data['mask'][i])
            timestamp = self.data['timestamp'][i].decode() if 'timestamp' in self.data else None
            wp_yaw = self.data['wp_yaw'][i] if 'wp_yaw' in self.data else None
            alt = self.data['altitude'][i] if 'altitude' in self.data else None
            action = self.data['action'][i] if 'action' in self.data else None
            overlaid = self.data['overlaid'][i] if 'overlaid' in self.data else None
            log.info(f'Timestamp: {timestamp}, Action: {action}, WP-Yaw: {wp_yaw}, Altitude: {alt}, Overlaid: {overlaid}')

            cv2.waitKey(1000)  # Wait for 1 second

    def save_as_video(self, video_path: str = 'hitl_video.mp4', fps: int = 1):
        n = len(next(iter(self.data.values())))
        height, width = self.data['image'][0].shape[:2]
        fig_height = 1.2 * height  # Extra space for text
        fig_width = 2 * width

        video_writer = cv2.VideoWriter(
            video_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (int(fig_width), int(fig_height))
        )

        step: int = 0
        for i in tqdm(range(n)):
            img = self.data['image'][i]
            mask = self.data['mask'][i] if 'mask' in self.data else np.zeros_like(img)
            # timestamp = self.data['timestamp'][i].decode() if 'timestamp' in self.data else ''
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
            # text = f'Time: {timestamp}\nAction: {action}\nOverlaid: {overlaid}'
            text = f'Step: {step}\nAction: {action}\nOverlaid: {overlaid}'
            axs[0].text(0.5, 0.5, text, ha='center', va='center', fontsize=6, wrap=True)

            # Image+mask subplot
            axs[1].imshow(np.hstack((img, mask_rgb)), interpolation='nearest')
            axs[1].axis('off')

            # Render to numpy array using buffer_rgba
            canvas = FigureCanvas(fig)
            canvas.draw()
            frame = np.frombuffer(canvas.buffer_rgba(), dtype=np.uint8)
            frame = frame.reshape(fig.canvas.get_width_height()[::-1] + (4,))
            frame_rgb = frame[..., :3]  # Drop alpha channel
            plt.close(fig)

            # Resize to match video size
            # frame_rgb = cv2.resize(frame_rgb, (int(fig_width), int(fig_height)))
            video_writer.write(cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))

            step += 1

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
    # data_files = [
    #     '../data/data_log_20250910_143236.h5',  # battery 1
    #     '../data/data_log_19691231_190334.h5',  # battery 2
    #     '../data/data_log_20250910_143334.h5',  # battery 3
    #     '../data/data_log_20250910_150110.h5',  # battery 4
    #     '../data/data_log_20250910_152547.h5',  # battery 5
    # ]

    data_files = [
        '../data/data_log_20251017_163715.h5',
        '../data/data_log_20251017_163956.h5',
    ]

    # Test h5 with nadir view images saved
    # data_files = [
    #     '../data/data_log_20251013_164923.h5'
    # ]

    reader = DataReader(filenames=data_files)

    try:
        # Usage 1: show logged image, mask and actions
        # reader.play()

        # Usage 2: save them as a video
        # reader.save_as_video(video_path='../videos/wabash_uptream_hitl_0729.mp4', fps=1)
        # reader.save_as_video(video_path='../videos/wabash_downstream_hitl_0729.mp4', fps=1)
        # reader.save_as_video(video_path='../videos/wabash_upstream_hitl_0910_battery5.mp4', fps=1)

        # Usage 3: save waypoints to map
        # reader.save_wps_to_map(map_name='wabash_upstream_0729.html')
        # reader.save_wps_to_map(map_name='wabash_downstream_0729.html')
        # reader.save_wps_to_map(map_name='wabash_upstream_0910.html', separate_trajectories=True)
        reader.save_wps_to_map(map_name='kepner_1017.html')

        # Usage 4: Save image with exif meta data
        # reader.save_image_with_exif(out_dir='../wabash_images_0910', mask_out_dir='../wabash_masks_0910', per_trajectory=True)
        # reader.save_image_with_exif(out_dir='../kepner_images_1017')

        # Usage 5: Save intervention rate plot as PDF
        # reader.save_intervention_rate_pdf(steps=50, pdf_path='../images/wabash_upstream_0910_intervention_rate.pdf',
        #                                   fig_width=7.0, fig_height=2.0, include_overall=True, show=False)

    except KeyboardInterrupt:
        log.warning("Playback interrupted by user.")
    finally:
        cv2.destroyAllWindows()
