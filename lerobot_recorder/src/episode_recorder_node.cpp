// 원본: legalaspro/so101-ros-physical-ai (Apache-2.0, 커밋 58318c9) 의 episode_recorder/src/episode_recorder_node.cpp
// 변경:
//   - 시작하자마자 configure → activate (launch 없이 ros2 run 으로 쓰기 위해)
//   - Ctrl+C 처리를 직접 한다: 신호는 "멈춰라" 표시만 하고, 정리(녹화 중이던 에피소드 저장)가 끝날 때까지
//     추가 신호는 무시한다. launch 에서는 터미널과 launch 가 SIGINT 를 두 번 보내는데, rclcpp 기본 처리로는
//     두 번째 신호가 bag 을 쓰는 도중에 프로세스를 죽여 에피소드가 깨질 수 있었다.

#include "episode_recorder/episode_recorder.hpp"

#include <atomic>
#include <chrono>
#include <csignal>

#include "lifecycle_msgs/msg/state.hpp"
#include "rclcpp/executors/single_threaded_executor.hpp"
#include "rclcpp/rclcpp.hpp"

namespace {
std::atomic<bool> g_stop{false};
void on_signal(int) { g_stop.store(true); }
}  // namespace

int main(int argc, char **argv) {
  // [UNITA] rclcpp 기본 신호 처리기는 쓰지 않는다 (위 설명)
  rclcpp::init(argc, argv, rclcpp::InitOptions(), rclcpp::SignalHandlerOptions::None);
  std::signal(SIGINT, on_signal);
  std::signal(SIGTERM, on_signal);

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
  while (rclcpp::ok() && !g_stop.load()) {
    executor.spin_once(std::chrono::milliseconds(100));
  }

  // [UNITA] 정리 중에는 신호를 무시하고, 녹화 중이던 에피소드를 끝까지 저장한다.
  //         먼저 deactivate 해야 on_deactivate → stop_episode (저장 + metadata.yaml 에 task 기록) 가 불린다.
  //         바로 shutdown 하면 원본 on_cleanup 은 상태가 이미 ShuttingDown 이라 deactivate 를 건너뛴다.
  std::signal(SIGINT, SIG_IGN);
  std::signal(SIGTERM, SIG_IGN);
  RCLCPP_INFO(node->get_logger(), "Shutting down (saving any episode in progress)...");
  executor.remove_node(node->get_node_base_interface());
  if (node->get_current_state().id() == State::PRIMARY_STATE_ACTIVE) {
    node->deactivate();
  }
  node->shutdown();
  rclcpp::shutdown();
  return 0;
}
