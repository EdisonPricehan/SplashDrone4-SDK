// umbus.cpp: Micro message communication bus protocol.
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


#include "SplashDrone4-ros/umbus.h"
#include "SplashDrone4-ros/definitions.h"
#include "SplashDrone4-ros/crc.h"

#include <iostream>
#include <cstring>

using namespace std;

/* static variables */
static UMBUS UCDP_UART1;
const static uint32_t BUFFER_SIZE = 256;
static uint8_t UCDP_RX_DataBuff[BUFFER_SIZE];
static uint8_t UCDP_TX_DataBuff[BUFFER_SIZE];

// fly report
static FLY_REPORT_V1 flyState;
static bool flyStateReady = false;

// gimbal report
static GimbalBroadcast gimbal_broadcast;
static bool gimbal_broad_ready = false;

// gimbal report
static t_BatteryInf battery_info;
static bool battery_info_ready = false;

// navigation state report
static WP_NAV_STATE wp_nav_state;
static bool wp_nav_ready = false;

// acknowledge packet payload
static ACK mission_ack;
static bool ack_ready = false;

/* data structure with counter used in unpacking */
typedef struct {
  uint8_t* p_InData; // copy of received data's initial address
  int inDataNum; // keep track of remaining bytes that are unpacked yet
  int idx; // keep track of the next byte index to unpack
} UMBUS_DECODE_DATA;

/* loop over received bytes until find start flag, then reset umbus */
static void UMBUS_CheckHead(UMBUS* THIS, UMBUS_DECODE_DATA* UDD){
  int rxByte;
  while (UDD->inDataNum > 0) {
    rxByte = UDD->p_InData[UDD->idx];
    UDD->inDataNum--;
    UDD->idx++;
    if (rxByte == THIS->StrMark) {
      THIS->m1.m_RxState = UMBUS_STATE_LEN;
      THIS->m1.pRxBuff[0] = rxByte;
      THIS->m1.m_wIdx = 1;
      THIS->m1.m_rxCrcSate = 0;
      THIS->m1.m_rxChkSum = 0;
      return ;
    }
  }
}

/**/
static void UMBUS_CheckPayload(UMBUS* THIS, UMBUS_DECODE_DATA* UDD){
  int rxByte;
  int wIdx = THIS->m1.m_wIdx;
  uint8_t crc = THIS->m1.m_rxCrcSate;
  uint8_t chksum = THIS->m1.m_rxChkSum;
  int packEndLength = THIS->m1.pRxBuff[1] - 1;

  while (UDD->inDataNum > 0 && wIdx < packEndLength) {
    rxByte = UDD->p_InData[UDD->idx];
    UDD->inDataNum--;
    UDD->idx++;
    THIS->m1.pRxBuff[wIdx++] = rxByte;
    crc = CRC8_Table[crc ^ rxByte];
    chksum = chksum ^ rxByte;
  }

  THIS->m1.m_wIdx = wIdx;
  THIS->m1.m_rxCrcSate = crc;
  THIS->m1.m_rxChkSum = chksum;
  if(wIdx == packEndLength)
    THIS->m1.m_RxState = UMBUS_STATE_CHKSUM;
}

/* make sense of the buffered byte array */
/* [STAR][LENGTH][MsgID][SRC][DEST][DATA][CRC] */
void UMBUS_DecodePack(UMBUS* THIS, UMBUS_MSG* msgPack){
  if (THIS->m1.pRxBuff[0] == UMBUS_StrMarker) { // 0xa6
    msgPack->MsgID  = THIS->m1.pRxBuff[2];
    msgPack->Len  = THIS->m1.pRxBuff[1] - 6;
    msgPack->Data = &THIS->m1.pRxBuff[5];
    msgPack->pRawData = THIS->m1.pRxBuff;
    // with source and destination info
    msgPack->SRC = THIS->m1.pRxBuff[3];
    msgPack->DEST = THIS->m1.pRxBuff[4];
  }
  if (THIS->m1.pRxBuff[0] == UMBUS_StrMarker1) { // 0xa3
    msgPack->MsgID  = THIS->m1.pRxBuff[2];
    msgPack->Len  = THIS->m1.pRxBuff[1] - 4;
    msgPack->Data = &THIS->m1.pRxBuff[3];
    msgPack->pRawData = THIS->m1.pRxBuff;
    // no source and destination info
    msgPack->SRC  = 0x00;
    msgPack->DEST = 0x00;
  }
}

