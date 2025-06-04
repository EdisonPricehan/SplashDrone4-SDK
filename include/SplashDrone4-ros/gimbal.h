// gimbal.h: Definition of gimbal state report.
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


#ifndef SPLASHDRONE4_ROS_GIMBAL_H
#define SPLASHDRONE4_ROS_GIMBAL_H

// Gimbal camera roll/pitch/yaw def
typedef struct {
    float roll; // +-180
    float pitch; // +-90
    float yaw; // +-180
} GimbalBroadcast;

// Gimbal setting
typedef struct {
    uint32_t UserFlag;
    uint8_t  RESERVE1[3][2*6];
    uint8_t  RESERVE2[3][6];
    uint8_t  RESERVE3[3][6];
    uint8_t  angleLimit_Pitch[2]; // up,down max allowed control angle in degree
    uint8_t  angleLimit_Roll[2];
    uint8_t  angleLimit_Yaw[2];
    uint8_t  UI_Sens[3]; // Control input sensitivity, the higher the value is, the faster the head rotates. range: 0-128
    uint8_t  UI_DeadArea[3]; // Control input dead area
} GIMBAL_SETTING;


#endif //SPLASHDRONE4_ROS_GIMBAL_H
