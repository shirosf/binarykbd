#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
import sys
import time
import subprocess
import logging
from random import randint, seed

FONTFILE="/usr/share/fonts/opentype/freefont/FreeSans.otf"

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger('bkbpractice')

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
    def __init__(self, pstr: str):
        super().__init__()
        self.pstr=pstr

    def nextchar(self) -> str:
        plen=len(self.pstr)
        while True:
            i=randint(0, plen-1)
            yield self.pstr[i]

if __name__ == "__main__":
    seed()
    codetable=CodeTable()
    codetable.readconf()
    fimage=FingersImage()
    fimage.createimg(0, "")
    fimage.showimg()
    pkey=PracticeOneKey('aeiou')
    for k in pkey.nextchar():
        kt=codetable.chr2code(k)
        if kt[0]==0:
            fimage.createimg(kt[1], k)
        else:
            fimage.createimg(kt[0], "")
            time.sleep(0.5)
            fimage.createimg(kt[1], "")
        a=input("hit 'Retrun' for Next, 'q' to quite ")
        if a and a[0]=='q':break
    fimage.close()
