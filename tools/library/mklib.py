"""Make a synthetic MUSIC.LIB with N scanned records, as the stock scan leaves it, for the
index-pass tests.

usage: mklib.py N OUT.LIB [SEED] [LOCATION_MODE]
The names are pseudo-random but deterministic.  They include the cases the passes must get
right: titles shared between albums, albums shared between artists, names that differ only in
case, the same name stored as ASCII in one record and UTF-16 in another, tracks without a
number, and a few names with characters above U+00FF.

LOCATION_MODE is ``random`` by default.  ``observed`` fills the unresolved
location blob with the byte-level correlations measured on an M30 card: one
of the two cluster words at primary offsets +0x18/+0x20 equals the secondary
cluster, and its companion offset is aligned relative to the secondary
dir_entry.  This is a fixture mode, not a claim that the primary fields have
been semantically decoded.
"""
import random
import struct
import sys

WORDS = ('Black', 'River', 'Night', 'Golden', 'Silver', 'Dream', 'Fire', 'Stone', 'Wild', 'Blue',
         'Heart', 'Road', 'Moon', 'Sun', 'Rain', 'Ghost', 'City', 'Light', 'Dark', 'Love',
         'Time', 'Wind', 'Sea', 'Sky', 'Star', 'Iron', 'Glass', 'Paper', 'Velvet', 'Neon')
GENRES = ('Rock', 'Pop', 'Jazz', 'Blues', 'Metal', 'Hip-Hop', 'Electronic', 'Folk', 'Punk Rock',
          'Soul', 'Funk', 'Country', 'Classical', 'Ambient', 'Indie', 'Reggae', 'Soundtrack',
          'Alternative', 'Trip-Hop', 'Gospel', 'Latin', 'Techno', 'House', 'Grunge', 'Ska',
          'Industrial', 'Dub', 'Shoegaze', 'Post-Rock', 'Drone')


def field(text, width, ascii_ok, rnd):
    """A record text field: UTF-16LE with BOM, or plain ASCII now and then."""
    if ascii_ok and rnd.random() < 0.08 and all(ord(c) < 128 for c in text):
        b = text.encode('ascii')[:width - 1]
    else:
        b = b'\xff\xfe' + text.encode('utf-16-le')[:width - 4]
    return b.ljust(width, b'\0')


def observed_location_fields(record, index):
    """Write only the observed primary/secondary location relationships."""
    cluster_no = 0x1000 + (index // 8) * 0x40
    dir_entry = (index % 8) * 0x80
    companion_delta = (index % 71) * 0x20
    companion = dir_entry + companion_delta

    # The real card uses both pair positions.  Alternate by directory group
    # so the fixture exercises both observed representations.
    use_first_pair = (index // 8) % 2 == 0
    if use_first_pair:
        struct.pack_into('<II', record, 0xa9 + 0x18, cluster_no, companion)
    else:
        struct.pack_into('<II', record, 0xa9 + 0x20, cluster_no, companion)

    # These constants were stable across the observed card image.  Keep them
    # as raw fixture bytes; their semantic names remain unresolved.
    struct.pack_into('<II', record, 0xa9 + 0x28, 0x45f56, 0xd80)
    struct.pack_into('<II', record, 0xa9 + 0x30, 0, 0)
    struct.pack_into('<I', record, 0xa9 + 0x38, 0)
    struct.pack_into('<I', record, 0xa9 + 0x3c, 0)
    struct.pack_into('<I', record, 0xa9 + 0x40, 0)
    struct.pack_into('<II', record, 0xf4, cluster_no, dir_entry)


def main(n, out, seed=1, location_mode='random'):
    if location_mode not in ('random', 'observed'):
        raise ValueError("LOCATION_MODE must be 'random' or 'observed'")

    rnd = random.Random(seed)
    artists = ['%s %s' % (rnd.choice(WORDS), rnd.choice(WORDS)) for _ in range(max(2, n // 15))]
    artists += ['The ' + a for a in artists[:len(artists) // 6]]
    albums = ['%s %s' % (rnd.choice(WORDS), rnd.choice(('Sessions', 'Live', 'Greatest Hits', 'EP', 'II', 'Songs')))
              for _ in range(max(2, n // 8))]
    albums += [a.upper() for a in albums[:len(albums) // 10]]            # case variants
    albums += ['Déjà Vu', 'Ἀποκάλυψις', '“Quoted”', 'Año Nuevo']
    hdr = bytearray(0x200)
    hdr[0:5] = b'MUSIC'
    struct.pack_into('<HH', hdr, 8, n, 1)
    hdr[0x1fe:0x200] = b'\x55\xaa'
    for off, name in ((0x10, b'ALLSONG'), (0x2c, b'ALBUM'), (0x48, b'ARTIST'), (0x64, b'GENRE')):
        hdr[off:off + len(name)] = name
    recs = []
    for i in range(n):
        r = bytearray(256)
        trk = rnd.randint(1, 18) if rnd.random() < 0.9 else 0xffff
        title = '%02d %s %s' % (trk if trk != 0xffff else rnd.randint(1, 30), rnd.choice(WORDS), rnd.choice(WORDS))
        if rnd.random() < 0.05:
            title = title.lower()
        r[0x00:0x40] = field(title, 0x40, True, rnd)
        r[0x40:0x58] = field(rnd.choice(artists), 0x18, True, rnd)
        r[0x58:0x88] = field(rnd.choice(albums), 0x30, True, rnd)
        r[0x88:0xa0] = field(rnd.choice(GENRES), 0x18, True, rnd)
        r[0xa0:0xa3] = (b'%d' % trk if trk != 0xffff else b'')[:3].ljust(3, b'\0')
        r[0xa3] = 1
        r[0xa4:0xa8] = b'MP3\0' if rnd.random() < 0.95 else b'M4A\0'
        r[0xa8] = 1
        r[0xa9:0xf2] = bytes(rnd.getrandbits(8) for _ in range(0xf2 - 0xa9))
        if location_mode == 'observed':
            observed_location_fields(r, i)
        struct.pack_into('<H', r, 0xf2, trk)
        if location_mode == 'random':
            r[0xf4:0xfc] = bytes(rnd.getrandbits(8) for _ in range(8))
        struct.pack_into('<HH', r, 0xfc, (i - 1) & 0xffff, i + 1)
        recs.append(bytes(r))
    body = b''.join(recs)
    body = body.ljust((len(body) + 511) // 512 * 512, b'\0')
    with open(out, 'wb') as output:
        output.write(bytes(hdr) + body)
    print('wrote %s: %d songs, %d artists, %d albums, location=%s' %
          (out, n, len(artists), len(albums), location_mode))


if __name__ == '__main__':
    main(int(sys.argv[1]), sys.argv[2],
         int(sys.argv[3]) if len(sys.argv) > 3 else 1,
         sys.argv[4] if len(sys.argv) > 4 else 'random')
