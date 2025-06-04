// fc_setting.h: Definition of flight control setting.
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


#ifndef SPLASHDRONE4_ROS_FC_SETTING_H
#define SPLASHDRONE4_ROS_FC_SETTING_H

#pragma once

/* Flight Control Settings Data Structure */
#include <cstdint>

typedef struct {
  uint8_t Gain_Gyro_pitch;      /* Gyroscope Pitch Sensitivity */
  uint8_t Gain_Gyro_roll;       /* Gyroscope Roll Sensitivity */
  uint8_t Gain_Gyro_yaw;        /* Gyroscope Yaw Sensitivity */
  uint8_t Gain_Attitude;        /* Attitude Control Sensitivity */
  uint8_t Gain_Altitude;        /* Altitude Control Sensitivity*/
  uint8_t Gain_Position;        /* Position Control Sensitivity */
  uint8_t JoystickScale;        /* Control Stick Sensitivity */

  /* Flight Limitation, FailSafe(Signal Lost) Behavior, Low Battery Behavior Settings */
  uint8_t AlarmVoltage;         /* Low Battery Alarm Voltage, unit: 0.1v */
  uint8_t LandVoltage;          /* Low Battery Auto Landing Voltage, unit: 0.1v */
  uint8_t MaxFlySpeed;          /* Maximum Flight Speed, unit: 0.1m */
  uint8_t Limit_Height;         /* Maximum Flight Altitude, unit: m */
  uint8_t RTH_ALT;              /* Return-to-Home Alitude */
  uint8_t MotorBias;            /* Motor Bias */
  uint8_t ModeCtrMap[5];        /* Flight Mode Map */
    /* Flight Mode Map
     3-stage slider with 5 configurable custom flight modes
     Different flight mode：
    FM_Manual    = 0x00  Manual Mode
    FM_Balance   = 0x01  Balance Mode
    FM_Altitude  = 0x02  ATTI Mode
    FM_Gps       = 0x03  GPS Mode 
    FM_Cruise    = 0x04  Cruise Mode
    FM_AOC       = 0x05  Headless Mode
    FM_Circular  = 0x06  Orbit Mode
    FM_GoHome    = 0x07  Return-to-Home
    FM_GPS_S     = 0x08  GPS-Sport Mode
    FM_NONE      = 0x80  Null
 */
  int8_t MotorMixMap[8 * 4];    /* Motor output map */
  uint16_t Limit_Distance;      /* Maximum Flight Distance(m) */
  uint8_t reserve1;             /* Reserved Value */
  uint8_t FrameNum;             /* Bodyframe Number */
  /* 
  bit7=1: Lock key parameter
  bit5=1: Turn off Arm Lights, bit4:=1 Turn off Strobe Light
  bit0=1: Turn on Low Battery Return-to-Home */
  uint8_t BIT_FLAG_1;  
  /* bit0:=1 Low Battery Auto Payload Release
     bit1:=1 Return-to-Home Auto Payload Release
     bit3-4: Failsafe Behavior =0: Return-to-Home; =1: Hover; =2: Land
  */
  uint8_t BIT_FLAG_2;           
} tParVar;

/* FC setting, request-response */
typedef struct FC_SETTING {
  uint8_t  Flag1;             //Flag
  uint8_t  BatteryVoltage;    //Battery Voltage
  uint8_t  WorkMode;          //Flight Mode
  uint8_t  reserve1;
  uint32_t VER_FW;            //Flight Control Firmware Version
  uint32_t DevId;             //Device ID
  uint32_t FlyTime;           //Total Flight Time(not for single flight)
  uint32_t BuildTime;         //Build Time
  uint8_t  ProductName[16];   //Product Name
  uint16_t VER_HW;            //Flight Control Hardware Version
  uint8_t  reserve2;          /* Reserved Value */
  uint8_t  reserve3;          /* Reserved Value */
  tParVar  ParVar;
} FC_SETTING;


#endif //SPLASHDRONE4_ROS_FC_SETTING_H