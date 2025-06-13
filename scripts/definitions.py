import struct
import ctypes
import utm
import math
from loguru import logger

# topics to subscribe to
TOPIC_FLY_REPORT = "topic_fly_report"
TOPIC_BATTERY_REPORT = "topic_battery_report"
TOPIC_GIMBAL_REPORT = "topic_gimbal_report"
TOPIC_NAV_REPORT = "topic_nav_report"
TOPIC_ACK = "topic_ack"

# topics to publish to
TOPIC_EXT_DEV = "topic_external_device"
TOPIC_CAMERA_CONTROL = "topic_camera_control"
TOPIC_TAKEOFF = "topic_takeoff"
TOPIC_LAND = "topic_land"
TOPIC_RETURN_TO_HOME = "topic_rth"
TOPIC_GIMBAL_CONTROL = "topic_gimbal_control"
TOPIC_MOVEMENT_3D = "topic_move_3d"
TOPIC_WAYPOINT = "topic_waypoint"

# topics related to mission queue
TOPIC_SET_SPEED = "topic_set_speed"
TOPIC_SET_ALT = "topic_set_alt"
TOPIC_CLEAR_MISSION_QUEUE = "topic_clear_mq"
TOPIC_SEND_START = "topic_send_start"
TOPIC_SEND_END = "topic_send_end"
TOPIC_EXEC_MISSION = "topic_exec_mission"
TOPIC_STOP_MISSION = "topic_stop_mission"
TOPIC_SUSPEND_MISSION = "topic_suspend_mission"
TOPIC_REPLAY_MISSION = "topic_replay_mission"


def deg2rad(deg):
    return deg / 180.0 * math.pi


def rad2deg(rad):
    return rad / math.pi * 180.0


# normalize angle in rad to (-pi, pi]
def normalize(rad):
    while rad > math.pi:
        rad -= 2 * math.pi
    while rad <= -math.pi:
        rad += 2 * math.pi
    return rad


class FlyReport:
    def __init__(self, report_tuple: tuple = ()):
        if len(report_tuple) == 0:
            logger.debug("Empty fly report tuple!")
            self.updated = False
        else:
            assert len(report_tuple) == 21, "Fly report tuple wrong size!"
            self.update(report_tuple)

    def update(self, report_tuple: tuple):
        self.ATTPitch = report_tuple[0] * 0.1  # Pitch angle, unit: degree
        self.ATTRoll = report_tuple[1] * 0.1  # Roll angle, unit: degree
        self.ATTYaw = -report_tuple[2] * 0.1  # Yaw angle (-180, 180], unit: degree, 0 degree points to the north
        self.FlySpeed = report_tuple[3] * 0.1  # Horizontal speed, unit: m/s
        self.Altitude = report_tuple[4] * 0.1  # Altitude, unit: m
        self.Distance = report_tuple[5]  # Distance, unit: m
        self.Voltage = report_tuple[6] * 0.1  # Voltage, unit: v
        self.GpsHead = report_tuple[7] * 0.1  # GPS Course, in degree
        self.HomeHead = report_tuple[8] * 0.1  # Home Course, in degree
        self.FlyTime_Sec = report_tuple[9]  # unit: 1 sec
        self.Lon, self.Lat = report_tuple[10], report_tuple[11]  # the lag\lng of aircraft
        self.hLat, self.hLon = report_tuple[12], report_tuple[13]  # the lag\lng of home point (take off point)
        self.FrameType = report_tuple[14]  # Frame type   0:quad-rotor   1:boat   2:fixed wing
        self.InGas = report_tuple[15]  # Motor throttle %0-100
        self.VSpeed = report_tuple[16] * 0.1  # Vertical speed unit: m/s
        self.VDOP = report_tuple[17]  # Positioning accuracy
        self.GpsNum = report_tuple[18]  # Number of GPS satellites being received
        self.reserve1 = report_tuple[19]
        self.data = report_tuple[20]  # SysState1

        self.updated = True


