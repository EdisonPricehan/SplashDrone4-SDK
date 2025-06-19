from datetime import datetime
from pathlib import Path
# import rospy
# import rosbag
# import tf_conversions
from std_msgs.msg import Header
from sensor_msgs.msg import Imu, NavSatFix, Image
from geometry_msgs.msg import Quaternion
from cv_bridge import CvBridge, CvBridgeError

import rclpy
from rclpy.node import Node

from definitions import FlyReport, GimbalReport, deg2rad


def create_ros_header(ref_frame: str = "map") -> Header:
    h = Header()
    h.stamp = rospy.Time.now()
    h.frame_id = ref_frame
    return h


def create_ros_imu(fly_report: FlyReport) -> Imu:
    imu = Imu()
    imu.header = create_ros_header("map")
    # convert deg to rad
    roll, pitch, yaw = deg2rad(fly_report.ATTRoll), deg2rad(fly_report.ATTPitch), deg2rad(fly_report.ATTYaw)
    imu.orientation = Quaternion(*tf_conversions.transformations.quaternion_from_euler(roll, pitch, yaw))
    return imu


def create_ros_gps(fly_report: FlyReport) -> NavSatFix:
    gps = NavSatFix()
    gps.header = create_ros_header("map")
    gps.latitude = fly_report.Lat
    gps.longitude = fly_report.Lon
    gps.altitude = fly_report.Altitude
    return gps


def create_ros_img(cv_img) -> Image:
    img = None
    bridge = CvBridge()
    try:
        img = bridge.cv2_to_imgmsg(cv_img)
        img.header = create_ros_header("drone_link")
    except CvBridgeError as e:
        print(e)
    return img


class RosTopicRecorder:
    def __init__(self, rosbag_path='', publish=False):
        # use current date as bag file name is not specified
        if rosbag_path == '':
            date = datetime.now().strftime("%Y_%m_%d-%I:%M:%S_%p")
            print(f"{__file__=}")
            rosbag_path = Path(__file__).parents[1] / "bags" / f"bag_{date}.bag"

        self.bag = rosbag.Bag(rosbag_path, 'w')
        self.topic_imu = "imu"
        self.topic_img = "image"
        self.topic_gps = "gps"
        rospy.init_node("rosbag_recorder")
        self.publish = publish
        self.pub_imu = rospy.Publisher(self.topic_imu, Imu, queue_size=10)
        self.pub_img = rospy.Publisher(self.topic_img, Image, queue_size=10)
        self.pub_gps = rospy.Publisher(self.topic_gps, NavSatFix, queue_size=10)

    def write_loc_att(self, fly_report: FlyReport):
        msg_imu = create_ros_imu(fly_report)
        msg_gps = create_ros_gps(fly_report)
        self.bag.write(self.topic_imu, msg_imu)
        self.bag.write(self.topic_gps, msg_gps)

        if self.publish:
            self.pub_imu.publish(msg_imu)
            self.pub_gps.publish(msg_gps)

    def write_img(self, cv_img):
        msg_img = create_ros_img(cv_img)
        self.bag.write(self.topic_img, msg_img)

        if self.publish:
            self.pub_img.publish(msg_img)

    def close(self):
        self.bag.close()

