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
import argparse
from PIL import Image, ImageDraw, ImageFont
import sys
import time
import subprocess
import logging
import random
import select
import termios
from at42qt1070_ft232_touchpad import AT42QT1070_FT232
from keysw_ft232 import CodeTable, KeySw_FT232

FONTFILE="/usr/share/fonts/opentype/freefont/FreeSans.otf"

logger=logging.getLogger('bkbpractice')
logger.setLevel(logging.INFO)

def check_keyin():
    dp=select.poll()
    dp.register(sys.stdin, select.POLLIN)
    pres=dp.poll(0.0)
    if not pres: return False
    return True

class PraCodeTable(CodeTable):
    SPECIAL_KEYS = {'BS':'\b', 'SP':' ', 'VBAR':'|', 'TAB':'\t', 'ESC':'\x1B', 'RET':'\n',
                    'UP':'\x1B[A', 'DOWN':'\x1B[B', 'RIGHT':'\x1B[C', 'LEFT':'\x1B[D'}
    def code2charWm(self, dcode: int) -> str:
        key=self.code2char(dcode)
        if key[1]:
            if key[1] in self.SPECIAL_KEYS:
                return self.SPECIAL_KEYS[key[1]]
            return key[1]
        return key[0]

    def key2code(self, kchr:str) -> int:
        for i, keydef in enumerate(self.keytables[self.csel]):
            if keydef==None: continue
            if keydef['key'] == kchr:
                return i
        return 0

    def chr2code(self, kchr:str) -> tuple[int, int]:
        for i, keydef in enumerate(self.keytables[self.csel]):
            if keydef==None: continue
            for j in ('key','M1','M2','M3','M4','M5'):
                if keydef[j] == kchr:
                    if j=='key': return (0, i)
                    return (self.key2code(j), i)
        return (0, 0)

class FingersImage(object):
    def __init__(self):
        super().__init__()
        self.font=ImageFont.truetype(FONTFILE, 80)

    def showimg(self) -> None:
        if self.showfile:
            args=["xviewer", self.showfile]
            self.showproc=subprocess.Popen(args)

    def closeimg(self) -> None:
        if self.showproc:
            self.showproc.terminate()
            self.showproc.wait()
            self.showproc=None

    def createimg(self, code: int, text: str, red: bool=None) -> None:
        image = Image.open("fingersb.png")
        imgs = []
        k=1
        for i in range(5):
            if k & code:
                imgs.append(Image.open("fingers%d.png" % i))
            k=k<<1
        for img in imgs:
            image.paste(img, (0,0), mask = img)
            img.close()
        d=ImageDraw.Draw(image)
        if red:
            d.text((180,360), text, font=self.font, fill=(255,0,0,255))
        else:
            d.text((180,360), text, font=self.font)
        self.showfile="showfile.png"
        image.save(self.showfile)
        image.close()

    def close(self):
        self.closeimg()
        self.showfile=None

