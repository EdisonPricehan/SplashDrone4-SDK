
# ZMQ pub/sub addresses
ZMQ_SUB_ADDR = "tcp://localhost:5555"
ZMQ_PUB_ADDR = "tcp://*:5556"

# Formats of received reports
FORMAT_FLY_REPORT = "3hHhH3hH4i2Bb3BH"  # refer to definition in fly_state_report.h
FORMAT_BATTERY_REPORT = "3HBb4Bi"  # refer to definition in battery_info.h
FORMAT_GIMBAL_REPORT = "3f"  # refer to definition in gimbal.h
FORMAT_NAV_REPORT = "6BHh2i"  # refer to definition in nav_state_report.h
FORMAT_ACK = "=BBI"  # refer to definition in fly_state_report.h