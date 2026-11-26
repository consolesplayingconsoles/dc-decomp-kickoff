#!/usr/bin/env python3
"""Step 9: look inside the running game over Flycast's GDB server. Stdlib only.

The emulator is a Flycast built with -DENABLE_GDB_SERVER=ON, started from a terminal so that its log is read:

    <Flycast> -config config:Debug.GDBEnabled=yes <disc>.gdi > flycast.out 2>&1

(`-config config:rend.EmulateFramebuffer=yes` as well, to dump the screen: VRAM from A5000000.) Port 3263; GDB_HOST and GDB_PORT change
where. One command at a time:

    flycast_gdb.py running <seconds>                      wait until the game's own code runs (its vector base): before that the loader
                                                          overwrites memory, and breakpoints and patches with it
    flycast_gdb.py sample <seconds> <every> <out.json>    stop, read the registers, continue, again and again
    flycast_gdb.py trail <seconds> <every> <lo> <hi> <out.json> [stack words] [--game <lo> <hi>] [--vbr [<hex>]]
                                                          sample fast and keep the last 60 stops with the words at r15; end when the pc
                                                          enters [lo, hi) (physical; 0 0 for never) or, with --vbr, at the first stop
                                                          without the game's vector base (it reset or quit): the states before that
    flycast_gdb.py bp <seconds> <out.json> [--halt <prefix>] [--after <s>] [--in <lo> <hi>] <address|@file> ...
                                                          log each address at its first hit, in order, then take its breakpoint out. With
                                                          every function's address: the order the code first ran in. --halt: at the first
                                                          hit write <prefix>.json (registers) and <prefix>.ram, and stay stopped
    flycast_gdb.py hook <seconds> <address>[=name] ...    count every call of each address, by caller (pr) and r4 when small
    flycast_gdb.py snap <seconds> <lo> <hi> <prefix>      run until the pc is in [lo, hi), stop, write registers and RAM
    flycast_gdb.py mem <address> <length>                 read memory
    flycast_gdb.py write <address> <bytes> [<address> <bytes> ...]
                                                          write bytes (memory order) in one stop; `feaf0900` (a branch to itself) over a
                                                          routine's entry holds the CPU there for a sample to find
    flycast_gdb.py dump <address> <length> <out>          save memory to a file
    flycast_gdb.py watch <seconds> <out.json> <address>   log each change of one word

Addresses and lengths are hex. A breakpoint address may be given as 0C... or 8C...: it is set and matched as 8C..., the address the
CPU reports (given as 0C it is hit and counted nowhere). `@file` reads addresses from a file, separated by blanks or lines.
"""
import collections
import json
import os
import socket
import sys
import time

HOST = os.environ.get('GDB_HOST', '127.0.0.1')
PORT = int(os.environ.get('GDB_PORT', '3263'))
GAME_VBR = 0x8C00F400          # the vector base while a Katana game runs; the boot ROM and the BIOS menu use others
RAM = 0x8C000000
CHUNK = 0x800


def run_address(a):
    """The address the CPU reports for a place in main RAM, from either of its mirrors."""
    return RAM | (a & 0x00FFFFFF) if (a & 0x1F000000) == 0x0C000000 else a


def little(h):
    return int(''.join(reversed([h[i:i + 2] for i in range(0, len(h), 2)])), 16)


