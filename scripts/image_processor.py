import time
import cv2
from loguru import logger

from freshest_frame import FreshestFrame

# Constant rtsp address
RTSP_ADDR = "rtsp://192.168.2.220:554"  # https://support.swellpro.com/hc/en-us/articles/5890485717017-SplashDrone-4-SDK


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
            return frame
        return None

    def release(self):
        self.fcap.release()
        logger.info('Released RTSP stream.')
