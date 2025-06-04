// tcp_client_ros2.cpp: ROS2 node that communicates with the controller of
// Splashdrone 4 using TCP/IP, then relays data between TCP and ZMQ.
// Copyright (C) <2025>  <Zihan Wang>
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.


#include <rclcpp/rclcpp.hpp>
#include <sys/types.h>
#include <sys/socket.h>
#include <netdb.h>
#include <unistd.h>
#include <cstring>
#include <string>
#include <memory>
#include <chrono>
#include <sstream>

#include "zmq.h"
#include "SplashDrone4-ros/controls.h"
#include "SplashDrone4-ros/umbus.h"

#define DEFAULT_PORT "2022"
#define DEFAULT_BUFLEN 256

static const std::string TOPIC_FLY_REPORT = "topic_fly_report";
static const std::string TOPIC_BATTERY_REPORT = "topic_battery_report";
static const std::string TOPIC_GIMBAL_REPORT = "topic_gimbal_report";
static const std::string TOPIC_ACK = "topic_ack";

static const std::string TOPIC_EXT_DEV = "topic_external_device";
static const std::string TOPIC_CAMERA_CONTROL = "topic_camera_control";
static const std::string TOPIC_TAKEOFF = "topic_takeoff";
static const std::string TOPIC_LAND = "topic_land";
static const std::string TOPIC_RETURN_TO_HOME = "topic_rth";
static const std::string TOPIC_GIMBAL_CONTROL = "topic_gimbal_control";
static const std::string TOPIC_MOVE_3D = "topic_move_3d";
static const std::string TOPIC_WAYPOINT = "topic_waypoint";

static const std::string TOPIC_SET_SPEED = "topic_set_speed";
static const std::string TOPIC_SET_ALT = "topic_set_alt";

static const std::string TOPIC_CLEAR_MISSION_QUEUE = "topic_clear_mq";
static const std::string TOPIC_SEND_START = "topic_send_start";
static const std::string TOPIC_SEND_END = "topic_send_end";
static const std::string TOPIC_EXEC_MISSION = "topic_exec_mission";
static const std::string TOPIC_STOP_MISSION = "topic_stop_mission";
static const std::string TOPIC_SUSPEND_MISSION = "topic_suspend_mission";
static const std::string TOPIC_REPLAY_MISSION = "topic_replay_mission";


class TcpClientRos2Node : public rclcpp::Node
{
public:
    TcpClientRos2Node()
    : Node("tcp_client_ros2"), sock_(-1), context_(nullptr), pub_(nullptr), sub_(nullptr), inited_(false)
    {
        this->declare_parameter<std::string>("tcp_address", "192.168.2.1");
        std::string tcp_address = this->get_parameter("tcp_address").as_string();

        RCLCPP_INFO(this->get_logger(), "TCP Client ROS2 node started.");
        RCLCPP_INFO(this->get_logger(), "Connecting to server: %s", tcp_address.c_str());

        // TCP setup
        struct addrinfo hints, *result = nullptr;
        memset(&hints, 0, sizeof(hints));
        hints.ai_family = AF_UNSPEC;
        hints.ai_socktype = SOCK_STREAM;
        hints.ai_protocol = IPPROTO_TCP;

        int res = getaddrinfo(tcp_address.c_str(), DEFAULT_PORT, &hints, &result);
        if (res != 0) {
            RCLCPP_ERROR(this->get_logger(), "getaddrinfo failed: %s", gai_strerror(res));
            rclcpp::shutdown();
            return;
        }

        for (auto ptr = result; ptr != nullptr; ptr = ptr->ai_next) {
            sock_ = socket(ptr->ai_family, ptr->ai_socktype, ptr->ai_protocol);
            if (sock_ < 0) continue;
            if (connect(sock_, ptr->ai_addr, ptr->ai_addrlen) == 0) {
                break;
            }
            close(sock_);
            sock_ = -1;
        }
        freeaddrinfo(result);

        if (sock_ < 0) {
            RCLCPP_ERROR(this->get_logger(), "Could not connect to server.");
            rclcpp::shutdown();
            return;
        }
        RCLCPP_INFO(this->get_logger(), "Connected to server.");

        // ZMQ setup
        context_ = zmq_ctx_new();
        if (!context_) {
            RCLCPP_ERROR(this->get_logger(), "ZeroMQ context creation failed: %s", zmq_strerror(errno));
            rclcpp::shutdown();
            return;
        }
        pub_ = zmq_socket(context_, ZMQ_PUB);
        if (zmq_bind(pub_, "tcp://*:5555") != 0) {
            RCLCPP_ERROR(this->get_logger(), "ZeroMQ PUB bind failed: %s", zmq_strerror(errno));
            rclcpp::shutdown();
            return;
        }
        sub_ = zmq_socket(context_, ZMQ_SUB);
        if (zmq_connect(sub_, "tcp://localhost:5556") != 0) {
            RCLCPP_ERROR(this->get_logger(), "ZeroMQ SUB connect failed: %s", zmq_strerror(errno));
            rclcpp::shutdown();
            return;
        }
        zmq_setsockopt(sub_, ZMQ_SUBSCRIBE, "", 0);

        // Main loop timer (10ms)
        timer_ = this->create_wall_timer(
            std::chrono::milliseconds(10),
            std::bind(&TcpClientRos2Node::main_loop, this)
        );
    }

