from Definitions import *

import zmq
from time import sleep


def led_onoff():
    with zmq.Context() as context:
        pub = context.socket(zmq.PUB)
        pub.bind("tcp://*:5556")
        sleep(1)

        # clear mission queue
        clear_mq = ClearMissionQueue()
        pub.send(clear_mq.getPacked())
        sleep(1)

        # start sending to mission queue
        # start_mq = SendMissionQueueStart()
        # pub.send(start_mq.getPacked())
        # sleep(1)

        # execute mission queue
        # exec_mq = ExecMissionQueue()
        # pub.send(exec_mq.getPacked())
        # sleep(1)

        # turn on all LEDs
        ext_dev_onoff = ExtDevOnOff(strobe_light=True, arm_light=True, act_now=False)
        pub.send(ext_dev_onoff.getPacked())
        sleep(1)

        # suspend mission queue for a while to see change
        suspend_mq = SuspendMissionQueue(wait_time_s=5)
        pub.send(suspend_mq.getPacked())
        sleep(1)

        # turn off all LEDs
        ext_dev_onoff = ExtDevOnOff(strobe_light=False, arm_light=False, act_now=False)
        pub.send(ext_dev_onoff.getPacked())
        sleep(1)

        # suspend mission queue for a while to see change
        suspend_mq = SuspendMissionQueue(wait_time_s=5)
        pub.send(suspend_mq.getPacked())
        sleep(1)

        # turn on all LEDs
        # ext_dev_onoff = ExtDevOnOff(strobe_light=True, arm_light=True)
        # pub.send(ext_dev_onoff.getPacked())
        # sleep(1)

        # end sending to mission queue
        # end_mq = SendMissionQueueEnd()
        # pub.send(end_mq.getPacked())
        # sleep(1)

        # repeat mission queue
        repeat_mq = ReplayMissionQueue(2)
        pub.send(repeat_mq.getPacked())
        sleep(1)

        # execute mission queue
        exec_mq = ExecMissionQueue()
        pub.send(exec_mq.getPacked())
        sleep(1)

        print("Sending finished!")
        sleep(2)
        return


if __name__ == "__main__":
    led_onoff()
