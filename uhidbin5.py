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

import asyncio
import logging
import uhid
from at42qt1070_ft232_touchpad import AT42QT1070_FT232
from keysw_ft232 import CodeTable, KeySw_FT232
import signal
import sys

logger=logging.getLogger('uhidbin5')
logger.setLevel(logging.INFO)

class Bin5Uhid():
    def __init__(self, device: uhid.UHIDDevice, mode: str='keysw'):
        if mode=='touchpad':
            self.tdev=AT42QT1070_FT232()
            logger.info("touchpad mode")
        elif mode=='keysw':
            self.tdev=KeySw_FT232()
            logger.info("keysw mode")
        else:
            return
        if not self.tdev.probe_device():
            raise Exception("No device is attached")
        self.device=device
        self.codetable=CodeTable()
        self.ready=(self.codetable.readconf()==0)
        self.inkey=None
        self.modifiers={'RightGUI':(1<<7), 'RightAlt':(1<<6), 'RightShift':(1<<5),
                        'RightCtl':(1<<4), 'LeftGui':(1<<3), 'LeftAlt':(1<<2),
                        'LeftShift':(1<<1), 'LeftCtr':(1<<0)}

    def scancode(self, rkey: str, mkey: str, mod: dict[str, int]) -> tuple[int, int]:
        scodes={
            '0':(0x27,0,0),
            'RET':(0x28,0,0),
            'ESC':(0x29,0,0),
            'BS':(0x2a,0,0),
            'TAB':(0x2b,0,0),
            'SP':(0x2c,0,0),
            '-':(0x2d,0,0),
            '=':(0x2e,0,0),
            '[':(0x2f,0,0),
            ']':(0x30,0,0),
            '\\':(0x31,0,0),
            ';':(0x33,0,0),
            "'":(0x34,0,0),
            '`':(0x35,0,0),
            ',':(0x36,0,0),
            '.':(0x37,0,0),
            '/':(0x38,0,0),
            'F1':(0x3a,0,0),
            'F2':(0x3b,0,0),
            'F3':(0x3c,0,0),
            'HOME':(0x4a,0,self.modifiers['LeftCtr']),
            'PUP':(0x4b,0,self.modifiers['LeftAlt']),
            'DEL':(0x4c,0,self.modifiers['LeftCtr']),
            'CSDEL':(0x4c,self.modifiers['LeftShift']|self.modifiers['LeftCtr'],0),
            'END':(0x4d,0,self.modifiers['LeftCtr']),
            'PDOWN':(0x4e,0,self.modifiers['LeftCtr']),
            'RIGHT':(0x4f,0,self.modifiers['LeftCtr']),
            'CRIGHT':(0x4f,self.modifiers['LeftCtr'],self.modifiers['LeftAlt']),
            'LEFT':(0x50,0,self.modifiers['LeftCtr']),
            'CLEFT':(0x50,self.modifiers['LeftCtr'],self.modifiers['LeftAlt']),
            'DOWN':(0x51,0,self.modifiers['LeftCtr']),
            'UP':(0x52,0,self.modifiers['LeftCtr']),
            '!':(0x1e,self.modifiers['LeftShift'],0),
            '@':(0x1f,self.modifiers['LeftShift'],0),
            '#':(0x20,self.modifiers['LeftShift'],0),
            '$':(0x21,self.modifiers['LeftShift'],0),
            '%':(0x22,self.modifiers['LeftShift'],0),
            '^':(0x23,self.modifiers['LeftShift'],0),
            '*':(0x25,self.modifiers['LeftShift'],0),
            '&':(0x24,self.modifiers['LeftShift'],0),
            '(':(0x26,self.modifiers['LeftShift'],0),
            ')':(0x27,self.modifiers['LeftShift'],0),
            '_':(0x2d,self.modifiers['LeftShift'],0),
            '+':(0x2e,self.modifiers['LeftShift'],0),
            '{':(0x2f,self.modifiers['LeftShift'],0),
            '}':(0x30,self.modifiers['LeftShift'],0),
            'VBAR':(0x32,self.modifiers['LeftShift'],0),
            ':':(0x33,self.modifiers['LeftShift'],0),
            '"':(0x34,self.modifiers['LeftShift'],0),
            '~':(0x35,self.modifiers['LeftShift'],0),
            '<':(0x36,self.modifiers['LeftShift'],0),
            '>':(0x37,self.modifiers['LeftShift'],0),
            '?':(0x38,self.modifiers['LeftShift'],0),
        }

        mbits=0
        if mod['M1']:
            mbits|=self.modifiers['LeftShift']
        if mod['M4']:
            mbits|=self.modifiers['LeftAlt']
        if mod['M5']:
            mbits|=self.modifiers['LeftCtr']
        if not mkey:
            return (ord(rkey)-ord('a')+0x04, mbits);
        if len(mkey)==1 and mkey>='A' and mkey<='Z':
            if mod['M5']:
                # when M5 table defines upper case letter, swich CTRL -> ALT
                mbits&=~self.modifiers['LeftCtr']
                mbits|=self.modifiers['LeftAlt']
                return (ord(mkey)-ord('A')+0x04, mbits);
            if mod['M4']:
                # when M4 table defines upper case letter, swich ALT -> CTRL
                mbits&=~self.modifiers['LeftAlt']
                mbits|=self.modifiers['LeftCtr']
                return (ord(mkey)-ord('A')+0x04, mbits);
            return (ord(rkey)-ord('a')+0x04, mbits);

        if len(mkey)==1 and mkey>='1' and mkey<='9':
            return (ord(mkey)-ord('1')+0x1e, mbits);
        if len(mkey)==1 and mkey>='a' and mkey<='z':
            return (ord(mkey)-ord('a')+0x04, mbits);
        mbits|=scodes[mkey][1]
        mbits&=~scodes[mkey][2]
        return (scodes[mkey][0], mbits)

    async def get_tinput(self) -> None:
        while True:
            pkey,change,repeat=self.tdev.scan_key()
            if not change: continue
            if pkey==0:
                if repeat:
                    # get out from repeat status, send ZERO
                    self.device.send_input((0,0,0,0,0,0,0,0))
                return
            ik=self.codetable.code2char(pkey)
            if not ik[0]:
                if not repeat: continue
                mbits=0
                dv=0
                if self.codetable.modfier_status('M1'):
                    mbits|=self.modifiers['LeftShift']
                    dv=0xe1
                if self.codetable.modfier_status('M4'):
                    mbits|=self.modifiers['LeftAlt']
                    dv=0xe2
                if self.codetable.modfier_status('M5'):
                    mbits|=self.modifiers['LeftCtr']
                    dv=0xe0
                continue
            self.inkey=self.scancode(ik[0], ik[1], ik[2])
            # new key pushed status, send the code
            self.device.send_input((self.inkey[1],0,self.inkey[0],0,0,0,0,0))
            if repeat: return
            # non-repeat key event, pushed status is end, send ZERO
            self.device.send_input((0,0,0,0,0,0,0,0))
            return

    async def inject_input(self) -> None:
        while True:
            await self.get_tinput()
            while self.device._uhid._writer_registered: await asyncio.sleep(0)

