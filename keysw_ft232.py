#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import os
os.environ["BLINKA_FT232H"]="1"
import board
import digitalio

class InputBase_FT232(object):
    SCAN_KEY_MIN_INTERVAL=int(12E6) # 12msec
    def __init__(self):
        self.scan_ts=0
        self.last_keys=0
        self.zero_ts=0
        self.nonzero_ts=0
        self.keys_maxbitn=0
        self.keys_maxbits=0
        self.state_zero=True
        super().__init__()

    def __update_maxbits(self) -> bool:
        n=0
        for i in range(5):
            if self.last_keys & (1<<i): n+=1
        if n>self.keys_maxbitn:
            self.keys_maxbitn=n
            self.keys_maxbits=self.last_keys
            return True
        return False

    def __update_state_zero(self, dts: int) -> bool:
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
        if dts<self.SCAN_KEY_MIN_INTERVAL:
                time.sleep((self.SCAN_KEY_MIN_INTERVAL-dts)/1E9)
        self.scan_ts=ts
        keys=self.key_status()
        if keys!=self.last_keys:
            #print("{0:b}".format(keys))
            self.last_keys=keys
        uz=self.__update_state_zero(dts)
        if not self.state_zero:
            self.__update_maxbits()
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


class KeySw_FT232(InputBase_FT232):
    ZERO_NONZERO_THRESHOLD=int(4E6) # 4msec
    ZERO_NONZERO_HYSTERISIS=int(2E6) # 2msec
    KEY_REPEAT_TIME=int(50E6) # 50msec
    KEY_REPEAT_START=int(1E9)//KEY_REPEAT_TIME # 1sec
    def probe_device(self) -> bool:
        self.keys=[None]*5
        self.keys[0]=digitalio.DigitalInOut(board.C0)
        self.keys[1]=digitalio.DigitalInOut(board.C1)
        self.keys[2]=digitalio.DigitalInOut(board.C2)
        self.keys[3]=digitalio.DigitalInOut(board.C3)
        self.keys[4]=digitalio.DigitalInOut(board.C4)
        self.groundkey=digitalio.DigitalInOut(board.C5)
        self.groundkey.direction=digitalio.Direction.OUTPUT
        self.groundkey.value=False
        for i in range(5):
            self.keys[i].direction=digitalio.Direction.INPUT
        self.scan_ts=time.time_ns()
        return True

    def key_status(self) -> int:
        result=0
        for i in range(5):
            result|=(1<<i) if not self.keys[i].value else 0
        return result
