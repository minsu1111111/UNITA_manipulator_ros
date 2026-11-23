// 원본: legalaspro/so101-ros-physical-ai (Apache-2.0, 커밋 58318c9) 의 episode_recorder/src/episode_recorder.cpp
// 변경:
//   - root_dir 기본값: /tmp/episode_recorder → $HOME/ros_episodes
//   - storage_id 기본값: mcap → sqlite3 (Humble 기본 플러그인)
//   - task 가 비어도 configure 는 통과 (녹화 시작 때 검사는 원본 그대로)
//   - ~/delete_last_episode 서비스 (마지막 저장 에피소드 삭제 + 번호 되돌림)
//   - topics 를 비우면 /robot/joint_states, /robot/command + /robot/cam/*/image/compressed 자동 탐색
//     (자동 탐색일 때는 탐색 타이머를 멈추지 않아 늦게 생긴 카메라도 구독한다)



#include "episode_recorder/episode_recorder.hpp"

#include <algorithm>
#include <cstdlib>

#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <regex>
#include <sstream>

#include "lifecycle_msgs/msg/state.hpp"
#include "rosbag2_cpp/converter_options.hpp"
#include "rosbag2_storage/serialized_bag_message.hpp"
#include "rosbag2_storage/storage_options.hpp"
#include "rosbag2_storage/topic_metadata.hpp"
#include <yaml-cpp/yaml.h>

