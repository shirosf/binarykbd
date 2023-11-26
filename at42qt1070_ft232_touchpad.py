#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
To use this program, 'pyftdi' and 'blinka' packages must be installed.
The instruction of installation is at the next link,
https://learn.adafruit.com/circuitpython-on-any-computer-with-ft232h/linux

pyftdi needs a patch to deal with delayed Ack/NAck from the device.
(the device pull down SCL until it becomes ready to send Ack/NAck.)
'pyftd_i2c.patch' is in the same directory of this file.
In the patch, 'Wait On I/O High' MPSSE command (0x88) is used
to detect the delayed signal.
For that, 'D5 <-> SCL' connection is needed.
'''
import sys
import time
import select
import logging
import board
from adafruit_bus_device import i2c_device

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger('at42qt1070_ft232_touchpad')
logger.setLevel(logging.INFO)

class AT42QT1070_FT232:
    I2C_ADDRESS=0x1B
    AT42QT1070_CHIPID=0x2E
    def probe_device(self) -> bool:
        self.i2cdev = i2c_device.I2CDevice(board.I2C(), self.I2C_ADDRESS, probe=False)
        result = bytearray(1)
        self.i2cdev.write_then_readinto(bytes([0]), result)
        if result[0]!=self.AT42QT1070_CHIPID:
            logger.error("can't find AT42QT1070")
            return False
        # remove low power mode, and set the shortest 8 msec interval
        self.i2cdev.write(bytes([54, 0]))
        self.i2cdev.write_then_readinto(bytes([54]), result)
        if result[0]!=0:
            logger.error("can't write to AT42QT1070")
            return False
        logger.info("found AT42QT1070, initialization okay")
        return True

    def key_status(self) -> int:
        result = bytearray(1)
        self.i2cdev.write_then_readinto(bytes([3]), result)
        logger.debug("key status=0x%x" % result[0])
        return result[0]

    def key_signal_ref(self, keyno: int) -> tuple[int, int]:
        result = bytearray(1)
        self.i2cdev.write_then_readinto(bytes([4+2*keyno]), result)
        msb=result[0]
        self.i2cdev.write_then_readinto(bytes([5+2*keyno]), result)
        lsb=result[0]
        signal=(msb<<8)|lsb
        self.i2cdev.write_then_readinto(bytes([18+2*keyno]), result)
        msb=result[0]
        self.i2cdev.write_then_readinto(bytes([19+2*keyno]), result)
        lsb=result[0]
        ref=(msb<<8)|lsb
        return (signal, ref)

if __name__ == "__main__":
    tdev=AT42QT1070_FT232()
    if not tdev.probe_device(): sys.exit(1)
    keys=0
    while True:
        for i in range(5):
            data=tdev.key_signal_ref(i)
            print(data)
        print("----- key status=%s" %  "{0:b}".format(tdev.key_status()))
        time.sleep(0.5)
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []): sys.exit(0)
