//
// Created by princ on 2022/7/29.
//

#ifndef UMBUS_EXAMPLE_CONTROLS_H
#define UMBUS_EXAMPLE_CONTROLS_H

#pragma once

#include <cstdint>
#include <cstdio>
#include <cstring>

#include "Definitions.h"
#include "UMBUS.h"

static int mid = 0;

using namespace std;

int reverseByteOrder(const void*  array, int startIndex, int size) {
    int intNumber = 0;
    for (int i = 0; i < size; i++)
        intNumber = (intNumber << 8) | static_cast<const uint8_t*>(array)[startIndex + i];
    return intNumber;
}

struct Base {
    bool act_now = false;

    virtual void set(const char* data) = 0;

    virtual int get(uint8_t*& data) const = 0;
};

// If the designated altitude is set < 50 cm, the aircraft only unlocks and does not take off.
struct TakeOff : Base {
    float height = 0.4;

    void set(const char* data) override {
        memcpy(&height, data, 4);
        act_now = data[4];
    }

    int get(uint8_t*& data) const override {
        uint8_t taskData[5];
        // set metadata in payload
        taskData[0] = act_now ? FC_TASK_OC_ACTION : FC_TASK_OC_ADD;
        taskData[1] = act_now ? FC_TASK_RESTART : mid++;
        taskData[2] = FC_TSK_TakeOff; // Unlock and take off the aircraft to the designated altitude

        // copy bytes to payload
        auto altitude = uint16_t (height * 100); // from m to cm
        memcpy(&taskData[3], &altitude, sizeof(altitude));

        printf("\t Hex byte array: ");
        for (int i = 0; i < 5; ++i)
            printf("%02x ", taskData[i]);
        printf("\n");

        // send mission, source device is defined by user, destination is Flight Control
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 5, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

struct Land : Base {
    void set(const char* data) override {
        act_now = data[0];
    }

    int get(uint8_t*& data) const override {
        uint8_t taskData[3];
        // set metadata in payload
        taskData[0] = act_now ? FC_TASK_OC_ACTION : FC_TASK_OC_ADD;
        taskData[1] = act_now ? FC_TASK_RESTART : mid++;
        taskData[2] = FC_TSK_Land; // Land in the current position and then lock the motors

        // send mission, source device is defined by user, destination is Flight Control
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 3, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

struct RetToHome : Base {
    void set(const char* data) override {
        act_now = data[0];
    }

    int get(uint8_t*& data) const override {
        uint8_t taskData[3];
        // set metadata in payload
        taskData[0] = act_now ? FC_TASK_OC_ACTION : FC_TASK_OC_ADD;
        taskData[1] = act_now ? FC_TASK_RESTART : mid++;
        taskData[2] = FC_TSK_RTH; // Return to home and then lock the motors

        // send mission, source device is defined by user, destination is Flight Control
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 3, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

// Movement in 3d struct, zmq sub end, member data types and sequence need to be aligned with python zmq pub end
struct Movement3D : Base {
    float x, y, z, hs, vs; // meter and m/s

    Movement3D(): x(0), y(0), z(0), hs(0), vs(0) { }

    void set(const char* data) override {
        memcpy(&x, data, 4);
        memcpy(&y, &data[4], 4);
        memcpy(&z, &data[8], 4);
        memcpy(&hs, &data[12], 4);
        memcpy(&vs, &data[16], 4);
        act_now = data[20];
    }

    int get(uint8_t*& data) const override {
        uint8_t taskData[11];
        // set metadata in payload
        taskData[0] = act_now ? FC_TASK_OC_ACTION : FC_TASK_OC_ADD;
        taskData[1] = act_now ? FC_TASK_RESTART : mid++;
        taskData[2] = FC_TSK_MOVE; // Move in 3d

        // set data bytes in payload
        int16_t xg; // Front and back dimension relative to the aircraft: ± 32767 cm
        int16_t yg; // Left and right dimension relative to the aircraft: ± 32767 cm
        int16_t zg; // Up and down dimension relative to the aircraft: ± 32767 cm
        uint8_t hsg; // Horizontal flight speed: 0 - 250 = 0 - 25 m/s
        int8_t vsg; // Vertical flight speed: ± 40 = ± 4.0 m/s     sign is redundant??

        xg = int16_t (x * 100); // meter to centimeter
        yg = int16_t (y * 100);
        zg = int16_t (z * 100);
        hsg = uint8_t (hs * 10); // m/s to dm/s
        vsg = int8_t (vs * 10);

        memcpy(&taskData[3], &xg, 2);
        memcpy(&taskData[5], &yg, 2);
        memcpy(&taskData[7], &zg, 2);
        memcpy(&taskData[9], &hsg, 1);
        memcpy(&taskData[10], &vsg, 1);

        printf("\t Hex byte array: ");
        for (int i = 0; i < 11; ++i)
            printf("%02x ", taskData[i]);
        printf("\n");

        // send mission, source device is defined by user, destination is Flight Control
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 11, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

// Waypoint planning
struct WayPoint : Base {
    float lat = 0;
    float lon = 0;
    uint16_t hover_time = 0; // sec

    void set(const char* data) override {
        memcpy(&lat, data, 4);
        memcpy(&lon, &data[4], 4);
        memcpy(&hover_time, &data[8], 2);
        act_now = data[10];
    }

    int get(uint8_t*& data) const override {
        uint8_t taskData[13];
        // set metadata in payload
        taskData[0] = act_now ? FC_TASK_OC_ACTION : FC_TASK_OC_ADD;
        taskData[1] = act_now ? FC_TASK_RESTART : mid++;
        taskData[2] = FC_TSK_WayPoint; // Waypoint planning

        // set data bytes in payload
        auto latitude = int (lat * 1e7);
        auto longitude = int (lon * 1e7);
//        printf("Lat: %d, Long: %d, hover time: %ds\n", latitude, longitude, hover_time);
        memcpy(&taskData[3], &hover_time, 2);
        memcpy(&taskData[5], &latitude, 4);
        memcpy(&taskData[9], &longitude, 4);

        printf("\t Hex byte array: ");
        for (int i = 0; i < 13; ++i)
            printf("%02x ", taskData[i]);
        printf("\n");

        // send mission, source device is defined by user, destination is Flight Control
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 13, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

// External Device ON/OFF struct, zmq sub end, member data types and sequence need to be aligned with python zmq pub end
// Control on/off of 2 payloads release and 2 LED lights
struct ExtDevOnOffStruct : Base {
    bool plr1 = false;
    bool plr2 = false;
    bool strobe_light = false;
    bool arm_light = false;

    // set from zmq bytes
    void set(const char* data) override {
        plr1 = data[0];
        plr2 = data[1];
        strobe_light = data[2];
        arm_light = data[3];
        act_now = data[4];
    }

    // get to data bytes according to packet definition
    int get(uint8_t*& data) const override {
        uint8_t taskData[11];
        // set metadata in payload
        taskData[0] = act_now ? FC_TASK_OC_ACTION : FC_TASK_OC_ADD; // Execute command immediately or add to the queue
        taskData[1] = act_now ? FC_TASK_RESTART : mid++; // Mission ID, user-defined, do not set to the same ID as other missions
        taskData[2] = FC_TSK_SetEXTIO; // Mission Type

        // Payload release, strobe light, arm light. Can select a total of 32 IO (bits) at max
        // Select the bits of IO to operate
        uint32_t io_select = PAYLOAD_RELEASE_1 | PAYLOAD_RELEASE_2 | STROBE_LIGHT | ARM_LIGHT;
        // Set bit to 1 to turn ON the selected IO, 0 to turn OFF
        uint32_t on_off = 0;
        if (plr1) on_off |= PAYLOAD_RELEASE_1;
        if (plr2) on_off |= PAYLOAD_RELEASE_2;
        if (strobe_light) on_off |= STROBE_LIGHT;
        if (arm_light) on_off |= ARM_LIGHT;

        // reverse byte order from little-endian to big-endian for transmission
        io_select = reverseByteOrder(&io_select, 0, 4);
        on_off = reverseByteOrder(&on_off, 0, 4);

        memcpy(&taskData[3], &io_select, 4);
        memcpy(&taskData[7], &on_off, 4);

        printf("\t Hex byte array: ");
        for (int i = 0; i < 11; ++i)
            printf("%02x ", taskData[i]);
        printf("\n");

        // send mission, source device is defined by user, destination is Flight Control
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 11, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

// Gimbal Control
// Roll: +-45 deg, Pitch: +-90 deg, Yaw: +-45 deg
struct GimbalControl : Base {
    int16_t pitch = 0;
    int16_t roll = 0;
    int16_t yaw = 0;

    void set(const char* data) override {
        memcpy(&roll, data, 2);
        memcpy(&pitch, &data[2], 2);
        memcpy(&yaw, &data[4], 2);
        act_now = data[6];
    }

    int get(uint8_t*& data) const override {
        uint8_t taskData[9];
        // set metadata in payload
        taskData[0] = act_now ? FC_TASK_OC_ACTION : FC_TASK_OC_ADD;
        taskData[1] = act_now ? FC_TASK_RESTART : mid++;
        taskData[2] = FC_TSK_Gimbal; // Control gimbal

        // set data bytes in payload
        memcpy(&taskData[3], &pitch, 2);
        memcpy(&taskData[5], &roll, 2);
        memcpy(&taskData[7], &yaw, 2);

        printf("\t Hex byte array: ");
        for (int i = 0; i < 9; ++i)
            printf("%02x ", taskData[i]);
        printf("\n");

        // send mission, source device is defined by user, destination is Flight Control
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 9, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

// Camera Control, take photo or record video.
// Fill in all payload bytes in get
struct CameraControl : Base {
    bool take_photo, record;

    CameraControl(): take_photo(false), record(false) { }

    void set(const char* data) override {
        take_photo = data[0];
        record = data[1];
        act_now = data[2];
    }

    int get(uint8_t*& data) const override {
        uint8_t taskData[5];
        taskData[0] = act_now ? FC_TASK_OC_ACTION : FC_TASK_OC_ADD;
        taskData[1] = act_now ? FC_TASK_RESTART : mid++;
        taskData[2] = FC_TSK_CAMERA;
        taskData[3] = take_photo;
        taskData[4] = record ? 0x01 : 0x02;

        printf("\t Hex byte array: ");
        for (int i = 0; i < 5; ++i)
            printf("%02x ", taskData[i]);
        printf("\n");

        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 5, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

// Need to set fly speed before using waypoints planning, otherwise the default 6m/s speed or the last set speed will be used
struct SetSpeed : Base {
    float speed_set = 0;

    void set(const char* data) override {
        memcpy(&speed_set, data, 4);
        act_now = data[4];
    }

    int get(uint8_t*& data) const override {
        uint8_t taskData[5];
        // set metadata in payload
        taskData[0] = act_now ? FC_TASK_OC_ACTION : FC_TASK_OC_ADD;
        taskData[1] = act_now ? FC_TASK_RESTART : mid++;
        taskData[2] = FC_TSK_SetSpeed;
        // copy bytes to payload
        auto spd = uint16_t (speed_set * 100); // from m/s to cm/s, range 0-65535 cm/s
        memcpy(&taskData[3], &spd, sizeof(spd));

        printf("\t Hex byte array: ");
        for (int i = 0; i < 5; ++i)
            printf("%02x ", taskData[i]);
        printf("\n");

        // send mission, source device is defined by user, destination is Flight Control
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 5, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

// Set the fly altitude of waypoints planning, if not set the drone will fly at the current height
struct SetAlt : Base {
    float altitude_set = 0;

    void set(const char* data) override {
        memcpy(&altitude_set, data, 4);
        act_now = data[4];
    }

    int get(uint8_t*& data) const override {
        uint8_t taskData[5];
        // set metadata in payload
        taskData[0] = act_now ? FC_TASK_OC_ACTION : FC_TASK_OC_ADD;
        taskData[1] = act_now ? FC_TASK_RESTART : mid++;
        taskData[2] = FC_TSK_SetALT;
        // copy bytes to payload
        auto alt = uint16_t (altitude_set * 100); // from m/s to cm/s, range 0-65535 cm/s
        memcpy(&taskData[3], &alt, sizeof(alt));

        printf("\t Hex byte array: ");
        for (int i = 0; i < 5; ++i)
            printf("%02x ", taskData[i]);
        printf("\n");

        // send mission, source device is defined by user, destination is Flight Control
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 5, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

struct ClearMissionQueue {
    int get(uint8_t*& data) const {
        mid = 0; // reset mission id
        uint8_t taskData[2];
        taskData[0] = FC_TASK_OC_CLEAR; // fixed value
        taskData[1] = FC_TASK_RESTART; // fixed value
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 2, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

struct StartSendingToMissionQueue {
    int get(uint8_t*& data) const {
        uint8_t taskData[2];
        taskData[0] = FC_TASK_OC_TRAN_STR; // fixed value
        taskData[1] = FC_TASK_RESTART; // fixed value
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 2, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

struct EndSendingToMissionQueue {
    int get(uint8_t*& data) const {
        uint8_t taskData[2];
        taskData[0] = FC_TASK_OC_TRAN_END; // fixed value
        taskData[1] = FC_TASK_CONTINUE; // fixed value
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 2, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

struct ExecuteMissionQueue {
    int get(uint8_t*& data) const {
        uint8_t taskData[2];
        taskData[0] = FC_TASK_OC_START; // fixed value
        taskData[1] = FC_TASK_RESTART; // execute from the first mission
//        taskData[1] = FC_TASK_CONTINUE; // execute from last stopped mission
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 2, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

struct StopMissionQueue {
    int get(uint8_t*& data) const {
        uint8_t taskData[2];
        taskData[0] = FC_TASK_OC_STOP; // fixed value
        taskData[1] = FC_TASK_RESTART; // fixed value
        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 2, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

struct SuspendMissionQueue {
    float suspend_time_s = 0;

    void set(const char* data) {
        memcpy(&suspend_time_s, data, 4);
    }

    int get(uint8_t*& data) const {
        uint8_t taskData[7];
        taskData[0] = FC_TASK_OC_ADD; // fixed value
        taskData[1] = mid++; // must have a unique mission id
        taskData[2] = FC_TSK_WAIT_MS;

        auto wait_time_ms = uint32_t (suspend_time_s * 1000); // s to ms
        if (wait_time_ms < 10) {
            printf("Mission suspend time should not be less than 10 ms!\n");
            wait_time_ms = 10;
        }
        memcpy(&taskData[3], &wait_time_ms, sizeof(wait_time_ms));

        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 7, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }

};

struct ReplayMissionQueue {
    uint16_t replay_time = 0;

    void set(const char* data) {
        memcpy(&replay_time, data, 2);
    }

    int get(uint8_t*& data) const {
        uint16_t rt = replay_time;
        if (rt > 100) {
            printf("Mission queue repeat time %d should NOT exceeds 100!\n", rt);
            rt = 100;
        }

        uint8_t taskData[5];
        taskData[0] = FC_TASK_OC_ADD; // fixed value
        taskData[1] = mid++; // must have a unique mission id
        taskData[2] = FC_TSK_REPLAY;
        memcpy(&taskData[3], &rt, sizeof(rt));

        commUart1_TxPackFill(MSG_FLIGHT_CONTROL, taskData, 5, DEVICE_MY_LAPTOP, DEVICE_FLIGHT_CONTROL);
        return UART1_DataGet(data);
    }
};

#endif //UMBUS_EXAMPLE_CONTROLS_H