namespace episode_recorder {

EpisodeRecorder::EpisodeRecorder(const rclcpp::NodeOptions &options)
    : rclcpp_lifecycle::LifecycleNode("episode_recorder", options) {
  // Declare parameters
  this->declare_parameter<std::vector<std::string>>("topics", std::vector<std::string>{});
  this->declare_parameter<std::string>("root_dir", "");  // [UNITA] 비우면 $HOME/ros_episodes
  this->declare_parameter<std::string>("storage_id", "sqlite3");  // [UNITA] Humble 기본. mcap 은 ros-humble-rosbag2-storage-mcap 필요
  this->declare_parameter<double>("max_episode_duration", 0.0);
  this->declare_parameter<std::string>("experiment_name", "");
  this->declare_parameter<std::string>("task", "");
  this->declare_parameter<double>("start_gate_max_age_s", 0.5);
  this->declare_parameter<std::string>("storage_preset_profile", "");
  this->declare_parameter<std::string>("storage_config_uri", "");

  RCLCPP_INFO(get_logger(), "EpisodeRecorder node create (unconfigured)");
}

// --------------------------------------------------------
// Lifecycle
// --------------------------------------------------------

EpisodeRecorder::CallbackReturn
EpisodeRecorder::on_configure(const rclcpp_lifecycle::State & /*state*/) {
  RCLCPP_INFO(get_logger(), "Configuring... ");

  // Read parameter values
  topics_ = this->get_parameter("topics").as_string_array();
  root_dir_ = this->get_parameter("root_dir").as_string();
  storage_id_ = this->get_parameter("storage_id").as_string();
  max_episode_duration_ = this->get_parameter("max_episode_duration").as_double();
  experiment_name_ = this->get_parameter("experiment_name").as_string();
  task_ = this->get_parameter("task").as_string();
  start_gate_max_age_s_ = this->get_parameter("start_gate_max_age_s").as_double();
  storage_preset_profile_ = this->get_parameter("storage_preset_profile").as_string();
  storage_config_uri_ = this->get_parameter("storage_config_uri").as_string();

  if (!storage_preset_profile_.empty() && !storage_config_uri_.empty()) {
    RCLCPP_WARN(
      get_logger(),
      "Both storage_preset_profile and storage_config_uri are set. "
      "Prefer setting only one."
    );
  }

  // [UNITA] task 는 녹화를 시작할 때 필요하다 (-p task:=... 또는 키보드 t / ros2 param set 으로 나중에)
  if (task_.empty()) {
    RCLCPP_WARN(get_logger(), "Parameter 'task' is empty — set it before recording (-p task:=\"...\" or key 't')");
  }
  // [UNITA] topics 를 비우면 우리 토픽 계약의 기본값 + 카메라 자동 탐색
  if (topics_.empty()) {
    topics_ = {"/robot/joint_states", "/robot/command"};
    auto_cameras_ = true;
    RCLCPP_INFO(get_logger(), "Default topics: /robot/joint_states, /robot/command + /robot/cam/*/image/compressed");
  }
  if (root_dir_.empty()) {
    const char *home = std::getenv("HOME");
    root_dir_ = std::string(home ? home : ".") + "/ros_episodes";
  }

  // Build effective output directory: root_dir / experiment_name (if set)
  output_dir_ = std::filesystem::path(root_dir_);
  if (!experiment_name_.empty()) {
    output_dir_ /= experiment_name_;
  }

  try {
    std::filesystem::create_directories(output_dir_);
  } catch (const std::filesystem::filesystem_error &e) {
    RCLCPP_ERROR(get_logger(), "Cannot create root directory '%s': %s", root_dir_.c_str(),
                 e.what());
    return CallbackReturn::FAILURE;
  }

  // Scan for existing episodes to resume numbering (per-experiment)
  next_episode_index_ = scan_existing_episodes(output_dir_);
  RCLCPP_INFO(get_logger(), "Next episode index: %u", next_episode_index_);

  // Create Services ( will start working only when the node is ACTIVE)
  start_service_ = create_service<std_srvs::srv::Trigger>(
      "~/start_recording", std::bind(&EpisodeRecorder::handle_start, this, std::placeholders::_1,
                                     std::placeholders::_2));

  stop_service_ = create_service<std_srvs::srv::Trigger>(
      "~/stop_recording",
      std::bind(&EpisodeRecorder::handle_stop, this, std::placeholders::_1, std::placeholders::_2));

  discard_service_ = create_service<std_srvs::srv::Trigger>(
      "~/discard_episode", std::bind(&EpisodeRecorder::handle_discard, this, std::placeholders::_1,
                                     std::placeholders::_2));

  delete_last_service_ = create_service<std_srvs::srv::Trigger>(
      "~/delete_last_episode", std::bind(&EpisodeRecorder::handle_delete_last, this,
                                         std::placeholders::_1, std::placeholders::_2));

  topic_type_map_.clear();
  subs_by_topic_.clear();
  cleaned_up_ = false;

  RCLCPP_INFO(get_logger(), "Configuration complete. %zu topics requested.", topics_.size());
  return CallbackReturn::SUCCESS;
}

EpisodeRecorder::CallbackReturn
EpisodeRecorder::on_activate(const rclcpp_lifecycle::State & /*state*/) {
  RCLCPP_INFO(get_logger(), "Activating...");

  // Resolve topic types from the ROS graph (publishers should be up by now)
  resolve_topic_types();
  if (topic_type_map_.size() < topics_.size()) {
    for (const auto &topic : topics_) {
      if (topic_type_map_.find(topic) == topic_type_map_.end()) {
        RCLCPP_WARN(get_logger(), "Topic not yet available: '%s'", topic.c_str());
      }
    }
    RCLCPP_WARN(get_logger(),
                "Only %zu of %zu topics resolved — missing topics must appear before recording",
                topic_type_map_.size(), topics_.size());
  }

  // Create generic subscriptions (messages are only written when is_recording_ is true)
  create_subscriptions();

  discovery_timer_ = this->create_wall_timer(
    std::chrono::milliseconds(300),
    [this]() {
      if (get_current_state().id() != lifecycle_msgs::msg::State::PRIMARY_STATE_ACTIVE) {
        return;
      }

      resolve_topic_types();
      create_subscriptions();

      // [UNITA] 카메라 자동 탐색이면 타이머를 멈추지 않는다 — 카메라 토픽은 robot 노드가 첫 프레임을 받을 때
      //         생기므로, launch 로 같이 띄우면 recorder 가 먼저 떠서 관절 토픽만 보고 탐색을 끝내 버린다
      if (subs_by_topic_.size() == topics_.size() && !auto_cameras_) {
        RCLCPP_INFO(get_logger(), "Discovery complete: subscribed to all %zu topics.",
                    topics_.size());
        discovery_timer_.reset();
      }
    });

  return CallbackReturn::SUCCESS;
}

EpisodeRecorder::CallbackReturn
EpisodeRecorder::on_deactivate(const rclcpp_lifecycle::State & /*state*/) {
  RCLCPP_INFO(get_logger(), "Deactivating...");
  if (is_recording_.load()) {
    RCLCPP_WARN(get_logger(), "Recording was active during deactivation — stopping episode");
    stop_episode();
  }
  // destroy subscriptions
  subs_by_topic_.clear();
  topic_type_map_.clear();
  duration_timer_.reset();
  discovery_timer_.reset();
  last_rx_.clear();
  return CallbackReturn::SUCCESS;
}

//  Only called from Inactive state (after on_deactivate already ran). So subscriptions are already
//  gone.
EpisodeRecorder::CallbackReturn EpisodeRecorder::on_cleanup(const rclcpp_lifecycle::State &state) {
  RCLCPP_INFO(get_logger(), "Cleaning up...");
  // If still active, deactivate first (stop recording + destroy subscriptions)
  if (get_current_state().id() == lifecycle_msgs::msg::State::PRIMARY_STATE_ACTIVE) {
    (void)on_deactivate(state);
  }
  // destroy subscriptions
  subs_by_topic_.clear();
  topic_type_map_.clear();

  start_service_.reset();
  stop_service_.reset();
  discard_service_.reset();
  delete_last_service_.reset();
  duration_timer_.reset();
  discovery_timer_.reset();
  last_rx_.clear();
  cleaned_up_ = true;
  return CallbackReturn::SUCCESS;
}

// on_shutdown: Called from any state — including Active (e.g., Ctrl+C while recording).
// So it must handle the case where recording is still in progress.
EpisodeRecorder::CallbackReturn EpisodeRecorder::on_shutdown(const rclcpp_lifecycle::State &state) {
  RCLCPP_INFO(get_logger(), "Shutting down...");
  if (!cleaned_up_) {
    (void)on_cleanup(state);
  }
  return CallbackReturn::SUCCESS;
}

// -------------------------------------------------------
// Service Handlers
// -------------------------------------------------------
void EpisodeRecorder::handle_start(
    const std::shared_ptr<std_srvs::srv::Trigger::Request> /*request*/,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response) {
  if (get_current_state().id() != lifecycle_msgs::msg::State::PRIMARY_STATE_ACTIVE) {
    response->success = false;
    response->message = "Node is not ACTIVE";
    return;
  }
  if (is_recording_.load()) {
    response->success = false;
    response->message = "Already recording";
    return;
  }

  if (start_episode()) {
    response->success = true;
    response->message = "Recording started: " + current_episode_dir_.string();
  } else {
    response->success = false;
    // Build a message listing which topics are missing
    std::string missing;
    for (const auto &topic : topics_) {
      if (topic_type_map_.find(topic) == topic_type_map_.end()) {
        if (!missing.empty()) {
          missing += ", ";
        }
        missing += topic;
      }
    }
    if (!missing.empty()) {
      response->message = "Missing topics: " + missing;
    } else {
      response->message = "Failed to start recording";
    }
  }
}

void EpisodeRecorder::handle_stop(
    const std::shared_ptr<std_srvs::srv::Trigger::Request> /*request*/,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response) {
  if (get_current_state().id() != lifecycle_msgs::msg::State::PRIMARY_STATE_ACTIVE) {
    response->success = false;
    response->message = "Node is not ACTIVE";
    return;
  }
  if (!is_recording_.load()) {
    response->success = false;
    response->message = "Not recording";
    return;
  }

  response->success = stop_episode();
  response->message = response->success ? "Recording stopped" : "Failed to stop recording";
}

void EpisodeRecorder::handle_discard(
    const std::shared_ptr<std_srvs::srv::Trigger::Request> /*request*/,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response) {
  if (get_current_state().id() != lifecycle_msgs::msg::State::PRIMARY_STATE_ACTIVE) {
    response->success = false;
    response->message = "Node is not ACTIVE";
    return;
  }
  if (!is_recording_.load()) {
    response->success = false;
    response->message = "Not recording";
    return;
  }

  response->success = discard_episode();
  response->message = response->success ? "Episode discarded" : "Failed to discard episode";
}

void EpisodeRecorder::handle_delete_last(
    const std::shared_ptr<std_srvs::srv::Trigger::Request> /*request*/,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response) {
  if (is_recording_.load()) {
    response->success = false;
    response->message = "Recording — use discard_episode";
    return;
  }
  if (last_saved_dir_.empty()) {
    response->success = false;
    response->message = "No saved episode to delete";
    return;
  }
  try {
    std::filesystem::remove_all(last_saved_dir_);
  } catch (const std::filesystem::filesystem_error &e) {
    response->success = false;
    response->message = std::string("Failed to delete: ") + e.what();
    return;
  }
  if (next_episode_index_ > 0) {
    --next_episode_index_;  // 지운 번호를 다시 쓴다 (discard 와 같음)
  }
  RCLCPP_INFO(get_logger(), "🗑 Last episode deleted (re-record): %s", last_saved_dir_.c_str());
  response->success = true;
  response->message = "Deleted " + last_saved_dir_.filename().string();
  last_saved_dir_.clear();
}

// --------------------------------------------------------
// Episode Control
// --------------------------------------------------------

bool EpisodeRecorder::start_episode() {
  // NOTE: recording_mutex_ not needed — SingleThreadedExecutor serializes
  // all service/timer/subscription callbacks on the same thread.
  // std::lock_guard<std::mutex> lock(recording_mutex_);

  // Re-resolve topic types in case publishers appeared since configure
  resolve_topic_types();

  // Strict - All requested topics must be available before recording
  if (topic_type_map_.size() < topics_.size()) {
    std::string missing;
    for (const auto &topic : topics_) {
      if (topic_type_map_.find(topic) == topic_type_map_.end()) {
        if (!missing.empty()) {
          missing += ", ";
        }
        missing += topic;
      }
    }
    RCLCPP_ERROR(get_logger(), "Cannot start recording — %zu of %zu topics missing: [%s]",
                 topics_.size() - topic_type_map_.size(), topics_.size(), missing.c_str());
    return false;
  }

  if (subs_by_topic_.size() < topics_.size()) {
    RCLCPP_ERROR(get_logger(), "Cannot start recording — not subscribed to all topics yet (%zu/%zu).",
                subs_by_topic_.size(), topics_.size());
    return false;
  }

  // Check if all the required topics are alive (skip if start_gate_max_age_s <= 0)
  if (start_gate_max_age_s_ > 0.0) {
    const auto bad = check_topics_alive(start_gate_max_age_s_);
    if (!bad.empty()) {
      RCLCPP_ERROR(get_logger(),
                  "Cannot start recording: topics not publishing recently: [%s]. "
                  "Is a camera disconnected?",
                  bad.c_str());
      return false;
    }
  }

  auto episode_dir = make_episode_dir(next_episode_index_);

  // Open a new bag writer for this episode
  writer_ = std::make_unique<rosbag2_cpp::Writer>();

  rosbag2_storage::StorageOptions storage_options;
  storage_options.uri = episode_dir.string();
  storage_options.storage_id = storage_id_;
  storage_options.max_cache_size = 100u * 1024u * 1024u; // 100 MB write cache

  storage_options.storage_preset_profile = storage_preset_profile_;
  storage_options.storage_config_uri = storage_config_uri_;

  task_ = this->get_parameter("task").as_string();
  if (task_.empty()) {
    RCLCPP_ERROR(get_logger(), "Cannot start recording: parameter 'task' is empty");
    return false;
  }

  // Store experiment metadata in rosbag2 custom_data (Jazzy+ only)
  #ifdef HAS_ROSBAG2_CUSTOM_DATA
    if (!experiment_name_.empty()) {
      storage_options.custom_data["experiment_name"] = experiment_name_;
    }
    storage_options.custom_data["episode_index"] = std::to_string(next_episode_index_);
    storage_options.custom_data["task"] = task_;
  #endif

  try {
    writer_->open(storage_options,
                  {rmw_get_serialization_format(), rmw_get_serialization_format()});
  } catch (const std::exception &e) {
    (void)std::filesystem::remove_all(episode_dir);
    RCLCPP_ERROR(get_logger(), "Failed to open bag writer: %s", e.what());
    writer_.reset();
    return false;
  }

  // Register topics in the bag
  for (const auto &[topic, type] : topic_type_map_) {
    rosbag2_storage::TopicMetadata meta;
    meta.name = topic;
    meta.type = type;
    meta.serialization_format = rmw_get_serialization_format();
    writer_->create_topic(meta);
  }

  current_episode_dir_ = episode_dir;
  episode_start_time_ = this->now();
  is_recording_.store(true);

  RCLCPP_INFO(get_logger(), "▶ Recording episode %06u → %s", next_episode_index_,
              episode_dir.string().c_str());

  // Start max-duration timer if configured
  if (max_episode_duration_ > 0.0) {
    duration_timer_ =
        this->create_wall_timer(std::chrono::duration<double>(max_episode_duration_),
                                std::bind(&EpisodeRecorder::on_max_duration_reached, this));
  }

  return true;
}

bool EpisodeRecorder::stop_episode() {
  // NOTE: recording_mutex_ not needed — SingleThreadedExecutor serializes
  // all service/timer/subscription callbacks on the same thread.
  // std::lock_guard<std::mutex> lock(recording_mutex_);

  if (!is_recording_.load()) {
    return false;
  }

  is_recording_.store(false);
  duration_timer_.reset();

  const auto end_time = this->now();

  // Close the writer — this finalizes the bag and writes metadata.yaml
  // (including custom_data with experiment_name and episode_index)
  writer_.reset();

  #ifndef HAS_ROSBAG2_CUSTOM_DATA
  if (!patch_metadata_yaml_after_close(current_episode_dir_,
                                       next_episode_index_,
                                       task_,
                                       experiment_name_)) {
    RCLCPP_ERROR(get_logger(),
                 "Failed to write episode metadata — bag saved but metadata is incomplete: %s",
                 current_episode_dir_.string().c_str());
    current_episode_dir_.clear();
    return false;
  }
  #endif

  RCLCPP_INFO(get_logger(), "⏹ Episode %06u saved → %s", next_episode_index_,
              current_episode_dir_.string().c_str());

  last_saved_dir_ = current_episode_dir_;
  ++next_episode_index_;
  current_episode_dir_.clear();
  return true;
}

bool EpisodeRecorder::discard_episode() {
  // NOTE: recording_mutex_ not needed — SingleThreadedExecutor serializes
  // all service/timer/subscription callbacks on the same thread.
  // std::lock_guard<std::mutex> lock(recording_mutex_);

  if (!is_recording_.load()) {
    return false;
  }

  is_recording_.store(false);
  duration_timer_.reset();

  // Close writer before deleting files
  writer_.reset();

  // Delete the episode directory
  try {
    std::filesystem::remove_all(current_episode_dir_);
    RCLCPP_INFO(get_logger(), "🗑 Episode discarded: %s", current_episode_dir_.c_str());
  } catch (const std::filesystem::filesystem_error &e) {
    RCLCPP_ERROR(get_logger(), "Failed to delete episode directory: %s", e.what());
    return false;
  }

  // Do NOT increment episode counter
  current_episode_dir_.clear();
  return true;
}

void EpisodeRecorder::on_max_duration_reached() {
  RCLCPP_WARN(get_logger(), "Max episode duration reached — auto-stopping");
  (void)stop_episode();
}

// --------------------------------------------------------
// Message Callback
// --------------------------------------------------------

void EpisodeRecorder::on_message_received(const std::string &topic, const std::string &type,
                                          std::shared_ptr<rclcpp::SerializedMessage> message) {
  // No mutex needed: rosbag2_cpp::Writer::write() holds its own internal
  // writer_mutex_, and SingleThreadedExecutor serializes all callbacks so
  // stop_episode() can never run concurrently with this function.
  last_rx_[topic] = std::chrono::steady_clock::now();
  
  if (!is_recording_.load() || !writer_) {
    return;
  }

  // writer_->write(message, topic, type, this->now());
  writer_->write(message, topic, type, bag_clock_.now());
}

// --------------------------------------------------------
// Topic discorvery & subscriptions
// --------------------------------------------------------

void EpisodeRecorder::resolve_topic_types() {
  topic_type_map_.clear();
  auto names_and_types = this->get_topic_names_and_types();

  // [UNITA] 카메라 자동 탐색 — robot 노드는 첫 프레임이 올 때 카메라 토픽을 만들므로 녹화 시작 때마다 다시 찾는다
  if (auto_cameras_) {
    static const std::regex cam_re(R"(^/robot/cam/[^/]+/image/compressed$)");
    for (const auto &[name, types] : names_and_types) {
      if (std::regex_match(name, cam_re) &&
          std::find(topics_.begin(), topics_.end(), name) == topics_.end()) {
        topics_.push_back(name);
        RCLCPP_INFO(get_logger(), "Camera topic found: %s", name.c_str());
      }
    }
  }

  for (const auto &topic : topics_) {
    auto it = names_and_types.find(topic);
    if (it != names_and_types.end() && !it->second.empty()) {
      topic_type_map_[topic] = it->second.front();
      RCLCPP_DEBUG(get_logger(), "Resolved topic '%s' → type '%s'", topic.c_str(),
                   it->second.front().c_str());
    } else {
      RCLCPP_WARN(get_logger(), "Topic '%s' not found on the graph — will retry on start_recording",
                  topic.c_str());
    }
  }
}

void EpisodeRecorder::create_subscriptions() {
  // Iterate topics_ to keep subscription creation deterministic
  // and scoped to exactly what was requested.
  for (const auto &topic : topics_) {
    if (subs_by_topic_.count(topic)) {
      continue;  // already subscribed
    }

    auto it = topic_type_map_.find(topic);
    if (it == topic_type_map_.end()) continue;
    const auto &type = it->second;

    auto qos = qos_for_topic(topic);
    auto sub = this->create_generic_subscription(
        topic, type, qos, [this, topic, type](std::shared_ptr<rclcpp::SerializedMessage> msg) {
          on_message_received(topic, type, std::move(msg));
        });

    if (sub) {
      subs_by_topic_[topic] = sub;
      RCLCPP_INFO(get_logger(), "Subscribed to '%s' [%s]", topic.c_str(), type.c_str());
    } else {
      RCLCPP_ERROR(get_logger(), "Failed to subscribe to '%s'", topic.c_str());
    }
  }
}

rclcpp::QoS EpisodeRecorder::qos_for_topic(const std::string &topic) const {
  auto qos = rclcpp::QoS(rclcpp::KeepLast(100));

  auto endpoints = this->get_publishers_info_by_topic(topic);
  if (endpoints.empty()) {
    // There are not yet any publishers on the topic - use defaults
    return qos;
  }

  // Count reliability and durability profiles
  size_t reliable_count = 0;
  size_t transient_local_count = 0;
  for (const auto &endpoint : endpoints) {
    const auto &profile = endpoint.qos_profile().get_rmw_qos_profile();
    if (profile.reliability == RMW_QOS_POLICY_RELIABILITY_RELIABLE) {
      ++reliable_count;
    }
    if (profile.durability == RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL) {
      ++transient_local_count;
    }
  }

  // Reliability - use reliable only if ALL publishers are reliable
  if (reliable_count == endpoints.size()) {
    qos.reliable();
  } else {
    if (reliable_count > 0) {
      RCLCPP_WARN(get_logger(), "Mixed reliability on '%s' — using best_effort", topic.c_str());
    }
    qos.best_effort();
  }

  // Durability - use transient_local only if ALL publishers are transient_local
  if (transient_local_count == endpoints.size()) {
    qos.transient_local();
  } else {
    if (transient_local_count > 0) {
      RCLCPP_WARN(get_logger(), "Mixed durability on '%s' — using volatile", topic.c_str());
    }
    qos.durability_volatile();
  }

  return qos;
}

std::string EpisodeRecorder::check_topics_alive(double max_age_s) const {
  const auto now = std::chrono::steady_clock::now();
  std::string bad;

  for (const auto &topic : topics_) {
    auto it = last_rx_.find(topic);
    if (it == last_rx_.end()) {
      if (!bad.empty()) bad += ", ";
      bad += topic + "(never)";
      continue;
    }
    const double age_s = std::chrono::duration<double>(now - it->second).count();
    if (age_s > max_age_s) {
      if (!bad.empty()) bad += ", ";
      bad += topic + "(stale)";
    }
  }
  return bad;
}

// --------------------------------------------------------
// Episode Directory Management
// --------------------------------------------------------

uint32_t EpisodeRecorder::scan_existing_episodes(const std::filesystem::path &dir) const {
  uint32_t max_index = 0;
  bool found_any = false;

  if (!std::filesystem::exists(dir)) {
    return 0;
  }

  // Match directories named episode_XXXXXX
  const std::regex pattern(R"(episode_(\d{6}))");

  for (const auto &entry : std::filesystem::directory_iterator(dir)) {
    if (!entry.is_directory()) {
      continue;
    }
    std::smatch match;
    std::string dirname = entry.path().filename().string();
    if (std::regex_match(dirname, match, pattern)) {
      uint32_t idx = static_cast<uint32_t>(std::stoul(match[1].str()));
      if (!found_any || idx >= max_index) {
        max_index = idx + 1;
        found_any = true;
      }
    }
  }

  return max_index;
}

std::filesystem::path EpisodeRecorder::make_episode_dir(uint32_t index) const {
  std::ostringstream ss;
  ss << "episode_" << std::setfill('0') << std::setw(6) << index;
  return output_dir_ / ss.str();
}

#ifndef HAS_ROSBAG2_CUSTOM_DATA
bool EpisodeRecorder::patch_metadata_yaml_after_close(
    const std::filesystem::path &episode_dir,
    uint32_t episode_index,
    const std::string &task,
    const std::string &experiment_name) {
  const auto meta_path = episode_dir / "metadata.yaml";

  if (!std::filesystem::exists(meta_path)) {
    RCLCPP_WARN(get_logger(), "metadata.yaml not found: %s", meta_path.c_str());
    return false;
  }

  try {
    YAML::Node root = YAML::LoadFile(meta_path.string());

    YAML::Node info = root["rosbag2_bagfile_information"];
    if (!info || !info.IsMap()) {
      RCLCPP_WARN(get_logger(),
                  "metadata.yaml missing 'rosbag2_bagfile_information': %s",
                  meta_path.c_str());
      return false;
    }

    YAML::Node custom = info["custom_data"];
    if (!custom || !custom.IsMap()) {
      custom = YAML::Node(YAML::NodeType::Map);
    }

    custom["episode_index"] = std::to_string(episode_index);
    custom["task"] = task;
    if (!experiment_name.empty()) {
      custom["experiment_name"] = experiment_name;
    }

    info["custom_data"] = custom;
    root["rosbag2_bagfile_information"] = info;

    std::ofstream out(meta_path);
    if (!out.is_open()) {
      RCLCPP_WARN(get_logger(), "Failed to open metadata.yaml for writing: %s",
                  meta_path.c_str());
      return false;
    }

    out << root;
    out.close();

    RCLCPP_DEBUG(get_logger(), "Patched rosbag metadata: %s", meta_path.c_str());
    return true;

  } catch (const std::exception &e) {
    RCLCPP_WARN(get_logger(), "Failed to patch metadata.yaml at %s: %s",
                meta_path.c_str(), e.what());
    return false;
  }
}
#endif  // !HAS_ROSBAG2_CUSTOM_DATA



} // namespace episode_recorder