// definitions.h: Definition of flight control codes.
// Reference: https://support.swellpro.com/hc/en-us/articles/5890485717017-SplashDrone-4-SDK
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


#ifndef SPLASHDRONE4_ROS_DEFINITIONS_H
#define SPLASHDRONE4_ROS_DEFINITIONS_H

#pragma once

#include <cstdint>

/****** Data Packets Metadata Codes ******/
/** [START FLAG] [PackLength] [MSGID] [SRC] [DEST] [PAYLOAD] [CHECKSUM] **/
/**     0xa6 	     N+6 	    0x34   xx 	  xx       N 	     xx     **/

/* Packet Start Byte */
#define UMBUS_StrMarker                 0xa6  // including router info
#define UMBUS_StrMarker1                0xa3  // NOT including router info

/* MSG ID Byte */
#define MSG_CALIBRATION                 0x06 // aircraft calibration for gyro, accelerometer and compass
#define MSG_DEV_INFO                    0x0d // device information: version number, name, device ID, etc
#define MSG_FC_PARAM                    0x18 // flight control params: Alarm voltage, return height, mode control, runaway behavior, LED switch, etc
#define MSG_FLIGHT_LOG                  0x1a // flight log
#define MSG_GIMBAL_PARAM                0x1b // gimbal control params
#define MSG_FLIGHT_REPORT               0x1d // flight status report
#define MSG_GIMBAL_BROADCAST            0x30 // gimbal position broadcast
#define MSG_STAT_REPORT                 0x31 // flight mission status
#define MSG_FLIGHT_CONTROL              0x34 // flight control message

/* Source & Destination Device Code */
// For your own defined external devices, Device Code can be set to any code between 0xc8 to 0xfe.
#define DEVICE_SHARE_CODE               0x00 // the device will recognize as its own device
#define DEVICE_FLIGHT_CONTROL           0x01
#define DEVICE_REMOTE_CONTROLLER        0X02
#define DEVICE_GIMBAL                   0x03
#define DEVICE_APP_GROUND_STATION       0x04
#define DEVICE_REPORT                   0xff // all devices will receive and forward the message
#define DEVICE_MY_LAPTOP                0xc8 // my laptop
/****** Data Packets Metadata Codes ******/

/****** Flight Control Data Packets Payload Codes ******/
/** Symbol:    OPCODE  TASK.ID  TASK.TYPE  TASK.DATA **/
/** Byte len:     1       1         1           n    **/

/* Flight Control Mission Operation Code (OPCODE) */
#define FC_TASK_OC_TRAN_STR             0x01 // Start sending
#define FC_TASK_OC_ADD                  0x03 // Add mission to queue
#define FC_TASK_OC_READ                 0x04 // Read mission on queue
#define FC_TASK_OC_START                0x05 // Execute mission from the assigned location
#define FC_TASK_OC_STOP                 0x06 // Stop the current mission immediately
#define FC_TASK_OC_ERROR                0xfb // Error Message
#define FC_TASK_OC_ACK                  0xfc // Acknowledge
#define FC_TASK_OC_ACTION               0xfd // Execute the received mission immediately
#define FC_TASK_OC_CLEAR                0xfe // Clear mission queue
#define FC_TASK_OC_TRAN_END             0xff // Sending ends

/* Flight Control Interaction Operation Code (first byte in payload) */
// Flight mission codes, for message MSG_STAT_REPORT
#define FC_STAT_BATTERY                 0x01 // Smart battery status code
#define FC_STAT_NAV                     0x02 // Waypoint navigation status code
#define FC_STAT_GPSFM                   0x04 // Follow Me flight status code
#define FC_STAT_AHRS                    0x05 // AHRS sensor status code
#define FC_STAT_CIRCLES                 0x06 // Orbit flight status code
// Drone sensor calibration codes, for message MSG_CALIBRATION
#define FC_CAL_COMP                     0x02 // calibration for compass
#define FC_CAL_ACC                      0x03 // calibration for accelerometer
#define FC_CAL_GYRO                     0x08 // calibration for gyro
// Gimbal param get/set codes, for message MSG_GIMBAL_PARAM
#define FC_GIMBAL_GET                   0x00 // get gimbal setting, struct defined in Gimbal.h
#define FC_GIMBAL_SET                   0x01 // set gimbal setting, struct defined in Gimbal.h
// Flight Control params get/set codes, for message MSG_FC_PARAM
#define FC_GET                          0x00 // get fc setting, struct defined in FC-Setting.h
#define FC_SET                          0x01 // set fc setting, struct defined in FC-Setting.h
#define FC_VER                          0x04 // fc get/set version byte, constant
#define FC_RESET                        0xff // fc reset params

/* Flight Control Task ID (TASK.ID) */
#define FC_TASK_CONTINUE                0xff // Flight Control executes the mission from the previous stopping location
#define FC_TASK_RESTART                 0x00 // Flight Control executes the mission from the first one

/* Flight Control Mission Type (TASK.TYPE) */
#define FC_TSK_Null                     0
#define FC_TSK_TakeOff                  1 // Take Off
#define FC_TSK_Land                     2 // Land
#define FC_TSK_RTH                      3 // Return to Home
#define FC_TSK_SetHome                  4 // Set Home Point
#define FC_TSK_SetPOI                   5 // Set Point-of-Interest
#define FC_TSK_DelPOI                   6 // Delete Point-of Interest
#define FC_TSK_MOVE                     7 // Control Movement in 3D
#define FC_TSK_Gimbal                   8 // Control Gimbal Angle
#define FC_TSK_SetEXTIO                 9 // Control External IO (Payload Release, arm lights, strobe light)
#define FC_TSK_WayPoint                 10 // Add Waypoint
#define FC_TSK_SetSpeed                 11 // Set Flight Speed
#define FC_TSK_SetALT                   12 // Set Flight Altitude
#define FC_TSK_WAIT_MS                  15 // Set Hover Time
#define FC_TSK_REPLAY                   16 // Set Times of Repetition
#define FC_TSK_CAMERA                   17 // Control Camera
#define FC_TSK_RESERVE                  18 // Reserve
#define FC_TSK_CIRCLE                   19 // Orbit Flight

/****** Flight Control Data Packets Payload Codes ******/

/* Gimbal Position Broadcast */
#define GIMBAL_BROADCAST_ID             0x07 // fixed value of start flag of gimbal report

/* External Device 32-bit Mask */
#define PAYLOAD_RELEASE_1               1 << 24
#define PAYLOAD_RELEASE_2               1 << 25
#define STROBE_LIGHT                    1 << 28
#define ARM_LIGHT                       1 << 29


#endif //SPLASHDRONE4_ROS_DEFINITIONS_H