/* Entry point decoder of socket */
void UMBUS_Decode(UMBUS* THIS, uint8_t* p_InData, int inDataNum, uint32_t DeviceID) {
  UMBUS_DECODE_DATA UDD;
  UMBUS_MSG         UMMsg;
  UDD.inDataNum = inDataNum;
  UDD.p_InData = p_InData;
  UDD.idx = 0;
  /**/
  while (UDD.inDataNum > 0) {
    if (THIS->m1.m_RxState == UMBUS_STATE_START) {
      UMBUS_CheckHead(THIS, &UDD);
    }// check length
    else if (THIS->m1.m_RxState == UMBUS_STATE_LEN && UDD.inDataNum > 0) {
      THIS->m1.pRxBuff[1] = UDD.p_InData[UDD.idx];
      THIS->m1.m_wIdx = 2;
      /**/
      UDD.inDataNum--;
      UDD.idx++;
      THIS->m1.m_RxState = UMBUS_STATE_DATA;
      /**/
      THIS->m1.InfLength = 4;
      if(THIS->m1.pRxBuff[0] == UMBUS_StrMarker){
        THIS->m1.InfLength = 6;
      }
      // start crc and checksum from 'length' byte to the last byte of 'payload'
      if(THIS->m1.pRxBuff[1] < THIS->m1.InfLength || THIS->m1.pRxBuff[1] > THIS->m1.BuffSize){
        THIS->m1.m_RxState = UMBUS_STATE_START;
        THIS->RxErrCount++;
      }
      /* length byte itself should also be checked */
      uint8_t rxByte = THIS->m1.pRxBuff[1];
      THIS->m1.m_rxCrcSate = CRC8_Table[THIS->m1.m_rxCrcSate ^ rxByte];
      THIS->m1.m_rxChkSum = THIS->m1.m_rxChkSum ^ rxByte;
    } // check payload
    else if (THIS->m1.m_RxState == UMBUS_STATE_DATA) {
      UMBUS_CheckPayload(THIS, &UDD);
    } // check crc
    else if (THIS->m1.m_RxState == UMBUS_STATE_CHKSUM) {
      THIS->m1.pRxBuff[THIS->m1.m_wIdx++] = UDD.p_InData[UDD.idx];
      UDD.inDataNum--;
      UDD.idx++;
      if(THIS->m1.m_rxCrcSate == THIS->m1.pRxBuff[THIS->m1.m_wIdx-1] ||
         THIS->m1.m_rxChkSum == THIS->m1.pRxBuff[THIS->m1.m_wIdx-1]){
        THIS->RxPackCount++;
        UMBUS_DecodePack(THIS, &UMMsg);
        UMMsg.DeviceID = DeviceID;
        if (THIS->pRxPackCallBack != 0)
          THIS->pRxPackCallBack(THIS, &UMMsg);
      } else { // check failed
        THIS->RxErrCount++;
      }
      THIS->m1.m_RxState = UMBUS_STATE_START;
    }
    /**/
  }
}

/* Init umbus buffer pointer and size */
void UMBUS_Init(UMBUS* THIS, uint8_t* RxBuff, uint8_t* TxBuff) {
  THIS->pRxPackCallBack = nullptr;
  THIS->FillToTxBuff = nullptr;
  THIS->m1.pRxBuff = RxBuff;
  THIS->m1.pTxBuff = TxBuff;
  THIS->m1.BuffSize = BUFFER_SIZE;
  THIS->StrMark = UMBUS_StrMarker;
}

