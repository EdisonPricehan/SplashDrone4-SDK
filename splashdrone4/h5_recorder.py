#!/usr/bin/env python3
# h5_recorder.py: Record images, GPS waypoints with yaw, and altitude to HDF5.
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

from __future__ import annotations

import sys
import time
import signal
import argparse
import datetime as dt
import numpy as np
import cv2
from typing import Optional
from loguru import logger as log

log.remove()
log.add(sys.stderr, level="INFO")

# Local imports
from splashdrone4.constants import IMG_HEIGHT, IMG_WIDTH, ACTION_DIM
from splashdrone4.zmq_interface import ZmqInterface
from splashdrone4.data_logger import DataLogger


class H5Recorder:
    def __init__(
        self,
        data_len: int = 1000,
        start_tcp_client: bool = True,
        use_init_heading: bool = False,
        debug: bool = False,
        poll_hz: float = 20.0,
        image_wait_timeout_s: float = 0.5,
    ) -> None:
        """
        Initialize the H5 recorder.
        Saves an entry each time a new fly report is received.
        """
        self.poll_hz = max(poll_hz, 1.0)
        self.image_wait_timeout_s = max(image_wait_timeout_s, 0.0)

        # Initialize interfaces
        self.zmq = ZmqInterface(
            img_height=IMG_HEIGHT,
            img_width=IMG_WIDTH,
            start_tcp_client=start_tcp_client,
            use_init_heading=use_init_heading,
            debug=debug,
        )
        self.logger = DataLogger(data_len=data_len)

        # Shutdown flag
        self._running = True

    def _get_latest_image(self) -> Optional[np.ndarray]:
        """Try to fetch the latest image with a short timeout."""
        end_time = time.time() + self.image_wait_timeout_s
        img = None
        while time.time() < end_time:
            img = self.zmq.get_img()
            if img is not None:
                # Ensure dtype and shape are correct
                if img.dtype != np.uint8:
                    img = img.astype(np.uint8)
                if img.shape == (IMG_HEIGHT, IMG_WIDTH, 3):
                    return img
                else:
                    log.warning(
                        f"Image shape {img.shape} does not match expected {(IMG_HEIGHT, IMG_WIDTH, 3)}; retrying..."
                    )
                    # brief wait before next try
            time.sleep(0.01)
        return None

    def _save_one(self) -> None:
        """Save one record when a new fly report arrives."""
        # Build timestamp
        # timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp = dt.datetime.now().isoformat(sep=' ', timespec='milliseconds')

        # Extract GPS + yaw + altitude from fly report (no need to wait for gimbal report)
        fr = self.zmq.fly_report
        lat = fr.Lat / 1e7
        lon = fr.Lon / 1e7
        yaw = fr.ATTYaw
        alt = float(fr.Altitude)
        wp_yaw = np.array([lat, lon, yaw], dtype=np.float32)

        # Get latest image (with a brief wait)
        img = self._get_latest_image()
        if img is None:
            log.warning("No valid image available at fly report update; skipping this record.")
            return

        # Show image
        cv2.imshow("Live Image", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        cv2.waitKey(1)

        # Fill optional fields with safe defaults
        image_nadir = img  # use current image for nadir placeholder
        mask = np.zeros((IMG_HEIGHT, IMG_WIDTH), dtype=np.uint8)
        action = np.ones((ACTION_DIM,), dtype=np.uint8)
        overlaid = True

        # Log to HDF5
        self.logger.log_data(
            timestamp=timestamp,
            wp_yaw=wp_yaw,
            alt=alt,
            image=img,
            image_nadir=image_nadir,
            mask=mask,
            action=action,
            overlaid=overlaid,
        )

    def run(self) -> None:
        """Main loop: poll reports and save on fly report updates."""
        log.info("H5 recorder started. Waiting for fly report updates...")
        try:
            while self._running:
                # Pull any new reports
                self.zmq.update_reports()

                # If a fresh fly report is available, record a sample
                if self.zmq.fly_report.updated:
                    try:
                        self._save_one()
                    finally:
                        # Reset flag so we only save once per update
                        self.zmq.fly_report.updated = False
                else:
                    # Sleep a bit to avoid busy loop
                    time.sleep(1.0 / self.poll_hz)
        except KeyboardInterrupt:
            log.info("Keyboard interrupt received. Stopping recorder...")
        finally:
            self.close()

    def close(self) -> None:
        """Gracefully close all resources."""
        if self._running:
            self._running = False
        try:
            self.logger.close()
        except Exception as e:
            log.error(f"Error closing DataLogger: {e}")
        try:
            self.zmq.close()
        except Exception as e:
            log.error(f"Error closing ZmqInterface: {e}")
        log.info("H5 recorder stopped and resources released.")


def _setup_sig_handlers(rec: H5Recorder) -> None:
    def _handler(signum, frame):
        log.info(f"Signal {signum} received. Shutting down...")
        rec.close()
        sys.exit(0)

    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, _handler)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Record SplashDrone4 data to HDF5 on fly report updates.")
    parser.add_argument("--data-len", type=int, default=500, help="Max records per HDF5 file before rolling over.")
    parser.add_argument("--no-start-tcp-client", action="store_true", help="Do not auto-start the tcp_client process.")
    parser.add_argument("--use-init-heading", action="store_true", help="Use initial heading for yaw fusion (ZMQ interface).")
    parser.add_argument("--debug", action="store_true", help="Debug mode for ZMQ interface.")
    parser.add_argument("--poll-hz", type=float, default=20.0, help="Polling rate for ZMQ reports.")
    parser.add_argument("--img-wait", type=float, default=0.5, help="Max seconds to wait for an image per save.")

    args = parser.parse_args(argv)

    rec = H5Recorder(
        data_len=args.data_len,
        # start_tcp_client=not args.no_start_tcp_client,
        start_tcp_client=False,
        use_init_heading=args.use_init_heading,
        debug=args.debug,
        poll_hz=args.poll_hz,
        image_wait_timeout_s=args.img_wait,
    )
    _setup_sig_handlers(rec)
    rec.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

