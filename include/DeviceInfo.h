//
// Created by princ on 2022/8/10.
//

#ifndef UMBUS_EXAMPLE_DEVICEINFO_H
#define UMBUS_EXAMPLE_DEVICEINFO_H

#pragma once

#include <cstdint>

// Device info, request-response
typedef struct {
    uint32_t SysId;
    uint32_t ChipId;
    uint32_t FlyTime;
    uint32_t BuildTime;
    char     DesStr[32];
    uint32_t VER_FW;
    uint32_t VER_HW;
} DeviceInfo;

#endif //UMBUS_EXAMPLE_DEVICEINFO_H
