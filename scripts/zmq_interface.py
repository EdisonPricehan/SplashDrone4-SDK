#!/usr/bin/env python3
import cv2
# System packages
import zmq
import time
import numpy as np
from typing import Optional, List, Union, Tuple
from loguru import logger

# Local packages
from definitions import *
from gui import *
from constants import *
from image_processor import ImageProcessor
from key2action import Key2Action


class ZmqInterface:
    def __init__(
            self,
            enable_keyboard_control: bool = False,
            long_dist: float = 2.,
            lat_dist: float = 1.,
            vert_dist: float = 1.,
            yaw_angle: float = 20.,
            hori_speed: float = 1.,
            vert_speed: float = 0.5,
    ):
        # Init all reports (received from drone)
        self.fly_report = FlyReport()
        self.battery_report = BatteryReport()
        self.gimbal_report = GimbalReport()
        self.ack = Ack()

        # Init control commands that vary (sent to drone)
        self.ext_dev_onoff = ExtDevOnOff()
        self.gimbal_control = GimbalControl()

        # Init constants
        self.enable_keyboard_control = enable_keyboard_control
        self.long_dist = long_dist
        self.lat_dist = lat_dist
        self.vert_dist = vert_dist
        self.yaw_angle = yaw_angle
        self.hori_speed = hori_speed
        self.vert_speed = vert_speed

        # Init runtime variables
        self.m3d_waypoints = []  # movement in 3d, each item is relative position in meter (x, y, z) - NOT WORKING
        self.mission_waypoints = []  # waypoint as (lat, lon, hover_time), need to specify fly speed and altitude first
        self.img = None

        # Init image processor
        self.img_proc = ImageProcessor()
        self.img_proc.init()  # blocking operation until received image stream

        # Start keyboard listening thread
        self.k2a = Key2Action() if enable_keyboard_control else None

        # Create ZMQ context
        self.context = zmq.Context()

        # Init ZMQ publisher
        self.pub = self.context.socket(zmq.PUB)
        self.pub.bind(ZMQ_PUB_ADDR)

        # Init ZMQ subscribers
        self.sub1 = self.create_sub_and_connect(TOPIC_FLY_REPORT)
        self.sub2 = self.create_sub_and_connect(TOPIC_BATTERY_REPORT)
        self.sub3 = self.create_sub_and_connect(TOPIC_GIMBAL_REPORT)
        self.sub4 = self.create_sub_and_connect(TOPIC_ACK)

        # Create mapping from topic name to tuple (format, sub socket, report variable)
        self.topic2tuple = {TOPIC_FLY_REPORT: (FORMAT_FLY_REPORT, self.sub1, self.fly_report),
                            TOPIC_BATTERY_REPORT: (FORMAT_BATTERY_REPORT, self.sub2, self.battery_report),
                            TOPIC_GIMBAL_REPORT: (FORMAT_GIMBAL_REPORT, self.sub3, self.gimbal_report),
                            TOPIC_ACK: (FORMAT_ACK, self.sub4, self.ack)}

    def update_reports(self) -> None:
        for k, (fmt, sub, report) in self.topic2tuple.items():
            try:
                binary_topic, data_buffer = sub.recv(zmq.DONTWAIT).split(b' ', 1)
                topic = binary_topic.decode(encoding='ascii')
                if topic == k:
                    report_tuple = struct.unpack(fmt, data_buffer)
                    report.update(report_tuple)
                else:
                    logger.warning("Topic name mismatched!")
            except zmq.ZMQError as e:
                if e.errno == zmq.EAGAIN:
                    pass  # no message was ready (yet!)
                else:
                    logger.error(str(e))

    def create_sub_and_connect(self, topic: str) -> zmq.Socket:
        sub = self.context.socket(zmq.SUB)
        sub.setsockopt(zmq.SUBSCRIBE, topic.encode('ascii'))
        sub.setsockopt(zmq.LINGER, 0)
        # sub.setsockopt(zmq.CONFLATE, 1)
        sub.connect(ZMQ_SUB_ADDR)
        logger.info(f"Sub to {topic} connected!")
        return sub

    def get_img(self):
        self.img = self.img_proc.get_cv_img()

        if self.img is None:
            logger.warning("Image is None, please check the image stream.")
        else:
            logger.info(f'Image received with shape: {self.img.shape}, dtype: {self.img.dtype}')

        return self.img

    def step(self, action: Union[List, np.ndarray]):
        """
        Execute the action on the drone.

        :param action: A list or numpy array of shape (4,) representing the action to be taken.
        :return: None
        """
        if isinstance(action, List):
            a = np.array(action, dtype=int)
        elif isinstance(action, np.ndarray):
            a = action.astype(int)
        else:
            raise TypeError(f"Action must be a List or np.ndarray, got {type(action)}")

        logger.info(f"Action received: {a}")

        # Update reports from drone
        self.update_reports()

        if not self.fly_report.updated:
            logger.warning("Fly report not updated, waiting for new report...")
            return

        if self.fly_report.GpsNum < 9:
            logger.warning(f"GPS number {self.fly_report.GpsNum} is less than 9, waiting for better GPS signal...")
            return

        # Get relative distances in 3D space
        x, y, z, theta = self._get_relative_dist(a)

        # Yaw control
        if abs(theta) > 1e-3:
            self.set_gimbal(yaw=theta)

            self.gimbal_report.updated = False
        # Waypoint control
        else:
            # Set horizontal speed
            set_speed = SetSpeed(speed=self.hori_speed, act_now=True)
            self.pub.send(set_speed.getPacked())

            # Set altitude
            set_alt = SetAlt(alt=self.fly_report.Altitude + z, act_now=True)
            self.pub.send(set_alt.getPacked())

            # Set waypoint
            cur_wp_with_yaw = WayPointWithYaw(self.fly_report.Lat / 1e7,
                                              self.fly_report.Lon / 1e7,
                                              self.fly_report.ATTYaw)
            wp = WayPoint.from_cartesian(cur_wp_with_yaw, x=x, y=y, hover_time=0, act_now=True)
            self.pub.send(wp.getPacked())

            # Reset fly report updated flag
            self.fly_report.updated = False

    def _get_relative_dist(self, action: np.ndarray) -> Tuple[float, float, float, float]:
        """
        Convert action to relative distance in 3D space.
        Action is expected to be a numpy array of shape (4,) with values in [0, 2], where 1 means no operation.
        Although the action space is multi-discrete, here we treat it as a single discrete action.
        The 3 action branches are exclusive, meaning only one of them can be activated at a time.
        The judgement order of the action branches is as follows:
        - action[0]: vertical movement (0: up, 1: no operation, 2: down)
        - action[1]: yaw control (0: counter-clockwise, 1: no operation, 2: clockwise) in top-down view
        - action[2]: horizontal movement in longitudinal direction (0: forward, 1: no operation, 2: backward)
        - action[3]: horizontal movement in lateral direction (0: left, 1: no operation, 2: right)

        Args:
            action (np.ndarray): A numpy array of shape (4,) with values in [0, 2].

        Returns:
            Tuple[float, float, float, float]: A tuple containing the relative distances in x, y, z and theta.
        """
        assert action.shape == (4,), f"Action shape must be (4,), got {action.shape}"

        x, y, z, theta = 0, 0, 0, 0
        if action[0] != 1:
            z = self.vert_dist if action[0] == 0 else -self.vert_dist
        elif action[1] != 1:
            theta = self.yaw_angle if action[1] == 0 else -self.yaw_angle
        elif action[2] != 1:
            x = self.long_dist if action[2] == 0 else -self.long_dist
        elif action[3] != 1:
            y = self.lat_dist if action[3] == 0 else -self.lat_dist

        return x, y, z, theta

    def take_off(self, height: float = 1.0):
        """
        Send the takeoff command to the drone with a specified height.
        :param height: The height to take off to in meters. Default is 1.0 meter.
        :return: None
        """
        takeoff = TakeOff(height=height)
        self.pub.send(takeoff.getPacked())
        logger.info(f"Takeoff command sent with height {height}.")

    def land(self):
        """
        Send the land command to the drone.
        :return: None
        """
        land = Land()
        self.pub.send(land.getPacked())
        logger.info("Land command sent.")

    def return_home(self):
        """
        Send the return home command to the drone.
        :return: None
        """
        return_home = ReturnToHome()
        self.pub.send(return_home.getPacked())
        logger.info("Return home command sent.")

    def set_ext_dev(
            self,
            plr1_on: bool = False,
            plr2_on: bool = False,
            strobe_light_on: bool = True,
            arm_light_on: bool = True,
    ):
        """
        Set the external devices on/off state.
        :param plr1_on: Whether to turn on the first Payload Release (PLR1).
        :param plr2_on: Whether to turn on the second Payload Release (PLR2).
        :param strobe_light_on: Whether to turn on the strobe light.
        :param arm_light_on: Whether to turn on the arm light.
        :return: None
        """
        self.ext_dev_onoff.plr1 = plr1_on
        self.ext_dev_onoff.plr2 = plr2_on
        self.ext_dev_onoff.strobe_light = strobe_light_on
        self.ext_dev_onoff.arm_light = arm_light_on
        self.pub.send(self.ext_dev_onoff.getPacked())
        logger.info(f"External devices set: "
                    f"PLR1={plr1_on}, "
                    f"PLR2={plr2_on}, "
                    f"Strobe Light={strobe_light_on}, "
                    f"Arm Light={arm_light_on}.")

    def set_gimbal(
            self,
            roll: Optional[float] = None,
            pitch: Optional[float] = None,
            yaw: Optional[float] = None,
    ):
        """
        Set the gimbal control angles.
        :param roll: The roll angle in degrees, if None, it remains as is.
        :param pitch: The pitch angle in degrees, if None, it remains as is.
        :param yaw: The yaw angle in degrees, if None, it remains as is.
        :return: None
        """
        if roll is not None:
            self.gimbal_control.roll = int(roll)
        if pitch is not None:
            self.gimbal_control.pitch = int(pitch)
        if yaw is not None:
            self.gimbal_control.yaw = int(yaw)
        self.pub.send(self.gimbal_control.getPacked())
        logger.info(f"Gimbal control set: "
                    f"Roll={self.gimbal_control.roll}, "
                    f"Pitch={self.gimbal_control.pitch}, "
                    f"Yaw={self.gimbal_control.yaw}.")


if __name__ == '__main__':
    # Test image
    zmq_interface = ZmqInterface(enable_keyboard_control=True)
    i = 0
    while i < 1000:
        img = zmq_interface.get_img()
        cv2.imshow('Image', img)
        cv2.waitKey(10)
        i += 1



