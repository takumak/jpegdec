# License: MIT

# Supports:
#   SOF0: Baseline
#   SOF2: Progressive
# Not supports:
#   DRI, RSTx

import sys
import math

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

#  0  1  2  3  4  5  6  7
#  8  9 10 11 12 13 14 15
# 16 17 18 19 20 21 22 23
# 24 25 26 27 28 29 30 31
# 32 33 34 35 36 37 38 39
# 40 41 42 43 44 45 46 47
# 48 49 50 51 52 53 54 55
# 56 57 58 59 60 61 62 63

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

def cos_tbl():
  tbl = []
  for i in range(8):
    row = []
    for j in range(8):
      v = math.cos((2 * i + 1) * j * math.pi / 16)
      if j == 0:
        v /= math.sqrt(2)
      row.append(v)
    tbl.append(row)
  return tbl

cos_tbl = cos_tbl()

class Component:
  def __init__(self, cid, DQTid, factorh, factorv, maxfactors, width, height, data = None):
    self.cid = cid
    self.factorh = factorh
    self.factorv = factorv
    self.factors = factorh, factorv
    self.maxfactors = maxfactors
    self.DQTid = DQTid
    self.scalex = factorh / maxfactors[0]
    self.scaley = factorv / maxfactors[1]
    self.imgwidth = width
    self.imgheight = height
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

  def get_img_pos(self, x, y):
    x = math.floor(x * self.scalex)
    y = math.floor(y * self.scaley)
    return self.get(x, y)

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