/*  
  0xa5,packLength,MsgID,SrcDev,DstDev,Data,CRC8
  DstDev=DestinationDevice , SrcDev=sourceDevice
*/
int UMBUS_StartPack(UMBUS* THIS, uint8_t MsgID, uint8_t Length, uint8_t SrcDev, uint8_t DstDev) {
  uint8_t headPack[5]; // 5 bytes before payload
  int headLength = 3; // will be set to 5 later
  THIS->m1.m_txChkSum = THIS->m1.m_txCrcSate = 0; // reset tx crc and checksum
  THIS->m1.m_wtIdx = 0; // reset tx write index
  // check bytes overflow before packing
  if (Length > (THIS->m1.BuffSize - (headLength+1))){
    THIS->TxOverCount++;
    return -1;
  }
  // fill in header bytes
  if (THIS->StrMark == UMBUS_StrMarker) {
    headPack[3] = SrcDev;
    headPack[4] = DstDev;
    headLength = 5;
  }
  headPack[0] = THIS->StrMark;
  headPack[1] = Length + headLength + 1; // payload + head + crc
  headPack[2] = MsgID;

  // update transmission crc and checksum from 'length' byte to 'dest' byte
  int k;
  for (k=1; k<headLength; k++) {
    THIS->m1.m_txCrcSate = CRC8_Table[THIS->m1.m_txCrcSate ^ headPack[k]];
    THIS->m1.m_txChkSum ^= headPack[k];
  }
  THIS->FillToTxBuff(THIS, &headPack[0], headLength);
  return 0;
}

/* update crc and checksum for payload bytes, and fill payload into transmission buffer */
void UMBUS_Fill(UMBUS* THIS, uint8_t* p_Data, uint8_t Length) {
  int k;
  for (k = 0; k < Length; k++) {
    THIS->m1.m_txCrcSate = CRC8_Table[THIS->m1.m_txCrcSate ^ p_Data[k]];
    THIS->m1.m_txChkSum = THIS->m1.m_txChkSum ^ p_Data[k];
  }
  THIS->FillToTxBuff(THIS, p_Data, Length);
}

/* append crc8 byte to the transmission packet buffer */
void UMBUS_EndPack(UMBUS* THIS){
  uint8_t endPack[2];
  endPack[0] = THIS->m1.m_txCrcSate;
  if (THIS->StrMark == UMBUS_StrMarker1)
    endPack[0] = THIS->m1.m_txChkSum;
  /**/
  THIS->TxPackCount++;
  THIS->FillToTxBuff(THIS, &endPack[0], 1);
}

/* Decode fly report from umbus message */
void UMBUS_PackRXD(UMBUS* THIS, UMBUS_MSG* pMsg){
    if (pMsg->MsgID == MSG_FLIGHT_REPORT) {
        memcpy((void*)&flyState, (void*)pMsg->Data, sizeof(flyState));
//        printf("Roll: %f \t Pitch: %f \t Yaw: %f \t Lon: %d \t Lat: %d \t throttle: %d \n",
//               flyState.ATTRoll * 0.1, flyState.ATTPitch * 0.1, flyState.ATTYaw * 0.1,
//               flyState.Lon, flyState.Lat,
//               flyState.InGas);
        flyStateReady = true;
    } else if (pMsg->MsgID == MSG_GIMBAL_BROADCAST) {
        if (pMsg->Data[0] == 0x07) {
            memcpy((void*)&gimbal_broadcast, (void*)&pMsg->Data[1], sizeof(gimbal_broadcast));
//            printf("Gimbal roll: %.1f \t pitch: %.1f \t yaw: %.1f \n",
//                   gimbal_broadcast.roll, gimbal_broadcast.pitch, gimbal_broadcast.yaw);
            gimbal_broad_ready = true;
        } else {
            printf("Gimbal broadcast decoding failed! \n");
        }
    } else if (pMsg->MsgID == MSG_STAT_REPORT) {
        if (pMsg->Data[0] == FC_STAT_BATTERY) {
            memcpy((void*)&battery_info, (void*)&pMsg->Data[1], sizeof(battery_info));
//            printf("Battery voltage: %.1f mV, rem time: %d min, rem pct: %d\% \n",
//                   battery_info.Voltage / 1000.0, battery_info.RemainHoverTime, battery_info.Percent);
            battery_info_ready = true;
        } else if (pMsg->Data[0] == FC_STAT_NAV) {
            memcpy((void*)&wp_nav_state, (void*)&pMsg->Data[1], sizeof(wp_nav_state));
//            printf("Waypoint navigation stat received!\n");
            wp_nav_ready = true;
        }
        // TODO accept other stat reports
    } else if (pMsg->MsgID == MSG_FLIGHT_CONTROL) {
        if (pMsg->Data[0] == FC_TASK_OC_ACK) {
            memcpy((void*)&mission_ack, (void*)&pMsg->Data[1], sizeof(mission_ack));
            ack_ready = true;
            printf("\t Ack received, id: %d, type: %d, code: %d \n",
                   mission_ack.mission_id, mission_ack.mission_type, mission_ack.mission_data);
        }
    }
    // TODO accept other FC responses
}

