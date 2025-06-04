// battery_info.h: Definition of battery info report.
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


#ifndef SPLASHDRONE4_ROS_BATTERY_INFO_H
#define SPLASHDRONE4_ROS_BATTERY_INFO_H

#pragma once

#include <cstdint>

/* Intelligent Flight Battery Report Message Structure */
typedef struct {
  uint16_t Voltage;         /* Battery Voltage(mV) */
  uint16_t Capacity;        /* Battery Capacity(mah) */
  uint16_t RemainCap;       /* Remaining Battery Capacity(mah) */
  uint8_t  Percent;         /* Remaining Battery Percentage */
  int8_t   temperature;     /* Battery Temperature(degree Celcius) */
  uint8_t  RemainHoverTime; /* Remaining Hover Time(Minutes) */
  uint8_t  Reserve1;        /* Reserve Value */
  uint8_t  Reserve2;        /* Reserve Value */
  uint8_t  Reserve3;        /* Reserve Value */
  int32_t  eCurrent;        /* Battery Current(mA) */
} t_BatteryInf;

#endif //SPLASHDRONE4_ROS_BATTERY_INFO_H