from definitions import *

import zmq
from time import sleep


FORMAT_FLY_REPORT = "3hHhH3hH4i2Bb3BH"  # refer to definition in fly_state_report.h


fly_report = FlyReport()


def update_report(sub):
    try:
        binary_topic, data_buffer = sub.recv(zmq.DONTWAIT).split(b' ', 1)
        topic = binary_topic.decode(encoding='ascii')
        if topic == TOPIC_FLY_REPORT:
            # print(f"{topic=}")
            report_tuple = struct.unpack(FORMAT_FLY_REPORT, data_buffer)
            # print(f"{report_tuple=}")
            fly_report.update(report_tuple)
        else:
            print("Topic name mismatched!")
    except zmq.ZMQError as e:
        if e.errno == zmq.EAGAIN:
            pass  # no message was ready (yet!)
        else:
            print(str(e))
    return fly_report.updated


def report2wp(sub):
    while not update_report(sub):
        print("Waiting for fly report ...")

    print(f"GPS#: {fly_report.GpsNum}, VDOP: {fly_report.VDOP}")
    if fly_report.GpsNum < 9:
        return None

    wp = WayPointWithYaw(fly_report.Lat / 1e7, fly_report.Lon / 1e7, fly_report.ATTYaw)
    # print(wp)
    fly_report.updated = False
    return wp


def left_right():
    with zmq.Context() as context:
        # create publisher
        pub = context.socket(zmq.PUB)
        pub.bind("tcp://*:5556")
        print("Publisher created!")
        sleep(1)

        # create subscriber
        sub = context.socket(zmq.SUB)
        sub.setsockopt(zmq.SUBSCRIBE, TOPIC_FLY_REPORT.encode('ascii'))
        sub.setsockopt(zmq.LINGER, 0)
        # sub.setsockopt(zmq.CONFLATE, 1)
        sub.connect("tcp://localhost:5555")
        print("Subscriber connected!")
        sleep(1)

        # clear mission queue
        clear_mq = ClearMissionQueue()
        pub.send(clear_mq.getPacked())
        sleep(1)

        # takeoff
        takeoff = TakeOff(height=1.0, act_now=False)
        pub.send(takeoff.getPacked())
        sleep(1)

        # set speed
        set_speed = SetSpeed(speed=1, act_now=False)
        pub.send(set_speed.getPacked())
        sleep(1)

        # set altitude
        set_alt = SetAlt(alt=3, act_now=False)
        pub.send(set_alt.getPacked())
        sleep(1)

        # hover for some time
        suspend_mq = SuspendMissionQueue(wait_time_s=5)
        pub.send(suspend_mq.getPacked())
        sleep(1)

        # add forward waypoint
        lly = report2wp(sub)  # blocking
        while not lly:
            sleep(0.5)
            lly = report2wp(sub)
        wp = WayPoint.from_cartesian(lly, x=0, y=3, hover_time=5, act_now=False)
        pub.send(wp.getPacked())
        sleep(1)

        # add backward waypoint
        wp = WayPoint.from_cartesian(lly, x=0, y=0, hover_time=5, act_now=False)
        pub.send(wp.getPacked())
        sleep(1)

        wp = WayPoint.from_cartesian(lly, x=0, y=-3, hover_time=5, act_now=False)
        pub.send(wp.getPacked())
        sleep(1)

        wp = WayPoint.from_cartesian(lly, x=0, y=0, hover_time=5, act_now=False)
        pub.send(wp.getPacked())
        sleep(1)

        # land
        land = Land(act_now=False)
        pub.send(land.getPacked())
        sleep(1)

        # execute mission queue
        exec_mq = ExecMissionQueue()
        pub.send(exec_mq.getPacked())
        sleep(1)

        print("Forward-backward sending finished!")
        return