class PracticeOneKey(object):
    def __init__(self, ktype:str, codetable: PraCodeTable,
                 fimage: FingersImage=None, pstr: str=""):
        super().__init__()
        self.codetable=codetable
        self.fimage=fimage
        self.setpstr(pstr)
        if ktype=='touchpad':
            self.tdev=AT42QT1070_FT232()
        else:
            self.tdev=KeySw_FT232()
        if not self.tdev.probe_device():
            self.tdev=None

    def setpstr(self, pstr: str) -> None:
        if len(pstr)>=3 and pstr[1]=='.' and pstr[2]=='.':
            self.pstr=""
            for i in range(ord(pstr[0]), ord(pstr[3])+1):
                self.pstr+=chr(i)
            if len(pstr)>=5:
                self.pstr+=pstr[4:]
        elif len(pstr)==0:
            self.pstr=""
            for i in range(ord('a'), ord('z')+1):
                self.pstr+=chr(i)
            self.pstr+=self.pstr.upper()
            self.pstr+="0123456789 |@~&`%^,.()-{}<>[]_\"'+;=*\\:$/?"
        else:
            self.pstr=pstr

    def nextchar(self) -> str:
        plen=len(self.pstr)
        while True:
            i=random.randint(0, plen-1)
            yield self.pstr[i]

    def play(self, trytimes:int=0, gap:float=0.5, interval:float=3.0) -> None:
        count: int = 0
        self.modifier: tuple[str, int] = ('', 0)
        for k in self.nextchar():
            kt=self.codetable.chr2code(k)
            self.fimage.createimg(0, k)
            if self.tdev:
                while True:
                    pkey,change,repeat=self.tdev.scan_key()
                    if not change: continue
                    if pkey==0: continue
                    ik=self.codetable.code2charWm(pkey)
                    if check_keyin(): return
                    if ik!='': break
                if ik==k: continue
                self.fimage.createimg(0, ik, red=True)
            time.sleep(gap)
            if kt[0]==0:
                self.fimage.createimg(kt[1], k)
            else:
                self.fimage.createimg(kt[0], "")
                time.sleep(gap)
                self.fimage.createimg(kt[1], "")
            time.sleep(interval)
            count+=1
            if trytimes==count: break
            if check_keyin(): return

    def tplay(self, trytimes:int=0) -> None:
        ccode={'red':'\033[91m', 'green':'\033[92m', 'yellow':'\033[93m',
                'blue':'\033[94m', 'purple':'\033[95m', 'cyan':'\033[96m',
                'gray':'\033[97m', 'black':'\033[98m',
                'end':'\033[0m', 'bold':'\033[1m', 'underline':'\033[4m'}
        wordlen=4
        count=0
        while True:
            word=''
            for k in self.nextchar():
                word+=k
                if len(word)==wordlen: break
            print(word)
            wc=0
            while wc<wordlen:
                while True:
                    pkey,change,repeat=self.tdev.scan_key()
                    if pkey==0: continue
                    if change: break
                ik=self.codetable.code2charWm(pkey)
                if ik:
                    if ik!=word[wc]:
                        print(("%s{}%s" % (ccode['red'], ccode['end'])) .format(ik), end='')
                    else:
                        print(ik, end='')
                    sys.stdout.flush()
                    wc+=1
                if check_keyin(): return
            print()
            print("----------")
            count+=1
            if trytimes==count: break

def parse_args():
    pname=sys.argv[0]
    i=pname.rfind('/')
    if i>=0: pname=pname[i+1:]
    opt_parser=argparse.ArgumentParser(prog=pname,
                                       description="binary5 keyboard practice")
    opt_parser.add_argument("-s", "--string", nargs='?', default="",
                            help="charcters set to proctice, " \
                            "the first 4 charcters can be like a..e to set 'abcde'")
    opt_parser.add_argument("-g", "--gap", nargs='?', default=0.5, type=float,
                            help="gap time showing 2 sequential graphics")
    opt_parser.add_argument("-i", "--interval", nargs='?', default=2.0, type=float,
                            help="interval time of 1 prctice character")
    opt_parser.add_argument("-t", "--times", nargs='?', default=0, type=int,
                            help="times of repeating practice")
    opt_parser.add_argument("-m", "--mode", nargs='?', default=0, type=int,
                            help="practice mode, 0:graphics(default), 1:text")
    opt_parser.add_argument("-k", "--ktype", nargs='?', default="keysw",
                            help="keytype 'keysw' or 'touchpad'")
    return opt_parser.parse_args()

class ConsoleKeyIn():
    def __init__(self, keyin):
        self.keyin=keyin
        if not keyin: return
        fd=sys.stdin.fileno()
        self.sattr=termios.tcgetattr(fd)
        nattr=termios.tcgetattr(fd)
        nattr[3] &= ~termios.ICANON
        #nattr[3] &= ~termios.ECHO
        nattr[6][termios.VMIN]=1
        nattr[6][termios.VTIME]=0
        termios.tcsetattr(fd, termios.TCSANOW, nattr)

    def close(self):
        if not self.keyin: return
        fd=sys.stdin.fileno()
        termios.tcsetattr(fd, termios.TCSANOW, self.sattr)

if __name__ == "__main__":
    random.seed()
    options=parse_args()
    codetable=PraCodeTable()
    codetable.readconf()
    ckeyin=ConsoleKeyIn(True)
    if options.mode==0:
        fimage=FingersImage()
        fimage.createimg(0, "")
        fimage.showimg()
        pkey=PracticeOneKey(options.ktype, codetable, fimage, pstr=options.string)
        pkey.play(options.times, gap=options.gap, interval=options.interval)
        fimage.close()
    else:
        pkey=PracticeOneKey(options.ktype, codetable, pstr=options.string)
        pkey.tplay()

    ckeyin.close()
    sys.exit(0)