class JPEGDecoder:
  component_ids = {1: 'Y', 2: 'Cb', 3: 'Cr'}
  quantizetbl = {}
  hufftblDC = {}
  hufftblAC = {}

  def __init__(self):
    self.prevDC = {}
    self.prevAl = {}
    self.EOBrun = 0
    self.save_id = 0

  def parse_APP0(self, data):
    if len(data) < 14:
      raise RuntimeError('Segment too small')

    if data[0:5] != b'JFIF\0':
      raise RuntimeError('Segment does not starts with JFIF identifier')

    thumb_width = data[12]
    thumb_height = data[13]

    segment_size = 14 + (thumb_width * thumb_height * 3)
    if len(data) != segment_size:
      raise RuntimeError('Invalid segment size: expected=%d, got=%d'
                         % (segment_size, len(data)))

    units = {0: 'No units', 1: 'Pixels per inch', 2: 'Pixels per centimeter'}
    print('JFIF version: %d.%d' % tuple(data[5:7]))
    print('Dencity units: %d (%s)' % (data[7], units.get(data[7], 'Unknown')))
    print('X dencity: %d' % ((data[8]<<8) | data[9]))
    print('Y dencity: %d' % ((data[10]<<8) | data[11]))
    print('Thumbnail width: %d' % thumb_width)
    print('Thumbnail height: %d' % thumb_height)

  def parse_COM(self, data):
    print(repr(data))

  def parse_SOF(self, data):
    if len(data) < 6:
      raise RuntimeError('Segment too small')

    precision = data[0]
    height = (data[1] << 8) | data[2]
    width = (data[3] << 8) | data[4]
    cnt = int(data[5])

    segment_size = 6 + (cnt * 3)
    if len(data) != segment_size:
      raise RuntimeError('Invalid segment size: expected=%d, got=%d'
                         % (segment_size, len(data)))

    if precision != 8:
      raise RuntimeError('Unsupported precision (supports only 8): got=%d' % precision)

    if width < 1 or height < 1:
      raise RuntimeError('Image width and height must be positive: got=%dx%d' % (width, height))

    comps = []
    for i in range(cnt):
      p = 6 + (i * 3)
      cid_ = int(data[p])

      if cid_ not in self.component_ids:
        raise RuntimeError('Unknown component id: %02x' % cid_)

      cid = self.component_ids[cid_]
      factorh = data[p + 1] >> 4
      factorv = data[p + 1] & 0xf
      DQTid = data[p + 2]

      comps.append(dict(cid=cid, DQTid=DQTid, factorh=factorh, factorv=factorv))
      print('Component: %02d (%s) factor=%d:%d, DQTid=%d'
            % (cid_, cid, factorh, factorv, DQTid))

    if set([c['cid'] for c in comps]) != set(['Y', 'Cb', 'Cr']):
      raise RuntimeError(
        'Unsupported components pattern (supports only YCbCr): got=%s' % ''.join(cids))

    self.width = width
    self.height = height

    mfh = max([c['factorh'] for c in comps])
    mfv = max([c['factorv'] for c in comps])

    w = 8 * mfh
    h = 8 * mfv
    padwidth = math.ceil(width / w) * w
    padheight = math.ceil(height / h) * h
    self.padwidth = padwidth
    self.padheight = padheight

    comps = [Component(maxfactors=(mfh, mfv), width=padwidth, height=padheight, **c)
             for c in comps]
    self.comps = dict([(c.cid, c) for c in comps])

  def parse_SOF0(self, data):
    self.parse_SOF(data)
    self.progressive = False

  def parse_SOF2(self, data):
    self.parse_SOF(data)
    self.progressive = True

  def parse_DQT(self, data):
    if len(data) < 65:
      raise RuntimeError('Segment too small')

    precision = data[0] >> 4
    tbl_idx = data[0] & 0xf

    segment_size = 1 + (64 * (precision + 1))
    if len(data) != segment_size:
      raise RuntimeError('Invalid segment size: expected=%d, got=%d'
                         % (segment_size, len(data)))

    if precision == 1:
      raise RuntimeError('64 bit DQT is not supported')
    elif precision != 0:
      raise RuntimeError(
        'Invalid DQT precision: expected=(0 or 1), got=%d' % precision)

    if tbl_idx in self.quantizetbl:
      raise RuntimeError('Multiple definition of DQT: idx=%d' % tbl_idx)

    self.quantizetbl[tbl_idx] = [0] * 64
    for i, q in enumerate(data[1:]):
      self.quantizetbl[tbl_idx][zigzag_order[i]] = q

    print('Index: %d' % tbl_idx)
    self.print_block(self.quantizetbl[tbl_idx], 8)

  # def parse_DRI(self, data):
  #   pass

  def parse_DHT(self, data):
    if len(data) < 17:
      raise RuntimeError('Segment too small')

    bits = data[1:17]
    segment_size = 17 + sum(bits)
    if len(data) != segment_size:
      raise RuntimeError('Invalid segment size: expected=%d, got=%d'
                         % (segment_size, len(data)))

    tbl_cls = data[0] >> 4
    AC = tbl_cls != 0
    tbl_cls_s = 'AC' if AC else 'DC'
    tbl_idx = data[0] & 0xf

    if tbl_cls & 0xe:
      raise RuntimeError('Invalid class: expected=(0 or 1), got=%x' % tbl_cls)

    tbl = {}
    if AC:
      self.hufftblAC[tbl_idx] = tbl
    else:
      self.hufftblDC[tbl_idx] = tbl

    print('Class: %x %s' % (tbl_cls, 'AC' if AC else 'DC'))
    print('Table idx: %d' % tbl_idx)
    print('Bit counts: ' + repr(list(data[1:17])))
    print('Huffman table:')

    code = 0
    width = 1
    for i, s in enumerate(sum([[i + 1] * s for i, s in enumerate(bits)], [])):
      code <<= (s - width)
      width = s
      if width not in tbl:
        tbl[width] = {}

      read = int(data[17 + i])
      run = 0
      if AC:
        run = read >> 4
        read &= 0xf

      tbl[width][code] = read, run

      l = ('  {0:0%db}{1} (read={2}' % width).format(code, 'x' * read, read)
      if AC:
        l += ', run=%d)' % run
      else:
        l += ')'
      print(l)

      code += 1

  def parse_SOS(self, data):
    if len(data) < 1:
      raise RuntimeError('Segment too small')

    cnt = int(data[0]);
    segment_size = 4 + (cnt * 2)
    if len(data) != segment_size:
      raise RuntimeError('Invalid segment size: expected=%d, got=%d'
                         % (segment_size, len(data)))

    print('Component count: %02x' % cnt)

    p = 1 + (cnt * 2)
    Ss = int(data[p])
    Se = int(data[p + 1])
    Ah = data[p + 2] >> 4
    Al = data[p + 2] & 0xf

    comps = []
    for i in range(cnt):
      p = 1 + (2 * i)
      cid_ = int(data[p])

      if cid_ not in self.component_ids:
        raise RuntimeError('Unknown component id: %02x' % cid_)

      cid = self.component_ids[cid_]
      hufftbl_dc = data[p + 1] >> 4
      hufftbl_ac = data[p + 1] & 0xf

      if cid not in self.comps:
        raise RuntimeError('Unexpected component id: expected=%s, got=%s'
                           % (repr(self.comps.keys()), cid))

      comps.append((
        self.comps[cid],
        self.hufftblDC.get(hufftbl_dc),
        self.hufftblAC.get(hufftbl_ac)
      ))
      print('Component: %02d (%s) DC=%d, AC=%d' % (cid_, cid, hufftbl_dc, hufftbl_ac))

    if self.progressive:
      print('Ss: %d' % Ss)
      print('Se: %d' % Se)
      print('Ah, Al: %d, %d' % (Ah, Al))

      if (Ss == 0 and Se != 0) or (Ss != 0 and (Ss >= Se or Se > 63)):
        raise RuntimeError('Invalid Ss, Se pattern (progressive): Ss=%d, Se=%d' % (Ss, Se))
      if Ah != 0 and Al != Ah - 1:
        raise RuntimeError('Al must be Ah - 1 for non-zero Ah: Ah=%d, Al=%d' % (Ah, Al))

      for comp, hufftblDC, hufftblAC in comps:
        for i in range(Ss, Se + 1):
          if Ah != comp.Al[i]:
            raise RuntimeError('Unexpected Ah for %s[%d]: expected=%d, got=%d'
                               % (comp.cid, i, comp.Al[i], Ah))
          comp.Al[i] = Al

    else:
      if Ss != 0 or Se != 63 or Ah != 0 or Al != 0:
        raise RuntimeError(
          '(Ss, Se, Ah, Al) must be (0, 63, 0, 0) for baseline JPEG: Ss=%d, Se=%d, Ah=%d, Al=%d'
          % (Ss, Se, Ah, Al))

    self.scan_comps = comps
    self.Ss = Ss
    self.Se = Se
    self.Ah = Ah
    self.Al = Al
    if Ss == 0:
      self.prevAl['DC'] = Al
    else:
      for comp, t1, t2 in comps:
        self.prevAl[comp.cid] = Al

  def print_block(self, blk, width):
    for p in range(0, len(blk), width):
      print(' '.join(['% 5s' % i for i in blk[p:p+width]]))

  def read_bits(self, bits, update_scanpos = True):
    data = self.scandata
    ret = 0
    p = self.scanpos

    while bits > 0:
      pos_B = p // 8
      if len(data) <= pos_B:
        raise RuntimeError('Unexpected EOF')

      c = data[pos_B]
      if c == 0xff:
        if len(data) <= (pos_B + 1):
          raise RuntimeError('Unexpected EOF')
        if data[pos_B + 1] == 0xff:
          p += 8
          continue
        elif data[pos_B + 1] != 0:
          raise RuntimeError('Unexpected segment marker found at 0x%x (0x%x bit): ff%02x'
                             % (pos_B, p, data[pos_B + 1]))
      if pos_B > 0 and c == 0 and data[pos_B - 1] == 0xff:
        p += 8
        continue

      left = p % 8
      right = min(left + bits, 8)
      read_bits = right - left

      d = (c >> (8 - right)) & ((1 << read_bits) - 1)
      ret = (ret << read_bits) | d

      bits -= read_bits
      p += read_bits

    if update_scanpos:
      pos_B = p // 8
      if pos_B > 0 and data[pos_B] == 0 and data[pos_B - 1] == 0xff:
        if (p % 8) != 0:
          raise RuntimeError('[Bug] Current position is at second half part of 0xff00')
        p += 8
      self.scanpos = p
      return ret
    return ret, p

  def expand_value(self, value, bits):
    if bits > 0 and (value & (1 << (bits - 1))) == 0:
      return -((~value) & ((1 << bits) - 1))
    return value

  def decode(self, tbl):
    data = self.scandata
    for bitwidth, codemap in tbl.items():
      bits, newpos = self.read_bits(bitwidth, False)
      if bits in codemap:
        _p = self.scanpos
        self.scanpos = newpos
        read, run = codemap[bits]
        value = self.read_bits(read)
        value_e = self.expand_value(value, read)
        print(('{0: 8x}: {1:0%db} (read:{2} run:{3}) {4:0%db} => {5:0%db} ({5})'
               % (bitwidth, read, read)).format(_p, bits, read, run, value, value_e))
        return run, value_e, read

    p = self.scanpos
    raise RuntimeError('Failed to decode huffman code: pos=(0x%x; 0x%xB+%d)'
                       % (p, p // 8, p % 8))

  def scan_image_data(self, data):

    def dump():
      import re
      d_ = data[0:next(re.finditer(b'\xff(?!\x00)', data)).span(0)[0]+2]
      self.hexdump(d_)
      print()
      for i in range(0, len(d_), 4):
        print('% 8x: ' % (i * 8) + ' '.join(map('{0:08b}'.format, d_[i:i+4])))

    self.scandata = data
    self.scanpos = 0

    # <-----------------------> Image width with padding (Block width * N)
    # <--------------------->   Image width (actual)
    #   <----->                 MCU width (Horizontal sampling factor * Block width)
    #   <-->                    Block width
    # +-----------------------+
    # | +--+--+ +--+--+       |
    # | | 1| 2| | 1| 2|       |
    # | +--+--+ +--+--+  ...  |
    # | | 3| 4| | 3| 4|       |
    # | +-----+ +-----+       |
    # | +--+--+               |
    # | | 1| 2|               |
    # | +--+--+               |
    # | | 3| 4|               |
    # | +-----+               |
    # |    .                  |
    # |    .                  |
    # |    .                  |
    # +-----------------------+
    #
    # Block width: 8 for SOF0, SOF2; may be change for others
    #
    # If the scan is non-interleaved, MCU width == Block width

    interleaved = len(self.scan_comps) > 1
    if interleaved:
      MCUblkW = max([c.factorh for c, t1, t2 in self.scan_comps])
      MCUblkH = max([c.factorv for c, t1, t2 in self.scan_comps])
      MCUcntX = math.ceil(self.width / (MCUblkW * 8))
      MCUcntY = math.ceil(self.height / (MCUblkH * 8))
    else:
      MCUblkW = 1
      MCUblkH = 1
      c = self.scan_comps[0][0]
      mfh = max([c.factorh for c in self.comps.values()])
      mfv = max([c.factorv for c in self.comps.values()])
      MCUcntX = math.ceil(self.width / (8 * mfh / c.factorh))
      MCUcntY = math.ceil(self.height / (8 * mfv / c.factorv))

    print('Interleaved: %s' % interleaved)
    print('Num MCUs: %dx%d' % (MCUcntX, MCUcntY))
    print('Num blocks in MCU: %dx%d' % (MCUblkW, MCUblkH))

    print()
    dump()
    print()

    mfh = max([c.factorh for c, t1, t2 in self.scan_comps])
    mfv = max([c.factorv for c, t1, t2 in self.scan_comps])

    for MCUy in range(MCUcntY):
      for MCUx in range(MCUcntX):
        for comp, hufftblDC, hufftblAC in self.scan_comps:

          bw = min(comp.factorh, MCUblkW)
          bh = min(comp.factorv, MCUblkH)
          for by in range(bh):
            y = (MCUy * MCUblkH + by) * 8 * comp.factorv // mfv
            for bx in range(bw):
              x = (MCUx * MCUblkW + bx) * 8 * comp.factorh // mfh
              print('%s: MCU=+%d+%d, Block=+%d+%d, x=%d, y=%d'
                    % (comp.cid, MCUx, MCUy, bx, by, x, y))

              if self.progressive:
                if self.Ss == 0:
                  if self.Ah == 0:
                    val = self.decode(hufftblDC)[1]
                    val += self.prevDC.get(comp.cid, 0)
                    self.prevDC[comp.cid] = val
                  else:
                    val = self.read_bits(1)
                  val <<= self.Al
                  comp.refine_DC(x, y, val)
                elif self.Ah == 0:
                  self.scan_block(x, y, comp, hufftblDC, hufftblAC)
                else:
                  self.refine_AC(x, y, comp, hufftblAC)
              else:
                self.scan_block(x, y, comp, hufftblDC, hufftblAC)

  def scan_block(self, x, y, comp, hufftblDC, hufftblAC):
    if self.EOBrun > 0:
      self.EOBrun -= 1
      return

    blk = [0] * 64
    i = self.Ss
    while i <= self.Se:
      if i == 0:
        val = self.decode(hufftblDC)[1]
        val += self.prevDC.get(comp.cid, 0)
        self.prevDC[comp.cid] = val
      else:
        run, val, read = self.decode(hufftblAC)
        if read == 0 and run != 15:
          self.EOBrun = (1 << run) + self.read_bits(run)
          print('EOB run: %d' % self.EOBrun)
          self.EOBrun -= 1
          break
        i += run

      blk[zigzag_order[i]] = val << self.Al
      i += 1

    comp.refine_block(x, y, blk)
    self.print_block(blk, 8)

  def refine_AC(self, x, y, comp, hufftblAC):
    p1 = 1 << self.Al
    m1 = (-1) << self.Al
    blk = [0] * 64
    i = self.Ss

    def get():
      idx = zigzag_order[i]
      return comp.get(x + (idx % 8), y + (idx // 8))

    def refine():
      v = get()
      if not v:
        return v
      refine = self.read_bits(1)
      if refine and (v & p1) == 0:
        idx = zigzag_order[i]
        add = p1 if v >= 0 else m1
        blk[idx] += add
        print('Refine: %d, %d += %d' % (idx % 8, idx // 8, add))
      else:
        print('Skip: %d' % i)
      return v

    if self.EOBrun == 0:
      while i <= self.Se:
        run, val, read = self.decode(hufftblAC)
        if read == 0 and run != 15:
          self.EOBrun = (1 << run) + self.read_bits(run)
          print('EOB run: %d' % self.EOBrun)
          break

        while i <= self.Se:
          if not refine():
            run -= 1
            if run < 0:
              break
          i += 1

        blk[zigzag_order[i]] = (val << self.Al) - get()
        i += 1

    if self.EOBrun > 0:
      while i <= self.Se:
        refine()
        i += 1
      self.EOBrun -= 1

    comp.refine_block(x, y, blk)

  def save_image(self):
    w, h = self.padwidth, self.padheight
    data = bytearray(w * h * 3)
    for off, cid in enumerate(['Y', 'Cb', 'Cr']):
      comp = self.comps[cid]
      comp = comp.decode(self.quantizetbl[comp.DQTid])
      for y in range(h):
        for x in range(w):
          data[(y * w + x) * 3 + off] = comp.get_img_pos(x, y)

    from PIL import Image
    img = Image.frombytes('YCbCr', (self.padwidth, self.padheight), bytes(data))
    img.convert('RGB').crop((0, 0, self.width, self.height)).save('decode_%d.png' % self.save_id)
    self.save_id += 1

  def hexdump(self, data):
    data_hex = list(map('%02x%02x'.__mod__, zip(data[0::2], data[1::2])))
    if len(data) & 1: data_hex.append('%02x' % data[-1])
    for p in range(0, len(data_hex), 8):
      print('% 8x: ' % (p*2) + ' '.join(data_hex[p:p+8]))

  def parse(self, data):
    if data[0:2] != b'\xff\xd8':
      raise RuntimeError('Data does not starts with SOI')

    pos = 2
    while True:
      marker = data[pos:pos+2]
      if marker[0] != 0xff:
        print('WARNING: Expected segment marker at %08x, but got %02x; skipping...'
              % (pos, marker[0]))
        pos += 1
        continue
      if marker[1] == 0xff:
        # Multiple 0xFFs should be ignored excepting the last one
        pos += 1
        continue

      marker_name = markers.get(marker[1], '????')
      if marker_name == 'EOI':
        print()
        print('%08x: %02x%02x %s' % (pos, marker[0], marker[1], marker_name))
        break

      size = (data[pos + 2] << 8) | data[pos + 3]
      data_seg = data[pos+4:pos+size+2]

      fun = getattr(self, 'parse_%s' % marker_name, None)
      if fun is None:
        raise RuntimeError('Unsupported segment: %02x%02x %s'
                           % (marker[0], marker[1], marker_name))

      print()
      print('%08x+%04x: %02x%02x %s' % (pos, size, marker[0], marker[1], marker_name))

      self.hexdump(data_seg)
      fun(data_seg)

      pos += size + 2;
      if marker_name == 'SOS':
        self.scan_image_data(data[pos:])
        read_size = math.ceil(self.scanpos / 8)
        pos += read_size
        if read_size >= 2 and data[pos] == 0 and data[pos - 1] == 0xff:
          pos += 1
        self.save_image()

def main():
  filename = sys.argv[1]
  print(filename)
  JPEGDecoder().parse(open(filename, 'rb').read())

if __name__ == '__main__':
  main()
