#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import uhid
import at42qt1070_ft232_touchpad
from bkbpractice import CodeTable

class Bin5Uhid():
    def __init__(self, device: uhid.UHIDDevice):
        self.tdev=at42qt1070_ft232_touchpad.AT42QT1070_FT232()
        if not self.tdev.probe_device():
                raise Exception("No device is attached")
        self.device=device
        self.codetable=CodeTable()
        self.codetable.readconf()

    def scancode(self, rkey: str, mkey: str, mod: dict[str, int]) -> tuple[int, int]:
        modifiers={'RightGUI':(1<<7), 'RightAlt':(1<<6), 'RightShift':(1<<5), 'RightCtl':(1<<4),
                   'LeftGui':(1<<3), 'LeftAlt':(1<<2), 'LeftShift':(1<<1), 'LeftCtr':(1<<0)}
        scodes={'0':(0x27,0), 'BS':(0x2a,0), 'RET':(0x28,0), 'TAB':(0x2b,0), 'SP':(0x2c,0),
                'RIGHT':(0x4f,0), 'LEFT':(0x50,0), 'UP':(0x52,0), 'DOWN':(0x51,0), 'ESC':(0x29,0),
                'VBAR':(0x32,1), '@':(0x1f,1), '~':(0x35,1), '&':(0x24,1), '`':(0x35,0),
                '%':(0x22,1), '^':(0x23,1), ',':(0x36,0), '.':(0x37,0), '(':(0x26,1),
                ')':(0x27,1), '-':(0x2d,0), '{':(0x2f,1), '}':(0x30,1), '<':(0x36,1),
                '>':(0x37,1), '[':(0x2f,0), ']':(0x30,0), '_':(0x2d,1), '"':(0x34,1),
                "'":(0x34,0), 'HOME':(0x4a,0), 'END':(0x4d,0), '+':(0x2e,1), ';':(0x33,0),
                '=':(0x2e,0), '*':(0x25,1), '\\':(0x31,0), ':':(0x33,1), '$':(0x21,1),
                '/':(0x38,0), '?':(0x38,1)}

        mbits=0
        mbits|=modifiers['LeftShift'] if mod['M1'] else 0
        mbits|=modifiers['LeftAlt'] if mod['M4'] else 0
        mbits|=modifiers['LeftCtr'] if mod['M5'] else 0
        if not mkey:
            return (ord(rkey)-ord('a')+0x04, mbits);
        if len(mkey)==1 and mkey>='A' and mkey<'Z':
            return (ord(rkey)-ord('a')+0x04, mbits);
        if len(mkey)==1 and mkey>='1' and mkey<='9':
            return (ord(mkey)-ord('1')+0x1e, mbits);
        if scodes[mkey][1]:
            mbits|=modifiers['LeftShift']
        else:
            mbits&=~modifiers['LeftShift']
        return (scodes[mkey][0], mbits)

    async def get_tinput(self) -> None:
        while True:
            while not self.tdev.scan_key(): pass
            ik=self.codetable.code2char(self.tdev.keys_maxbits)
            if not ik[0]: continue
            uk=self.scancode(ik[0], ik[1], ik[2])
            self.device.send_input((uk[1],0,uk[0],0,0,0,0,0))
            self.device.send_input((0,0,0,0,0,0,0,0))
            break
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
    buhid=Bin5Uhid(device)
    asyncio.create_task(buhid.inject_input())

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())  # create device
    loop.run_forever()  # run queued dispatch tasks
