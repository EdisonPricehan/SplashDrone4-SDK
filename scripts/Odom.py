#!/usr/bin/python3

import rospy
import utm
import tf

from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry, Path
from sensor_msgs.msg import NavSatFix, Imu


# Original ENU coordinate
ori_e, ori_n, ori_u = None, None, None
poses = []


def gps_callback(data):
    global ori_e, ori_n, ori_u
    easting, northing, zone_number, zone_letter = utm.from_latlon(latitude=data.latitude / 1e7,
                                                                  longitude=data.longitude / 1e7)
    if not ori_e or not ori_n or not ori_u:
        ori_e, ori_n, ori_u = easting, northing, data.altitude

    # publish current pose
    pose_stamped = PoseStamped()
    pose_stamped.header = data.header
    pose_stamped.pose.position.x = easting - ori_e
    pose_stamped.pose.position.y = northing - ori_n
    pose_stamped.pose.position.z = data.altitude - ori_u
    poses.append(pose_stamped)
    pose_pub.publish(pose_stamped)

    # publish path
    path = Path()
    path.header = data.header
    path.poses = poses
    path_pub.publish(path)


def imu_callback(data):
    if poses:
        br.sendTransform((poses[-1].pose.position.x, poses[-1].pose.position.y, poses[-1].pose.position.z),
                         (data.orientation.x, data.orientation.y, data.orientation.z, data.orientation.w),
                         data.header.stamp,
                         "drone_link",
                         data.header.frame_id)
    else:
        br.sendTransform((0, 0, 0),
                         (data.orientation.x, data.orientation.y, data.orientation.z, data.orientation.w),
                         data.header.stamp,
                         "drone_link",
                         data.header.frame_id)


if __name__ == "__main__":
    rospy.init_node("odom_publisher")
    pose_pub = rospy.Publisher('pose', PoseStamped, queue_size=10)
    path_pub = rospy.Publisher('path', Path, queue_size=10)
    gps_sub = rospy.Subscriber('gps', NavSatFix, gps_callback)
    imu_sub = rospy.Subscriber('imu', Imu, imu_callback)
    br = tf.TransformBroadcaster()

    rospy.loginfo("GPS/imu to pose/path conversion started!")

    rospy.spin()



