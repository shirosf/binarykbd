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

FONTFILE="/usr/share/fonts/opentype/freefont/FreeSans.otf"

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger('bkbpractice')

def getchar():
    if select.select([sys.stdin], [], [], 0) != ([sys.stdin], [], []):
        return ''
    return sys.stdin.read(1)

class CodeTable(object):
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

    def createimg(self, code: int, text: str) -> None:
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
        d.text((180,360), text, font=self.font)
        self.showfile="showfile.png"
        image.save(self.showfile)
        image.close()

    def close(self):
        self.closeimg()
        self.showfile=None

class PracticeOneKey(object):
    def __init__(self, codetable: CodeTable, fimage: FingersImage, pstr: str=""):
        super().__init__()
        self.codetable=codetable
        self.fimage=fimage
        self.setpstr(pstr)

    def setpstr(self, pstr: str) -> None:
        if len(pstr)>=3 and pstr[1]=='.' and pstr[2]=='.':
            self.pstr=""
            for i in range(ord(pstr[0]), ord(pstr[3])+1):
                self.pstr+=chr(i)
            if len(pstr)>=5:
                self.pstr+=pstr[4:]
        else:
            self.pstr=pstr

    def nextchar(self) -> str:
        plen=len(self.pstr)
        while True:
            i=random.randint(0, plen-1)
            yield self.pstr[i]

    def play(self, trytimes:int=0, gap:float=0.5, interval:float=3.0) -> None:
        count=0
        for k in self.nextchar():
            kt=self.codetable.chr2code(k)
            self.fimage.createimg(0, k)
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
            if getchar()!='': break

def parse_args():
    pname=sys.argv[0]
    i=pname.rfind('/')
    if i>=0: pname=pname[i+1:]
    opt_parser=argparse.ArgumentParser(prog=pname,
                                       description="binary5 keyboard practice")
    opt_parser.add_argument("-s", "--string", nargs='?', default="a..z",
                            help="charcters set to proctice, " \
                            "the first 4 charcters can be like a..e to set 'abcde'")
    opt_parser.add_argument("-g", "--gap", nargs='?', default=0.5, type=float,
                            help="gap time showing 2 sequential graphics")
    opt_parser.add_argument("-i", "--interval", nargs='?', default=2.0, type=float,
                            help="interval time of 1 prctice character")
    opt_parser.add_argument("-t", "--times", nargs='?', default=0, type=int,
                            help="times of repeating practice")
    return opt_parser.parse_args()

if __name__ == "__main__":
    random.seed()
    options=parse_args()
    codetable=CodeTable()
    codetable.readconf()
    fimage=FingersImage()
    fimage.createimg(0, "")
    fimage.showimg()
    pkey=PracticeOneKey(codetable, fimage, pstr=options.string)
    pkey.play(options.times, gap=options.gap, interval=options.interval)
    fimage.close()
