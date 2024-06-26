#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 Shiro Ninomiya
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see
# <https://www.gnu.org/licenses/old-licenses/gpl-2.0.html>.
#
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
    MODLOCK_TIMEOUT = 500000000
    RESET_MODIFIERS = {'M1':0,'M2':0,'M3':0,'M4':0,'M5':0}
    def readconf(self, conffile: str="config.org") -> int:
        inf=open(conffile, "r")
        started=False
        self.keytables={'A':[None]*32, 'B':[None]*32}
        while True:
            keydef={}
            line=inf.readline()
            if line=='': break
            if not started:
                if line.find('code table')>0:
                    self.csel=line.strip()[-1]
                    if self.csel=='A' or self.csel=='B':
                        started=True
                continue
            if line[0]!='|':
                started=False
                continue
            items=line.split('|')
            if len(items)<11: continue
            try:
                item1=items[1].strip()
                if item1=='dcode': continue
                dcode=int(item1)
                if dcode<1 or dcode>31: raise ValueError
            except ValueError:
                logger.error("'dcode' item msut be a number in 1 to 31")
                return -1
            if items[4].strip()=='':
                logger.error("'key' item is not defined")
                return -1
            for i,j in enumerate(('key','M1','M2','M3','M4','M5')):
                keydef[j]=items[4+i].strip()
            self.keytables[self.csel][dcode]=keydef
        inf.close()
        self.modifiers = deepcopy(self.RESET_MODIFIERS)
        self.lastmod = ''
        self.modts = 0
        self.csel='A'
        self.printconf()
        return 0

    def printconf(self):
        for i,keydef in enumerate(self.keytables[self.csel]):
            if i==0:
                print("bcode\t", end='')
            else:
                print("%s\t" % bin(i+32)[3:], end='')
            for n in ('key','M1','M2','M3','M4','M5'):
                if i==0:
                    print("%s\t" % n, end='')
                else:
                    print("%s\t" % keydef[n], end='')
            print()

    def modstate_print(self) -> None:
        print(' '*56, end='\r')
        print("[%s] " % self.csel, end='')
        for k,v in reversed(self.modifiers.items()):
            print("%s:%d " % (k,v), end='')
        print("", end='\r', flush=True)

    def switch_config(self) -> None:
        if self.csel=='B':
            self.csel='A'
        else:
            if self.keytables[self.csel][1]:
                self.csel='B'
        self.printconf()

    def code2char(self, dcode: int) -> tuple[str, str, dict]:
        spbs=dcode&0x60
        dcode=dcode&0x1f
        if spbs:
            if spbs&0x20:
                return ('s', 'BS', deepcopy(self.RESET_MODIFIERS))
            else:
                return ('t', 'SP', deepcopy(self.RESET_MODIFIERS))
        keydef=self.keytables[self.csel][dcode]
        ik=keydef['key']
        if ik not in self.modifiers:
            rm=deepcopy(self.modifiers)
            if not self.lastmod:
                return (ik,'', rm) # regular key without modifier
            mk=keydef[self.lastmod] # modified with the last modifier
            if mk=='SWTB': ik=''
            if self.modifiers[self.lastmod]!=2:
                # last modifier is not locked
                for k,v in self.modifiers.items():
                    if v!=2: self.modifiers[k]=0 # clear all unlocked modifiers
                self.lastmod=''
                self.modstate_print()
                if mk=='SWTB': self.switch_config()
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
                        # different modifier, set a new modifier
                        self.modifiers[self.lastmod]=1
                    else:
                        # the same modifier, reset the modifier
                        self.modifiers[self.lastmod]=0
                        self.lastmod=''
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

    def modfier_status(self, mkey:str) -> int:
        if mkey not in self.modifiers: return 0
        return self.modifiers[mkey]

class InputBase_FT232(object):
    KEY_VALID_MIN=int(20E6) # 20msec
    KEY_INVALID_MIN=int(20E6) # 20msec
    KEY_REPEAT_START=int(400E6) # 300msec
    SCAN_KEY_MIN_INTERVAL=int(10E6) # 10msec
    def __init__(self):
        self.scan_ts=0
        self.last_keys=0
        self.stable_ts=0
        self.stable_keys=0
        self.maxbitn=0
        self.repeat=False
        super().__init__()

    # return (key_status, change_status, repeta_status)
    # change_status becomes True when (NOT PUSHED -> PUSHED) OR (PUSHED -> NOT PUSHED)
    # repeat_status becomes True when (PUSHED time >= KEY_REPEAT_START)
    def scan_key(self) -> tuple[int,bool,bool]:
        ts=time.time_ns()
        dts=ts-self.scan_ts
        # for at42qt1070, dts is around 16-18 msec, and no sleep happens
        # for keysw, dts is less than 1 msec, and sleep happens
        if dts<self.SCAN_KEY_MIN_INTERVAL:
                time.sleep((self.SCAN_KEY_MIN_INTERVAL-dts)/1E9)
                ts=time.time_ns()
                dts=ts-self.scan_ts
        self.scan_ts=ts
        keys=self.key_status()
        if keys!=self.last_keys:
            #print(bin(keys))
            self.last_keys=keys
            self.stable_ts=0
        else:
            self.stable_ts+=dts
        if self.last_keys and self.stable_ts>=self.KEY_VALID_MIN:
            if self.stable_keys!=self.last_keys:
                mn=self.last_keys.bit_count()
                if self.maxbitn<mn:
                    self.maxbitn=mn
                    self.stable_keys=self.last_keys
            if self.stable_ts>=self.KEY_REPEAT_START:
                if self.stable_ts-dts<self.KEY_REPEAT_START:
                    self.repeat=True
                    return (self.stable_keys, True, self.repeat) # repeat event start
                else:
                    return (self.stable_keys, False, self.repeat) # repeat event continue
        elif self.last_keys==0 and self.stable_ts>=self.KEY_INVALID_MIN:
            if self.stable_keys!=0:
                stbkeys=self.stable_keys
                self.stable_keys=0
                self.maxbitn=0
                if self.repeat:
                    self.repeat=False
                    return (0, True, True) # repeat event end
                return (stbkeys, True, False) # non-repeat event
        return (self.stable_keys, False, self.repeat) # transition

class KeySw_FT232(InputBase_FT232):
    def probe_device(self) -> bool:
        self.keys=[None]*7
        self.keys[0]=digitalio.DigitalInOut(board.C0)
        self.keys[1]=digitalio.DigitalInOut(board.C1)
        self.keys[2]=digitalio.DigitalInOut(board.C2)
        self.keys[3]=digitalio.DigitalInOut(board.C3)
        self.keys[4]=digitalio.DigitalInOut(board.C4)
        self.keys[5]=digitalio.DigitalInOut(board.C5)
        self.keys[6]=digitalio.DigitalInOut(board.C6)
        for i in range(7):
            self.keys[i].direction=digitalio.Direction.INPUT
        self.scan_ts=time.time_ns()
        return True

    def key_status(self) -> int:
        result=0
        for i in range(5):
            result|=(1<<(4-i)) if not self.keys[i].value else 0
        result |= (1<<5) if not self.keys[5].value else 0
        result |= (1<<6) if not self.keys[6].value else 0
        return result
