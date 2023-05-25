#!/usr/bin/python3
import rospy
import zmq
import time
import os

from Definitions import *
from GUI import *
from ImageProcess import ImageProcessor
from RosUtils import RosTopicRecorder

STATES = ['standingby', 'takingoff', 'landing', 'rth']

ZMQ_SUB_ADDR = "tcp://localhost:5555"

# formats of received reports
FORMAT_FLY_REPORT = "3hHhH3hH4i2Bb3BH"  # refer to definition in FlyStateReport.h
FORMAT_BATTERY_REPORT = "3HBb4Bi"  # refer to definition in BatteryInfo.h
FORMAT_GIMBAL_REPORT = "3f"  # refer to definition in Gimbal.h
FORMAT_NAV_REPORT = "6BHh2i"  # refer to definition in NavStateReport.h
FORMAT_ACK = "=BBI"  # refer to definition in FlyStateReport.h

# init all reports
fly_report, battery_report, gimbal_report, ack = FlyReport(), BatteryReport(), GimbalReport(), Ack()

# Set to True if only want to test GUI
GUI_ONLY = False


def create_sub_and_connect(topic):
    sub = context.socket(zmq.SUB)
    sub.setsockopt(zmq.SUBSCRIBE, topic.encode('ascii'))
    sub.setsockopt(zmq.LINGER, 0)
    # sub.setsockopt(zmq.CONFLATE, 1)
    sub.connect(ZMQ_SUB_ADDR)
    print(f"Sub to {topic} connected!")
    return sub


def update_reports():
    for k, (fmt, sub, report) in topic2tuple.items():
        try:
            binary_topic, data_buffer = sub.recv(zmq.DONTWAIT).split(b' ', 1)
            topic = binary_topic.decode(encoding='ascii')
            if topic == k:
                # print(f"{topic=}")
                report_tuple = struct.unpack(fmt, data_buffer)
                # print(f"{report_tuple=}")
                report.update(report_tuple)
                # print(f"{report.updated}")
            else:
                print("Topic name mismatched!")
        except zmq.ZMQError as e:
            if e.errno == zmq.EAGAIN:
                pass  # no message was ready (yet!)
            else:
                print(str(e))


def update_window():
    # update fly report in gui
    if fly_report.updated:
        # print("Update fly report!")
        updateWindowFlyReport(fly_report)
        fly_report.updated = False

    # update battery report in gui
    if battery_report.updated:
        # print("Update battery report!")
        updateWindowBatteryReport(battery_report)
        battery_report.updated = False

    # update gimbal report in gui
    if gimbal_report.updated:
        # print("Update gimbal report!")
        updateWindowGimbalReport(gimbal_report)
        gimbal_report.updated = False

    # deal with ack
    if ack.updated:
        print(f"Ack received: {ack.mission_id=} {ack.mission_type=} {ack.mission_data=}")
        # TODO deal with ack
        ack.updated = False


