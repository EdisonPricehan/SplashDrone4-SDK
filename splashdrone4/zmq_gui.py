#!/usr/bin/env python3
# zmq_gui.py: GUI for interacting with SplashDrone4.
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
from splashdrone4.gui import *

from loguru import logger as log


class ZmqGui:
    # Finite states of drone
    STATES = ['standingby', 'takingoff', 'landing', 'rth']

    def __init__(self, img_height: int = 480, img_width: int = 640):
        """
        A pure Python class that communicates with SplashDrone4 with GUI.
        This class does not depend on ROS or ROS2.
        """
        self.zmq_interface = ZmqInterface(
            img_height=img_height,
            img_width=img_width,
            start_tcp_client=True,
            debug=True
        )

        # Init the variables
        self.cur_state = self.STATES[0]  # standingby by default

    def update_window(self):
        """
        Update the GUI window with the latest reports and image.
        """
        # Update fly report in gui
        if self.zmq_interface.fly_report.updated:
            # self.get_logger().info("Update fly report!")
            updateWindowFlyReport(self.zmq_interface.fly_report)
            # fly_report.updated = False

        # Update battery report in gui
        if self.zmq_interface.battery_report.updated:
            # self.get_logger().info("Update battery report!")
            updateWindowBatteryReport(self.zmq_interface.battery_report)
            # battery_report.updated = False

        # Update gimbal report in gui
        if self.zmq_interface.gimbal_report.updated:
            # self.get_logger().info("Update gimbal report!")
            updateWindowGimbalReport(self.zmq_interface.gimbal_report)
            # gimbal_report.updated = False

        # Deal with ack
        if self.zmq_interface.ack.updated:
            # log.info(f"Ack received: {self.zmq_interface.ack.mission_id=} {self.zmq_interface.ack.mission_type=} {self.zmq_interface.ack.mission_data=}")
            # TODO deal with ack
            self.zmq_interface.ack.updated = False

        # Update image in gui
        imgbytes = self.zmq_interface.img_proc.get_bytes_img()
        if imgbytes:
            window['-IMAGE-'].update(data=imgbytes)

    def process_event_ext_dev(self, event, values):
        """
        Process events related to payload release, strobe and arm lights.
        :param event:
        :param values:
        :return:
        """
        if event in ['-PLR1-', '-PLR2-', '-STROBE_LED-', '-ARM_LED-']:
            self.zmq_interface.set_ext_dev(
                plr1_on=values['-PLR1-'],
                plr2_on=values['-PLR2-'],
                strobe_light_on=values['-STROBE_LED-'],
                arm_light_on=values['-ARM_LED-'],
            )

    def process_event_gimbal(self, event, values):
        """
        Process events related to gimbal control.
        :param event:
        :param values:
        :return:
        """
        if event == '-GIMBAL_RESET-':
            self.zmq_interface.set_gimbal(0, 0, 0)
            updateWindowGimbalControl(self.zmq_interface.gimbal_control)
        elif event in ['-GIMBAL_SET_ROLL-RELEASE', '-GIMBAL_SET_PITCH-RELEASE', '-GIMBAL_SET_YAW-RELEASE']:
            self.zmq_interface.set_gimbal(
                roll=int(values['-GIMBAL_SET_ROLL-']),
                pitch=int(values['-GIMBAL_SET_PITCH-']),
                yaw=int(values['-GIMBAL_SET_YAW-']),
            )

    def process_event_photo_video(self, event, values):
        """
        Process events related to photo shooting and video recording.
        :param event:
        :param values:
        :return:
        """
        if event == '-PHOTO-':
            self.zmq_interface.set_camera(take_photo=True, start_video=False)
            window['-CAMERA_STATUS-'].update("Took a photo!")
        elif event == '-RECORD-':
            self.zmq_interface.set_camera(take_photo=False, start_video=True)
            window['-CAMERA_STATUS-'].update("Recording ...")
            window['-RECORD-'].update(disabled=True)
        elif event == '-STOP_RECORD-':
            self.zmq_interface.set_camera(take_photo=False, start_video=False)
            window['-CAMERA_STATUS-'].update("Stopped recording.")
            window['-RECORD-'].update(disabled=False)

    def process_event_waypoints(self, event, values):
        """
        Process events related to waypoints. Currently, this is a placeholder method.
        :param event:
        :param values:
        :return:
        """
        pass

    def process_event_takeoff_landing(self, event, values):
        """
        Process events related to takeoff, landing and return to home.
        :param event:
        :param values:
        :return:
        """
        if values['-TAKEOFF-'] and self.cur_state != self.STATES[1]:
            self.cur_state = self.STATES[1]
            height = values['-TAKEOFF_HEIGHT-']
            self.zmq_interface.take_off(height=float(height))
        elif values['-LAND-'] and self.cur_state != self.STATES[2]:
            self.cur_state = self.STATES[2]
            self.zmq_interface.land()
        elif values['-RTH-'] and self.cur_state != self.STATES[3]:
            self.cur_state = self.STATES[3]
            self.zmq_interface.return_home()
        elif values['-STANDBY-'] and self.cur_state != self.STATES[0]:
            self.cur_state = self.STATES[0]
            # TODO interface to set drone to standby mode

    def run(self):
        """
        Main loop of running ZMQ GUI.
        :return:
        """
        try:
            while True:
                # Update reports received from drone
                self.zmq_interface.update_reports()

                # Update the GUI window with the latest reports and image
                self.update_window()

                # Read window
                event, values = window.read(timeout=1)  # 1ms timeout for events reading
                if event == sg.WIN_CLOSED:  # if user closes window
                    break

                # Process events from GUI window
                self.process_event_ext_dev(event=event, values=values)
                self.process_event_takeoff_landing(event=event, values=values)
                self.process_event_gimbal(event=event, values=values)
                self.process_event_photo_video(event=event, values=values)
                self.process_event_waypoints(event=event, values=values)
        except KeyboardInterrupt:
            log.warning("Keyboard interrupt received, exiting...")
        finally:
            self.zmq_interface.close()


if __name__ == '__main__':
    zmq_gui = ZmqGui()
    zmq_gui.run()
