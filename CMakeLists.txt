cmake_minimum_required(VERSION 3.8)
project(splashdrone)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)

# find libzmq
pkg_check_modules(ZMQ REQUIRED libzmq)
include_directories(
  ${ZMQ_INCLUDE_DIRS}
)

# include directories
include_directories(
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)

# add executable (for ROS2)
add_executable(tcp_client_ros2
  src/tcp_client_ros2.cpp
  src/umbus.cpp
)

# add executable
add_executable(tcp_client
  src/tcp_client.cpp
  src/umbus.cpp
)

# link in dependencies for ros2 node of tcp_client_ros2
ament_target_dependencies(tcp_client_ros2
  rclcpp
  std_msgs
)

# for external libraries
target_link_libraries(tcp_client_ros2
  ${ZMQ_LIBRARIES}
)
target_link_libraries(tcp_client
  ${ZMQ_LIBRARIES}
)

# install node
install(TARGETS tcp_client_ros2
  DESTINATION lib/${PROJECT_NAME}
)
install(TARGETS tcp_client
  DESTINATION lib/${PROJECT_NAME}
)

# install header
install(
  DIRECTORY include/
  DESTINATION include/${PROJECT_NAME}
)

# install launch files
install(
  DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# install config files
install(
  DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

# collect all python scripts
file(GLOB PY_SCRIPTS
  "${CMAKE_CURRENT_SOURCE_DIR}/scripts/*.py"
)

# install python scripts
install(
  PROGRAMS ${PY_SCRIPTS}
  DESTINATION lib/${PROJECT_NAME}
)
list(REMOVE_ITEM PY_SCRIPTS "${CMAKE_CURRENT_SOURCE_DIR}/scripts/__init__.py")

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()


ament_package()
