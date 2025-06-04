import rclpy
from rclpy.node import Node
from rclpy.serialization import serialize_message
from std_msgs.msg import Header
from sensor_msgs.msg import Imu, NavSatFix, Image
from tf_transformations import quaternion_from_euler
from cv_bridge import CvBridge, CvBridgeError
from rosbag2_py import SequentialWriter, StorageOptions

import os
from datetime import datetime
from typing import Optional, List

from definitions import FlyReport, GimbalReport, deg2rad


class BagRecorder(Node):
    def __init__(
            self,
            image_topic_name: Optional[str] = 'image',
            imu_topic_name: Optional[str] = 'imu',
            gps_topic_name: Optional[str] = 'gps',
            publish: bool = False,
    ):
        super().__init__('bag_recorder')
        self.get_logger().info(f'Name and namespace: {self.get_node_names_and_namespaces()}')

        # Make bag directory
        self.output_dir = os.path.dirname(__file__) + '/../bags'
        os.makedirs(self.output_dir, exist_ok=True)

        # Init bag name and path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_bag = os.path.join(self.output_dir, f"bag_{timestamp}.bag")
        self.get_logger().info(f'{self.output_bag=}')

        # Init topic names
        self.image_topic_name: Optional[str] = image_topic_name
        self.imu_topic_name: Optional[str] = imu_topic_name
        self.gps_topic_name: Optional[str] = gps_topic_name
        self.publish = publish

        # Get topics
        self.topic_list = self._get_topics()
        if len(self.topic_list) == 0:
            raise ValueError(f'Need to specify at least 1 topic for recording.')

        # Create publishers
        self.imu_publisher = self.create_publisher(Imu, self.imu_topic_name, 10)
        self.gps_publisher = self.create_publisher(NavSatFix, self.gps_topic_name, 10)
        self.image_publisher = self.create_publisher(Image, self.image_topic_name, 10)

        # Init variables
        self.is_recording = False
        self.writer = SequentialWriter()

        # Start recording
        self.start_recording()

    def _get_topics(self) -> List[str]:
        topics: List[str] = []

        if self.image_topic_name is not None:
            topics.append(self.image_topic_name)
        if self.imu_topic_name is not None:
            topics.append(self.imu_topic_name)
        if self.gps_topic_name is not None:
            topics.append(self.gps_topic_name)

        return topics

    def create_header(self, ref_frame: str = 'map'):
        h = Header()
        h.frame_id = ref_frame
        h.stamp = self.get_clock().now().to_msg()
        return h

    def create_imu_msg(self, fly_report: FlyReport) -> Imu:
        imu = Imu()
        imu.header = self.create_header('map')

        # Convert deg to rad
        roll, pitch, yaw = deg2rad(fly_report.ATTRoll), deg2rad(fly_report.ATTPitch), deg2rad(fly_report.ATTYaw)

        # Convert rpy to quaternion
        q = quaternion_from_euler(roll, pitch, yaw)

        # Fill imu's orientation with quaternion values
        imu.orientation.x = float(q[0])
        imu.orientation.y = float(q[1])
        imu.orientation.z = float(q[2])
        imu.orientation.w = float(q[3])

        return imu

    def create_gps_msg(self, fly_report: FlyReport) -> NavSatFix:
        gps = NavSatFix()
        gps.header = self.create_header('map')

        gps.latitude = fly_report.Lat
        gps.longitude = fly_report.Lon
        gps.altitude = fly_report.Altitude

        return gps

    def create_img_msg(self, cv_img) -> Image:
        img = None

        bridge = CvBridge()
        try:
            img = bridge.cv2_to_imgmsg(cv_img)
            img.header = self.create_header('drone_link')
        except CvBridgeError as e:
            print(e)

        return img

    def write_gps_imu(self, fly_report: FlyReport) -> None:
        imu_msg = self.create_imu_msg(fly_report)
        gps_msg = self.create_gps_msg(fly_report)

        # Publish if required
        if self.publish:
            self.imu_publisher.publish(imu_msg)
            self.gps_publisher.publish(gps_msg)

        if self.is_recording:
            self.writer.write(
                self.imu_topic_name,
                serialize_message(imu_msg),
                imu_msg.header.stamp.nanosec,
            )
            self.writer.write(
                self.gps_topic_name,
                serialize_message(gps_msg),
                gps_msg.header.stamp.nanosec,
            )
        else:
            self.get_logger().warn('Write imu and gps when recording is not started.')

    def write_image(self, cv_img) -> None:
        img_msg = self.create_img_msg(cv_img)

        # Publish if required
        if self.publish:
            self.image_publisher.publish(img_msg)

        if self.is_recording:
            self.writer.write(
                self.image_topic_name,
                serialize_message(img_msg),
                img_msg.header.stamp.nanosec,
            )
        else:
            self.get_logger().warn('Write image when recording is not started.')

    def start_recording(self) -> None:
        if self.is_recording:
            self.get_logger().warn('Already recording.')
            return

        storage_options = StorageOptions(
            uri=self.output_bag,
            storage_id='sqlite3',
        )

        self.writer.open(storage_options)
        self.is_recording = True
        self.get_logger().info(f'Start recording to {self.output_bag} for topics: {self.topic_list} ...')

    def stop_recording(self) -> None:
        if not self.is_recording:
            self.get_logger().warn('Not currently recording.')
            return

        self.writer.close()
        self.is_recording = False
        self.get_logger().info('Stopped recording.')





