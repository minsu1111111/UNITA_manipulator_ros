# 원본: legalaspro/so101-ros-physical-ai (Apache-2.0, 커밋 58318c9) 의 episode_recorder/CMakeLists.txt
# 변경: 패키지 이름 lerobot_recorder, 실행 파일 이름 recorder / keyboard, launch·config 설치·lint 테스트 제거
cmake_minimum_required(VERSION 3.8)
project(lerobot_recorder)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(lifecycle_msgs REQUIRED)
find_package(rcl_interfaces REQUIRED)
find_package(rosbag2_cpp REQUIRED)
find_package(rosbag2_storage REQUIRED)
find_package(std_srvs REQUIRED)
find_package(yaml-cpp REQUIRED)

include_directories(include)

# ros2 run lerobot_recorder recorder
add_executable(recorder
  src/episode_recorder_node.cpp
  src/episode_recorder.cpp
)
ament_target_dependencies(recorder
  rclcpp rclcpp_lifecycle lifecycle_msgs rosbag2_cpp rosbag2_storage std_srvs yaml-cpp
)
# rosbag2 0.22 (Jazzy) 부터 custom_data 를 직접 쓴다. Humble 은 닫은 뒤 metadata.yaml 을 고친다
if(rosbag2_storage_VERSION VERSION_GREATER_EQUAL "0.22.0")
  target_compile_definitions(recorder PRIVATE HAS_ROSBAG2_CUSTOM_DATA=1)
endif()

# ros2 run lerobot_recorder keyboard
add_executable(keyboard
  src/teleop_episode_keyboard.cpp
)
ament_target_dependencies(keyboard rclcpp std_srvs rcl_interfaces)

install(TARGETS recorder keyboard DESTINATION lib/${PROJECT_NAME})

ament_package()