/* Callback function when receiving packet from socket */
void UART1_DataReceived(uint8_t* rxBuff, int Length) {
    UMBUS_Decode(&UCDP_UART1, &rxBuff[0], Length, 0);
}

bool GetFlyReport(FLY_REPORT_V1& fly_report) {
    if (flyStateReady) {
        fly_report = flyState;
        flyStateReady = false;
        return true;
    } else {
//        printf("Fly report not ready yet!\n");
        return false;
    }
}

bool GetBatteryReport(t_BatteryInf& battery_report) {
    if (battery_info_ready) {
        battery_report = battery_info;
        battery_info_ready = false;
        return true;
    } else {
//        printf("Battery report not ready yet!\n");
        return false;
    }
}

bool GetGimbalReport(GimbalBroadcast& gimbal_report) {
    if (gimbal_broad_ready) {
        gimbal_report = gimbal_broadcast;
        gimbal_broad_ready = false;
        return true;
    } else {
//        printf("Gimbal report not ready yet!\n");
        return false;
    }
}

bool GetAck(ACK& ack) {
    if (ack_ready) {
        ack = mission_ack;
        ack_ready = false;
        return true;
    } else {
//        printf("ACK not ready yet!\n");
        return false;
    }
}

bool GetWaypointReport(WP_NAV_STATE& wp_state) {
    if (wp_nav_ready) {
        wp_state = wp_nav_state;
        wp_nav_ready = true;
        return true;
    } else {
//        printf("Waypoint navigation report not ready yet!\n");
        return false;
    }
}

/* Write bytes to tx buffer */
int UMBUS_TxPackFill(UMBUS* THIS, uint8_t* txData, int length) {
    if (BUFFER_SIZE - THIS->m1.m_wtIdx < length) {
        printf("Not enough vacant bytes to fill!");
        return -1;
    }
    memcpy(&THIS->m1.pTxBuff[THIS->m1.m_wtIdx], txData, length);
    THIS->m1.m_wtIdx += length;
    return 0;
}

/* Get tx data pointer and length */
int UART1_DataGet(uint8_t*& txBuff) {
    txBuff = UCDP_UART1.m1.pTxBuff;
    return UCDP_UART1.m1.m_wtIdx;
}

/* Initializes the protocol decoding object */
void Init() {
    UMBUS_Init(&UCDP_UART1, &UCDP_RX_DataBuff[0], &UCDP_TX_DataBuff[0]);
    UCDP_UART1.pRxPackCallBack = &UMBUS_PackRXD;
    UCDP_UART1.FillToTxBuff = &UMBUS_TxPackFill;
}

/* Encode and form a tx packet with given payload */
int commUart1_TxPackFill(int MsgID, uint8_t* Data, int Len, int SRC, int DEST) {
    if (UMBUS_StartPack(&UCDP_UART1, MsgID, Len, SRC, DEST) < 0) {
        printf("Buffer overflow!");
        return 0;
    }
    UMBUS_Fill(&UCDP_UART1, Data, Len);
    UMBUS_EndPack(&UCDP_UART1);
    return UCDP_UART1.m1.m_wtIdx; // current total bytes in the tx buffer
}