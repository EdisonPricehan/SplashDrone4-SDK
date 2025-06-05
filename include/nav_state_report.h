// nav_state_report.h: Definition of navigation state report.
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


#ifndef SPLASHDRONE4_ROS_NAV_STATE_REPORT_H
#define SPLASHDRONE4_ROS_NAV_STATE_REPORT_H

#pragma once

#include <cstdint>

/* Waypoint Navigation Report */
typedef struct {
    uint8_t  NavState;            // Navigation state
    uint8_t  WPNumber;            // Index of the currently executing waypoint
    uint8_t  DelayTimeSec;        // Waiting countdown time
    uint8_t  WPMaxNum;            // Maximum waypoints number
    uint8_t  DirRate;             // Turning rate, deg/s
    uint8_t  MaxFlySpeed;         // Maximum fly speed, m/s
    uint16_t EndDistance;         // Distance to ending waypoint, m
    int16_t  PathCourseDiff;      // Route deviation
    int32_t  lat, lng;            // Lat and Lon of current target waypoint
} WP_NAV_STATE;

/* Navigation State Definition */
typedef enum {
    NS_NULL = 0,
    NS_ReadyToFly,
    NS_Delay,
    NS_Flying,
    NS_ReadyToEnd,
    NS_Complete,
    NS_Pause,
} NavState;


#endif //SPLASHDRONE4_ROS_NAV_STATE_REPORT_H