class NavReport:
    def __init__(self, report_tuple: tuple = ()):
        if len(report_tuple) == 0:
            logger.debug("Empty fly report tuple!")
            self.updated = False
        else:
            assert len(report_tuple) == 21, "Fly report tuple wrong size!"
            self.update(report_tuple)

    def update(self, report_tuple: tuple):
        self.nav_state = report_tuple[0]  # Navigation state
        self.wp_num = report_tuple[1]  # Index of the currently executing waypoint
        self.delay_time_sec = report_tuple[2]  # Waiting countdown time
        self.wp_max_num = report_tuple[3]  # Maximum waypoints number
        self.turning_rate = report_tuple[4]  # deg/s
        self.max_fly_speed = report_tuple[5]  # Maximum fly speed, m/s
        self.end_dist = report_tuple[6]  # Distance to ending waypoint, m
        self.route_deviation = report_tuple[7]  # Route deviation from expected course, m
        self.lat, self.lon = report_tuple[8], report_tuple[9]  # Latitude and Longitude of current target waypoint

        self.updated = True


class BatteryReport:
    def __init__(self, report_tuple: tuple = ()):
        if len(report_tuple) == 0:
            logger.debug("Empty battery report tuple!")
            self.updated = False
        else:
            assert len(report_tuple) == 10, "Battery report tuple wrong size!"
            self.update(report_tuple)

    def update(self, report_tuple: tuple):
        self.Voltage = report_tuple[0] / 1000  # Battery Voltage(V)
        self.Capacity = report_tuple[1]  # Battery Capacity(mah)
        self.RemainCap = report_tuple[2]  # Remaining Battery Capacity(mah)
        self.Percent = report_tuple[3]  # Remaining Battery Percentage
        self.temperature = report_tuple[4]  # Battery Temperature(degree Celcius)
        self.RemainHoverTime = report_tuple[5]  # Remaining Hover Time(Minutes)
        self.eCurrent = report_tuple[9]  # Battery Current(mA)

        self.updated = True


class GimbalReport:
    def __init__(self, report_tuple: tuple = ()):
        if len(report_tuple) == 0:
            logger.debug("Empty gimbal report tuple!")
            self.updated = False
        else:
            assert len(report_tuple) == 3, "Battery report tuple wrong size!"
            self.update(report_tuple)

    def update(self, report_tuple: tuple):
        self.roll = report_tuple[0]
        self.pitch = report_tuple[1]
        self.yaw = report_tuple[2]

        self.updated = True


class Ack:
    def __init__(self, ack_tuple: tuple = ()):
        if len(ack_tuple) == 0:
            logger.debug("Empty ACK tuple!")
            self.updated = False
        else:
            assert len(ack_tuple) == 3, "Ack tuple wrong size!"
            self.update(ack_tuple)

    def update(self, ack_tuple: tuple):
        self.mission_id = ack_tuple[0]
        self.mission_type = ack_tuple[1]
        self.mission_data = ack_tuple[2]

        self.updated = True


class Base:
    def __init__(self, act_now: bool = False):
        self.act_now = act_now


class ExtDevOnOff(Base):
    def __init__(self, plr1: bool = False, plr2: bool = False,
                 strobe_light: bool = True, arm_light: bool = True,
                 act_now: bool = True):
        super().__init__(act_now)
        self.plr1 = plr1
        self.plr2 = plr2
        self.strobe_light = strobe_light
        self.arm_light = arm_light
        self.topic = TOPIC_EXT_DEV

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1 + 5)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        struct.pack_into('?', buffer, topic_len + 1, self.plr1)
        struct.pack_into('?', buffer, topic_len + 2, self.plr2)
        struct.pack_into('?', buffer, topic_len + 3, self.strobe_light)
        struct.pack_into('?', buffer, topic_len + 4, self.arm_light)
        struct.pack_into('?', buffer, topic_len + 5, self.act_now)

        # struct.pack_into('4?', buffer, topic_len + 1, self.plr1, self.plr2, self.strobe_light, self.arm_light)

        # struct.pack_into('4h', buffer, topic_len + 1,
        #                  int(self.plr1), int(self.plr2), int(self.strobe_light), int(self.arm_light))

        # buf_str = str(buffer.value).encode('ascii')
        buf_str = buffer.raw
        logger.debug(f'[ExtDevOnOff] Buf size: {len(buffer)}, content: {buf_str}')
        # un = struct.unpack('22s4?', buffer)
        # print(f'unpacked {un}')
        return buf_str


