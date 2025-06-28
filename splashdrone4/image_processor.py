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


import time
import cv2
from loguru import logger

from splashdrone4.freshest_frame import FreshestFrame
from splashdrone4.constants import RTSP_ADDR


class ImageProcessor:
    def __init__(self, height: int = 480, width: int = 640):
        self.fcap = None
        self.h = height
        self.w = width

    def init(self):
        # Get RTSP streamed video
        vcap = cv2.VideoCapture(RTSP_ADDR)
        while not vcap.isOpened():
            logger.warning('Cannot open RTSP stream, waiting ...')
            time.sleep(1)
        vcap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        vcap.set(cv2.CAP_PROP_FRAME_WIDTH, self.w)
        vcap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.h)
        fps = vcap.get(cv2.CAP_PROP_FPS)
        logger.info(f'RTSP stream available, fps {fps}, height: {self.h}, width: {self.w}!')

        # Use threading to always get the latest frame
        self.fcap = FreshestFrame(vcap)

    def get(self):
        if not self.fcap:
            logger.warning('Call init() first!')
            return None

        ret, frame = self.fcap.read()
        if ret:
            frame = cv2.resize(frame, (self.w, self.h))
            imgbytes = cv2.imencode('.ppm', frame)[1].tobytes()
            return imgbytes
        else:
            logger.warning("RTSP frame is empty!")
            return None

    def get_cv_img(self):
        if not self.fcap:
            logger.warning('Call init() first!')
            return None

        ret, frame = self.fcap.read()
        if ret:
            frame = cv2.resize(frame, (self.w, self.h))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # Convert BGR to RGB
            return frame
        return None

    def release(self):
        self.fcap.release()
        logger.info('Released RTSP stream.')
