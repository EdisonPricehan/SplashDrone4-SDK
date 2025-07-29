#!/usr/bin/env python3
# zmq_gui_node.py: GUI run by ROS2 as a node to interact with SplashDrone4.
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


"""
Note: Needs to adapt to zmq_interface.py and zmq_gui.py.
"""


# ROS2 packages
import rclpy
from rclpy.node import Node

# System packages
import zmq
import time
from typing import Optional

# Local packages
from splashdrone4.definitions import *
from splashdrone4.gui import *
from splashdrone4.constants import *
from splashdrone4.image_processor import ImageProcessor
from splashdrone4.bag_recorder import BagRecorder
from splashdrone4.key2action import Key2Action


class ZmqGuiNode(Node):
    # Finite states of drone
    STATES = ['standingby', 'takingoff', 'landing', 'rth']

    def __init__(
            self,
            enable_video: bool = True,
            enable_ros: bool = False,
            enable_keyboard_control: bool = False,
            long_dist: Optional[float] = 2.,
            lat_dist: Optional[float] = 1.,
            vert_dist: Optional[float] = 1.,
            hori_speed: Optional[float] = 1.,
            vert_speed: Optional[float] = 0.5,
    ):
        super().__init__('Zmq_GUI_node')

        # Init all reports
        self.fly_report = FlyReport()
        self.battery_report = BatteryReport()
        self.gimbal_report = GimbalReport()
        self.ack = Ack()

        # Init all variables
        self.enable_video = enable_video
        self.enable_ros = enable_ros
        self.enable_keyboard_control = enable_keyboard_control
        self.long_dist = long_dist
        self.lat_dist = lat_dist
        self.vert_dist = vert_dist
        self.hori_speed = hori_speed
        self.vert_speed = vert_speed

        # Init runtime variables
        self.m3d_waypoints = []  # movement in 3d, each item is relative position in meter (x, y, z)
        self.mission_waypoints = []  # waypoint as (lat, lon, hover_time), need to specify fly speed and altitude first

        # Declare parameters
        self.declare_parameter('record_bag', False)
        self.declare_parameter('do_publish', False)

        # Init image processor
        self.img_proc = ImageProcessor()
        if enable_video:  # get the latest frame in another thread
            self.img_proc.init()  # blocking operation until received image stream

        # Start keyboard listening thread
        self.k2a = Key2Action() if enable_keyboard_control else None

        # Init bag recorder
        if enable_ros:
            self.record_rosbag = self.get_parameter('record_bag').get_parameter_value().bool_value
            self.publish_topic = self.get_parameter('do_publish').get_parameter_value().bool_value

            if self.record_rosbag:
                self.get_logger().info(f'Start recording rosbag ...')
                if self.publish_topic:
                    self.get_logger().info('Publish topics while recording ...')
                self.recorder = BagRecorder(publish=self.publish_topic)
                time.sleep(1)

    def update_window(self):
        """
        Update the GUI window with the latest reports.
        """
        # Update fly report in gui
        if self.fly_report.updated:
            # self.get_logger().info("Update fly report!")
            updateWindowFlyReport(self.fly_report)
            # fly_report.updated = False

        # Update battery report in gui
        if self.battery_report.updated:
            # self.get_logger().info("Update battery report!")
            updateWindowBatteryReport(self.battery_report)
            # battery_report.updated = False

        # Update gimbal report in gui
        if self.gimbal_report.updated:
            # self.get_logger().info("Update gimbal report!")
            updateWindowGimbalReport(self.gimbal_report)
            # gimbal_report.updated = False

        # Deal with ack
        if self.ack.updated:
            self.get_logger().info(f"Ack received: {self.ack.mission_id=} {self.ack.mission_type=} {self.ack.mission_data=}")
            # TODO deal with ack
            self.ack.updated = False

    def update_reports(self, topic2tuple):
        for k, (fmt, sub, report) in topic2tuple.items():
            try:
                binary_topic, data_buffer = sub.recv(zmq.DONTWAIT).split(b' ', 1)
                topic = binary_topic.decode(encoding='ascii')
                if topic == k:
                    # self.get_logger().info(f"{topic=}")
                    report_tuple = struct.unpack(fmt, data_buffer)
                    # self.get_logger().info(f"{report_tuple=}")
                    report.update(report_tuple)
                    # self.get_logger().info(f"{report.updated}")
                else:
                    self.get_logger().warn("Topic name mismatched!")
            except zmq.ZMQError as e:
                if e.errno == zmq.EAGAIN:
                    pass  # no message was ready (yet!)
                else:
                    self.get_logger().error(str(e))

    def create_sub_and_connect(self, context, topic):
        sub = context.socket(zmq.SUB)
        sub.setsockopt(zmq.SUBSCRIBE, topic.encode('ascii'))
        sub.setsockopt(zmq.LINGER, 0)
        # sub.setsockopt(zmq.CONFLATE, 1)
        sub.connect(self.ZMQ_SUB_ADDR)
        self.get_logger().info(f"Sub to {topic} connected!")
        return sub

    def keyboard_control(self, pub):  # TODO use KeyboardControl class
        # Use keyboard to control Move3D
        if self.k2a is not None:
            action = self.k2a.get_multi_discrete_action()
            x, y, z = 0, 0, 0
            intact = True  # no operation
            if action[0] != 1:
                z = self.vert_dist if action[0] == 0 else -self.vert_dist
                intact = False
            # TODO need yaw control
            if action[2] != 1:
                x = self.long_dist if action[2] == 0 else -self.long_dist
                intact = False
            if action[3] != 1:
                y = self.lat_dist if action[3] == 0 else -self.lat_dist
                intact = False

            if not intact:
                self.get_logger().info(f'{action=}')
                if not self.fly_report.updated:
                    self.get_logger().warn('Fly report has not been updated, try command again.')
                elif self.fly_report.GpsNum < 9:
                    self.get_logger().warn(f'GPS number {self.fly_report.GpsNum} is not enough.')
                else:
                    set_speed = SetSpeed(speed=6, act_now=True)
                    pub.send(set_speed.getPacked())
                    set_alt = SetAlt(alt=self.fly_report.Altitude + z, act_now=True)
                    pub.send(set_alt.getPacked())
                    cur_wp_with_yaw = WayPointWithYaw(self.fly_report.Lat / 1e7, self.fly_report.Lon / 1e7,
                                                      self.fly_report.ATTYaw)
                    wp = WayPoint.from_cartesian(cur_wp_with_yaw, x=x, y=y, hover_time=0, act_now=True)
                    # move3d = Movement3D(x, y, z, hori_speed, vert_speed, act_now=True)
                    # pub.send(move3d.getPacked())
                    pub.send(wp.getPacked())
                    self.fly_report.updated = False
                    self.get_logger().info(f'New keyboard waypoint sent!')

    def run(self):
        # Loop of zmq gui
        with zmq.Context() as context:
            # Use PUB socket to publish control commands
            pub = context.socket(zmq.PUB)
            pub.bind(ZMQ_PUB_ADDR)

            # Use SUB socket to receive fly report, battery report, gimbal report, etc
            # Set different topic filters for different subscribers
            sub1 = self.create_sub_and_connect(context, TOPIC_FLY_REPORT)
            sub2 = self.create_sub_and_connect(context, TOPIC_BATTERY_REPORT)
            sub3 = self.create_sub_and_connect(context, TOPIC_GIMBAL_REPORT)
            sub4 = self.create_sub_and_connect(context, TOPIC_ACK)

            # Create mapping from topic name to tuple (format, sub socket, report variable)
            topic2tuple = {TOPIC_FLY_REPORT: (FORMAT_FLY_REPORT, sub1, self.fly_report),
                           TOPIC_BATTERY_REPORT: (FORMAT_BATTERY_REPORT, sub2, self.battery_report),
                           TOPIC_GIMBAL_REPORT: (FORMAT_GIMBAL_REPORT, sub3, self.gimbal_report),
                           TOPIC_ACK: (FORMAT_ACK, sub4, self.ack)}

            # Main loop
            cur_state = self.STATES[0]  # standingby by default
            try:
                while True:
                    # Receive packet and split it into topic and data
                    self.update_reports(topic2tuple=topic2tuple)

                    # Reset event flags
                    ext_dev_triggered = False
                    gimbal_control_triggered = False
                    camera_control_triggered = False

                    # Read window
                    event, values = window.read(timeout=1)  # 1ms timeout for events reading
                    if event == sg.WIN_CLOSED:  # if user closes window
                        break

                    # Define variables that can change with window events
                    ext_dev_onoff = ExtDevOnOff()
                    gimbal_control = GimbalControl()
                    takeoff = TakeOff()
                    land = Land()
                    rth = ReturnToHome()

                    # Update rosbag by fly reports if updated
                    if self.enable_ros and self.record_rosbag and self.fly_report.updated:
                        self.recorder.write_gps_imu(self.fly_report)

                    # Update window by fly reports if updated
                    self.update_window()

                    # dealing with all possible events from gui input
                    ## update all device values if any device checkbox is checked
                    if event in ['-PLR1-', '-PLR2-', '-STROBE_LED-', '-ARM_LED-']:
                        ext_dev_triggered = True
                        ext_dev_onoff.plr1 = values['-PLR1-']
                        ext_dev_onoff.plr2 = values['-PLR2-']
                        ext_dev_onoff.strobe_light = values['-STROBE_LED-']
                        ext_dev_onoff.arm_light = values['-ARM_LED-']
                        self.get_logger().info(f"External device triggered! "
                                               f"plr1: {ext_dev_onoff.plr1}, "
                                               f"plr2: {ext_dev_onoff.plr2}, "
                                               f"strobe led: {ext_dev_onoff.strobe_light}, "
                                               f"arm led: {ext_dev_onoff.arm_light}")

                    if event in ['-GIMBAL_SET_ROLL-RELEASE', '-GIMBAL_SET_PITCH-RELEASE', '-GIMBAL_SET_YAW-RELEASE']:
                        gimbal_control_triggered = True
                        gimbal_control.roll = int(values['-GIMBAL_SET_ROLL-'])
                        gimbal_control.pitch = int(values['-GIMBAL_SET_PITCH-'])
                        gimbal_control.yaw = int(values['-GIMBAL_SET_YAW-'])
                        self.get_logger().info(f"Gimbal Control triggered! "
                                               f"roll: {gimbal_control.roll}, "
                                               f"pitch: {gimbal_control.pitch}, "
                                               f"yaw: {gimbal_control.yaw}")

                    if event == '-GIMBAL_RESET-':
                        gimbal_control_triggered = True
                        gimbal_control = GimbalControl()
                        updateWindowGimbalControl(gimbal_control)
                        self.get_logger().info(f"Gimbal Control reset!")

                    # Send packed struct to zmq when there is an event
                    if ext_dev_triggered:
                        pub.send(ext_dev_onoff.getPacked())
                    if gimbal_control_triggered:
                        pub.send(gimbal_control.getPacked())

                    # Deal with photo taking and video recording
                    if event == '-PHOTO-':
                        cam_ctl = CameraControl(take_photo=True, record=False, act_now=True)
                        self.get_logger().info(f"Take a photo!")
                        window['-CAMERA_STATUS-'].update("Took a photo!")
                        pub.send(cam_ctl.getPacked())
                    elif event == '-RECORD-':
                        cam_ctl = CameraControl(take_photo=False, record=True, act_now=True)
                        self.get_logger().info(f"Start recording!")
                        window['-CAMERA_STATUS-'].update("Recording ...")
                        window['-RECORD-'].update(disabled=True)
                        pub.send(cam_ctl.getPacked())
                    elif event == '-STOP_RECORD-':
                        cam_ctl = CameraControl(take_photo=False, record=False, act_now=True)
                        self.get_logger().info(f"Stop recording!")
                        window['-RECORD-'].update(disabled=False)
                        window['-CAMERA_STATUS-'].update("Recording stopped!")
                        pub.send(cam_ctl.getPacked())

                    # Update all added 3d movements in listbox
                    if event == '-CLEAR_M3D-':
                        # Clear contents in listbox
                        self.m3d_waypoints = []
                        window['-LIST_M3D-'].update(self.m3d_waypoints)
                        # Clear mission queue
                        clear_mq = ClearMissionQueue()
                        pub.send(clear_mq.getPacked())
                    elif event == '-ADD_M3D-':
                        # Start sending to mission queue
                        if len(self.m3d_waypoints) == 0:
                            start_mq = SendMissionQueueStart()
                            pub.send(start_mq.getPacked())
                        # Update mission queue list box
                        x, y, z = float(values['-X-']), float(values['-Y-']), float(values['-Z-'])
                        hs, vs = float(values['-HS_SET-']), float(values['-VS_SET-'])
                        self.m3d_waypoints.append((x, y, z, hs, vs))
                        window['-LIST_M3D-'].update(self.m3d_waypoints)
                        # Send new 3d movement to mission queue
                        move3d = Movement3D(*self.m3d_waypoints[-1])
                        pub.send(move3d.getPacked())
                    elif event == '-EXEC_M3D-':
                        if len(self.m3d_waypoints) == 0:
                            self.get_logger().warn("No 3d movements to execute!")
                        else:
                            # End sending to mission queue
                            end_mq = SendMissionQueueEnd()
                            pub.send(end_mq.getPacked())
                            # Execute mission queue TODO do not know what happens if clicked multiple times
                            exec_mq = ExecMissionQueue()
                            pub.send(exec_mq.getPacked())
                    elif event == '-SUSPEND_M3D-':
                        suspend_time = float(values['-SUSPEND_TIME_M3D-'])
                        if suspend_time < 0.01:
                            self.get_logger().warn(f"Mission suspension time should be at least 10 ms!")
                            suspend_time = 0.01
                        self.m3d_waypoints.append(suspend_time)
                        window['-LIST_M3D-'].update(self.m3d_waypoints)
                        suspend_mq = SuspendMissionQueue(suspend_time)
                        pub.send(suspend_mq.getPacked())
                    elif event == '-STOP-M3D-':
                        stop_mq = StopMissionQueue()
                        pub.send(stop_mq.getPacked())

                    # Update all added waypoints in listbox
                    if event == '-SPEED_SET-':
                        set_speed = SetSpeed(speed=float(values['-SPEED-']))
                        pub.send(set_speed.getPacked())
                    elif event == '-ALT_SET-':
                        set_alt = SetAlt(alt=float(values['-ALT-']))
                        pub.send(set_alt.getPacked())
                    elif event == '-CLEAR_WP-':
                        mission_waypoints = []
                        window['-LIST_WP-'].update(mission_waypoints)
                        # Clear mission queue
                        clear_mq = ClearMissionQueue()
                        pub.send(clear_mq.getPacked())
                    elif event == '-ADD_WP-':
                        # Start sending to mission queue
                        if len(mission_waypoints) == 0:
                            pub.send(SendMissionQueueStart().getPacked())
                        # Update mission queue list box
                        lat, lon, hover_time = float(values['-LAT_WP-']), float(values['-LON_WP-']), int(values['-HOVER_TIME-'])
                        mission_waypoints.append((lat, lon, hover_time))
                        window['-LIST_WP-'].update(mission_waypoints)
                        # Send new waypoint to mission queue
                        wp = WayPoint(*mission_waypoints[-1])
                        pub.send(wp.getPacked())
                    elif event == '-EXEC_WP-':
                        if len(mission_waypoints) == 0:
                            self.get_logger().warn("No waypoints to execute!")
                        else:
                            # end sending to mission queue
                            pub.send(SendMissionQueueEnd().getPacked())
                            # execute mission queue TODO do not know what happens if clicked multiple times
                            pub.send(ExecMissionQueue().getPacked())
                    elif event == '-SUSPEND_WP-':
                        suspend_time = float(values['-SUSPEND_TIME_WP-'])
                        if suspend_time < 0.01:
                            self.get_logger().warn(f"Mission suspension time should be at least 10 ms!")
                            suspend_time = 0.01
                        mission_waypoints.append(suspend_time)
                        window['-LIST_WP-'].update(mission_waypoints)
                        suspend_mq = SuspendMissionQueue(suspend_time)
                        pub.send(suspend_mq.getPacked())
                    elif event == '-STOP-WP-':
                        stop_mq = StopMissionQueue()
                        pub.send(stop_mq.getPacked())

                    # Takeoff or land
                    if values['-TAKEOFF-'] and cur_state != self.STATES[1]:
                        cur_state = self.STATES[1]
                        height = values['-TAKEOFF_HEIGHT-']
                        takeoff.height = float(height)
                        self.get_logger().info(f"Takeoff, height {height} m.")
                        pub.send(takeoff.getPacked())
                    elif values['-LAND-'] and cur_state != self.STATES[2]:
                        cur_state = self.STATES[2]
                        self.get_logger().info("Land!")
                        pub.send(land.getPacked())
                    elif values['-RTH-'] and cur_state != self.STATES[3]:
                        cur_state = self.STATES[3]
                        self.get_logger().info("Return to home!")
                        pub.send(rth.getPacked())
                    elif values['-STANDBY-']:
                        cur_state = self.STATES[0]
                        self.get_logger().info("Standby!")
                        # TODO send standby command to drone

                    self.keyboard_control(pub=pub)

                    # Update streamed video frame in GUI
                    if self.enable_video:
                        imgbytes = self.img_proc.get_bytes_img()
                        if imgbytes:
                            window['-IMAGE-'].update(data=imgbytes)

                    # Update rosbag
                    if self.enable_ros and self.record_rosbag:
                        cv_image = self.img_proc.get_cv_img()
                        self.recorder.write_image(cv_image)

            # Check zmq exceptions
            except Exception as error:
                self.get_logger().error("ERROR: {}".format(error))
            finally:
                # Close sub sockets
                sub1.close()
                sub2.close()
                sub3.close()
                sub4.close()
                self.get_logger().info("ZMQ sockets closed.")

                # Close gui window
                window.close()
                self.get_logger().info("GUI window closed.")

                # Release image processing thread
                if self.enable_video:
                    self.img_proc.release()
                    self.get_logger().info("Image processor released.")

                # Close rosbag recording
                if self.enable_ros and self.record_rosbag:
                    self.recorder.stop_recording()
                    self.get_logger().info(f'Rosbag recording stopped.')


def main(args=None):
    rclpy.init(args=args)
    node = ZmqGuiNode()

    try:
        node.run()
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()


