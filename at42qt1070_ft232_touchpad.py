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

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger('at42qt1070_ft232_touchpad')
logger.setLevel(logging.INFO)
logging.getLogger('pyftdi.i2c').setLevel(logging.ERROR)

class AT42QT1070_FT232:
    I2C_ADDRESS=0x1B
    AT42QT1070_CHIPID=0x2E
    ZERO_NONZERO_THRESHOLD=int(4E6) # 4msec
    ZERO_NONZERO_HYSTERISIS=int(2E6) # 2msec
    KEY_REPEAT_TIME=int(50E6) # 50msec
    KEY_REPEAT_START=int(1E9)//KEY_REPEAT_TIME # 1sec
    def probe_device(self) -> bool:
        self.i2cdev = i2c_device.I2CDevice(board.I2C(), self.I2C_ADDRESS, probe=False)
        result = bytearray(1)
        self.i2cdev.write_then_readinto(bytes([0]), result)
        if result[0]!=self.AT42QT1070_CHIPID:
            logger.error("can't find AT42QT1070")
            return False

        if not self.calibrate(): return False
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
        self.last_keys=0
        self.zero_ts=0
        self.nonzero_ts=0
        self.nonzero_keys=0
        self.keys_maxbitn=0
        self.keys_maxbits=0
        self.state_zero=True
        return True

    def calibrate(self) -> bool:
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

    def update_maxbits(self) -> bool:
        n=0
        for i in range(5):
            if self.last_keys & (1<<i): n+=1
        if n>self.keys_maxbitn:
            self.keys_maxbitn=n
            self.keys_maxbits=self.last_keys
            return True
        return False

    def update_state_zero(self, dts: int) -> bool:
        if self.last_keys==0:
            self.zero_ts+=dts
            self.nonzero_ts=0
        else:
            self.zero_ts=0
            self.nonzero_ts+=dts
        if not self.state_zero:
           if self.zero_ts > (self.ZERO_NONZERO_THRESHOLD+self.ZERO_NONZERO_HYSTERISIS):
               self.state_zero=True
               return True
        else:
           if self.nonzero_ts > (self.ZERO_NONZERO_THRESHOLD+self.ZERO_NONZERO_HYSTERISIS):
               self.state_zero=False
               return True
        return False

    def scan_key(self) -> tuple[bool,bool]:
        ts=time.time_ns()
        # dts is around 16-18 msec
        dts=ts-self.scan_ts
        self.scan_ts=ts
        keys=self.key_status()
        if keys!=self.last_keys:
            #print("{0:b}".format(keys))
            self.last_keys=keys
        uz=self.update_state_zero(dts)
        if not self.state_zero:
            self.update_maxbits()
        if not uz and not self.state_zero:
            # holding down state
            rt=self.nonzero_ts // self.KEY_REPEAT_TIME
            if rt>self.KEY_REPEAT_START:
                if self.nonzero_ts-dts < rt*self.KEY_REPEAT_TIME:
                    return (True,True)
        if uz and self.state_zero:
            # get a new key code
            self.keys_maxbitn=0
            return (True,False)
        return (False,False)

if __name__ == "__main__":
    tdev=AT42QT1070_FT232()
    if not tdev.probe_device(): sys.exit(1)
    keys=0
    nkeys=0
    while True:
        if tdev.scan_key()[0]:
            print("{0:b}".format(tdev.keys_maxbits))
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []): break

    sys.exit(0)