def forward_backward():
    with zmq.Context() as context:
        # create publisher
        pub = context.socket(zmq.PUB)
        pub.bind("tcp://*:5556")
        print("Publisher created!")
        sleep(1)

        # create subscriber
        sub = context.socket(zmq.SUB)
        sub.setsockopt(zmq.SUBSCRIBE, TOPIC_FLY_REPORT.encode('ascii'))
        sub.setsockopt(zmq.LINGER, 0)
        # sub.setsockopt(zmq.CONFLATE, 1)
        sub.connect("tcp://localhost:5555")
        print("Subscriber connected!")
        sleep(1)

        # clear mission queue
        clear_mq = ClearMissionQueue()
        pub.send(clear_mq.getPacked())
        sleep(1)

        # takeoff
        takeoff = TakeOff(height=1.0, act_now=False)
        pub.send(takeoff.getPacked())
        sleep(1)

        # set speed
        set_speed = SetSpeed(speed=0.5, act_now=False)
        pub.send(set_speed.getPacked())
        sleep(1)

        # set altitude
        set_alt = SetAlt(alt=2, act_now=False)
        pub.send(set_alt.getPacked())
        sleep(1)

        # hover for some time
        suspend_mq = SuspendMissionQueue(wait_time_s=5)
        pub.send(suspend_mq.getPacked())
        sleep(1)

        # add forward waypoint
        lly = report2wp(sub)  # blocking
        while not lly:
            sleep(0.5)
            lly = report2wp(sub)
        wp = WayPoint.from_cartesian(lly, x=3, y=0, hover_time=10, act_now=False)
        pub.send(wp.getPacked())
        sleep(1)

        # add backward waypoint
        wp = WayPoint.from_cartesian(lly, x=0, y=0, hover_time=10, act_now=False)
        pub.send(wp.getPacked())
        sleep(1)

        wp = WayPoint.from_cartesian(lly, x=-3, y=0, hover_time=10, act_now=False)
        pub.send(wp.getPacked())
        sleep(1)

        wp = WayPoint.from_cartesian(lly, x=0, y=0, hover_time=15, act_now=False)
        pub.send(wp.getPacked())
        sleep(1)

        # land
        land = Land(act_now=False)
        pub.send(land.getPacked())
        sleep(1)

        # execute mission queue
        exec_mq = ExecMissionQueue()
        pub.send(exec_mq.getPacked())
        sleep(1)

        print("Forward-backward sending finished!")
        return

def wp_square():
    with zmq.Context() as context:
        # create publisher
        pub = context.socket(zmq.PUB)
        pub.bind("tcp://*:5556")
        print("Publisher created!")
        sleep(1)

        # create subscriber
        sub = context.socket(zmq.SUB)
        sub.setsockopt(zmq.SUBSCRIBE, TOPIC_FLY_REPORT.encode('ascii'))
        sub.setsockopt(zmq.LINGER, 0)
        # sub.setsockopt(zmq.CONFLATE, 1)
        sub.connect("tcp://localhost:5555")
        print("Subscriber connected!")
        sleep(1)

        # clear mission queue
        clear_mq = ClearMissionQueue()
        pub.send(clear_mq.getPacked())
        sleep(1)

        # takeoff
        takeoff = TakeOff(height=1.0, act_now=False)
        pub.send(takeoff.getPacked())
        sleep(1)

        # set speed
        set_speed = SetSpeed(speed=1, act_now=False)
        pub.send(set_speed.getPacked())
        sleep(1)

        # set altitude
        set_alt = SetAlt(alt=3, act_now=False)
        pub.send(set_alt.getPacked())
        sleep(1)

        # hover for some time
        suspend_mq = SuspendMissionQueue(wait_time_s=5)
        pub.send(suspend_mq.getPacked())
        sleep(1)

        # get initial lat, lon and yaw of drone
        lly = report2wp(sub)  # blocking
        while not lly:
            sleep(0.5)
            lly = report2wp(sub)

        # add waypoint 1
        wp = WayPoint.from_cartesian(lly, x=0, y=-3, hover_time=5, act_now=False)
        pub.send(wp.getPacked())
        sleep(1)

        # add waypoint 2
        wp = WayPoint.from_cartesian(lly, x=6, y=-3, hover_time=5, act_now=False)
        pub.send(wp.getPacked())
        sleep(1)

        # add waypoint 3
        wp = WayPoint.from_cartesian(lly, x=6, y=3, hover_time=5, act_now=False)
        pub.send(wp.getPacked())
        sleep(1)

        # add waypoint 4
        wp = WayPoint.from_cartesian(lly, x=0, y=3, hover_time=5, act_now=False)
        pub.send(wp.getPacked())
        sleep(1)

        wp = WayPoint.from_cartesian(lly, x=0, y=0, hover_time=5, act_now=False)
        pub.send(wp.getPacked())
        sleep(1)

        # land
        land = Land(act_now=False)
        pub.send(land.getPacked())
        sleep(1)

        # execute mission queue
        exec_mq = ExecMissionQueue()
        pub.send(exec_mq.getPacked())
        sleep(1)

        print("Square sending finished!")
        return


if __name__ == "__main__":
    # wp_square()

    forward_backward()

    # left_right()


