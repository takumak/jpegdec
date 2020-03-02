from common import *

class Encoder:
  def __init__(self, out):
    self.out = out

  def prepare_scan(self):
    mfh = max([c.factorh for c in self.comps])
    mfv = max([c.factorv for c in self.comps])

    self.runvals = {}
    for c in self.comps:
      

  def write_marker(self, name):
    self.out.write(b'\xff')
    self.out.write(bytes([markers[name]]))

  def write_bytes(self, *data):
    for v in data:
      if not isinstance(v, bytes):
        v = bytes([v])
      self.out.write(v.replace(b'\xff', b'\xff\x00'))

  def write_APP0(self):
    self.write_marker('APP0')
    self.write_bytes(
      b'JFIF\0',
      1, 1,      # JFIF version: 1.1
      1,         # Dencity units: Pixels per inch
      0, 72,     # X: 72dpi
      0, 72,     # Y: 72dpi
      0,         # Thumbnail width: 0
      0          # Thumbnail height: 0
    )

  def write_DQT(self, id, table):
    self.write_marker('DQT')
    self.write_bytes(
      id,
      *[table[i] for i in zigzag_order]
    )

  def write_SOF0(self):
    self.write_marker('SOF0')
    self.write_bytes(
      8, # data precision
      (self.height >> 8) & 0xff, self.height & 0xff,
      (self.width >> 8) & 0xff, self.width & 0xff,
      len(self.comps)
    )
    for c in self.comps:
      self.write_bytes(
        component_ids[c.cid],
        ((c.factorh << 4) | (c.factorv & 0xf)) & 0xf,
        c.DQTid
      )

  def write_DHT(self):
    

  def write(self, out):
    self.prepare_data()

    self.write_marker('SOI')
    self.write_APP0()
    for id in sorted(self.quantizetbl.keys()):
      self.write_DQT(id, self.quantizetbl[id])
    self.write_SOF0()

def main():
  from data import *
  enc = Encoder()
  enc.width = 16
  enc.height = 16
  enc.comps = [
    Component('Y',  0, 1, 1, (2, 2), 16, 16, Y0 + Y1 + Y2 + Y3),
    Component('Cb', 1, 2, 2, (2, 2), 16, 16, Cb),
    Component('Cr', 1, 2, 2, (2, 2), 16, 16, Cr)
  ]
  enc.quantizetbl = {
    0: DQT0,
    1: DQT1
  }

if __name__ == '__main__':
  main()
