from definitions import *

import zmq
from time import sleep


def move3d_square():
    with zmq.Context() as context:
        pub = context.socket(zmq.PUB)
        pub.bind("tcp://*:5556")
        sleep(1)

        # clear mission queue
        clear_mq = ClearMissionQueue()
        pub.send(clear_mq.getPacked())
        sleep(1)

        # takeoff
        takeoff = TakeOff(height=2.0, act_now=False)
        pub.send(takeoff.getPacked())
        sleep(1)

        # move3d 1
        move3d = Movement3D(x=2, y=0, z=0, hs=1, vs=0.5, act_now=False)
        pub.send(move3d.getPacked())
        sleep(1)

        # move3d 2
        move3d = Movement3D(x=0, y=2, z=0, hs=1, vs=0.5, act_now=False)
        pub.send(move3d.getPacked())
        sleep(1)

        # move3d 3
        move3d = Movement3D(x=0, y=2, z=0, hs=1, vs=0.5, act_now=False)
        pub.send(move3d.getPacked())
        sleep(1)

        # move3d 4
        move3d = Movement3D(x=0, y=2, z=0, hs=1, vs=0.5, act_now=False)
        pub.send(move3d.getPacked())
        sleep(1)

        # land
        land = Land(act_now=False)
        pub.send(land.getPacked())
        sleep(1)

        # execute mission queue
        exec_mq = ExecMissionQueue()
        pub.send(exec_mq.getPacked())
        sleep(1)

        print("Sending finished!")
        return


def move3d_single_act():
    with zmq.Context() as context:
        pub = context.socket(zmq.PUB)
        pub.bind("tcp://*:5556")
        sleep(1)

        # takeoff
        takeoff = TakeOff(height=2.0, act_now=True)
        pub.send(takeoff.getPacked())
        print("Takeoff sent!")
        sleep(10)

        # move3d 1
        move3d = Movement3D(x=3, y=0, z=0, hs=1, vs=1, act_now=True)
        pub.send(move3d.getPacked())
        print("Move3d sent!")
        sleep(10)

        # land
        land = Land(act_now=True)
        pub.send(land.getPacked())
        print("Land sent!")
        sleep(1)


if __name__ == "__main__":
    # move3d_square()

    move3d_single_act()

