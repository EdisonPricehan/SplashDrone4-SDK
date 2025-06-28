# freshest_frame.py: A thread that keeps getting the latest received image frame.
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


import sys
import cv2
import threading
from loguru import logger as log
log.remove()
log.add(sys.stderr, level="INFO")


# acts (partly) like a cv.VideoCapture
class FreshestFrame(threading.Thread):
    def __init__(
            self,
            capture,
            th_name='FreshestFrame',
            record=False,
            output_path='output.mp4',
            fps=30.0,
    ):
        self.capture = capture
        assert self.capture.isOpened()

        # this lets the read() method block until there's a new frame
        self.cond = threading.Condition()

        # this allows us to stop the thread gracefully
        self.running = False

        # keeping the newest frame around
        self.frame = None

        # passing a sequence number allows read() to NOT block
        # if the currently available one is exactly the one you ask for
        self.latestnum = 0

        # Video recording setup
        self.recording = record
        self.video_writer = None
        self.video_fps = fps
        self.output_path = output_path
        self.callback = None

        super().__init__(name=th_name)
        self.start()

    def start(self):
        self.running = True
        super().start()

    def release(self, timeout=None):
        self.running = False
        self.join(timeout=timeout)
        self.capture.release()
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

    def run(self):
        counter = 0
        writer_initialized = False

        while self.running:
            # block for fresh frame
            (rv, img) = self.capture.read()
            assert rv
            counter += 1

            # publish the frame
            with self.cond:  # lock the condition for this operation
                self.frame = img if rv else None
                self.latestnum = counter
                self.cond.notify_all()

            # Initialize writer on first frame if recording requested
            if self.recording and not writer_initialized and img is not None:
                h, w = img.shape[:2]
                frame_size = (w, h)
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                self.video_writer = cv2.VideoWriter(self.output_path, fourcc, self.video_fps, frame_size)

                if not self.video_writer.isOpened():
                    log.error('Video writer is not opened. Something is wrong.')

                def save_frame_callback(frame):
                    if self.video_writer is not None and frame is not None:
                        self.video_writer.write(frame)

                self.callback = save_frame_callback
                writer_initialized = True
                log.info(f'Video is recording with frame size {frame_size}...')

            if self.callback:
                self.callback(img)

    def read(self, wait=True, seqnumber=None, timeout=None):
        # with no arguments (wait=True), it always blocks for a fresh frame
        # with wait=False it returns the current frame immediately (polling)
        # with a seqnumber, it blocks until that frame is available (or no wait at all)
        # with timeout argument, may return an earlier frame;
        #   may even be (0,None) if nothing received yet

        with self.cond:
            if wait:
                if seqnumber is None:
                    seqnumber = self.latestnum+1
                if seqnumber < 1:
                    seqnumber = 1

                rv = self.cond.wait_for(lambda: self.latestnum >= seqnumber, timeout=timeout)
                if not rv:
                    return self.latestnum, self.frame

            return self.latestnum, self.frame