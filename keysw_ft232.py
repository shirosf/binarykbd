#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import time
import os
os.environ["BLINKA_FT232H"]="1"
import board
import digitalio
from copy import deepcopy

logger=logging.getLogger('keysw_ft232')
logger.setLevel(logging.INFO)

class CodeTable(object):
    SPECIAL_KEYS = {'BS':'\b', 'SP':' ', 'VBAR':'|', 'TAB':'\t', 'ESC':'\x1B', 'RET':'\n',
                    'UP':'\x1B[A', 'DOWN':'\x1B[B', 'RIGHT':'\x1B[C', 'LEFT':'\x1B[D'}
    MODLOCK_TIMEOUT = 500000000
    def readconf(self, conffile: str="config.org") -> int:
        inf=open(conffile, "r")
        started=False
        self.keytable=[None]*32
        while True:
            keydef={}
            line=inf.readline()
            if line=='': break
            if line[0]!='|':
                started=False
                continue
            items=line.split('|')
            if len(items)<11: continue
            for i in items[3:]: print("%s\t" % i.strip(), end='')
            print()
            if not started:
                if items[1].strip() == 'dcode':
                    started=True
                continue
            try:
                dcode=int(items[1].strip())
                if dcode<1 or dcode>31: raise ValueError
            except ValueError:
                logger.error("'dcode' item msut be a number in 1 to 31")
                return -1
            if items[4].strip()=='':
                logger.error("'key' item is not defined")
                return -1
            for i,j in enumerate(('key','M1','M2','M3','M4','M5')):
                keydef[j]=items[4+i].strip()
            self.keytable[dcode]=keydef
        inf.close()
        self.modifiers = {'M1':0,'M2':0,'M3':0,'M4':0,'M5':0}
        self.lastmod = ''
        self.modts = 0

    def modstate_print(self) -> None:
        print(' '*80, end='\r')
        for k,v in reversed(self.modifiers.items()):
            print("%s:%d " % (k,v), end='')
        print("", end='\r', flush=True)

    def code2char(self, dcode: int) -> tuple[str, str, dict]:
        if dcode>=32: return ('', '', None)
        keydef=self.keytable[dcode]
        ik=keydef['key']
        if ik not in self.modifiers:
            rm=deepcopy(self.modifiers)
            if not self.lastmod:
                return (ik,'', rm) # regular key without modifier
            mk=keydef[self.lastmod] # modified with the last modifier
            if self.modifiers[self.lastmod]!=2:
                # last modifier is not locked
                for k,v in self.modifiers.items():
                    if v!=2: self.modifiers[k]=0 # clear all unlocked modifiers
                self.lastmod=''
                self.modstate_print()
                return (ik, mk, rm)
            else:
                # last modifier is locked
                return (ik, mk, rm)
        # got a modifier key
        if ik==self.lastmod:
            if self.modifiers[self.lastmod]==1:
                ts=time.time_ns()
                if ts-self.modts < self.MODLOCK_TIMEOUT:
                    logger.debug("modifiere %s=2" % self.lastmod)
                    if self.modifiers[self.lastmod]!=2:
                        self.modifiers[self.lastmod]=2 # only 2 sequencial mofiers make lock
                        self.modstate_print()
                else:
                    logger.debug("modifiere(no lock by timeout) %s=1" % self.lastmod)
                    self.modts=ts
                    if self.modifiers[self.lastmod]!=1:
                        self.modifiers[self.lastmod]=1
                        self.modstate_print()
            else:
                if self.modifiers[self.lastmod]!=0:
                    self.modifiers[self.lastmod]=0
                    logger.debug("modifiere %s=0" % self.lastmod)
                    self.lastmod=''
                    self.modstate_print()
        else:
            if self.modifiers[ik]==2:
                logger.debug("modifiere %s=0" % ik)
                self.modifiers[ik]=0
                self.lastmod=''
                self.modstate_print()
            else:
                logger.debug("modifiere %s=1" % ik)
                self.modts=time.time_ns()
                self.modifiers[ik]=1
                self.lastmod=ik
                self.modstate_print()
        return ('','',None)

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
    KEY_REPEAT_START=int(500E6)//KEY_REPEAT_TIME # 0.5sec
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
