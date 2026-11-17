// 원본: legalaspro/so101-ros-physical-ai (Apache-2.0, 커밋 58318c9) 의 episode_recorder/src/episode_recorder_node.cpp
// 변경:
//   - 시작하자마자 configure → activate (launch 없이 ros2 run 으로 쓰기 위해)

#include "episode_recorder/episode_recorder.hpp"

#include "rclcpp/executors/single_threaded_executor.hpp"
#include "lifecycle_msgs/msg/state.hpp"
#include "rclcpp/rclcpp.hpp"

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<episode_recorder::EpisodeRecorder>(rclcpp::NodeOptions{});

  // [UNITA] launch 없이 ros2 run 만으로 쓰도록 바로 configure → activate (원본은 launch 가 해 줌)
  using lifecycle_msgs::msg::State;
  if (node->configure().id() != State::PRIMARY_STATE_INACTIVE ||
      node->activate().id() != State::PRIMARY_STATE_ACTIVE) {
    RCLCPP_FATAL(node->get_logger(), "configure/activate failed — see errors above");
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::executors::SingleThreadedExecutor executor;
  executor.add_node(node->get_node_base_interface());
  executor.spin();
  rclcpp::shutdown();
  return 0;
}
