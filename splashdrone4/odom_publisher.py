#!/usr/bin/python3
# odom_publisher.py: Publish odometry of SplashDrone4 as ROS2 topic.
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

import rclpy
from rclpy.node import Node
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import PoseStamped, TransformStamped
from nav_msgs.msg import Odometry, Path
from sensor_msgs.msg import NavSatFix, Imu

import utm


class OdomPublisher(Node):
    def __init__(self):
        super().__init__('odom_publisher')

        # Init publishers
        self.pose_pub = self.create_publisher(PoseStamped, 'pose', 10)
        self.path_pub = self.create_publisher(Path, 'path', 10)

        # Init subscribers
        self.gps_sub = self.create_subscription(NavSatFix, 'gps', self.gps_callback, 10)
        self.imu_sub = self.create_subscription(Imu, 'imu', self.imu_callback, 10)

        # Init transform broadcaster
        self.br = TransformBroadcaster(self)

        # Define origin of UTM coordinate, will be inited as the first received GPS data
        self.ori_e, self.ori_n, self.ori_u = None, None, None

        # Init pose (ENU) list
        self.poses = []

        self.get_logger().info('Odometry publisher is started.')

    def gps_callback(self, data: NavSatFix):
        #TODO need to distinguish between gps data in different data structure (int v.s. float)
        easting, northing, zone_number, zone_letter = utm.from_latlon(latitude=data.latitude / 1e7,
                                                                      longitude=data.longitude / 1e7)
        # easting, northing, zone_number, zone_letter = utm.from_latlon(latitude=data.latitude,
        #                                                               longitude=data.longitude)
        if not self.ori_e or not self.ori_n or not self.ori_u:
            self.ori_e, self.ori_n, self.ori_u = easting, northing, data.altitude

        # publish current pose
        pose_stamped = PoseStamped()
        pose_stamped.header = data.header
        pose_stamped.pose.position.x = easting - self.ori_e
        pose_stamped.pose.position.y = northing - self.ori_n
        pose_stamped.pose.position.z = data.altitude - self.ori_u
        self.poses.append(pose_stamped)
        self.pose_pub.publish(pose_stamped)

        # publish path
        path = Path()
        path.header = data.header
        path.poses = self.poses
        self.path_pub.publish(path)


    def imu_callback(self, data: Imu):
        transform = TransformStamped()

        # Fill in translation in transform
        if self.poses:
            transform.transform.translation.x = self.poses[-1].pose.position.x
            transform.transform.translation.y = self.poses[-1].pose.position.y
            transform.transform.translation.z = self.poses[-1].pose.position.z
        else:
            transform.transform.translation.x = 0
            transform.transform.translation.y = 0
            transform.transform.translation.z = 0

        # Fill in rotation in transform
        transform.transform.rotation.x = data.orientation.x
        transform.transform.rotation.y = data.orientation.y
        transform.transform.rotation.z = data.orientation.z
        transform.transform.rotation.w = data.orientation.w

        # Fill in header in transform
        transform.header.frame_id = data.header.frame_id
        transform.child_frame_id = 'drone_link'
        transform.header.stamp = data.header.stamp

        # Send TF
        self.br.sendTransform(transform)


def main(args=None):
    rclpy.init(args=args)
    node = OdomPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()



