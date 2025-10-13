#!/usr/bin/env python3
# zmq_gui_tk.py: GUI for interacting with SplashDrone4 using Tkinter.
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

from loguru import logger as log

from splashdrone4.zmq_interface import ZmqInterface
from splashdrone4.gui_tk import TkGui


class ZmqGuiTk:
    # Finite states of drone
    STATES = ['standingby', 'takingoff', 'landing', 'rth']

    def __init__(self, img_height: int = 480, img_width: int = 640):
        """
        A pure Python class that communicates with SplashDrone4 with Tkinter GUI.
        This class does not depend on ROS or ROS2.
        """
        self.zmq_interface = ZmqInterface(
            img_height=img_height,
            img_width=img_width,
            start_tcp_client=False,
            debug=True,
        )

        # Init the variables
        self.cur_state = self.STATES[0]  # standingby by default

        # Build view
        self.gui = TkGui()
        self.gui.cb_ext_dev = self._on_ext_dev
        self.gui.cb_takeoff_land = self._on_takeoff_land
        self.gui.cb_gimbal = self._on_gimbal
        self.gui.cb_photo = self._on_photo
        self.gui.cb_record = self._on_record
        self.gui.cb_stop_record = self._on_stop_record
        self.gui.cb_close = self._on_close

    # ---------- GUI callbacks ----------
    def _on_ext_dev(self, plr1_on, plr2_on, strobe_light_on, arm_light_on):
        self.zmq_interface.set_ext_dev(
            plr1_on=plr1_on,
            plr2_on=plr2_on,
            strobe_light_on=strobe_light_on,
            arm_light_on=arm_light_on,
        )

    def _on_gimbal(self, roll, pitch, yaw):
        self.zmq_interface.set_gimbal(roll=roll, pitch=pitch, yaw=yaw)

    def _on_photo(self):
        self.zmq_interface.set_camera(take_photo=True, start_video=False)
        self.gui.set_camera_status("Took a photo!")

    def _on_record(self):
        self.zmq_interface.set_camera(take_photo=False, start_video=True)
        self.gui.set_camera_status("Recording ...")
        self.gui.set_record_button_enabled(False)

    def _on_stop_record(self):
        self.zmq_interface.set_camera(take_photo=False, start_video=False)
        self.gui.set_camera_status("Stopped recording.")
        self.gui.set_record_button_enabled(True)

    def _on_takeoff_land(self, mode: str, height_text: str):
        try:
            height = float(height_text)
        except ValueError:
            height = 0.4
        if mode == "takeoff" and self.cur_state != self.STATES[1]:
            self.cur_state = self.STATES[1]
            self.zmq_interface.take_off(height=height)
        elif mode == "land" and self.cur_state != self.STATES[2]:
            self.cur_state = self.STATES[2]
            self.zmq_interface.land()
        elif mode == "rth" and self.cur_state != self.STATES[3]:
            self.cur_state = self.STATES[3]
            self.zmq_interface.return_home()
        elif mode == "standby" and self.cur_state != self.STATES[0]:
            self.cur_state = self.STATES[0]
            # TODO: interface to set drone to standby mode if available

    def _on_close(self):
        self.zmq_interface.close()

    # ---------- Periodic update ----------
    def _tick(self):
        try:
            # Update reports received from drone
            self.zmq_interface.update_reports()

            # Update the GUI window with the latest reports and image
            if self.zmq_interface.fly_report.updated:
                self.gui.update_fly_report(self.zmq_interface.fly_report)
            if self.zmq_interface.battery_report.updated:
                self.gui.update_battery_report(self.zmq_interface.battery_report)
            if self.zmq_interface.gimbal_report.updated:
                self.gui.update_gimbal_report(self.zmq_interface.gimbal_report)

            # Deal with ack
            if self.zmq_interface.ack.updated:
                # TODO: handle ack if needed by UI
                self.zmq_interface.ack.updated = False

            # Update image in gui
            imgbytes = self.zmq_interface.img_proc.get_bytes_img()
            if imgbytes:
                self.gui.set_image_bytes(imgbytes)
        except Exception as exc:
            log.debug(f"Tick error: {exc}")

        # Schedule next tick
        self.gui.after(1, self._tick)

    def run(self):
        try:
            self._tick()
            self.gui.mainloop()
        except KeyboardInterrupt:
            log.warning("Keyboard interrupt received, exiting...")
        finally:
            self.zmq_interface.close()


if __name__ == '__main__':
    ZmqGuiTk().run()