class Target:
    """The GDB server: packets, registers, memory, and breakpoints that are always taken back out."""

    def __init__(self, sock):
        self.sock = sock
        self.buf = b''
        self.saved = {}
        self.sock.sendall(b'+')

    def send(self, packet):
        self.sock.sendall(('$%s#%02x' % (packet, sum(packet.encode()) & 0xFF)).encode())

    def recv(self, timeout=10):
        self.sock.settimeout(timeout)
        end = time.time() + timeout
        while True:
            start = self.buf.find(b'$')
            stop = self.buf.find(b'#', start + 1) if start >= 0 else -1
            if stop >= 0 and len(self.buf) >= stop + 3:
                packet = self.buf[start + 1:stop].decode(errors='replace')
                self.buf = self.buf[stop + 3:]
                self.sock.sendall(b'+')
                return packet
            try:
                data = self.sock.recv(65536)
            except socket.timeout:
                if time.time() > end:
                    return None
                continue
            if not data:
                return None
            self.buf += data

    def cmd(self, packet, timeout=10):
        self.send(packet)
        return self.recv(timeout)

    def go(self):
        self.send('c')

    def stop(self):
        self.sock.sendall(b'\x03')
        return self.recv(5)

    def regs(self):
        g = self.cmd('g')
        for _ in range(3):                              # a stop reply can land after the g request: not registers
            if g and len(g) >= 16 * 8 and all(c in '0123456789abcdefABCDEFx' for c in g):
                break
            g = self.recv(5) if g and g[:1] in 'ST' else self.cmd('g')
        if not g or len(g) < 20 * 8:
            return None
        words = [g[i:i + 8] for i in range(0, len(g), 8)]
        v = [None if 'x' in w else little(w) for w in words]
        return {'r': v[:16], 'pc': v[16], 'pr': v[17], 'gbr': v[18], 'vbr': v[19], 'sr': v[22] if len(v) > 22 else None, 'all': g}

    def read(self, address, length):
        data = bytearray()
        for k in range(0, length, CHUNK):
            n = min(CHUNK, length - k)
            h = self.cmd('m%X,%X' % (address + k, n), 30)
            data += bytes.fromhex(h) if h and not h.startswith('E') else b'\0' * n
        return bytes(data)

    def read16(self, address):
        h = self.cmd('m%X,2' % address)
        return little(h[:4]) if h and len(h) >= 4 and not h.startswith('E') else None

    # Flycast patches the instruction for a breakpoint; a removal that does not put it back leaves the game to run into it with no
    # debugger attached, and it drops to the BIOS. Call these with the CPU stopped.
    def bp_add(self, address):
        if address not in self.saved:
            self.saved[address] = self.read16(address)
        return self.cmd('Z0,%X,2' % address)

    def bp_del(self, address):
        """Take the breakpoint out and check the instruction is back, writing it back when it is not. True when it is."""
        original = self.saved.pop(address, None)
        self.cmd('z0,%X,2' % address)
        if original is None:
            return True
        if self.read16(address) != original:
            self.cmd('M%X,2:%02x%02x' % (address, original & 0xFF, original >> 8))
        ok = self.read16(address) == original
        if not ok:
            print('[ERROR] %08X is still patched (original %04X): the game will stop there with no debugger' % (address, original))
        return ok

    def bp_clear(self):
        return all([self.bp_del(a) for a in list(self.saved)])


def connect():
    return Target(socket.create_connection((HOST, PORT), timeout=10))


def state(g, t0):
    row = {k: g[k] for k in ('r', 'pc', 'pr', 'gbr', 'vbr', 'sr')}
    row['t'] = round(time.time() - t0, 3)
    return row


def save_json(path, value):
    with open(path, 'w') as f:
        json.dump(value, f)


def save_stopped(t, prefix, row):
    """Registers and 16 MB of RAM of the stopped machine."""
    with open(prefix + '.ram', 'wb') as f:
        f.write(t.read(RAM, 0x1000000))
    save_json(prefix + '.json', row)


def option(args, name, count, default=None):
    """Take `name` and its `count` values out of args; the values, or default when it is not there."""
    if name not in args:
        return default
    i = args.index(name)
    values = args[i + 1:i + 1 + count]
    del args[i:i + 1 + count]
    return values


def addresses(args):
    out = []
    for a in args:
        if a.startswith('@'):
            with open(a[1:]) as f:
                out += addresses(f.read().split())
        else:
            out.append(run_address(int(a, 16)))
    return out


def cmd_running(t, args):
    """True once a stop shows the game's vector base."""
    end = time.time() + float(args[0])
    t.go()
    while time.time() < end:
        time.sleep(0.25)
        t.stop()
        g = t.regs()
        if g and g['vbr'] == GAME_VBR:
            print('the game is running: pc %08X' % g['pc'])
            t.go()
            return True
        t.go()
    print('the game never ran')
    return False


