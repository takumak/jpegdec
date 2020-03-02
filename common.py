markers = {
  0xc0: 'SOF0', 0xc1: 'SOF1', 0xc2: 'SOF2', 0xc3: 'SOF3',
  0xc5: 'SOF5', 0xc6: 'SOF6', 0xc7: 'SOF7',
  0xc8: 'JPG', 0xc9: 'SOF9', 0xca: 'SOF10', 0xcb: 'SOF11',
  0xcd: 'SOF13', 0xce: 'SOF14', 0xcf: 'SOF15',
  0xc4: 'DHT',
  0xcc: 'DAC',
  0xd0: 'RST0', 0xd1: 'RST1', 0xd2: 'RST2', 0xd3: 'RST3',
  0xd4: 'RST4', 0xd5: 'RST5', 0xd6: 'RST6', 0xd7: 'RST7',
  0xd8: 'SOI', 0xd9: 'EOI', 0xda: 'SOS', 0xdb: 'DQT',
  0xdc: 'DNL', 0xdd: 'DRI', 0xde: 'DHP', 0xdf: 'EXP',
  0xe0: 'APP0', 0xe1: 'APP1', 0xe2: 'APP2', 0xe3: 'APP3',
  0xe4: 'APP4', 0xe5: 'APP5', 0xe6: 'APP6', 0xe7: 'APP7',
  0xe8: 'APP8', 0xe9: 'APP9', 0xea: 'APP10', 0xeb: 'APP11',
  0xec: 'APP12', 0xed: 'APP13', 0xee: 'APP14', 0xef: 'APP15',
  0xf0: 'JPG0', 0xf8: 'JPG8', 0xfd: 'JPG13', 0xfe: 'COM',
  0x01: 'TEM'
}
markers.update(dict(map(reversed, markers.items())))

component_ids = {1: 'Y', 2: 'Cb', 3: 'Cr'}
component_ids.update(dict(map(reversed, component_ids.items())))

zigzag_order = [
   0,  1,  8, 16,  9,  2,  3, 10,
  17, 24, 32, 25, 18, 11,  4,  5,
  12, 19, 26, 33, 40, 48, 41, 34,
  27, 20, 13,  6,  7, 14, 21, 28,
  35, 42, 49, 56, 57, 50, 43, 36,
  29, 22, 15, 23, 30, 37, 44, 51,
  58, 59, 52, 45, 38, 31, 39, 46,
  53, 60, 61, 54, 47, 55, 62, 63
]

class Component:
  def __init__(self, cid, DQTid, factorh, factorv, maxfactors, imgwidth, imgheight, data = None):
    self.cid = cid
    self.factorh = factorh
    self.factorv = factorv
    self.factors = factorh, factorv
    self.maxfactors = maxfactors
    self.DQTid = DQTid
    self.scalex = factorh / maxfactors[0]
    self.scaley = factorv / maxfactors[1]
    self.imgwidth = imgwidth
    self.imgheight = imgheight
    self.width = math.floor(width * self.scalex)
    self.height = math.floor(height * self.scaley)
    self.data = data or ([0] * (width * height))
    self.Al = [0] * 64

  def get(self, x, y):
    if x >= self.width:
      raise IndexError('x out of range')
    if y >= self.height:
      raise IndexError('y out of range')
    return self.data[y * self.width + x]

  def refine_DC(self, x, y, val):
    if x + 8 > self.width:
      raise IndexError('x out of range')
    if y + 8 > self.height:
      raise IndexError('y out of range')
    self.data[y * self.width + x] |= val

  def refine_block(self, x, y, blk):
    if x + 8 > self.width:
      raise IndexError('x out of range')
    if y + 8 > self.height:
      raise IndexError('y out of range')
    for i in range(8):
      p1 = (y + i) * self.width + x
      p2 = i * 8
      for j in range(8):
        self.data[p1 + j] += blk[p2 + j]

  def decode_block(self, bx, by, quantizetbl, data):
    for y in range(8):
      for x in range(8):
        val = 0
        for v in range(8):
          for u in range(8):
            t = self.data[(by * 8 + v) * self.width + (bx * 8) + u]
            t *= quantizetbl[v * 8 + u]
            t *= cos_tbl[x][u]
            t *= cos_tbl[y][v]
            val += t
        val = min(max(0, round(val / 4) + 128), 255)
        data[(by * 8 + y) * self.width + (bx * 8) + x] = val

  def decode(self, quantizetbl):
    data = bytearray(len(self.data))
    for by in range(self.height // 8):
      for bx in range(self.width // 8):
        self.decode_block(bx, by, quantizetbl, data)
    return Component(self.cid, self.DQTid, self.factorh, self.factorv,
                     self.maxfactors, self.imgwidth, self.imgheight, data)
