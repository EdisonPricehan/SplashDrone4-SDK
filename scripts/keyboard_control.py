from zmq_interface import ZmqInterface
from key2action import Key2Action

import time
from loguru import logger as log


class KeyboardControl:
    def __init__(self):
        self.zmq_interface = ZmqInterface()
        self.k2a = Key2Action()

        self.strobe_light_on: bool = False
        self.arm_light_on: bool = False

    def run(self):
        while True:
            # Update fly reports
            self.zmq_interface.update_reports()

            # Get control input from keyboard
            arrow = self.k2a.get_arrow_key()
            space = self.k2a.get_space_key()
            action = self.k2a.get_multi_discrete_action()

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
                log.info("No action taken, please press a key.")
                time.sleep(0.5)

    def close(self):
        self.zmq_interface.close()
        self.k2a.stop()
        log.info("Keyboard control closed.")


if __name__ == "__main__":
    keyboard_control = KeyboardControl()
    try:
        keyboard_control.run()
    except KeyboardInterrupt:
        log.warning("Keyboard control interrupted.")
    finally:
        keyboard_control.close()