class CameraControl(Base):
    def __init__(self, take_photo: bool = False, record: bool = False, act_now: bool = True):
        super().__init__(act_now)
        self.take_photo = take_photo
        self.record = record
        self.act_now = act_now
        self.topic = TOPIC_CAMERA_CONTROL

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1 + 3)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0, self.topic.encode('ascii'))
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))
        struct.pack_into('?', buffer, topic_len + 1, self.take_photo)
        struct.pack_into('?', buffer, topic_len + 2, self.record)
        struct.pack_into('?', buffer, topic_len + 3, self.act_now)
        buf_str = buffer.raw
        logger.debug(f'[Camera Control] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class TakeOff(Base):
    def __init__(self, height: float = 0.4, act_now: bool = True):
        super().__init__(act_now)
        self.height = height
        self.topic = TOPIC_TAKEOFF
        self.act_now = act_now

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1 + 5)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        struct.pack_into('f', buffer, topic_len + 1, self.height)
        struct.pack_into('?', buffer, topic_len + 5, self.act_now)
        buf_str = buffer.raw
        logger.debug(f'[TakeOff] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class SetSpeed(Base):
    def __init__(self, speed: float = 3., act_now: bool = False):
        super().__init__(act_now)
        self.speed = speed
        self.topic = TOPIC_SET_SPEED

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1 + 5)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        struct.pack_into('f', buffer, topic_len + 1, self.speed)
        struct.pack_into('?', buffer, topic_len + 5, self.act_now)
        buf_str = buffer.raw
        logger.debug(f'[Set Speed] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class SetAlt(Base):
    def __init__(self, alt: float = 5, act_now: bool = False):
        super().__init__(act_now)
        self.alt = alt
        self.topic = TOPIC_SET_ALT

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1 + 5)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        struct.pack_into('f', buffer, topic_len + 1, self.alt)
        struct.pack_into('?', buffer, topic_len + 5, self.act_now)
        buf_str = buffer.raw
        logger.debug(f'[Set Altitude] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class Land(Base):
    def __init__(self, act_now: bool = True):
        super().__init__(act_now)
        self.topic = TOPIC_LAND

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 2)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        struct.pack_into('?', buffer, topic_len + 1, self.act_now)
        buf_str = buffer.raw
        logger.debug(f'[Land] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class ReturnToHome(Base):
    def __init__(self, act_now: bool = True):
        super().__init__(act_now)
        self.topic = TOPIC_RETURN_TO_HOME

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 2)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        struct.pack_into('?', buffer, topic_len + 1, self.act_now)
        buf_str = buffer.raw
        logger.debug(f'[RTH] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class Movement3D(Base):
    def __init__(self, x: float, y: float, z: float, hs: float, vs: float, act_now: bool = False):
        super().__init__(act_now)
        self.x, self.y, self.z = x, y, z  # relative distance in meter
        self.hs, self.vs = hs, vs  # horizontal and vertical speeds in m/s
        self.topic = TOPIC_MOVEMENT_3D

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1 + 21)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        struct.pack_into('f', buffer, topic_len + 1, self.x)
        struct.pack_into('f', buffer, topic_len + 1 + 4, self.y)
        struct.pack_into('f', buffer, topic_len + 1 + 8, self.z)
        struct.pack_into('f', buffer, topic_len + 1 + 12, self.hs)
        struct.pack_into('f', buffer, topic_len + 1 + 16, self.vs)
        struct.pack_into('?', buffer, topic_len + 1 + 20, self.act_now)
        buf_str = buffer.raw
        logger.debug(f'[Movement3D] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class WayPointBase:
    def __init__(self, lat: float, lon: float):
        self.lat, self.lon = lat, lon


class WayPointWithYaw(WayPointBase):
    def __init__(self, lat: float, lon: float, yaw: float):
        WayPointBase.__init__(self, lat, lon)
        self.yaw = yaw  # in degree


class WayPoint(Base, WayPointBase):
    def __init__(self, lat: float, lon: float, hover_time: int = 5, act_now: bool = False):
        Base.__init__(self, act_now)
        WayPointBase.__init__(self, lat, lon)
        self.ht = hover_time  # in second
        self.topic = TOPIC_WAYPOINT

    @classmethod
    def from_cartesian(cls, lly: WayPointWithYaw, x: float, y: float,
                       hover_time: int, act_now: bool = False):
        easting_ori, northing_ori, zone_number, zone_letter = utm.from_latlon(latitude=lly.lat, longitude=lly.lon)
        dist = math.sqrt(x ** 2 + y ** 2)
        rela_angle = math.atan2(y, x)  # rad
        easting_target = easting_ori + dist * math.cos(deg2rad(lly.yaw + 90) + rela_angle)
        northing_target = northing_ori + dist * math.sin(deg2rad(lly.yaw + 90) + rela_angle)
        lat_target, lon_target = utm.to_latlon(easting_target, northing_target, zone_number, zone_letter)
        return cls(lat_target, lon_target, hover_time, act_now)

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1 + 11)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        struct.pack_into('f', buffer, topic_len + 1, self.lat)
        struct.pack_into('f', buffer, topic_len + 1 + 4, self.lon)
        struct.pack_into('H', buffer, topic_len + 1 + 8, self.ht)
        struct.pack_into('?', buffer, topic_len + 1 + 10, self.act_now)
        buf_str = buffer.raw
        logger.debug(f'[Waypoint] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class GimbalControl(Base):
    def __init__(self, roll=0, pitch=0, yaw=0, act_now: bool = True):
        super().__init__(act_now)
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw
        self.topic = TOPIC_GIMBAL_CONTROL

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1 + 7)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        struct.pack_into('h', buffer, topic_len + 1, self.roll)
        struct.pack_into('h', buffer, topic_len + 1 + 2, self.pitch)
        struct.pack_into('h', buffer, topic_len + 1 + 4, self.yaw)
        struct.pack_into('?', buffer, topic_len + 1 + 6, self.act_now)
        buf_str = buffer.raw
        logger.debug(f'[GimbalControl] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class ClearMissionQueue:
    def __init__(self):
        self.topic = TOPIC_CLEAR_MISSION_QUEUE

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        buf_str = buffer.raw
        logger.debug(f'[Clear mq] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class SendMissionQueueStart:
    def __init__(self):
        self.topic = TOPIC_SEND_START

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        buf_str = buffer.raw
        logger.debug(f'[Start send to mq] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class SendMissionQueueEnd:
    def __init__(self):
        self.topic = TOPIC_SEND_END

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        buf_str = buffer.raw
        logger.debug(f'[End send to mq] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class ExecMissionQueue:
    def __init__(self):
        self.topic = TOPIC_EXEC_MISSION

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        buf_str = buffer.raw
        logger.debug(f'[Exec mq] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class StopMissionQueue:
    def __init__(self):
        self.topic = TOPIC_STOP_MISSION

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        buf_str = buffer.raw
        logger.debug(f'[Stop mq] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class SuspendMissionQueue:
    def __init__(self, wait_time_s: float):
        self.wait_time_s = wait_time_s
        self.topic = TOPIC_SUSPEND_MISSION

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1 + 4)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        struct.pack_into('f', buffer, topic_len + 1, self.wait_time_s)
        buf_str = buffer.raw
        logger.debug(f'[Suspend mq] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str


class ReplayMissionQueue:
    def __init__(self, repeat_time):
        self.rt = repeat_time
        self.topic = TOPIC_REPLAY_MISSION

    def getPacked(self):
        topic_len = len(self.topic)
        buffer = ctypes.create_string_buffer(topic_len + 1 + 2)
        struct.pack_into('{:d}s'.format(topic_len), buffer, 0,
                         self.topic.encode('ascii'))  # pack topic string into buffer
        struct.pack_into('c', buffer, topic_len, ' '.encode('ascii'))  # pack empty space after topic
        struct.pack_into('H', buffer, topic_len + 1, self.rt)
        buf_str = buffer.raw
        logger.debug(f'[Replay mq] Buf size: {len(buffer)}, content: {buf_str}')
        return buf_str

