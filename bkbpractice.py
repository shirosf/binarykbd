#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

FONTFILE="/usr/share/fonts/opentype/freefont/FreeSans.otf"

logger=logging.getLogger('bkbpractice')
logger.setLevel(logging.INFO)

def check_keyin():
    dp=select.poll()
    dp.register(sys.stdin, select.POLLIN)
    pres=dp.poll(0.0)
    if not pres: return False
    return True

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

    def key2code(self, kchr:str) -> int:
        for i, keydef in enumerate(self.keytable):
            if keydef==None: continue
            if keydef['key'] == kchr:
                return i
        return 0

    def chr2code(self, kchr:str) -> tuple[int, int]:
        for i, keydef in enumerate(self.keytable):
            if keydef==None: continue
            for j in ('key','M1','M2','M3','M4','M5'):
                if keydef[j] == kchr:
                    if j=='key': return (0, i)
                    return (self.key2code(j), i)
        return (0, 0)

    def code2char(self, dcode: int) -> tuple[str, str]:
        if dcode>=32: return ''
        keydef=self.keytable[dcode]
        ik=keydef['key']
        if ik not in self.modifiers:
            if not self.lastmod:
                return (ik,'') # regular key without modifier
            mk=keydef[self.lastmod] # modified with the last modifier
            if self.modifiers[self.lastmod]!=2:
                # last modifier is not locked
                for k,v in self.modifiers.items():
                    if v!=2: self.modifiers[k]=0 # clear all unlocked modifiers
                self.lastmod=''
                return (ik, mk)
            else:
                # last modifier is locked
                return (ik, mk)
        # got a modifier key
        if ik==self.lastmod:
            if self.modifiers[self.lastmod]==1:
                ts=time.time_ns()
                if ts-self.modts < self.MODLOCK_TIMEOUT:
                    logger.debug("modifiere %s=2" % self.lastmod)
                    self.modifiers[self.lastmod]=2 # only 2 sequencial mofiers make lock
                else:
                    logger.debug("modifiere(no lock by timeout) %s=1" % self.lastmod)
                    self.modts=ts
                    self.modifiers[self.lastmod]=1
            else:
                self.modifiers[self.lastmod]=0
                logger.debug("modifiere %s=0" % self.lastmod)
                self.lastmod=''
        else:
            if self.modifiers[ik]==2:
                logger.debug("modifiere %s=0" % ik)
                self.modifiers[ik]=0
                self.lastmod=''
            else:
                logger.debug("modifiere %s=1" % ik)
                self.modts=time.time_ns()
                self.modifiers[ik]=1
                self.lastmod=ik
        return ('','')

    def code2charWm(self, dcode: int) -> str:
        key=self.code2char(dcode)
        if key[1]: return key[1]
        return key[0]


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
    def __init__(self, codetable: CodeTable, fimage: FingersImage=None, pstr: str=""):
        super().__init__()
        self.codetable=codetable
        self.fimage=fimage
        self.setpstr(pstr)
        self.tdev=AT42QT1070_FT232()
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
                    while not self.tdev.scan_key(): pass
                    ik=self.codetable.code2charWm(self.tdev.keys_maxbits)
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
                while not self.tdev.scan_key(): pass
                ik=self.codetable.code2charWm(self.tdev.keys_maxbits)
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
    codetable=CodeTable()
    codetable.readconf()
    ckeyin=ConsoleKeyIn(True)
    if options.mode==0:
        fimage=FingersImage()
        fimage.createimg(0, "")
        fimage.showimg()
        pkey=PracticeOneKey(codetable, fimage, pstr=options.string)
        pkey.play(options.times, gap=options.gap, interval=options.interval)
        fimage.close()
    else:
        pkey=PracticeOneKey(codetable, pstr=options.string)
        pkey.tplay()

    ckeyin.close()
    sys.exit(0)