    ~TcpClientRos2Node() override
    {
        if (sock_ >= 0) close(sock_);
        if (pub_) zmq_close(pub_);
        if (sub_) zmq_close(sub_);
        if (context_) zmq_ctx_destroy(context_);
    }

private:
    void main_loop()
    {
        char recvbuf[DEFAULT_BUFLEN];
        int bytes = recv(sock_, recvbuf, DEFAULT_BUFLEN, MSG_DONTWAIT);
        if (bytes > 0) {
            if (!inited_) { Init(); inited_ = true; }
            UART1_DataReceived((uint8_t*)recvbuf, bytes);

            // Initialize reports
            FLY_REPORT_V1 fly_report;
            t_BatteryInf battery_report;
            GimbalBroadcast gimbal_report;
            ACK ack;

            // Publish fly report using zmq once one unpacking succeeds
            if (GetFlyReport(fly_report)) {
                this->sendToZmq(TOPIC_FLY_REPORT, (void*)&fly_report, sizeof(fly_report));
            } else if (GetBatteryReport(battery_report)) {
                this->sendToZmq(TOPIC_BATTERY_REPORT, (void*)&battery_report, sizeof(battery_report));
            } else if (GetGimbalReport(gimbal_report)) {
                this->sendToZmq(TOPIC_GIMBAL_REPORT, (void*)&gimbal_report, sizeof(gimbal_report));
            } else if (GetAck(ack)) {
                this->sendToZmq(TOPIC_ACK, (void*)&ack, sizeof(ack));
            }
        } else if (bytes == 0) {
            RCLCPP_WARN(this->get_logger(), "TCP connection closed.");
            rclcpp::shutdown();
            return;
        }

        // Poll ZMQ for commands
        zmq_msg_t msg;
        zmq_msg_init(&msg);
        int num_bytes = zmq_msg_recv(&msg, sub_, ZMQ_NOBLOCK);
        if (num_bytes > 0 && num_bytes <= DEFAULT_BUFLEN) {
            std::string topic;
            std::istringstream iss((char*)zmq_msg_data(&msg));
            std::getline(iss, topic, ' ');
            auto topic_len = topic.length();
            RCLCPP_INFO(this->get_logger(), "Received ZMQ topic: %s", topic.c_str());

            // Handle different topics and send commands back to TCP
            // Currently can only process one topic at a time, polling
            uint8_t* sb = nullptr; // sendbuf pointer of UMBUS.m1.pTxBuff
            if (topic == TOPIC_EXT_DEV) {
                ExtDevOnOffStruct extDevOnOff;
                extDevOnOff.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                RCLCPP_INFO(this->get_logger(), "\t pl1: %d, pl2: %d, sl: %d, al: %d, act_now: %d \n",
                       extDevOnOff.plr1, extDevOnOff.plr2, extDevOnOff.strobe_light, extDevOnOff.arm_light,
                       extDevOnOff.act_now);
                uint8_t len = extDevOnOff.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_CAMERA_CONTROL) {
                CameraControl cameraControl;
                cameraControl.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                RCLCPP_INFO(this->get_logger(), "\t Take photo: %d, record: %d, act now: %d \n",
                       cameraControl.take_photo, cameraControl.record, cameraControl.act_now);
                int len = cameraControl.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_TAKEOFF) {
                TakeOff take_off;
                take_off.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                RCLCPP_INFO(this->get_logger(), "\t Take off to height %.1fm, act_now: %d \n",
                take_off.height,
                take_off.act_now);
                int len = take_off.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_LAND) {
                Land land;
                land.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                RCLCPP_INFO(this->get_logger(), "\t Land, act_now: %d \n", land.act_now);
                int len = land.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_RETURN_TO_HOME) {
                RetToHome rth;
                rth.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                RCLCPP_INFO(this->get_logger(), "\t Return to home, act_now: %d \n", rth.act_now);
                int len = rth.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_GIMBAL_CONTROL) {
                RCLCPP_INFO(this->get_logger(), "\t Controlling gimbal ...\n");
                GimbalControl gimbal_control;
                gimbal_control.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                RCLCPP_INFO(this->get_logger(), "\t Gimbal control (deg) roll: %d, pitch: %d, yaw: %d, act_now: %d \n",
                       gimbal_control.roll, gimbal_control.pitch, gimbal_control.yaw, gimbal_control.act_now);
                int len = gimbal_control.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_SET_SPEED) {
                SetSpeed ss;
                ss.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                RCLCPP_INFO(this->get_logger(), "\t Set fly speed to %.1f m/s, act_now: %d \n", ss.speed_set, ss.act_now);
                int len = ss.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_SET_ALT) {
                SetAlt sa;
                sa.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                RCLCPP_INFO(this->get_logger(), "\t Set fly height to %.1f m/s, act_now: %d \n",
                sa.altitude_set,
                sa.act_now);
                int len = sa.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_CLEAR_MISSION_QUEUE) {
                RCLCPP_INFO(this->get_logger(), "\t Clear mission queue!\n");
                ClearMissionQueue clear_mq;
                int len = clear_mq.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_SEND_START) {
                RCLCPP_INFO(this->get_logger(), "\t Start sending to mission queue ...\n");
                StartSendingToMissionQueue start_send_mq;
                int len = start_send_mq.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_MOVE_3D) {
                Movement3D m3d;
                m3d.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                RCLCPP_INFO(this->get_logger(), "\t 3D movement x: %.1fm, y: %.1fm, z: %.1fm, hs: %.1fm/s, vs: %.1fm/s, act_now: %d!\n",
                       m3d.x, m3d.y, m3d.z, m3d.hs, m3d.vs, m3d.act_now);
                int len = m3d.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_WAYPOINT) {
                WayPoint wp;
                wp.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                RCLCPP_INFO(this->get_logger(), "\t Waypoint lat: %f, lon: %f, hover time: %ds, act_now: %d!\n",
                       wp.lat, wp.lon, wp.hover_time, wp.act_now);
                int len = wp.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_SEND_END) {
                RCLCPP_INFO(this->get_logger(), "\t End sending to mission queue!\n");
                EndSendingToMissionQueue end_send_mq;
                int len = end_send_mq.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_EXEC_MISSION) {
                RCLCPP_INFO(this->get_logger(), "\t Start execute mission queue ...\n");
                ExecuteMissionQueue exec_mq;
                int len = exec_mq.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_STOP_MISSION) {
                RCLCPP_INFO(this->get_logger(), "\t Stop execution of mission queue!\n");
                StopMissionQueue stop_mq;
                int len = stop_mq.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_SUSPEND_MISSION) {
                SuspendMissionQueue suspend_mq;
                suspend_mq.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                RCLCPP_INFO(this->get_logger(), "\t Suspend mission queue for %.1f seconds!\n", suspend_mq.suspend_time_s);
                int len = suspend_mq.get(sb);
                sendToDrone(sb, len);
            } else if (topic == TOPIC_REPLAY_MISSION) {
                ReplayMissionQueue replay_mq;
                replay_mq.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                RCLCPP_INFO(this->get_logger(), "\t Replay mission queue for %d times!\n", replay_mq.replay_time);
                int len = replay_mq.get(sb);
                sendToDrone(sb, len);
            }
            else {
                RCLCPP_WARN(this->get_logger(), "\t Unrecognized topic %s\n", topic.c_str());
            }
        }
        zmq_msg_close(&msg);
    }

