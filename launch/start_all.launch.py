import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_path


def generate_launch_description():
    # Define launch arguments
    tcp_address = DeclareLaunchArgument('tcp_address', default_value='192.168.2.1',
                                        description='TCP address of the server.')
    record_bag = DeclareLaunchArgument('record_bag', default_value='false',
                                       description='Whether record the ros bag after connection is established.')
    do_publish = DeclareLaunchArgument('do_publish', default_value='false',
                                       description='Whether publish those topics when recording bag.')

    # Define rviz config path
    pkg_share = get_package_share_path('splashdrone')
    rviz_cfg = os.path.join(pkg_share, 'config', 'test.rviz')

    return LaunchDescription([
            tcp_address,
            record_bag,
            do_publish,

            # TCP client ros2 node
            Node(
                package='splashdrone',
                executable='tcp_client_ros2',
                name='tcp_client_ros2',
                output='screen',
                # arguments=[LaunchConfiguration('tcp_address')],
                parameters=[{'tcp_address': LaunchConfiguration('tcp_address')}],
            ),

            # ZMQ-GUI node
            Node(
                package='splashdrone',
                executable='zmq_gui.py',
                name='zmq_gui',
                output='screen',
                parameters=[{'record_bag': LaunchConfiguration('record_bag'),
                             'do_publish': LaunchConfiguration('do_publish')}],
            ),

            # Odometry node (optional)
            Node(
                package='splashdrone',
                executable='odom_publisher.py',
                name='odom',
                output='screen',
                condition=IfCondition(LaunchConfiguration('do_publish')),
            ),

            # Rviz node (optional)
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2',
                output='screen',
                arguments=['-d', rviz_cfg],
                condition=IfCondition(LaunchConfiguration('do_publish')),
            )
    ])
