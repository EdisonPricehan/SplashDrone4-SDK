//
// Created by princ on 2022/8/10.
//

#ifndef UMBUS_EXAMPLE_GIMBAL_H
#define UMBUS_EXAMPLE_GIMBAL_H

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


#endif //UMBUS_EXAMPLE_GIMBAL_H
