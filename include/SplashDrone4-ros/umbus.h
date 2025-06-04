// umbus.h: Micro message communication bus protocol.
// [STAR][LENGTH][MsgID][SRC][DEST][DATA][CRC]
// [STAR][LENGTH][MsgID][DATA][CHECKSUM]
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


#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <cstdint>

#include "fly_state_report.h"
#include "nav_state_report.h"
#include "battery_info.h"
#include "gimbal.h"
#include "device_info.h"
#include "fc_setting.h"

#define UMBUS_OK              0
#define UMBUS_NOMARK          1
#define UMBUS_WAITDATA        2
#define UMBUS_DATA_ERR        3


/* Packet decoding status */
typedef enum UMBUS_RX_STATE {
  UMBUS_STATE_START,
  UMBUS_STATE_LEN,
  UMBUS_STATE_DATA,
  UMBUS_STATE_CHKSUM,
  UMBUS_STATE_END
} UMBUS_RX_STATE;


/* Structure to store packet metadata and payload */
typedef struct UMBUS_MSG {
  uint32_t DeviceID;
  uint8_t  MsgID;
  uint16_t Len; // byte length of payload only
  uint8_t *Data; // pointer to start byte of payload
  uint8_t  SRC;
  uint8_t  DEST;
  uint8_t* pRawData; // pointer to the start flag (0xa6)
} UMBUS_MSG;


/* Structure that keeps track of unpacking and packing process of data */
typedef struct UMBUS {
  /* public */
  uint16_t TxPackCount;
  uint16_t RxPackCount;
  uint16_t RxErrCount;
  uint8_t  TxOverCount; /* Send overflow counter */
  uint8_t StrMark; /* start flag, a constant */
  int (*FillToTxBuff)(struct UMBUS* THIS, uint8_t*, int); // form packet
  void (*pRxPackCallBack)(struct UMBUS* THIS, UMBUS_MSG* pMsg); // received packet
  // private:
  struct {
    uint8_t m_rxCrcSate, m_rxChkSum;
    uint8_t m_txCrcSate, m_txChkSum;
    uint16_t BuffSize; /* range 8 - 256, a constant for both rx and tx buffers*/
    uint8_t m_wIdx; /* rx buffer write index */
    UMBUS_RX_STATE m_RxState;
    uint8_t *pRxBuff;
    uint8_t *pTxBuff;
    uint8_t m_wtIdx; // tx buffer write index
    uint8_t InfLength; // length of additional (non-payload) bytes
  } m1;
} UMBUS;


/***** Init *****/
/* Init umbus with allocated memory pointer and length, BufferSize length can only be 8 16 32 64 128 256  */
void UMBUS_Init(UMBUS *THIS, uint8_t* RxBuff, uint8_t* TxBuff);

/* Initializes the protocol decoding object */
void Init();


/***** Encoding and Transmitting *****/
/* Encode a packet (message id, length, src, dest) to send */
int UMBUS_StartPack(UMBUS *THIS, uint8_t MsgID, uint8_t Length, uint8_t SrcDev, uint8_t DstDev);
void UMBUS_Fill(UMBUS* THIS, uint8_t *p_Data, uint8_t Length);
void UMBUS_EndPack(UMBUS* THIS);

/* Encode and form a tx packet with given payload */
int commUart1_TxPackFill(int MsgID, uint8_t* Data, int Len, int SRC, int DEST);

/* Write bytes to tx buffer */
int UMBUS_TxPackFill(UMBUS* THIS, uint8_t* txData, int length);

/* Get tx data pointer and length */
int UART1_DataGet(uint8_t*& txBuff);


/***** Receiving and Decoding *****/
/* Decode from socket to umbus */
void UMBUS_Decode(UMBUS *THIS,uint8_t *p_InData,int inDataNum,uint32_t DeviceID);

/* Decode from umbus to umbus struct */
void UMBUS_DecodePack(UMBUS *THIS, UMBUS_MSG* msgPack);

/* Decode fly report from umbus message */
void UMBUS_PackRXD(UMBUS* THIS,UMBUS_MSG* pMsg);

/* Callback function when receiving packet from socket */
void UART1_DataReceived(uint8_t* rxBuff, int Length);

/* Get fly report and set flag */
bool GetFlyReport(FLY_REPORT_V1& fly_report);

/* Get battery report and set flag */
bool GetBatteryReport(t_BatteryInf& battery_report);

/* Get gimbal report and set flag */
bool GetGimbalReport(GimbalBroadcast& gimbal_report);

/* Get ack and set flag */
bool GetAck(ACK& ack);

/* Get Waypoint navigation report */
bool GetWaypointReport(WP_NAV_STATE& wp_nav_state);

#ifdef __cplusplus
}
#endif