async def main():
    device = uhid.UHIDDevice(
        0x15d9, 0x2323, 'binary5kbd', [
	0x05, 0x01,	#/* USAGE_PAGE (Generic Desktop) */
	0x09, 0x06,	#/* USAGE (Keyboard) */
	0xa1, 0x01,	#/* COLLECTION (Application) */
	0x05, 0x07,	#/* USAGE_PAGE(KeyCodes) */
	0x19, 0xE0,	#/* USAGE_MINIMUM (224) */
	0x29, 0xE7,	#/* USAGE_MAXIMUM (231) */
	0x15, 0x00,	#/* LOGICAL_MINIMUM (0) */
	0x25, 0x01,	#/* LOGICAL_MAXIMUM (1) */
	0x75, 0x01,	#/* REPORT_SIZE (1) */
	0x95, 0x08,	#/* REPORT_COUNT (8) */
	0x81, 0x02,	#/* Input (Data,Variable,Absolute);Modifier byte */
	0x95, 0x01,	#/* REPORT_COUNT (1) */
	0x75, 0x08,	#/* REPORT_SIZE (8) */
	0x81, 0x01,	#/* Input (Constant);Reserved byte */
	0x95, 0x05,	#/* REPORT_COUNT (5) */
	0x75, 0x01,	#/* REPORT_SIZE (1) */
	0x05, 0x08,	#/* USAGE_PAGE(for LEDs) */
	0x19, 0x01,	#/* USAGE_MINIMUM (1) */
	0x29, 0x05,	#/* USAGE_MAXIMUM (5) */
	0x91, 0x02,	#/* Output (Data,Var,Abs);LED report */
	0x95, 0x01,	#/* REPORT_COUNT (1) */
	0x75, 0x03,	#/* REPORT_SIZE (3) */
	0x91, 0x01,	#/* Output (Constant);LED report padding */
	0x95, 0x06,	#/* REPORT_COUNT (6) */
	0x75, 0x08,	#/* REPORT_SIZE (8) */
	0x15, 0x00,	#/* LOGICAL_MINIMUM (0) */
	0x25, 0x65,	#/* USAGE_MAXIMUM (101) */
	0x05, 0x07,	#/* USAGE_PAGE(Key Codes) */
	0x19, 0x00,	#/* USAGE_MINIMUM (0) */
	0x29, 0x65,	#/* USAGE_MAXIMUM (101) */
	0x81, 0x00,	#/* Input (Data, Array); Key array(6 bytes) */
	0xc0,		#/* END_COLLECTION */
        ],
        backend=uhid.AsyncioBlockingUHID,
    )
    logging.getLogger(device.__class__.__name__).setLevel(logging.ERROR)
    await device.wait_for_start_asyncio()
    mode = sys.argv[1] if len(sys.argv)>1 else 'keysw'
    buhid=Bin5Uhid(device, mode)
    if not buhid.ready: sys.exit(1)
    asyncio.create_task(buhid.inject_input())

def handler(signum, frame):
    global loop
    loop.stop()

if __name__ == '__main__':
    global loop
    signal.signal(signal.SIGINT, handler)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())  # create device
    loop.run_forever()  # run queued dispatch tasks
