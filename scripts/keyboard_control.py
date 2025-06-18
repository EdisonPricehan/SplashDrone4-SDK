from zmq_interface import ZmqInterface
from key2action import Key2Action
from data_logger import DataLogger

import sys
import cv2
import datetime
import numpy as np
from loguru import logger as log
log.remove()
log.add(sys.stderr, level="INFO")


class KeyboardControl:
    def __init__(self, save_data: bool = True, data_len: int = 1000):
        """
        Initialize the KeyboardControl class.
        :param save_data: Whether to save data or not.
        :param data_len: The length of the data to be saved.
        """
        # Init zmq interface and keyboard reader
        self.zmq_interface = ZmqInterface(debug=True)
        self.k2a = Key2Action()

        # Define constants
        self.save_data = save_data
        if self.save_data:
            self.data_logger = DataLogger(data_len=data_len)

        # Define variables
        self.strobe_light_on: bool = False
        self.arm_light_on: bool = False

    def run(self):
        while True:
            # Update fly reports
            self.zmq_interface.update_reports()

            # Get image
            img = self.zmq_interface.get_img()
            if img is None:
                log.warning('No image!')
            else:
                img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                cv2.imshow('img', img_bgr)
                cv2.waitKey(1)

            # Get control input from keyboard
            arrow = self.k2a.get_arrow_key()
            space = self.k2a.get_space_key()
            action = self.k2a.get_multi_discrete_action()

            key_pressed = True
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
            elif space == 'space':  # Consent agent action
                # TODO implement consent logic
                log.info("Consent for agent action received.")
            elif action is not None:  # Take action based on key input
                self.zmq_interface.step(action=action)
            else:
                key_pressed = False
                log.debug("No action taken, please press a key.")

            # Save data if required
            if self.save_data and key_pressed:
                if img is None or action is None:
                    log.warning("No image or action when saving data!")
                    continue

                # Save data to file
                self.data_logger.log_data(
                    timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    image=img,
                    action=np.array(action),
                )

    def close(self):
        self.zmq_interface.close()
        self.k2a.stop()
        log.info("Keyboard control closed.")
        if self.save_data:
            self.data_logger.close()
            log.info("Data logger closed.")


if __name__ == "__main__":
    keyboard_control = KeyboardControl(save_data=True, data_len=3)

    try:
        keyboard_control.run()
    except KeyboardInterrupt:
        log.warning("Keyboard control interrupted.")
    finally:
        keyboard_control.close()
