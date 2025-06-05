// tcp_client.cpp: Executable that communicates with the controller of
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


#define WIN32_LEAN_AND_MEAN

#ifdef _WIN32
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment (lib, "Ws2_32.lib")
#pragma comment (lib, "Mswsock.lib")
#pragma comment (lib, "AdvApi32.lib")
#else
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <cerrno>
#endif

#pragma comment (lib, "umbus")
#pragma comment (lib, "libzmq")

#include <cstdio>
#include <chrono>
#include <cstring>
#include <sstream>

#include "controls.h"

#include "zmq.h"

#ifdef _WIN32
#define ISVALIDSOCKET(s) ((s) != INVALID_SOCKET)
#define CLOSESOCKET(s) closesocket(s)
#define GETSOCKETERRNO()(WSAGetLastError())
#else
#define ISVALIDSOCKET(s) ((s) >= 0)
#define CLOSESOCKET(s) close(s)
#define GETSOCKETERRNO()(errno)
#define SOCKET int
#endif

#define DEFAULT_BUFLEN 256
#define DEFAULT_PORT "2022"

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


void sendToDrone(SOCKET& socket, uint8_t* sendbuf, uint8_t len) {
    if (len > 0 && sendbuf) {
        int iResult = send(socket, (const char*)sendbuf, len, 0);
        if (iResult == -1) {
            printf("Send failed with error: %d\n", GETSOCKETERRNO());
            CLOSESOCKET(socket);
#ifdef _WIN32
            WSACleanup();
#endif
            return;
        }
//        printf("Bytes Sent: %ld\n", iResult);
    } else {
        printf("Send buf empty!\n");
    }
}

void sendToZmq(void* pub, const std::string& topic, void* data, uint8_t len) {
    // PUB sockets need a topic to be associated with the messages they send
    // Topics can be used by the receivers to filter messages
    const size_t topic_size = strlen(topic.c_str());
    const size_t envelope_size = topic_size + 1 + len;
//    printf("Topic: %s; topic size: %zu; Envelope size: %zu\n", topic.c_str(), topic_size, envelope_size);

    // Create a ZeroMQ message and allocate the memory necessary for the message
    zmq_msg_t envelope;
    const int rmi = zmq_msg_init_size(&envelope, envelope_size);
    if (rmi != 0) {
        printf("ERROR: ZeroMQ error occurred during zmq_msg_init_size(): %s\n", zmq_strerror(errno));
        zmq_msg_close(&envelope);
        return;
    }

    // topic, followed by a space, then the binary data
    // whitespace as a separator between the topic and the data
    memcpy(zmq_msg_data(&envelope), topic.c_str(), topic_size);
    memcpy((void*)((char*)zmq_msg_data(&envelope) + topic_size), " ", 1);
    memcpy((void*)((char*)zmq_msg_data(&envelope) + 1 + topic_size), data, len);

    // Send the message through the data_socket
    const size_t rs = zmq_msg_send(&envelope, pub, 0);
    if (rs != envelope_size) {
        printf("ERROR: ZeroMQ error occurred during zmq_msg_send(): %s\n", zmq_strerror(errno));
        zmq_msg_close(&envelope);
        return;
    }

    // dispose of the envelope after used it
    zmq_msg_close(&envelope);
}


