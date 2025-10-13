# image_processor.py: Process received image frames.
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
import os.path
import sys
import time
import cv2
from datetime import datetime
from loguru import logger as log
log.remove()
log.add(sys.stderr, level="INFO")

from splashdrone4.freshest_frame import FreshestFrame
from splashdrone4.constants import RTSP_ADDR


class ImageProcessor:
    def __init__(
            self,
            height: int = 480,
            width: int = 640,
            record_video: bool = True,
    ):
        self.fcap = None
        self.h = height
        self.w = width
        self.record_video = record_video

    def init(self):
        # Get RTSP streamed video
        vcap = cv2.VideoCapture(RTSP_ADDR)
        while not vcap.isOpened():
            log.warning('Cannot open RTSP stream, waiting ...')
            time.sleep(1)
        vcap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        vcap.set(cv2.CAP_PROP_FRAME_WIDTH, self.w)
        vcap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.h)
        fps = vcap.get(cv2.CAP_PROP_FPS)
        log.info(f'RTSP stream available, fps {fps}, height: {self.h}, width: {self.w}!')

        # Use threading to always get the latest frame
        video_filename: str = f'video_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4'
        video_path: str = os.path.join(os.path.dirname(__file__), f'../videos/{video_filename}')
        self.fcap = FreshestFrame(vcap, record=self.record_video, output_path=video_path)

    def get_bytes_img(self):
        if not self.fcap:
            log.warning('Call init() first!')
            return None

        ret, frame = self.fcap.read()
        if ret:
            frame = cv2.resize(frame, (self.w, self.h))
            imgbytes = cv2.imencode('.ppm', frame)[1].tobytes()
            return imgbytes
        else:
            log.warning("RTSP frame is empty!")
            return None

    def get_cv_img(self):
        if not self.fcap:
            log.warning('Call init() first!')
            return None

        ret, frame = self.fcap.read()
        if ret:
            frame = cv2.resize(frame, (self.w, self.h))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # Convert BGR to RGB
            return frame
        return None

    def release(self):
        self.fcap.release()
        log.info('Released RTSP stream.')


if __name__ == '__main__':
    # Display image stream
    ip = ImageProcessor(width=1280, height=720, record_video=True)
    try:
        ip.init()
        while True:
            img = ip.get_cv_img()
            if img is not None:
                img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                cv2.imshow('Image', img_bgr)
                cv2.waitKey(1)
    except KeyboardInterrupt:
        log.warning(f'Video interrupted by user.')
    finally:
        ip.release()