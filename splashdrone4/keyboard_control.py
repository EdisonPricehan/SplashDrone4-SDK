# keyboard_control.py: High level interface to interact with SplashDrone4.
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


from splashdrone4.zmq_interface import ZmqInterface
from splashdrone4.key2action import Key2Action
from splashdrone4.data_logger import DataLogger
from splashdrone4.constants import IMG_HEIGHT, IMG_WIDTH, ACTION_DIM
from splashdrone4.definitions import WayPointWithYaw

import sys
import cv2
import datetime
import numpy as np
from typing import Optional, List
from loguru import logger as log
log.remove()
log.add(sys.stderr, level="INFO")


class KeyboardControl:
    def __init__(self, save_data: bool = True, data_len: int = 1000, debug: bool = False):
        """
        Initialize the KeyboardControl class.
        All key mappings are as follows:
            Left arrow: toggle strobe light.
            Right arrow: toggle arm lights.
            Up arrow: Take off.
            Down arrow: Land.
            Key r: reset gimbal.
            Key w: Increase drone altitude.
            Key s: Decrease drone altitude.
            Key a: Rotate drone camera ccw (top view).
            Key d: Rotate drone camera cw (top view).
            Key i: Move drone forward (along camera heading).
            Key k: Move drone backward (along camera heading).
            Key j: Move drone leftward (perpendicular to camera heading).
            Key l: Move drone rightward (perpendicular to camera heading).
        :param save_data: Whether to save data or not.
        :param data_len: The length of the data to be saved.
        :param debug: Whether check gps signal, skip check if True.
        """
        # Init zmq interface and keyboard reader
        self.zmq_interface = ZmqInterface(debug=debug)
        self.k2a = Key2Action()

        # Define constants
        self.save_data = save_data
        if self.save_data:
            self.data_logger = DataLogger(data_len=data_len)

        # Define variables
        self.strobe_light_on: bool = False
        self.arm_light_on: bool = False
        self.img = None

        # Reset the gimbal to a default position
        self.reset()

    def get_img(self, show: bool = True) -> np.ndarray:
        """
        Get the current image from the ZMQ interface.
        :param show: Whether to display the image using OpenCV.
        :return: The current image in RGB format.
        """
        self.img = self.zmq_interface.get_img()
        while self.img is None:
            log.warning('No image yet!')
            self.img = self.zmq_interface.get_img()

        if show:
            img_bgr = cv2.cvtColor(self.img, cv2.COLOR_RGB2BGR)
            cv2.imshow('img', img_bgr)
            cv2.waitKey(1)

        return self.img

    def reset(self):
        """
        Reset the gimbal and lights to default values.
        :return:
        """
        self.zmq_interface.reset()

    def step(self, action: Optional[List[int]] = None):
        """
        Take a step in the ZMQ interface with the given action.
        :param action: The action to be taken, if any.
        :return: A tuple containing the overlaid boolean, the action taken, the image when action was taken, and the
        reset boolean.
        """
        if action is not None:
            log.info(f'Agent action received: {action}')

        ep_reset, g2g, acted, overlaid, action_taken = self._keyboard_act(action_policy=action)

        img = self.get_img(show=True)
        wp_yaw = self.zmq_interface.get_gps_with_yaw(use_camera_heading=True)
        while not acted:  # acted is for internal check of whether a meaningful command has been received
            # Update the most recent image, a blocking call
            img = self.get_img(show=True)

            # Update the most recent drone gps and heading (actually is camera heading)
            wp_yaw = self.zmq_interface.get_gps_with_yaw(use_camera_heading=True)

            log.debug("Waiting for action input...")
            ep_reset, g2g, acted, overlaid, action_taken = self._keyboard_act(action_policy=action)

        log.info(f'lat: {wp_yaw.lat}, lon: {wp_yaw.lon}, yaw: {wp_yaw.yaw}')
        return img, wp_yaw, ep_reset, g2g, overlaid, action_taken

    def _keyboard_act(self, action_policy: Optional[List[int]] = None):
        # Update fly reports
        self.zmq_interface.update_reports()

        # Get control input from keyboard
        arrow = self.k2a.get_arrow_key()
        space = self.k2a.get_space_key()
        good_to_go = self.k2a.get_good_to_go_key()
        reset = self.k2a.get_reset_action()
        action = self.k2a.get_multi_discrete_action()

        reset_episode = False  # Whether the current episode is reset
        if arrow == 'up':  # Take off
            self.zmq_interface.take_off()
        elif arrow == 'down':  # Land
            self.zmq_interface.land()
        elif arrow == 'left':  # Toggle strobe light
            self.zmq_interface.set_ext_dev(
                plr1_on=False,
                plr2_on=False,
                strobe_light_on=not self.strobe_light_on,
                arm_light_on=self.zmq_interface.ext_dev_onoff.arm_light,
            )
            self.strobe_light_on = self.zmq_interface.ext_dev_onoff.strobe_light
        elif arrow == 'right':  # Toggle arm light
            self.zmq_interface.set_ext_dev(
                plr1_on=False,
                plr2_on=False,
                strobe_light_on=self.zmq_interface.ext_dev_onoff.strobe_light,
                arm_light_on=not self.arm_light_on,
            )
            self.arm_light_on = self.zmq_interface.ext_dev_onoff.arm_light
        elif reset == 'reset':
            self.zmq_interface.reset()
            reset_episode = True

        g2g = False  # Whether the agent is good to go (for inference)
        acted = True  # Whether a decision was made
        overlaid = False  # Whether the policy action was overlaid by human input
        # If human resets an episode, deems it as acted but not overlaid
        if not reset_episode:
            if good_to_go == 'good_to_go':  # Proceed agent policy
                if action_policy is not None:
                    log.warning(f'Already given agent action {action_policy} when good to go.')
                g2g = True
            elif space == 'space':  # Consent agent action
                if action_policy is not None:
                    log.info("Consent for agent action.")  # Take action based on agent policy
                    self.zmq_interface.step(action=action_policy)
                else:
                    log.warning('No agent action to consent to, please provide the policy action.')
                    acted = False
            elif action is not None:  # Take action based on keyboard input from human
                self.zmq_interface.step(action=action)
                overlaid = True
            else:
                acted = False
                log.debug("No action taken, please press a key.")

        return reset_episode, g2g, acted, overlaid, action if overlaid else action_policy

    def log_data(
            self,
            wp_yaw: Optional[WayPointWithYaw] = None,
            image: Optional[np.ndarray] = None,
            mask: Optional[np.ndarray] = None,
            action: List[int] = None,
            overlaid: bool = False,
    ):
        if self.save_data:
            self.data_logger.log_data(
                timestamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
                wp_yaw=np.zeros((3,)) if wp_yaw is None else np.array([wp_yaw.lat, wp_yaw.lon, wp_yaw.yaw]),
                image=self.img if image is None else image,
                mask=np.zeros((IMG_HEIGHT, IMG_WIDTH)) if mask is None else mask,
                action=np.ones(ACTION_DIM) if action is None else np.array(action),
                overlaid=overlaid,
            )

    def run(self):
        while True:
            # Get control input from keyboard while updating the image
            img, wp_yaw, ep_reset, g2g, overlaid, action = self.step()
            log.info(f'Action taken: {action}')

            # Save data if required
            self.log_data(
                wp_yaw=wp_yaw,
                image=img,
                mask=None,
                action=action,
                overlaid=overlaid,
            )

    def close(self):
        self.zmq_interface.close()
        self.k2a.stop()
        log.info("Keyboard control closed.")
        if self.save_data:
            self.data_logger.close()
            log.info("Data logger closed.")


if __name__ == "__main__":
    keyboard_control = KeyboardControl(save_data=True, data_len=10, debug=True)

    try:
        keyboard_control.run()
    except KeyboardInterrupt:
        log.warning("Keyboard control interrupted.")
    finally:
        keyboard_control.close()
