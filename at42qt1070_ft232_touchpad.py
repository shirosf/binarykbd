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
import os
import time
import select
import logging
os.environ["BLINKA_FT232H"]="1"
import board
from adafruit_bus_device import i2c_device
from keysw_ft232 import InputBase_FT232

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger('at42qt1070_ft232_touchpad')
logger.setLevel(logging.INFO)
logging.getLogger('pyftdi.i2c').setLevel(logging.ERROR)

class AT42QT1070_FT232(InputBase_FT232):
    KEY_VALID_MIN=int(80E6) # 80msec
    KEY_INVALID_MIN=int(80E6) # 80msec
    I2C_ADDRESS=0x1B
    AT42QT1070_CHIPID=0x2E
    def probe_device(self) -> bool:
        self.i2cdev = i2c_device.I2CDevice(board.I2C(), self.I2C_ADDRESS, probe=False)
        result = bytearray(1)
        self.i2cdev.write_then_readinto(bytes([0]), result)
        if result[0]!=self.AT42QT1070_CHIPID:
            logger.error("can't find AT42QT1070")
            return False

        if not self.__calibrate(): return False
        # remove low power mode, and set the shortest 8 msec interval
        self.i2cdev.write(bytes([54, 0]))
        self.i2cdev.write_then_readinto(bytes([54]), result)
        if result[0]!=0:
            logger.error("can't write to AT42QT1070")
            return False
        self.i2cdev.write(bytes([53, 0xf])) # no GUARD CHANNEL
        for i in range(5):
            self.i2cdev.write(bytes([39+i, (16<<2)|0])) # AVE=8, ADK=0 for all keys
            self.i2cdev.write(bytes([32+i, 100])) # Negative Threashold 30
        self.i2cdev.write(bytes([39+5, 0])) # disable key5
        self.i2cdev.write(bytes([39+6, 0])) # disable key6

        logger.info("found AT42QT1070, initialization okay")
        self.scan_ts=time.time_ns()
        return True

    def __calibrate(self) -> bool:
        result = bytearray(1)
        self.i2cdev.write(bytes([57, 1])) # start calibration
        for i in range(10):
            try:
                self.i2cdev.write_then_readinto(bytes([2]), result)
                if (result[0]&0x80)==0: break
            except:
                logger.info("no response after calibrate, wait more time")
            time.sleep(10e-3)
        else:
            logger.error("can't calibrate")
            return False
        return True

    def key_status(self) -> int:
        result = bytearray(1)
        self.i2cdev.write_then_readinto(bytes([3]), result)
        logger.debug("key status=0x%x" % result[0])
        return result[0]

    def __key_signal_ref(self, keyno: int) -> tuple[int, int]:
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
    nkeys=0
    while True:
        pkey,change=tdev.scan_key()
        if change:
            print("{0:b}".format(pkey))
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []): break

    sys.exit(0)
