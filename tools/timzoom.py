"""Zoomed TIM crop with pixel rulers: timzoom.py <file> <timoff> x0 y0 x1 y1 out.png [S]"""
import sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
import timtool
from PIL import Image, ImageDraw
f, off, x0, y0, x1, y1, out = sys.argv[1], int(sys.argv[2], 0), *map(int, sys.argv[3:7]), sys.argv[7]
S = int(sys.argv[8]) if len(sys.argv) > 8 else 4
d = open(f, 'rb').read(); t = timtool.parse(d, off); im = timtool.to_image(d, t).convert('RGB')
c = im.crop((x0, y0, x1, y1)).resize(((x1 - x0) * S, (y1 - y0) * S), Image.NEAREST)
o = Image.new('RGB', (c.width + 22, c.height + 14), (0, 0, 60)); o.paste(c, (22, 14)); dr = ImageDraw.Draw(o)
for x in range(x0, x1):
    if x % 5 == 0: dr.line([((x - x0) * S + 22, 9), ((x - x0) * S + 22, 13)], fill=(255, 60, 60))
    if x % 10 == 0: dr.text(((x - x0) * S + 23, 0), str(x), fill=(255, 255, 0))
for y in range(y0, y1):
    if y % 5 == 0: dr.line([(16, (y - y0) * S + 14), (21, (y - y0) * S + 14)], fill=(60, 255, 60))
    if y % 10 == 0: dr.text((0, (y - y0) * S + 10), str(y), fill=(60, 255, 60))
o.save(out)
