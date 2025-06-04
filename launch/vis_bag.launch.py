import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_path


def generate_launch_description():
    bag_name = DeclareLaunchArgument(
        'bag_path',
        default_value='static.bag',
        description='Bag file path.'
    )

    rate = DeclareLaunchArgument(
        'rate',
        default_value='5',
        description='Playback rate.',
    )

    gps_topic = DeclareLaunchArgument(
        'gps_topic',
        default_value='gps',
        description='Topic of GPS message.',
    )

    # Define rviz config path
    pkg_share = get_package_share_path('splashdrone')
    rviz_cfg = os.path.join(pkg_share, 'config', 'test.rviz')

    return LaunchDescription(
        [
            bag_name,
            rate,
            gps_topic,

            # Bag play node
            Node(
                package='rosbag2_player',
                executable='play',
                name='bag_player',
                output='screen',
                parameters=[
                    {
                        'play.bag_path': LaunchConfiguration('bag_path'),
                        'play.rate': LaunchConfiguration('rate'),
                    }
                ]
            ),

            # Odom publisher node
            Node(
                package='splashdrone',
                executable='odom_publisher.py',
                name='odom_publisher',
                output='screen',
                remappings=[('gps', LaunchConfiguration('gps_topic'))],
            ),

            # Rviz node
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2',
                output='screen',
                arguments=['-d', rviz_cfg],
            )
        ]
    )

