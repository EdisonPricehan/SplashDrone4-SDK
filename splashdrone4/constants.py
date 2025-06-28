# constants.py: Define constants used in communicating with SplashDrone4.
# Copyright (C) <2025>  <Zihan Wang>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


# Constant rtsp address for video streaming
# https://support.swellpro.com/hc/en-us/articles/5890485717017-SplashDrone-4-SDK
RTSP_ADDR = "rtsp://192.168.2.220:554"

# TCP client IP
TCP_CLIENT_ADDR = '192.168.2.1'

# ZMQ pub/sub addresses
ZMQ_SUB_ADDR = "tcp://localhost:5555"
ZMQ_PUB_ADDR = "tcp://*:5556"

# Formats of received reports
FORMAT_FLY_REPORT = "3hHhH3hH4i2Bb3BH"  # refer to definition in fly_state_report.h
FORMAT_BATTERY_REPORT = "3HBb4Bi"  # refer to definition in battery_info.h
FORMAT_GIMBAL_REPORT = "3f"  # refer to definition in gimbal.h
FORMAT_NAV_REPORT = "6BHh2i"  # refer to definition in nav_state_report.h
FORMAT_ACK = "=BBI"  # refer to definition in fly_state_report.h

IMG_HEIGHT = 128
IMG_WIDTH = 128
ACTION_DIM = 4

