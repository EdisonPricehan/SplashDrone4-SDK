#!/usr/bin/env python3
# zmq_interface.py: Interface using ZeroMQ to interact with tcp_client.
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


# System packages
import os
import sys
import zmq
import time
import numpy as np
from typing import Optional, List, Union, Tuple
from loguru import logger as log
log.remove()
log.add(sys.stderr, level="INFO")
import subprocess

# Local packages
from splashdrone4.constants import TCP_CLIENT_ADDR
from splashdrone4.definitions import *
from splashdrone4.constants import *
from splashdrone4.image_processor import ImageProcessor


class ZmqInterface:
    def __init__(
            self,
            img_height: int = 128,
            img_width: int = 128,
            long_dist: float = 5.,
            lat_dist: float = 3.,
            vert_dist: float = 2.,
            yaw_angle: float = 15.,
            pitch_angle_fixed: float = 15.,
            takeoff_height_default: float = 5.,
            hori_speed: float = 3.,
            vert_speed: float = 0.5,
            start_tcp_client: bool = True,
            debug: bool = False,
    ):
        """
        Initialize the ZMQ interface for communication with the SplashDrone4.
        :param img_height: Height of the image in pixels.
        :param img_width: Width of the image in pixels.
        :param long_dist: longitudinal distance for movement in meters.
        :param lat_dist: lateral distance for movement in meters.
        :param vert_dist: vertical distance for movement in meters.
        :param yaw_angle: yaw angle for rotation in degrees.
        :param pitch_angle_fixed: fixed pitch angle for gimbal in degrees.
        :param takeoff_height_default: default takeoff height in meters.
        :param hori_speed: horizontal speed for movement in meters per second.
        :param vert_speed: vertical speed for movement in meters per second.
        :param start_tcp_client: If True, starts the TCP client process to communicate with the drone.
        :param debug: If True, does not check GPS number, for indoor testing or non-flight commands.
        """
        if start_tcp_client:
            # Init TCP communication process
            tcp_client_install_path = 'install/splashdrone/lib/splashdrone/tcp_client'
            tcp_client_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../..', tcp_client_install_path)
            log.info(f'TCP client path: {tcp_client_path}')
            assert os.path.exists(tcp_client_path), (f'TCP client path {tcp_client_path} does not exist, '
                                                     f'make sure you have built the ROS2 package using '
                                                     f'"colcon build --symlink-install"!')

            # Start the TCP client process
            self.tcp_client_process = subprocess.Popen([tcp_client_path, TCP_CLIENT_ADDR])
            log.info('TCP client process started.')

        # Init all reports (received from drone)
        self.fly_report = FlyReport()
        self.battery_report = BatteryReport()
        self.gimbal_report = GimbalReport()
        self.ack = Ack()

        # Init control commands that vary (sent to drone)
        self.ext_dev_onoff = ExtDevOnOff()
        self.gimbal_control = GimbalControl()
        self.camera_control = CameraControl()

        # Init constants
        self.img_height = img_height
        self.img_width = img_width
        self.long_dist = long_dist
        self.lat_dist = lat_dist
        self.vert_dist = vert_dist
        self.yaw_angle = yaw_angle
        self.pitch_angle_fixed = pitch_angle_fixed
        self.takeoff_height_default = takeoff_height_default
        self.hori_speed = hori_speed
        self.vert_speed = vert_speed
        self.start_tcp_client = start_tcp_client
        self.debug = debug

        # Init runtime variables
        self.m3d_waypoints = []  # movement in 3d, each item is relative position in meter (x, y, z) - NOT WORKING
        self.mission_waypoints = []  # waypoint as (lat, lon, hover_time), need to specify fly speed and altitude first
        self.img = None
        self.camera_yaw_offset = 0.  # yaw change in degrees of drone camera

        # Init image processor
        self.img_proc = ImageProcessor(height=img_height, width=img_width)
        self.img_proc.init()  # blocking operation until received image stream
        log.info('Image processor initialized and ready to receive images.')

        # Create ZMQ context
        self.context = zmq.Context()
        log.info('ZMQ context created!')

        # Init ZMQ publisher
        self.pub = self.context.socket(zmq.PUB)
        self.pub.bind(ZMQ_PUB_ADDR)
        log.info(f'ZMQ publisher bound to {ZMQ_PUB_ADDR}!')

        # Init ZMQ subscribers
        self.sub1 = self.create_sub_and_connect(TOPIC_FLY_REPORT)
        self.sub2 = self.create_sub_and_connect(TOPIC_BATTERY_REPORT)
        self.sub3 = self.create_sub_and_connect(TOPIC_GIMBAL_REPORT)
        self.sub4 = self.create_sub_and_connect(TOPIC_ACK)
        log.info('ZMQ subscribers created and connected!')

        # Create mapping from topic name to tuple (format, sub socket, report variable)
        self.topic2tuple = {TOPIC_FLY_REPORT: (FORMAT_FLY_REPORT, self.sub1, self.fly_report),
                            TOPIC_BATTERY_REPORT: (FORMAT_BATTERY_REPORT, self.sub2, self.battery_report),
                            TOPIC_GIMBAL_REPORT: (FORMAT_GIMBAL_REPORT, self.sub3, self.gimbal_report),
                            TOPIC_ACK: (FORMAT_ACK, self.sub4, self.ack)}

    def update_reports(self) -> None:
        """
        Update the reports from the drone by receiving messages from the ZMQ subscribers.
        :return: None
        """
        for k, (fmt, sub, report) in self.topic2tuple.items():
            try:
                binary_topic, data_buffer = sub.recv(zmq.DONTWAIT).split(b' ', 1)
                topic = binary_topic.decode(encoding='ascii')
                if topic == k:
                    report_tuple = struct.unpack(fmt, data_buffer)
                    report.update(report_tuple)
                else:
                    log.warning("Topic name mismatched!")
            except zmq.ZMQError as e:
                if e.errno == zmq.EAGAIN:
                    pass  # no message was ready (yet!)
                else:
                    log.error(str(e))

    def create_sub_and_connect(self, topic: str) -> zmq.Socket:
        sub = self.context.socket(zmq.SUB)
        sub.setsockopt(zmq.SUBSCRIBE, topic.encode('ascii'))
        sub.setsockopt(zmq.LINGER, 0)
        # sub.setsockopt(zmq.CONFLATE, 1)
        sub.connect(ZMQ_SUB_ADDR)
        log.info(f"Sub to {topic} connected!")
        return sub

    def get_img(self) -> Optional[np.ndarray]:
        """
        Get the latest image from the image processor.
        :return:
        """
        self.img = self.img_proc.get_cv_img()

        if self.img is None:
            log.warning("Image is None, please check the image stream.")
        else:
            log.debug(f'Image received with shape: {self.img.shape}, dtype: {self.img.dtype}')

        return self.img

    def get_gps_with_yaw(self, use_camera_heading: bool = True) -> Optional[WayPointWithYaw]:
        """
        Get the current gps location and drone compass (angle relative to earth north, -180 to 180).
        :param use_camera_offset: Use camera heading if True, otherwise drone heading.
        :return: WayPointWithYaw
        """
        if self.fly_report.updated:
            waypoint_with_yaw = WayPointWithYaw(
                lat=self.fly_report.Lat / 1e7,
                lon=self.fly_report.Lon / 1e7,
                yaw=self.fly_report.ATTYaw + (self.camera_yaw_offset if use_camera_heading else 0),
            )
            return waypoint_with_yaw
        else:
            log.warning('Fly report is not updated when getting waypoint with yaw.')
            return None

    def reset(self):
        """
        Reset the gimbal and lights to the default values.
        :return: None
        """
        self.set_gimbal(roll=0, pitch=self.pitch_angle_fixed, yaw=0)

        self.set_ext_dev()

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

        log.info(f"Action received: {a}")

        # Update reports from drone
        self.update_reports()

        if not self.fly_report.updated:
            log.warning("Fly report not updated, waiting for new report...")
            return

        if not self.debug and self.fly_report.GpsNum < 9:
            log.warning(f"GPS number {self.fly_report.GpsNum} is less than 9, waiting for better GPS signal...")
            return

        # Get relative distances in 3D space
        x, y, z, theta = self._get_relative_dist(a)

        # Yaw control
        if abs(theta) > 1e-3:
            self.camera_yaw_offset += theta
            self.set_gimbal(yaw=self.camera_yaw_offset)
            # log.info(f"Gimbal yaw set to: {self.camera_yaw_offset}")

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
            cur_wp_with_yaw = self.get_gps_with_yaw(use_camera_heading=True)
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

    def take_off(self, height: Optional[float] = None):
        """
        Send the takeoff command to the drone with a specified height.
        :param height: The height to take off to in meters.
        :return: None
        """
        if height is None:
            height = self.takeoff_height_default
        else:
            assert height > 1.0, "Takeoff height must be greater than 1.0 meter."

        takeoff = TakeOff(height=height)
        self.pub.send(takeoff.getPacked())
        log.info(f"Takeoff command sent with height {height}.")

    def land(self):
        """
        Send the land command to the drone.
        :return: None
        """
        land = Land()
        self.pub.send(land.getPacked())
        log.info("Land command sent.")

    def return_home(self):
        """
        Send the return home command to the drone.
        :return: None
        """
        return_home = ReturnToHome()
        self.pub.send(return_home.getPacked())
        log.info("Return home command sent.")

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
        log.info(f"External devices set: "
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
        log.info(f"Gimbal control set: "
                    f"Roll={self.gimbal_control.roll}, "
                    f"Pitch={self.gimbal_control.pitch}, "
                    f"Yaw={self.gimbal_control.yaw}.")

    def set_camera(self, take_photo: bool = False, start_video: bool = False):
        """
        Set the camera control to take a photo or start video recording.
        :param take_photo: If True, take a photo.
        :param start_video: If True, start video recording; otherwise stop video recording.
        :return: None
        """
        if take_photo:
            self.camera_control.take_photo = True
            log.info("Camera set to take photo.")
        else:
            self.camera_control.take_photo = False

        if start_video:
            self.camera_control.start_video = True
            log.info("Camera set to start video recording.")
        else:
            self.camera_control.start_video = False
            log.info("Camera set to stop video recording.")

        self.pub.send(self.camera_control.getPacked())

    def close(self):
        # Terminate tcp_client process
        if hasattr(self, 'tcp_client_process') and self.tcp_client_process.poll() is None:
            self.tcp_client_process.terminate()
            self.tcp_client_process.wait()
            log.info('TCP client process terminated.')

        # Close ZMQ sockets
        for sub in [self.sub1, self.sub2, self.sub3, self.sub4]:
            sub.close()
        self.pub.close()
        self.context.term()
        log.info('ZMQ sockets closed and context terminated.')

        # Close image processor
        self.img_proc.release()
        log.info('Image processor closed.')

    def __del__(self):
        self.close()


if __name__ == '__main__':
    zmq_interface = ZmqInterface()

    # Test image
    # try:
    #     i = 0
    #     while i < 1000:
    #         img = zmq_interface.get_img()
    #         cv2.imshow('Image', img)
    #         cv2.waitKey(10)
    #         i += 1
    # except KeyboardInterrupt:
    #     log.info("Keyboard interrupt received.")
    #     zmq_interface.close()

    # Test external devices
    try:
        while True:
            zmq_interface.set_ext_dev(plr1_on=False, plr2_on=False, strobe_light_on=True, arm_light_on=True)
            log.info("Strobe light and arm light turned on for 3 seconds.")
            time.sleep(3)
            zmq_interface.set_ext_dev(plr1_on=False, plr2_on=False, strobe_light_on=False, arm_light_on=False)
            log.info("Strobe light and arm light turned off for 3 seconds.")
            time.sleep(3)
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received.")
        zmq_interface.close()