if __name__ == '__main__':
    m3d_waypoints = []  # movement in 3d, each item is relative position in meter (x, y, z)
    mission_waypoints = []  # waypoint as (lat, lon, hover_time), need to specify fly speed and altitude first

    # for 3d movement
    hori_speed = 1
    vert_speed = 0.5

    # get the latest frame in another thread
    img_proc = ImageProcessor()
    if not GUI_ONLY:
        img_proc.init()  # blocking operation until received image stream

    # record data to rosbag
    record_rosbag = rospy.get_param("/ZMQ_GUI/record_bag")
    publish_topic = rospy.get_param("/ZMQ_GUI/do_publish")
    if record_rosbag:
        print(f"Start recording rosbag ...")
        if publish_topic:
            print("Publish topics while recording ...")
        recorder = RosTopicRecorder(publish=publish_topic)
        time.sleep(1)

    # Loop of zmq and gui
    with zmq.Context() as context:
        # use PUB socket to publish control commands
        pub = context.socket(zmq.PUB)
        pub.bind("tcp://*:5556")

        # use SUB socket to receive fly report, battery report, gimbal report, etc
        # set different topic filters for different subscribers
        sub1 = create_sub_and_connect(TOPIC_FLY_REPORT)
        sub2 = create_sub_and_connect(TOPIC_BATTERY_REPORT)
        sub3 = create_sub_and_connect(TOPIC_GIMBAL_REPORT)
        sub4 = create_sub_and_connect(TOPIC_ACK)

        topic2tuple = {TOPIC_FLY_REPORT: (FORMAT_FLY_REPORT, sub1, fly_report),
                       TOPIC_BATTERY_REPORT: (FORMAT_BATTERY_REPORT, sub2, battery_report),
                       TOPIC_GIMBAL_REPORT: (FORMAT_GIMBAL_REPORT, sub3, gimbal_report),
                       TOPIC_ACK: (FORMAT_ACK, sub4, ack)}

        # main loop
        cur_state = STATES[0]
        while True:
            try:
                # receive packet and split it into topic and data
                update_reports()

                # reset event flags
                ext_dev_triggered = False
                gimbal_control_triggered = False
                camera_control_triggered = False

                # read window
                event, values = window.read(timeout=1)  # 1ms timeout for events reading
                if event == sg.WIN_CLOSED:  # if user closes window
                    break

                # define variables that can change with window events
                ext_dev_onoff = ExtDevOnOff()
                gimbal_control = GimbalControl()
                takeoff = TakeOff()
                land = Land()
                rth = ReturnToHome()

                # update rosbag
                if record_rosbag and fly_report.updated:
                    recorder.write_loc_att(fly_report)

                # update window by fly reports if updated
                update_window()

                # dealing with all possible events from gui input
                ## update all device values if any device checkbox is checked
                if event in ['-PLR1-', '-PLR2-', '-STROBE_LED-', '-ARM_LED-']:
                    ext_dev_triggered = True
                    ext_dev_onoff.plr1 = values['-PLR1-']
                    ext_dev_onoff.plr2 = values['-PLR2-']
                    ext_dev_onoff.strobe_light = values['-STROBE_LED-']
                    ext_dev_onoff.arm_light = values['-ARM_LED-']
                    print(f"External device triggered! plr1: {ext_dev_onoff.plr1}, plr2: {ext_dev_onoff.plr2}, "
                          f"strobe led: {ext_dev_onoff.strobe_light}, arm led: {ext_dev_onoff.arm_light}")

                if event in ['-GIMBAL_SET_ROLL-RELEASE', '-GIMBAL_SET_PITCH-RELEASE', '-GIMBAL_SET_YAW-RELEASE']:
                    gimbal_control_triggered = True
                    gimbal_control.roll = int(values['-GIMBAL_SET_ROLL-'])
                    gimbal_control.pitch = int(values['-GIMBAL_SET_PITCH-'])
                    gimbal_control.yaw = int(values['-GIMBAL_SET_YAW-'])
                    print(
                        f"Gimbal Control triggered! roll: {gimbal_control.roll}, pitch: {gimbal_control.pitch}, yaw: {gimbal_control.yaw}")

                if event == '-GIMBAL_RESET-':
                    gimbal_control_triggered = True
                    gimbal_control = GimbalControl()
                    updateWindowGimbalControl(gimbal_control)
                    print(f"Gimbal Control reset!")

                # send packed struct to zmq when there is event
                if ext_dev_triggered:
                    pub.send(ext_dev_onoff.getPacked())
                if gimbal_control_triggered:
                    pub.send(gimbal_control.getPacked())

                # deal with photo taking and video recording
                if event == '-PHOTO-':
                    cam_ctl = CameraControl(take_photo=True, record=False, act_now=True)
                    print(f"Take a photo!")
                    window['-CAMERA_STATUS-'].update("Took a photo!")
                    pub.send(cam_ctl.getPacked())
                elif event == '-RECORD-':
                    cam_ctl = CameraControl(take_photo=False, record=True, act_now=True)
                    print(f"Start recording!")
                    window['-CAMERA_STATUS-'].update("Recording ...")
                    window['-RECORD-'].update(disabled=True)
                    pub.send(cam_ctl.getPacked())
                elif event == '-STOP_RECORD-':
                    cam_ctl = CameraControl(take_photo=False, record=False, act_now=True)
                    print(f"Stop recording!")
                    window['-RECORD-'].update(disabled=False)
                    window['-CAMERA_STATUS-'].update("Recording stopped!")
                    pub.send(cam_ctl.getPacked())

                ## update all added 3d movements in listbox
                if event == '-CLEAR_M3D-':
                    # clear contents in listbox
                    m3d_waypoints = []
                    window['-LIST_M3D-'].update(m3d_waypoints)
                    # clear mission queue
                    clear_mq = ClearMissionQueue()
                    pub.send(clear_mq.getPacked())
                elif event == '-ADD_M3D-':
                    # start sending to mission queue
                    if len(m3d_waypoints) == 0:
                        start_mq = SendMissionQueueStart()
                        pub.send(start_mq.getPacked())
                    # update mission queue list box
                    x, y, z = float(values['-X-']), float(values['-Y-']), float(values['-Z-'])
                    hs, vs = float(values['-HS_SET-']), float(values['-VS_SET-'])
                    m3d_waypoints.append((x, y, z, hs, vs))
                    window['-LIST_M3D-'].update(m3d_waypoints)
                    # send new 3d movement to mission queue
                    move3d = Movement3D(*m3d_waypoints[-1])
                    pub.send(move3d.getPacked())
                elif event == '-EXEC_M3D-':
                    if len(m3d_waypoints) == 0:
                        print("No 3d movements to execute!")
                    else:
                        # end sending to mission queue
                        end_mq = SendMissionQueueEnd()
                        pub.send(end_mq.getPacked())
                        # execute mission queue TODO do not know what happens if clicked multiple times
                        exec_mq = ExecMissionQueue()
                        pub.send(exec_mq.getPacked())
                elif event == '-SUSPEND_M3D-':
                    suspend_time = float(values['-SUSPEND_TIME_M3D-'])
                    if suspend_time < 0.01:
                        print(f"Mission suspension time should be at least 10 ms!")
                        suspend_time = 0.01
                    m3d_waypoints.append(suspend_time)
                    window['-LIST_M3D-'].update(m3d_waypoints)
                    suspend_mq = SuspendMissionQueue(suspend_time)
                    pub.send(suspend_mq.getPacked())
                elif event == '-STOP-M3D-':
                    stop_mq = StopMissionQueue()
                    pub.send(stop_mq.getPacked())

                ## update all added waypoints in listbox
                if event == '-SPEED_SET-':
                    set_speed = SetSpeed(speed=float(values['-SPEED-']))
                    pub.send(set_speed.getPacked())
                elif event == '-ALT_SET-':
                    set_alt = SetAlt(alt=float(values['-ALT-']))
                    pub.send(set_alt.getPacked())
                elif event == '-CLEAR_WP-':
                    mission_waypoints = []
                    window['-LIST_WP-'].update(mission_waypoints)
                    # clear mission queue
                    clear_mq = ClearMissionQueue()
                    pub.send(clear_mq.getPacked())
                elif event == '-ADD_WP-':
                    # start sending to mission queue
                    if len(mission_waypoints) == 0:
                        pub.send(SendMissionQueueStart().getPacked())
                    # update mission queue list box
                    lat, lon, hover_time = float(values['-LAT_WP-']), float(values['-LON_WP-']), int(values['-HOVER_TIME-'])
                    mission_waypoints.append((lat, lon, hover_time))
                    window['-LIST_WP-'].update(mission_waypoints)
                    # send new waypoint to mission queue
                    wp = WayPoint(*mission_waypoints[-1])
                    pub.send(wp.getPacked())
                elif event == '-EXEC_WP-':
                    if len(mission_waypoints) == 0:
                        print("No waypoints to execute!")
                    else:
                        # end sending to mission queue
                        pub.send(SendMissionQueueEnd().getPacked())
                        # execute mission queue TODO do not know what happens if clicked multiple times
                        pub.send(ExecMissionQueue().getPacked())
                elif event == '-SUSPEND_WP-':
                    suspend_time = float(values['-SUSPEND_TIME_WP-'])
                    if suspend_time < 0.01:
                        print(f"Mission suspension time should be at least 10 ms!")
                        suspend_time = 0.01
                    mission_waypoints.append(suspend_time)
                    window['-LIST_WP-'].update(mission_waypoints)
                    suspend_mq = SuspendMissionQueue(suspend_time)
                    pub.send(suspend_mq.getPacked())
                elif event == '-STOP-WP-':
                    stop_mq = StopMissionQueue()
                    pub.send(stop_mq.getPacked())

                ## takeoff or land
                if values['-TAKEOFF-'] and cur_state != STATES[1]:
                    cur_state = STATES[1]
                    height = values['-TAKEOFF_HEIGHT-']
                    takeoff.height = float(height)
                    print(f"Takeoff, height {height} m.")
                    pub.send(takeoff.getPacked())
                elif values['-LAND-'] and cur_state != STATES[2]:
                    cur_state = STATES[2]
                    print("Land!")
                    pub.send(land.getPacked())
                elif values['-RTH-'] and cur_state != STATES[3]:
                    cur_state = STATES[3]
                    print("Return to home!")
                    pub.send(rth.getPacked())
                elif values['-STANDBY-']:
                    cur_state = STATES[0]
                    # print("Standby!")
                    # TODO

                # update streamed video frame in GUI
                if not GUI_ONLY:
                    imgbytes = img_proc.get()
                    if imgbytes:
                        window['-IMAGE-'].update(data=imgbytes)

                # update rosbag
                if record_rosbag:
                    cv_image = img_proc.get_cv_img()
                    recorder.write_img(cv_image)

            # check zmq exceptions
            except Exception as error:
                print("ERROR: {}".format(error))
                sub1.close()
                sub2.close()
                sub3.close()

                # close gui window
                window.close()

                # release image processing thread
                if not GUI_ONLY:
                    img_proc.release()

                # close rosbag
                if record_rosbag:
                    recorder.close()
                    print(f"Rosbag recording finished.")
