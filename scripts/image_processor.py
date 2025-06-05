
import time
import cv2

from freshest_frame import FreshestFrame

# constant rtsp address
RTSP_ADDR = "rtsp://192.168.2.220:554"  # https://support.swellpro.com/hc/en-us/articles/5890485717017-SplashDrone-4-SDK


class ImageProcessor:
    def __init__(self):
        self.fcap = None

    def init(self):
        # Get RTSP streamed video
        vcap = cv2.VideoCapture(RTSP_ADDR)
        while not vcap.isOpened():
            print('Cannot open RTSP stream, waiting ...')
            time.sleep(1)
        vcap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        vcap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        vcap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        fps = vcap.get(cv2.CAP_PROP_FPS)
        print(f'RTSP stream available, fps {fps}!')

        # Use threading to always get the latest frame
        self.fcap = FreshestFrame(vcap)

    def get(self):
        if not self.fcap:
            print('Call Init() first!')
            return None
        ret, frame = self.fcap.read()
        if ret:
            frame = cv2.resize(frame, (640, 480))
            imgbytes = cv2.imencode('.ppm', frame)[1].tobytes()
            return imgbytes
        else:
            print("RTSP frame is empty!")
            return None

    def get_cv_img(self):
        if not self.fcap:
            print('Call Init() first!')
            return None
        ret, frame = self.fcap.read()
        if ret:
            return frame
        return None

    def release(self):
        self.fcap.release()