    void sendToDrone(uint8_t* sendbuf, uint8_t len) {
        if (len > 0 && sendbuf) {
            int iResult = send(sock_, (const char*)sendbuf, len, 0);
            if (iResult == -1) {
                RCLCPP_ERROR(this->get_logger(), "Send failed with error: %d", errno);
                close(sock_);
                sock_ = -1;
            }
        } else {
            RCLCPP_WARN(this->get_logger(), "Send buf empty!");
        }
    }

    void sendToZmq(const std::string& topic, void* data, uint8_t len) {
        const size_t topic_size = topic.size();
        const size_t envelope_size = topic_size + 1 + len;
        zmq_msg_t envelope;
        if (zmq_msg_init_size(&envelope, envelope_size) != 0) {
            RCLCPP_ERROR(this->get_logger(), "ZeroMQ zmq_msg_init_size error: %s", zmq_strerror(errno));
            zmq_msg_close(&envelope);
            return;
        }
        memcpy(zmq_msg_data(&envelope), topic.c_str(), topic_size);
        memcpy((char*)zmq_msg_data(&envelope) + topic_size, " ", 1);
        memcpy((char*)zmq_msg_data(&envelope) + topic_size + 1, data, len);
        if (zmq_msg_send(&envelope, pub_, 0) != (ssize_t)envelope_size) {
            RCLCPP_ERROR(this->get_logger(), "ZeroMQ zmq_msg_send error: %s", zmq_strerror(errno));
        }
        zmq_msg_close(&envelope);
    }

    int sock_;
    void* context_;
    void* pub_;
    void* sub_;
    bool inited_;
    rclcpp::TimerBase::SharedPtr timer_;
};


int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<TcpClientRos2Node>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}