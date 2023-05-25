#!E:\anaconda/python

import zmq
import datetime
import struct

if __name__ == '__main__':
    with zmq.Context() as context:
        sub = context.socket(zmq.SUB)
        sub.connect("tcp://localhost:5556")
        # sub.setsockopt( zmq.LINGER,     0 )
        sub.setsockopt_string( zmq.SUBSCRIBE, "" )
        # sub.setsockopt( zmq.CONFLATE,   1 )
        while True:

            bin_topic, data = sub.recv().split(b' ', 1)
            topic = bin_topic.decode(encoding='ascii')
            print("topic: '{}'".format(topic))
            d = struct.unpack('4?', data)
            print("data: {}".format(d))

            # print("{1:}:: Py has got this [[[{0:}]]]".format(sub.recv(),
            #                                                    str(datetime.datetime.now())))