def cmd_sample(t, args):
    duration, every, out = float(args[0]), float(args[1]), args[2]
    rows = []
    t0 = time.time()
    t.go()
    while time.time() - t0 < duration:
        time.sleep(every)
        t.stop()
        g = t.regs()
        if g:
            rows.append(state(g, t0))
        t.go()
    save_json(out, rows)
    print('samples %d' % len(rows))
    if rows:
        print('last pc %08X pr %08X vbr %08X r15 %08X' % (rows[-1]['pc'], rows[-1]['pr'], rows[-1]['vbr'], rows[-1]['r'][15]))


def cmd_trail(t, args):
    args = list(args)
    game = option(args, '--game', 2)
    vbr = None
    if '--vbr' in args:
        i = args.index('--vbr')
        given = args[i + 1:i + 2]
        vbr = int(given[0], 16) if given else GAME_VBR
        del args[i:i + 1 + len(given)]
    duration, every, lo, hi, out = float(args[0]), float(args[1]), int(args[2], 16), int(args[3], 16), args[4]
    words = int(args[5]) if len(args) > 5 else 24
    game = [int(x, 16) for x in game] if game else None
    armed, ring, hit = game is None, collections.deque(maxlen=60), None
    t0 = time.time()
    t.go()
    while time.time() - t0 < duration:
        time.sleep(every)
        t.stop()
        g = t.regs()
        if g:
            row = state(g, t0)
            stack = t.read(g['r'][15], 4 * words)
            row['stack'] = [int.from_bytes(stack[i:i + 4], 'little') for i in range(0, len(stack), 4)]
            pc = g['pc'] & 0x1FFFFFFF
            if not armed and game[0] <= pc < game[1]:
                armed = True
                ring.clear()
            elif armed and (lo <= pc < hi or (vbr is not None and g['vbr'] != vbr)):
                hit = row
            ring.append(row)
            if hit:
                break
        t.go()
    if hit:
        t.go()                                          # the loop broke with the CPU stopped
    save_json(out, {'hit': hit, 'trail': list(ring)})
    print('stops kept %d | %s' % (len(ring), 'ended on pc %08X vbr %08X' % (hit['pc'], hit['vbr']) if hit else 'never ended'))


def cmd_bp(t, args):
    args = list(args)
    halt = option(args, '--halt', 1)
    after = option(args, '--after', 1)
    inside = option(args, '--in', 2)
    duration, out, wanted = float(args[0]), args[1], addresses(args[2:])
    if after:
        t.go()
        time.sleep(float(after[0]))
        t.stop()
    if inside:                                          # wait for the pc to be there: the loader has run by then
        lo, hi = [int(x, 16) for x in inside]
        end = time.time() + 60
        while time.time() < end:
            g = t.regs()
            if g and lo <= (g['pc'] & 0x1FFFFFFF) < hi:
                break
            t.go()
            time.sleep(0.25)
            t.stop()
    for a in wanted:
        t.bp_add(a)
    waiting, rows = set(wanted), []
    print('%d breakpoints set' % len(waiting))
    t0 = time.time()
    t.go()
    while waiting and time.time() - t0 < duration:
        packet = t.recv(1)
        if not packet:
            continue
        if packet[:1] not in 'ST':
            print('packet %r' % packet[:40])
            t.go()
            continue
        g = t.regs()
        if g:
            row = state(g, t0)
            rows.append(row)
            if g['pc'] in waiting:
                if halt:
                    save_stopped(t, halt[0], dict(row, g=g['all']))
                    t.bp_clear()
                    save_json(out, rows)
                    print('stopped at pc %08X pr %08X' % (g['pc'], g['pr']))
                    return
                t.bp_del(g['pc'])                       # once each: continuing over a breakpoint in place hits it again, for ever
                waiting.discard(g['pc'])
        t.go()
    t.stop()
    t.bp_clear()
    save_json(out, rows)
    print('hits %d, never hit %d: %s' % (len(rows), len(waiting), ' '.join('%08X' % a for a in sorted(waiting)[:20])))
    t.go()