int main(int argc, char **argv) {
#ifdef _WIN32
    WSADATA wsaData;
    // Initialize Winsock
    if (WSAStartup(MAKEWORD(2, 2), &wsaData)) {
        printf("WSAStartup failed!\n");
        return EXIT_FAILURE;
    }
#endif

    printf("Configure remote address ...\n");
    struct addrinfo *result = nullptr,
            *ptr = nullptr,
            hints;
#ifdef _WIN32
    ZeroMemory(&hints, sizeof(hints));
#else
    memset(&hints, 0, sizeof(hints));
#endif

    char recvbuf[DEFAULT_BUFLEN];
    int iResult;

    // Validate the parameters
    if (argc < 2) {
        printf("%d", argc);
        printf("usage: %s server-name\n", argv[0]);
        return EXIT_FAILURE;
    }

    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_protocol = IPPROTO_TCP;

    // Resolve the server address and port
    if (getaddrinfo(argv[1], DEFAULT_PORT, &hints, &result)) {
        printf("getaddrinfo failed with error: %d\n", GETSOCKETERRNO());
#ifdef _WIN32
        WSACleanup();
#endif
        return EXIT_FAILURE;
    }

    // Attempt to connect to an address until one succeeds
    SOCKET ConnectSocket;
    for (ptr = result; ptr != nullptr; ptr = ptr->ai_next) {
        // Create a SOCKET for connecting to server
        printf("Creating socket ...\n");
        ConnectSocket = socket(ptr->ai_family, ptr->ai_socktype,
                               ptr->ai_protocol);
        if (!ISVALIDSOCKET(ConnectSocket)) {
            printf("socket failed with error: %d\n", GETSOCKETERRNO());
#ifdef _WIN32
            WSACleanup();
#endif
            return EXIT_FAILURE;
        }

        // Connect to server.
        printf("Connecting ...\n");
        if (connect(ConnectSocket, ptr->ai_addr, (int)ptr->ai_addrlen)) {
            printf("connect failed with error: %d\n", GETSOCKETERRNO());
            CLOSESOCKET(ConnectSocket);
            ConnectSocket = 0;
            continue;
        }
        break;
    }

    freeaddrinfo(result);
    printf("Connected.\n");

    // shutdown the connection since no more data will be sent
//    iResult = shutdown(ConnectSocket, SD_SEND);
//    if (iResult == SOCKET_ERROR) {
//        printf("shutdown failed with error: %d\n", WSAGetLastError());
//        closesocket(ConnectSocket);
//        WSACleanup();
//        return 1;
//    }

    // init zmq context: an object that manages all the sockets, use publisher and subscriber mode
    void* context = zmq_ctx_new();
    if (!context) {
        printf("ERROR: ZeroMQ error occurred during zmq_ctx_new(): %s\n", zmq_strerror(errno));
        return EXIT_FAILURE;
    }

    // PUB socket that deliver copies of a message to multiple receivers
    void* pub = zmq_socket(context, ZMQ_PUB);

    // The PUB socket must be bound to an address so that the clients know where to connect
    const int rb = zmq_bind(pub, "tcp://*:5555");
    if (rb != 0) {
        printf("ERROR: ZeroMQ error occurred during zmq_bind(): %s\n", zmq_strerror(errno));
        return EXIT_FAILURE;
    }

    // SUB socket that receive commands to control flight
    void* sub = zmq_socket(context, ZMQ_SUB);

    // The SUB socket needs to connect to the specified PUB address
    const int rt = zmq_connect(sub, "tcp://localhost:5556");
    if (rt != 0) {
        printf("ERROR: ZeroMQ error occurred during zmq_connect(): %s\n", zmq_strerror(errno));
        return EXIT_FAILURE;
    }
    zmq_setsockopt(sub, ZMQ_SUBSCRIBE, "", 0);

    // Receive until the peer closes the connection
    FLY_REPORT_V1 fly_report;
    t_BatteryInf battery_report;
    GimbalBroadcast gimbal_report;
    ACK ack;
    bool inited = false;
//    auto start = std::chrono::system_clock::now();
    do {
        iResult = recv(ConnectSocket, recvbuf, DEFAULT_BUFLEN, 0);
        if (iResult > 0) {
            if (!inited) { // only init once
                Init();
                inited = true;
            }
//            printf("Bytes received: %d\n", iResult);
            UART1_DataReceived((uint8_t*)recvbuf, iResult);

            // Publish fly report using zmq once one unpacking succeeds
            if (GetFlyReport(fly_report)) {
                sendToZmq(pub, TOPIC_FLY_REPORT, (void*)&fly_report, sizeof(fly_report));
            } else if (GetBatteryReport(battery_report)) {
                sendToZmq(pub, TOPIC_BATTERY_REPORT, (void*)&battery_report, sizeof(battery_report));
            } else if (GetGimbalReport(gimbal_report)) {
                sendToZmq(pub, TOPIC_GIMBAL_REPORT, (void*)&gimbal_report, sizeof(gimbal_report));
            } else if (GetAck(ack)) {
                sendToZmq(pub, TOPIC_ACK, (void*)&ack, sizeof(ack));
            }

            // deal with received zmq commands
            zmq_msg_t msg;
            zmq_msg_init(&msg);
            const int num_bytes = zmq_msg_recv(&msg, sub, ZMQ_NOBLOCK);
            if (num_bytes > 0 && num_bytes <= DEFAULT_BUFLEN) {
//                printf("Received %d bytes: %s\n", num_bytes, (char*)zmq_msg_data(&msg));
                std::string topic;
                std::istringstream iss((char*)zmq_msg_data(&msg));
                std::getline(iss, topic, ' ');
                auto topic_len = strlen(topic.c_str());
                printf("Topic: %s\n", topic.c_str());
                // Currently can only process one topic at a time, polling
                uint8_t* sb = nullptr; // sendbuf pointer of UMBUS.m1.pTxBuff
                if (topic == TOPIC_EXT_DEV) {
                    ExtDevOnOffStruct extDevOnOff;
                    extDevOnOff.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                    printf("\t pl1: %d, pl2: %d, sl: %d, al: %d, act_now: %d \n",
                           extDevOnOff.plr1, extDevOnOff.plr2, extDevOnOff.strobe_light, extDevOnOff.arm_light,
                           extDevOnOff.act_now);
                    uint8_t len = extDevOnOff.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_CAMERA_CONTROL) {
                    CameraControl cameraControl;
                    cameraControl.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                    printf("\t Take photo: %d, record: %d, act now: %d \n",
                           cameraControl.take_photo, cameraControl.record, cameraControl.act_now);
                    int len = cameraControl.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_TAKEOFF) {
                    TakeOff take_off;
                    take_off.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                    printf("\t Take off to height %.1fm, act_now: %d \n", take_off.height, take_off.act_now);
                    int len = take_off.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_LAND) {
                    Land land;
                    land.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                    printf("\t Land, act_now: %d \n", land.act_now);
                    int len = land.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_RETURN_TO_HOME) {
                    RetToHome rth;
                    rth.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                    printf("\t Return to home, act_now: %d \n", rth.act_now);
                    int len = rth.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_GIMBAL_CONTROL) {
                    printf("\t Controlling gimbal ...\n");
                    GimbalControl gimbal_control;
                    gimbal_control.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                    printf("\t Gimbal control (deg) roll: %d, pitch: %d, yaw: %d, act_now: %d \n",
                           gimbal_control.roll, gimbal_control.pitch, gimbal_control.yaw, gimbal_control.act_now);
                    int len = gimbal_control.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_SET_SPEED) {
                    SetSpeed ss;
                    ss.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                    printf("\t Set fly speed to %.1f m/s, act_now: %d \n", ss.speed_set, ss.act_now);
                    int len = ss.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_SET_ALT) {
                    SetAlt sa;
                    sa.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                    printf("\t Set fly height to %.1f m/s, act_now: %d \n", sa.altitude_set, sa.act_now);
                    int len = sa.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_CLEAR_MISSION_QUEUE) {
                    printf("\t Clear mission queue!\n");
                    ClearMissionQueue clear_mq;
                    int len = clear_mq.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_SEND_START) {
                    printf("\t Start sending to mission queue ...\n");
                    StartSendingToMissionQueue start_send_mq;
                    int len = start_send_mq.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_MOVE_3D) {
                    Movement3D m3d;
                    m3d.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                    printf("\t 3D movement x: %.1fm, y: %.1fm, z: %.1fm, hs: %.1fm/s, vs: %.1fm/s, act_now: %d!\n",
                           m3d.x, m3d.y, m3d.z, m3d.hs, m3d.vs, m3d.act_now);
                    int len = m3d.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_WAYPOINT) {
                    WayPoint wp;
                    wp.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                    printf("\t Waypoint lat: %f, lon: %f, hover time: %ds, act_now: %d!\n",
                           wp.lat, wp.lon, wp.hover_time, wp.act_now);
                    int len = wp.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_SEND_END) {
                    printf("\t End sending to mission queue!\n");
                    EndSendingToMissionQueue end_send_mq;
                    int len = end_send_mq.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_EXEC_MISSION) {
                    printf("\t Start execute mission queue ...\n");
                    ExecuteMissionQueue exec_mq;
                    int len = exec_mq.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_STOP_MISSION) {
                    printf("\t Stop execution of mission queue!\n");
                    StopMissionQueue stop_mq;
                    int len = stop_mq.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_SUSPEND_MISSION) {
                    SuspendMissionQueue suspend_mq;
                    suspend_mq.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                    printf("\t Suspend mission queue for %.1f seconds!\n", suspend_mq.suspend_time_s);
                    int len = suspend_mq.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                } else if (topic == TOPIC_REPLAY_MISSION) {
                    ReplayMissionQueue replay_mq;
                    replay_mq.set((char*)zmq_msg_data(&msg) + topic_len + 1);
                    printf("\t Replay mission queue for %d times!\n", replay_mq.replay_time);
                    int len = replay_mq.get(sb);
                    sendToDrone(ConnectSocket, sb, len);
                }
                else {
                    printf("\t Unrecognized topic %s\n", topic.c_str());
                }
            } else if (num_bytes < 0) {
//                printf("WARNING: No zmq msg received yet ...\n");
            } else {
                printf("WARNING: Received %d bytes, overflow!\n", num_bytes);
            }
            zmq_msg_close(&msg);

            // print elapsed time
//            auto end = std::chrono::system_clock::now();
//            std::chrono::duration<double> dur =  end - start;
//            start = end;
//            printf("Loop duration: %f ms.\n", dur.count() * 1000);

        } else if (iResult == 0)
            printf("Connection closed\n"); // break loop
        else
            printf("recv failed with error: %d\n", GETSOCKETERRNO()); // break loop
    } while (iResult > 0);

    // cleanup tcp socket
    printf("Close socket.\n");
    CLOSESOCKET(ConnectSocket);
#ifdef _WIN32
    WSACleanup();
#endif

    // cleanup zmq socket
    int rc = zmq_close(pub);
    if (rc != 0) {
        printf("ERROR: ZeroMQ error occurred during zmq_close(pub): %s\n", zmq_strerror(errno));
        return EXIT_FAILURE;
    }
    rc = zmq_close(sub);
    if (rc != 0) {
        printf("ERROR: ZeroMQ error occurred during zmq_close(sub): %s\n", zmq_strerror(errno));
        return EXIT_FAILURE;
    }
    rc = zmq_ctx_destroy(context);
    if (rc != 0) {
        printf("Error occurred during zmq_ctx_destroy(): %s\n", zmq_strerror(errno));
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}