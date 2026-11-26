#!/usr/bin/env python3
"""tools/9-runtime/flycast_gdb.py against a stand-in target: no emulator, no game. What is protected: a breakpoint given on the 0C
mirror is set and counted on the 8C address the CPU reports; breakpoints are logged once, in order, and taken out with the
instruction checked; a trail ends at the first stop without the game's vector base; packets are read off a socket. Stdlib only."""
import io
import json
import os
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '9-runtime'))
import flycast_gdb as G  # noqa: E402

GAME = 0x8C00F400


def regs(pc, vbr=GAME, pr=0x8C010000):
    return {'r': [0] * 15 + [0x8C00F000], 'pc': pc, 'pr': pr, 'gbr': 0, 'vbr': vbr, 'sr': 0, 'all': ''}


class Fake(G.Target):
    """Memory in a dict; each `c` is followed by the next scripted stop."""

    def __init__(self, stops):
        self.saved = {}
        self.memory = {}
        self.stops = list(stops)
        self.now = None
        self.set = []

    def cmd(self, packet, timeout=10):
        if packet[0] == 'm':
            address, n = [int(x, 16) for x in packet[1:].split(',')]
            return ''.join('%02x' % self.memory.get(address + i, 9 if i % 2 == 0 else 0) for i in range(n))
        if packet[0] == 'Z':
            self.set.append(int(packet.split(',')[1], 16))
        return 'OK'

    def send(self, packet):
        pass

    def recv(self, timeout=10):
        if not self.stops:
            return None
        self.now = self.stops.pop(0)
        return 'S05'

    def stop(self):
        if self.stops:
            self.now = self.stops.pop(0)
        return 'S02'

    def regs(self):
        return self.now


def quiet(function, *args):
    with redirect_stdout(io.StringIO()):
        return function(*args)


class Addresses(unittest.TestCase):
    def test_mirrors_become_the_address_the_cpu_reports(self):
        self.assertEqual(G.run_address(0x0C22B560), 0x8C22B560)
        self.assertEqual(G.run_address(0x8C22B560), 0x8C22B560)
        self.assertEqual(G.run_address(0xA0000000), 0xA0000000)

    def test_a_file_of_addresses(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'a.txt')
            with open(path, 'w') as f:
                f.write('0C010000\n8C010004 8C010008\n')
            self.assertEqual(G.addresses(['@' + path, '0c01000c']), [0x8C010000, 0x8C010004, 0x8C010008, 0x8C01000C])


class Breakpoints(unittest.TestCase):
    def test_hook_counts_a_0c_address(self):
        t = Fake([regs(0, vbr=0), regs(0x8C010010), regs(0x8C010010)])
        calls = quiet(G.cmd_hook, t, ['0.05', '0C010010=f'])
        self.assertEqual(t.set[0], 0x8C010010, 'set where the CPU runs')
        self.assertEqual(sum(calls.values()), 2)
        self.assertEqual(t.saved, {}, 'every breakpoint taken out')

    def test_bp_logs_each_address_once_in_order(self):
        t = Fake([regs(0x8C010020), regs(0x8C010010)])
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'o.json')
            quiet(G.cmd_bp, t, ['1', out, '0C010010', '8C010020'])
            with open(out) as f:
                self.assertEqual([x['pc'] for x in json.load(f)], [0x8C010020, 0x8C010010])
        self.assertEqual(t.saved, {})


class Trail(unittest.TestCase):
    def test_ends_at_the_first_stop_without_the_game(self):
        t = Fake([regs(0x8C010000), regs(0x8C010002), regs(0x8C0000EC, vbr=0), regs(0x8C010004)])
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'o.json')
            quiet(G.cmd_trail, t, ['5', '0', '0', '0', out, '2', '--vbr'])
            with open(out) as f:
                result = json.load(f)
        self.assertEqual(result['hit']['pc'], 0x8C0000EC)
        self.assertEqual([x['pc'] for x in result['trail']], [0x8C010000, 0x8C010002, 0x8C0000EC])
        self.assertEqual(len(result['trail'][0]['stack']), 2)


class Running(unittest.TestCase):
    def test_waits_for_the_game_vector_base(self):
        t = Fake([regs(0x8C000800, vbr=0x8C000000), regs(0x8C010000)])
        self.assertTrue(quiet(G.cmd_running, t, ['5']))

    def test_says_when_it_never_runs(self):
        self.assertFalse(quiet(G.cmd_running, Fake([]), ['0.3']))


class Packets(unittest.TestCase):
    def test_a_packet_split_over_reads(self):
        here, there = socket.socketpair()
        self.addCleanup(here.close)
        self.addCleanup(there.close)
        t = G.Target(here)
        there.sendall(b'+$O')
        there.sendall(b'K#9a')
        self.assertEqual(t.recv(1), 'OK')


if __name__ == '__main__':
    unittest.main()