def cmd_hook(t, args):
    duration = float(args[0])
    names = {}
    for x in args[1:]:
        address, _, name = x.partition('=')
        names[run_address(int(address, 16))] = name or address
    calls, hits = collections.Counter(), 0
    t.stop()
    for a in names:
        print('breakpoint %08X %s: %s' % (a, names[a], t.bp_add(a)))
    t0 = time.time()
    t.go()
    try:
        while time.time() - t0 < duration:
            packet = t.recv(0.5)
            if not packet or packet[:1] not in 'ST':
                continue
            g = t.regs()
            if g and g['pc'] in names:
                a = g['pc']
                hits += 1
                calls[(names[a], g['pr'], g['r'][4] if g['r'][4] < 0x10000 else None)] += 1    # r4 kept when small (a count, an id)
                t.bp_del(a)                             # step over the call's first instruction, then set it again
                t.cmd('s', 5)
                t.bp_add(a)
            t.go()
    finally:
        t.stop()
        ok = t.bp_clear()
        t.go()
    print('%d hits; breakpoints %s' % (hits, 'all removed and checked' if ok else 'NOT ALL REMOVED'))
    for (name, pr, r4), count in calls.most_common(60):
        print('  %5dx %-24s from %08X  r4 %s' % (count, name, pr, r4 if r4 is not None else 'address'))
    return calls


def cmd_snap(t, args):
    duration, lo, hi, prefix = float(args[0]), int(args[1], 16), int(args[2], 16), args[3]
    t0 = time.time()
    t.go()
    while time.time() - t0 < duration:
        time.sleep(0.01)
        t.stop()
        g = t.regs()
        if g and lo <= (g['pc'] & 0x1FFFFFFF) < hi:
            save_stopped(t, prefix, dict(state(g, t0), g=g['all']))
            print('stopped at pc %08X pr %08X' % (g['pc'], g['pr']))
            t.go()
            return
        t.go()
    print('the pc never came into the range')


def cmd_mem(t, args):
    print(t.cmd('m%X,%X' % (int(args[0], 16), int(args[1], 16))))
    t.go()


def cmd_write(t, args):
    t.stop()
    for k in range(0, len(args) - 1, 2):
        print(t.cmd('M%X,%X:%s' % (int(args[k], 16), len(args[k + 1]) // 2, args[k + 1])))
    t.go()


def cmd_dump(t, args):
    address, length, out = int(args[0], 16), int(args[1], 16), args[2]
    t.stop()
    with open(out, 'wb') as f:
        f.write(t.read(address, length))
    print('%d bytes from %08X' % (length, address))
    t.go()


def cmd_watch(t, args):
    """Flycast has no write watchpoint: the word is polled, and the pc logged is where the CPU was just after the change."""
    duration, out, address = float(args[0]), args[1], int(args[2], 16)
    rows, previous = [], None
    t0 = time.time()
    while time.time() - t0 < duration:
        t.go()
        time.sleep(0.003)
        t.stop()
        value = int.from_bytes(t.read(address, 4), 'little')
        if value != previous:
            g = t.regs()
            if g:
                rows.append(dict(state(g, t0), value=value))
                print('%.3f s: value %08X pc %08X pr %08X' % (time.time() - t0, value, g['pc'], g['pr']))
            previous = value
    save_json(out, rows)
    print('changes %d' % len(rows))
    t.go()


COMMANDS = {'running': cmd_running, 'sample': cmd_sample, 'trail': cmd_trail, 'bp': cmd_bp, 'hook': cmd_hook, 'snap': cmd_snap,
            'mem': cmd_mem, 'write': cmd_write, 'dump': cmd_dump, 'watch': cmd_watch}


def main(argv):
    if not argv or argv[0] not in COMMANDS:
        sys.exit(__doc__)
    t = connect()
    t.cmd('?')
    if COMMANDS[argv[0]](t, argv[1:]) is False:
        sys.exit(1)


if __name__ == '__main__':
    main(sys.argv[1:])
