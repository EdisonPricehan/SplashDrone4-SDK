// device_info.h: Definition of device info.
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

#ifndef SPLASHDRONE4_ROS_DEVICE_INFO_H
#define SPLASHDRONE4_ROS_DEVICE_INFO_H

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

#endif //SPLASHDRONE4_ROS_DEVICE_INFO_H
