#!/usr/bin/python3
from definitions import *

import zmq
from time import sleep

import rospy
from sensor_msgs.msg import NavSatFix


fly_report = FlyReport()

FORMAT_FLY_REPORT = "3hHhH3hH4i2Bb3BH"  # refer to definition in fly_state_report.h


def update_report(sub):
    try:
        print("")
        binary_topic, data_buffer = sub.recv(zmq.DONTWAIT).split(b' ', 1)
        topic = binary_topic.decode(encoding='ascii')
        if topic == TOPIC_FLY_REPORT:
            print(f"{topic=}")
            report_tuple = struct.unpack(FORMAT_FLY_REPORT, data_buffer)
            print(f"{report_tuple=}")
            fly_report.update(report_tuple)
        else:
            print("Topic name mismatched!")
    except zmq.ZMQError as e:
        if e.errno == zmq.EAGAIN:
            pass  # no message was ready (yet!)
        else:
            print(str(e))
    return fly_report.updated


def report2wp(sub):
    while not update_report(sub):
        print("Waiting for fly report ...")

    print(f"GPS#: {fly_report.GpsNum}, VDOP: {fly_report.VDOP}")
    if fly_report.GpsNum < 9:
        return None

    wp = WayPointWithYaw(fly_report.Lat / 1e7, fly_report.Lon / 1e7, fly_report.ATTYaw)
    # print(wp)
    fly_report.updated = False
    return wp


def report2ros_gps(zmq_sub, ros_pub):
    if not update_report(zmq_sub):
        return
        # rospy.loginfo_throttle(0.5, "Waiting for fly report ...")
    rospy.loginfo("GPS#: {fly_report.GpsNum}, VDOP: {fly_report.VDOP}")
    drone_gps = NavSatFix()
    drone_gps.header.stamp = rospy.Time.now()
    drone_gps.latitude = fly_report.Lat / 1e7  # degrees
    drone_gps.longitude = fly_report.Lon / 1e7  # degrees
    drone_gps.altitude = fly_report.Altitude  # meters
    ros_pub.publish(drone_gps)
    fly_report.updated = False


class FollowMe:
    def __init__(self, goal_gps_topic="/ublox/fix", drone_gps_topic="/drone/fix"):
        self.goal_gps_topic = goal_gps_topic
        self.drone_gps_topic = drone_gps_topic
        rospy.init_node("follow_me_node", anonymous=True)
        self.goal_gps_sub = rospy.Subscriber(self.goal_gps_topic, NavSatFix, self.callback)
        self.drone_gps_pub = rospy.Publisher(self.drone_gps_topic, NavSatFix, queue_size=10)
        self.goal_gps, self.drone_gps = None, None
        self.zmq_pub, self.zmq_sub = None, None

    def callback(self, gps_data):
        rospy.loginfo_once("GPS data is ready!")
        self.goal_gps = gps_data

    def takeoff(self, height: float = 3):
        if self.pub is None:
            rospy.logwarn("ZMQ publisher is not inited when taking off!")
            return
        to = TakeOff(height=height, act_now=True)
        self.pub.send(to.getPacked())
        sleep(1)
        rospy.loginfo("Taking off!")
        # exec_mq = ExecMissionQueue()
        # self.pub.send(exec_mq.getPacked())
        # sleep(10)

    def set_speed_altitude(self, speed: float = 5, altitude: float = 4):
        if self.pub is None:
            rospy.logwarn("ZMQ publisher is not inited when setting speed and altitude!")
            return
        set_speed = SetSpeed(speed=speed, act_now=True)
        self.pub.send(set_speed.getPacked())
        sleep(1)
        set_alt = SetAlt(alt=altitude, act_now=True)
        self.pub.send(set_alt.getPacked())
        sleep(1)
        rospy.loginfo("Speed and altitude set!")

    def send_wp(self, hover_time: int = 0):
        if self.pub is None:
            rospy.logwarn("ZMQ publisher is not inited when sending waypoint!")
            return
        if self.goal_gps is None:
            rospy.loginfo_throttle(0.5, "Goal GPS is not available when sending waypoint!")
            return

        wp = WayPoint(lat=self.goal_gps.latitude, lon=self.goal_gps.longitude, hover_time=hover_time, act_now=True)
        self.pub.send(wp.getPacked())
        # sleep(0.5)
        rospy.loginfo("Waypoint sent!")

    def run(self):
        with zmq.Context() as context:
            # create publisher
            self.pub = context.socket(zmq.PUB)
            self.pub.bind("tcp://*:5556")
            print("ZMQ publisher created!")
            sleep(1)

            # create subscriber
            self.sub = context.socket(zmq.SUB)
            self.sub.setsockopt(zmq.SUBSCRIBE, TOPIC_FLY_REPORT.encode('ascii'))
            self.sub.setsockopt(zmq.LINGER, 0)
            # sub.setsockopt(zmq.CONFLATE, 1)
            self.sub.connect("tcp://localhost:5555")
            print("ZMQ subscriber connected!")
            sleep(1)

            # initial actions for waypoint navigation
            self.takeoff()
            self.set_speed_altitude()

            # main loop
            r = rospy.Rate(5)
            while not rospy.is_shutdown():
                r.sleep()

                self.send_wp()

                # just publish to ros topic
                # report2ros_gps(self.zmq_sub, self.drone_gps_pub)


if __name__ == "__main__":
    fm = FollowMe()
    fm.run()
