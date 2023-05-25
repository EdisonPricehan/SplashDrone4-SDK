//
// Created by princ on 2022/8/10.
//

#ifndef UMBUS_EXAMPLE_NAVSTATEREPORT_H
#define UMBUS_EXAMPLE_NAVSTATEREPORT_H

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


#endif //UMBUS_EXAMPLE_NAVSTATEREPORT_H
