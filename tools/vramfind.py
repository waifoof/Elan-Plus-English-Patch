"""Find which disc file holds the texture at a VRAM rectangle.
  python3 vramfind.py <state> <word_x> <word_w> <y0> <y1>"""
import sys, glob, os, struct
st=open(sys.argv[1],'rb').read(); v=st[2725701:2725701+1024*1024]
wx,ww,y0,y1=map(int,sys.argv[2:6])
files={}
for f in glob.glob(os.path.join(os.path.dirname(__file__),'../work/disc/**/*'),recursive=True):
    if os.path.isfile(f) and not f.endswith('OUTPUT.BIN'): files[os.path.relpath(f)]=open(f,'rb').read()
for f in glob.glob(os.path.join(os.path.dirname(__file__),'../work/arc/OUTPUT/*.bin')):
    files['OUT'+os.path.basename(f)]=open(f,'rb').read()
for y in range(y0,y1,4):
    row=v[y*2048+wx*2:y*2048+(wx+ww)*2]
    if row.count(0)>len(row)*0.8: continue
    for n,d in files.items():
        i=d.find(row)
        if i>=0: print(y,n,hex(i))
