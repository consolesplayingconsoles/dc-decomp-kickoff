#!/usr/bin/env python3
"""Hardware verification (scripts/dev/hwverify.py): run one function's test cases on the simulator and on the real
Dreamcast, over the serial cable, and compare. No game data, no hardware, no compiler: the simulator and the
console are stand-ins in this file, and the C the tool writes is checked as text.

    pool       how far past a function's own bytes its pc-relative loads reach (the literal pool must be copied too)
    case       a test case's registers and memory pokes become numbers; what the check cannot run is named, not skipped
    simresult  the simulator's answer reduced to what the console can be asked: r0 and the words the case poked
    harness    the C program for the console: the code at its own address, each case set up and its result printed
    output     the console's printed lines become results; other text (the loader's chatter) is ignored
    compare    each case is MATCH, DIFFER (with both values) or has no console result
    verify     the whole run with a fake simulator and console: every case is logged on both sides
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'dev'))

import hwverify  # noqa: E402


def words(*ws):
    out = b''
    for w in ws:
        out += bytes([w & 0xFF, (w >> 8) & 0xFF])
    return out


class PoolTest(unittest.TestCase):
    def test_a_function_with_no_pc_relative_load_ends_where_it_ends(self):
        code = words(0x6203, 0x000B, 0x0009)      # mov r0,r2 ; rts ; nop
        self.assertEqual(hwverify.pool_end(code, 0x8C001000), 0x8C001006)

    def test_a_long_load_reaches_its_literal(self):
        # mov.l @(2,pc),r4 at 0x1000: (0x1000 & ~3) + 4 + 2*4 = 0x100C, a 4-byte word: the pool ends at 0x1010
        code = words(0xD402, 0x000B, 0x0009)
        self.assertEqual(hwverify.pool_end(code, 0x8C001000), 0x8C001010)

    def test_a_word_load_reaches_its_literal(self):
        # mov.w @(3,pc),r1 at 0x1002: 0x1002 + 4 + 3*2 = 0x100C, a 2-byte word: ends at 0x100E
        code = words(0x0009, 0x9103, 0x000B)
        self.assertEqual(hwverify.pool_end(code, 0x8C001000), 0x8C00100E)

    def test_the_farthest_literal_wins(self):
        code = words(0xD400, 0xD503, 0x000B, 0x0009)
        # at 0x1000: (0x1000)+4+0 = 0x1004 -> 0x1008 ; at 0x1002: (0x1000)+4+12 = 0x1010 -> 0x1014
        self.assertEqual(hwverify.pool_end(code, 0x8C001000), 0x8C001014)


class CaseTest(unittest.TestCase):
    def test_pokes_and_registers_become_numbers(self):
        c = hwverify.parse_case({"regs": {"r4": "00000010", "r5": "FF"}, "poke": {"0c0f4270": "78563412"}})
        self.assertIsNone(c['unsupported'])
        self.assertEqual(c['regs'], {4: 0x10, 5: 0xFF})
        self.assertEqual(c['pokes'], [(0x0C0F4270, 0x12345678)])

    def test_an_empty_case_is_a_case(self):
        c = hwverify.parse_case({})
        self.assertIsNone(c['unsupported'])
        self.assertEqual((c['regs'], c['pokes']), ({}, []))

    def test_scripted_call_results_are_kept_in_order(self):
        c = hwverify.parse_case({"calls": [{"r0": "00000005"}, {}, {"r0": "FFFFFFFF"}]})
        self.assertIsNone(c['unsupported'])
        self.assertEqual(c['rets'], [5, 0, 0xFFFFFFFF])

    def test_what_cannot_run_is_named(self):
        for case, word in (({"dump": "ram.bin"}, 'dump'), ({"calls": [{"r0": "1", "poke_arg": {"r7": "00"}}]}, 'poke_arg'),
                           ({"calls": [{"fr0": 1.0}]}, 'fr0'),
                           ({"regs": {"fr4": 1.5}}, 'fr4'), ({"poke": {"0C000000": "0102"}}, 'poke')):
            c = hwverify.parse_case(case)
            self.assertIsNotNone(c['unsupported'], case)
            self.assertIn(word, c['unsupported'])


class SimResultTest(unittest.TestCase):
    def test_r0_and_the_final_word_at_each_poked_address(self):
        sim = {"error": None, "out": {"r0": "00000B71"}, "writes": [["0C0F4270", 4, "0B719151"]]}
        r = hwverify.sim_result(sim, [(0x0C0F4270, 0x12345678)])
        self.assertEqual(r, {'r0': 0xB71, 'mem': {0x0C0F4270: 0x0B719151}, 'calls': []})

    def test_the_calls_with_what_was_set_for_them(self):
        sim = {"error": None, "out": {"r0": "0"}, "writes": [],
               "calls": [{"to": "8C0F7CF0", "kind": "call", "r4-r7": ["40200000", "0", "0", "0"],
                          "chg": [True, False, False, False], "stack": "0EADBEE0",
                          "stackchg": [False] + [False] * 15}]}
        r = hwverify.sim_result(sim, [])
        self.assertEqual(r['calls'], [{'to': 0x8C0F7CF0, 'args': [0x40200000, 0, 0, 0],
                                       'chg': [True, False, False, False], 'stack': 0x0EADBEE0, 'stackchg': False}])

    def test_an_address_the_function_did_not_write_keeps_its_poked_value(self):
        sim = {"error": None, "out": {"r0": "00000000"}, "writes": []}
        r = hwverify.sim_result(sim, [(0x0C000010, 7)])
        self.assertEqual(r['mem'], {0x0C000010: 7})

    def test_a_write_through_another_mirror_of_the_poked_word_counts(self):
        # the simulator reports writes at the physical mirror (0C...); the case poked the cached one (8C...)
        sim = {"error": None, "out": {"r0": "0"}, "writes": [["0C2873C4", 4, "00000000"]]}
        self.assertEqual(hwverify.sim_result(sim, [(0x8C2873C4, 2)])['mem'], {0x8C2873C4: 0})

    def test_the_last_write_to_an_address_wins(self):
        sim = {"error": None, "out": {"r0": "0"}, "writes": [["0C000010", 4, "00000001"], ["0C000010", 4, "00000002"]]}
        self.assertEqual(hwverify.sim_result(sim, [(0x0C000010, 0)])['mem'][0x0C000010], 2)

    def test_a_simulator_error_is_an_error_not_a_result(self):
        with self.assertRaises(hwverify.SimError):
            hwverify.sim_result({"error": "unimplemented opcode"}, [])


class HarnessTest(unittest.TestCase):
    def setUp(self):
        self.src = hwverify.render_harness(b'\x01\x02\x03\x04', 0x0C049818, 0x0C04981E,
                                           [{'regs': {4: 5}, 'pokes': [(0x0C0F4270, 0xDEADBEEF)]}, {'regs': {}, 'pokes': []}],
                                           [0x0C0F4270])

    def test_the_code_is_written_through_the_uncached_mirror_and_run_from_it(self):
        self.assertIn('0xAC049818', self.src)
        self.assertIn('0xAC04981E', self.src)

    def test_data_is_touched_at_the_address_the_function_uses(self):
        self.assertIn('0x0C0F4270', self.src)
        self.assertNotIn('0xAC0F4270', self.src)

    def test_every_case_and_its_values_are_in_the_program(self):
        self.assertIn('0xDEADBEEF', self.src)
        self.assertIn('CASE', self.src)
        self.assertIn('0x01', self.src)

    def test_the_program_reads_back_the_checked_addresses(self):
        self.assertIn('M ', self.src)


class WriteTest(unittest.TestCase):
    """The loader's write call carries a whole buffer; a program that prints in fragments (a few bytes per call)
    puts the loader's protocol out of step and the console stops answering. A case's result is one write."""

    def src(self, checks):
        return hwverify.render_harness(b'\x00', 0x0C001000, 0x0C001000,
                                       [{'regs': {}, 'pokes': [(a, 1) for a in checks]}], checks)

    def test_a_result_is_written_in_one_call(self):
        src = self.src([0x0C000010, 0x0C000020])
        self.assertEqual(src.count('write(1, line, p)'), 1)
        self.assertIn('write(1, line, p)', src)

    def test_no_fragment_printer_is_left(self):
        self.assertNotIn('put(', self.src([0x0C000010]))

    def test_the_line_buffer_holds_the_longest_result(self):
        # "CASE nn R0 XXXXXXXX" is 19 characters, each checked word " M AAAAAAAA=VVVVVVVV" is 20, the stack pointer
        # " S XXXXXXXX" 11, plus the newline
        src = self.src([0x0C000010] * 3)
        self.assertIn('char line[%d]' % (19 + 20 * 3 + 11 + 2), src)


class MarkerTest(unittest.TestCase):
    """The program says how far it got, a whole line at a time, so a console that stops answering still leaves a
    trail in the log: started, done."""

    def setUp(self):
        self.src = hwverify.render_harness(b'\x01\x02', 0x0C001000, 0x0C001000,
                                           [{'regs': {4: 1}, 'pokes': [(0x0C000010, 5)]}, {'regs': {}, 'pokes': []}],
                                           [0x0C000010])

    def test_the_first_write_comes_after_the_code_is_in_place(self):
        # the order of the program that is known to run on the console: copy the code, then talk
        self.assertLess(self.src.index('dst[k] = blob[k]'), self.src.index('write(1, "hwverify start'))

    def test_it_announces_itself_then_says_when_it_is_done(self):
        self.assertIn('write(1, "hwverify start\\n", 15)', self.src)
        self.assertIn('write(1, "hwverify done\\n", 14)', self.src)
        self.assertLess(self.src.index('hwverify start'), self.src.index('hwverify done'))
        self.assertEqual(self.src.count('write(1, "'), 2)

    def test_the_cases_are_tables_walked_by_a_loop_not_repeated_code(self):
        self.assertIn('for (n = 0; n < 2; n++)', self.src)
        self.assertEqual(self.src.count('hw_enter(args'), 1)

    def test_a_case_pokes_only_the_words_it_names(self):
        # case 0 names the checked word, case 1 names none: the second case's mask is 0
        self.assertIn('pokem[2] = {0x00000001u,0x00000000u}', self.src)


class EdataTest(unittest.TestCase):
    """The loader's startup code clears the BSS with 4-byte stores from _edata: an _edata that is not a multiple of
    4 (read-only data of an odd size ends the image there) is an address error before main runs, and the console stops
    answering. The program keeps one initialized word in .data so _edata lands on a word, and the tool reads _edata
    from the linked program and refuses to upload one that is not aligned."""

    def test_the_program_keeps_a_word_in_data(self):
        src = hwverify.render_harness(b'\x00', 0x0C001000, 0x0C001000, [], [])
        self.assertIn('int hwverify_edata_word = 1;', src)
        self.assertNotIn('static int hwverify_edata_word', src)

    def test_edata_is_read_from_the_symbol_list(self):
        nm = "8c0105d0 B __bss_start\n8c01069e B _edata\n8c0106a8 B _end\n"
        self.assertEqual(hwverify.edata_from_nm(nm), 0x8C01069E)

    def test_no_edata_symbol_is_none(self):
        self.assertIsNone(hwverify.edata_from_nm("8c010000 T start\n"))

    def test_an_aligned_edata_passes_and_an_odd_one_is_named(self):
        self.assertEqual(hwverify.edata_problem(0x8C0105D0), '')
        self.assertIn('8C01069E', hwverify.edata_problem(0x8C01069E))
        self.assertIn('8C01069E', hwverify.edata_problem(0x8C01069E).upper())
        self.assertNotEqual(hwverify.edata_problem(None), '')


class OutputTest(unittest.TestCase):
    def test_result_lines_are_parsed_and_the_rest_ignored(self):
        text = ("Console enabled\nUpload <x>\nexecuting\nCASE 0 R0 000041C6 M 0C0F4270=41C67EA6\n"
                "noise\nCASE 1 R0 00000000 M 0C0F4270=00003039\n")
        r = hwverify.parse_output(text)
        self.assertEqual(r[0], {'r0': 0x41C6, 'mem': {0x0C0F4270: 0x41C67EA6}, 'calls': []})
        self.assertEqual(r[1], {'r0': 0, 'mem': {0x0C0F4270: 0x3039}, 'calls': []})
        self.assertEqual(sorted(r), [0, 1])

    def test_the_calls_a_case_made_are_parsed_in_order(self):
        text = ("CASE 0 R0 00000000 M 0C2873C4=00000000 C 8C0F7CF0 40200000 00000000 00000000 00000000 8CFFFFA0"
                " C 8C0F7CF0 00000001 00000002 00000003 00000004 00000005\n")
        r = hwverify.parse_output(text)[0]
        self.assertEqual(r['mem'], {0x0C2873C4: 0})
        self.assertEqual(r['calls'], [{'to': 0x8C0F7CF0, 'args': [0x40200000, 0, 0, 0], 'stack': 0x8CFFFFA0},
                                      {'to': 0x8C0F7CF0, 'args': [1, 2, 3, 4], 'stack': 5}])

    def test_too_many_calls_is_said(self):
        r = hwverify.parse_output("CASE 0 R0 00000000 C OVERFLOW\n")[0]
        self.assertEqual(r['calls'], 'OVERFLOW')

    def test_no_result_lines_give_nothing(self):
        self.assertEqual(hwverify.parse_output('executing\n'), {})


class CompareTest(unittest.TestCase):
    def test_equal_results_match(self):
        a = {'r0': 1, 'mem': {16: 2}}
        self.assertEqual(hwverify.compare(a, dict(a))[0], 'MATCH')

    def test_a_different_r0_differs_and_says_both_values(self):
        status, why = hwverify.compare({'r0': 1, 'mem': {}}, {'r0': 2, 'mem': {}})
        self.assertEqual(status, 'DIFFER')
        self.assertIn('r0', why)
        self.assertIn('00000001', why)
        self.assertIn('00000002', why)

    def test_a_different_word_in_memory_differs(self):
        status, why = hwverify.compare({'r0': 1, 'mem': {16: 2}}, {'r0': 1, 'mem': {16: 3}})
        self.assertEqual(status, 'DIFFER')
        self.assertIn('00000010', why)

    def test_a_missing_console_result_is_its_own_status(self):
        self.assertEqual(hwverify.compare({'r0': 1, 'mem': {}}, None)[0], 'NO CONSOLE RESULT')

    SIMCALL = {'to': 0x8C0F7CF0, 'args': [0x40200000, 7, 0, 0], 'chg': [True, False, False, False],
               'stack': 0x0EADBEE0, 'stackchg': False}

    def cmp_calls(self, hw_calls, sim_calls=None):
        return hwverify.compare({'r0': 0, 'mem': {}, 'calls': [self.SIMCALL] if sim_calls is None else sim_calls},
                                {'r0': 0, 'mem': {}, 'calls': hw_calls})

    def test_the_same_calls_match_and_leftover_registers_and_stack_are_not_compared(self):
        # r5 and the stack word were not set for the call (chg / stackchg false): what they hold is not an argument
        self.assertEqual(self.cmp_calls([{'to': 0x8C0F7CF0, 'args': [0x40200000, 9, 9, 9], 'stack': 0x8CFFFFA0}])[0], 'MATCH')

    def test_a_different_argument_differs(self):
        status, why = self.cmp_calls([{'to': 0x8C0F7CF0, 'args': [1, 7, 0, 0], 'stack': 0}])
        self.assertEqual(status, 'DIFFER')
        self.assertIn('call 1', why)
        self.assertIn('r4', why)

    def test_a_different_target_or_count_differs(self):
        self.assertEqual(self.cmp_calls([{'to': 0x8C000000, 'args': [0x40200000, 0, 0, 0], 'stack': 0}])[0], 'DIFFER')
        self.assertEqual(self.cmp_calls([])[0], 'DIFFER')

    def test_too_many_calls_on_the_console_differs(self):
        self.assertEqual(self.cmp_calls('OVERFLOW')[0], 'DIFFER')


class CallTargetsTest(unittest.TestCase):
    """A call the function makes is answered by a stub at the callee's address, so the callee's address must be known
    before the run: a bsr/bra out of the function, or a jsr/jmp through a register loaded from the literal pool. A
    target computed at run time is not stubbed yet: the function is refused with the reason."""

    @staticmethod
    def code(*words):
        return b''.join(bytes([w & 0xFF, w >> 8]) for w in words)

    def test_jsr_through_a_pool_word_is_resolved(self):
        # 0: mov.l @(4,pc),r3 -> pool at 8 (pc 0: (0&~3)+4+1*4 = 8); 2: mov r4,r2; 4: jsr @r3; 6: nop; 8: pool
        blob = self.code(0xD301, 0x6243, 0x430B, 0x0009) + bytes([0xF0, 0x7C, 0x0F, 0x8C])
        self.assertEqual(hwverify.call_targets(blob, 0x8C010000, 8), ([0x8C0F7CF0], []))

    def test_bsr_out_is_resolved(self):
        blob = self.code(0xB07E, 0x0009, 0x000B, 0x0009)     # bsr 8C010100 at 0
        self.assertEqual(hwverify.call_targets(blob, 0x8C010000, 8), ([0x8C010100], []))

    def test_a_register_written_otherwise_is_not_resolved(self):
        blob = self.code(0xD301, 0x7304, 0x430B, 0x0009) + bytes(4)   # add #4,r3 between the load and the jsr
        targets, problems = hwverify.call_targets(blob, 0x8C010000, 8)
        self.assertEqual(targets, [])
        self.assertIn('jsr @r3', problems[0])

    def test_bsrf_is_not_resolved(self):
        self.assertEqual(len(hwverify.call_targets(self.code(0x0203, 0x0009), 0x8C010000, 4)[1]), 1)


class StubTest(unittest.TestCase):
    """The stub at a callee's address: push r1, point r0 at its two literal words (the callee's address, the shared
    recorder), jump to the recorder with r0 = the callee's address. Nothing else is touched."""

    def test_the_stub_code_and_where_its_words_go(self):
        words, lit = hwverify.stub_code(0x8C0F7CF0)
        # mova at +2: pc 8C0F7CF2, base (pc & ~3) + 4 = 8C0F7CF4; the words go at the first 4-aligned spot past the code
        self.assertEqual(words[0], 0x2F16)                    # mov.l r1,@-r15
        self.assertEqual(words[1] & 0xFF00, 0xC700)           # mova @(disp,pc),r0
        self.assertEqual(words[2:5], [0x5101, 0x412B, 0x6002])  # mov.l @(4,r0),r1; jmp @r1; mov.l @r0,r0
        self.assertEqual(lit % 4, 0)
        self.assertEqual(lit, ((0x8C0F7CF2 & ~3) + 4 + (words[1] & 0xFF) * 4) - 0x8C0F7CF0)
        self.assertGreaterEqual(lit, 10)

    def test_stubs_that_would_overlap_the_function_or_each_other_are_problems(self):
        self.assertEqual(hwverify.stub_problems([0x8C020000], 0x8C010000, 0x8C010040), [])
        self.assertTrue(hwverify.stub_problems([0x8C010030], 0x8C010000, 0x8C010040))
        self.assertTrue(hwverify.stub_problems([0x8C020000, 0x8C020008], 0x8C010000, 0x8C010040))

    def test_the_program_installs_the_stubs_and_resets_the_call_list_per_case(self):
        src = hwverify.render_harness(b'\x00\x09', 0x0C001000, 0x0C001000,
                                      [{'regs': {}, 'pokes': [], 'rets': [5]}], [], [0x8C0F7CF0])
        self.assertIn('_hw_stub_common', src)
        self.assertIn('0xAC0F7CF0', src)                      # the stub is written through the uncached mirror
        self.assertIn('hw_callp = hw_calls', src)
        self.assertIn(' C', src)
        self.assertNotIn('%%', src)                           # C, not a leftover of Python formatting


class IncludeTest(unittest.TestCase):
    def test_the_loader_headers_next_to_the_runtime_come_first(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            rt = os.path.join(d, 'example-src')
            inc = os.path.join(d, 'target-inc')
            os.makedirs(rt)
            os.makedirs(inc)
            self.assertEqual(hwverify.include_dirs(rt), [inc, rt])

    def test_without_them_only_the_runtime_is_searched(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            rt = os.path.join(d, 'example-src')
            os.makedirs(rt)
            self.assertEqual(hwverify.include_dirs(rt), [rt])

    def test_the_program_hands_write_the_plain_char_buffer_the_loader_header_declares(self):
        src = hwverify.render_harness(b'\x00', 0x0C001000, 0x0C001000, [], [])
        self.assertIn('write(1, line, p)', src)
        self.assertIn('char line[', src)
        self.assertNotIn('const char line', src)


class PortTest(unittest.TestCase):
    def test_only_usb_serial_devices_are_candidates(self):
        names = ['/dev/cu.Bluetooth-Incoming-Port', '/dev/cu.usbserial-1440', '/dev/cu.BLTH', '/dev/cu.usbmodem14101',
                 '/dev/ttyUSB0', '/dev/tty.usbserial-1440', '/dev/ttyS0']
        self.assertEqual(hwverify.serial_candidates(names),
                         ['/dev/cu.usbmodem14101', '/dev/cu.usbserial-1440', '/dev/ttyUSB0'])

    def test_the_device_that_answers_is_the_port_whatever_its_number(self):
        probe = lambda p: 'dcload-serial 1.0.6' if p.endswith('1440') else ''
        self.assertEqual(hwverify.find_port(['/dev/cu.usbserial-1430', '/dev/cu.usbserial-1440'], probe),
                         '/dev/cu.usbserial-1440')

    def test_a_single_device_that_does_not_answer_is_named_in_the_error(self):
        with self.assertRaises(hwverify.PortError) as cm:
            hwverify.find_port(['/dev/cu.usbserial-1440'], lambda p: '')
        self.assertIn('/dev/cu.usbserial-1440', str(cm.exception))
        self.assertIn('did not answer', str(cm.exception))

    def test_no_device_at_all_says_so(self):
        with self.assertRaises(hwverify.PortError) as cm:
            hwverify.find_port([], lambda p: 'x')
        self.assertIn('no USB serial', str(cm.exception))

    def test_an_answer_that_is_not_dcload_does_not_count(self):
        with self.assertRaises(hwverify.PortError):
            hwverify.find_port(['/dev/cu.usbserial-1'], lambda p: 'some other modem')


class LoaderTest(unittest.TestCase):
    """The loader on the console is dcload-serial 1.0.7-cpc (KallistiOS's 1.0.7 with the crash report sent to the
    PC); the tool reads the version from the probe's answer and says so when it is another one, because the host tool
    and the loader are a pair and the stock 1.0.7 tells the PC nothing when a case crashes."""

    def test_the_version_is_read_from_the_probe_answer(self):
        self.assertEqual(hwverify.loader_version('Vdcload-serial 1.0.7-cpc\n\r'), '1.0.7-cpc')
        self.assertEqual(hwverify.loader_version('Vdcload-serial 1.0.7\n\r'), '1.0.7')
        self.assertEqual(hwverify.loader_version('dcload-serial 1.0.6'), '1.0.6')

    def test_an_answer_with_no_version_has_none(self):
        self.assertIsNone(hwverify.loader_version('dcload-ip'))
        self.assertIsNone(hwverify.loader_version(''))

    def test_the_expected_version_has_no_warning(self):
        self.assertEqual(hwverify.loader_warning('1.0.7-cpc'), '')

    def test_the_stock_loader_is_a_warning(self):
        self.assertIn('1.0.7-cpc', hwverify.loader_warning('1.0.7'))

    def test_another_version_is_named_in_the_warning(self):
        w = hwverify.loader_warning('1.0.6')
        self.assertIn('1.0.6', w)
        self.assertIn('1.0.7-cpc', w)

    def test_an_unreadable_version_is_a_warning_too(self):
        self.assertIn('1.0.7-cpc', hwverify.loader_warning(None))


class ExitStatusTest(unittest.TestCase):
    """0 every case matched (or --dry-run wrote the program), 1 a case did not match on the console, 2 nothing could
    be run."""

    def rows(self, *statuses):
        return [{'status': s, 'sim': None if s == 'NOT RUN' else {'r0': 0, 'mem': {}}} for s in statuses]

    def test_all_matched_is_0(self):
        self.assertEqual(hwverify.exit_status(self.rows('MATCH', 'MATCH', 'NOT RUN'), False), 0)

    def test_a_console_crash_is_1(self):
        self.assertEqual(hwverify.exit_status(self.rows('MATCH', 'CONSOLE CRASH', 'NOT RUN'), False), 1)

    def test_a_difference_or_no_console_result_is_1(self):
        self.assertEqual(hwverify.exit_status(self.rows('MATCH', 'DIFFER'), False), 1)
        self.assertEqual(hwverify.exit_status(self.rows('NO CONSOLE RESULT'), False), 1)

    def test_nothing_runnable_is_2(self):
        self.assertEqual(hwverify.exit_status(self.rows('NOT RUN', 'NOT RUN'), False), 2)
        self.assertEqual(hwverify.exit_status(self.rows('NOT RUN'), True), 2)

    def test_a_dry_run_that_wrote_the_program_is_0(self):
        self.assertEqual(hwverify.exit_status(self.rows('NO CONSOLE RESULT', 'NOT RUN'), True), 0)


class CrashTest(unittest.TestCase):
    """When a case crashes the console, the loader sends its exception report and dc-tool-ser prints it as one
    EXCEPTION line. The cases run in order in one program, so the crash belongs to the first case with no result."""

    LINE = ('EXCEPTION 0E0 address error (read) PC=8C014C3A PR=8C010122 SR=500000F0 R0=00000000 R1=FFFFFFFF '
            'R2=00000000 R3=00000000 R4=FFFFFFFF R5=00000000 R6=00000000 R7=00000000 R8=00000000 R9=00000000 '
            'R10=00000000 R11=00000000 R12=00000000 R13=00000000 R14=00000000 R15=8C00F3D0')

    def test_the_exception_line_is_found_in_the_output(self):
        text = 'hwverify start\nCASE 0 R0 00000001\n' + self.LINE + '\n'
        self.assertEqual(hwverify.parse_crash(text), self.LINE)

    def test_output_without_a_crash_has_none(self):
        self.assertIsNone(hwverify.parse_crash('hwverify start\nCASE 0 R0 00000001\nhwverify done\n'))

    def test_the_crash_is_the_first_case_without_a_result_and_the_rest_did_not_run(self):
        cases = [{"poke": {"0C000010": "0%d000000" % i}} for i in range(1, 4)]

        def sim(case):
            return {"error": None, "out": {"r0": "00000001"}, "writes": []}

        def hw(src, info):
            return 'hwverify start\nCASE 0 R0 00000001 M 0C000010=00000001\n' + self.LINE + '\n'

        log = []
        rows = hwverify.verify(b'\x00\x09', 0x0C001000, 0x0C001000, cases, sim, hw, log.append)
        self.assertEqual([r['status'] for r in rows], ['MATCH', 'CONSOLE CRASH', 'NOT RUN'])
        self.assertIn('PC=8C014C3A', rows[1]['why'])
        self.assertIn('case 2', rows[2]['why'])
        self.assertIn('PC=8C014C3A', '\n'.join(log))


class ReplugTest(unittest.TestCase):
    def test_a_console_that_stopped_answering_is_told_to_replug(self):
        with self.assertRaises(hwverify.PortError) as cm:
            hwverify.find_port(['/dev/cu.usbserial-1'], lambda p: '')
        self.assertIn('replug', str(cm.exception).lower())


class SimulatorPathTest(unittest.TestCase):
    def test_the_repo_simulator_is_in_its_sim_folder(self):
        self.assertEqual(hwverify.simulator_path('/r'), os.path.join('/r', 'tools', 'sim', 'sh4sim.py'))


class WaitTest(unittest.TestCase):
    """--wait: keep asking until the console answers, so a run can be started before the console is ready."""

    def clock(self):
        t = [0.0]
        return (lambda: t[0]), (lambda s: t.__setitem__(0, t[0] + s))

    def test_it_returns_the_port_as_soon_as_one_answers(self):
        now, sleep = self.clock()
        answers = [hwverify.PortError('no answer'), hwverify.PortError('no answer'), '/dev/cu.usbserial-9']

        def find():
            a = answers.pop(0)
            if isinstance(a, Exception):
                raise a
            return a
        self.assertEqual(hwverify.wait_for_port(find, 60, 2, now, sleep), '/dev/cu.usbserial-9')
        self.assertEqual(answers, [])

    def test_it_gives_up_after_the_limit_with_the_last_reason(self):
        now, sleep = self.clock()

        def find():
            raise hwverify.PortError('still silent')
        with self.assertRaises(hwverify.PortError) as cm:
            hwverify.wait_for_port(find, 10, 2, now, sleep)
        self.assertIn('still silent', str(cm.exception))
        self.assertIn('10', str(cm.exception))

    def test_a_limit_of_zero_asks_once(self):
        now, sleep = self.clock()
        calls = []

        def find():
            calls.append(1)
            raise hwverify.PortError('x')
        with self.assertRaises(hwverify.PortError):
            hwverify.wait_for_port(find, 0, 2, now, sleep)
        self.assertEqual(len(calls), 1)


class VerifyTest(unittest.TestCase):
    def cases(self):
        return [{"poke": {"0C000010": "01000000"}}, {"poke": {"0C000010": "02000000"}}, {"dump": "x.bin"}]

    def test_every_case_is_run_on_both_and_logged(self):
        log = []

        def sim(case):
            v = int(case['poke']['0C000010'][:2], 16)
            return {"error": None, "out": {"r0": "%08X" % (v * 2)}, "writes": [["0C000010", 4, "%08X" % v]]}

        def hw(src, blob_info):
            return "CASE 0 R0 00000002 M 0C000010=00000001\nCASE 1 R0 00000009 M 0C000010=00000002\n"

        rows = hwverify.verify(b'\x00\x09', 0x0C001000, 0x0C001000, self.cases(), sim, hw, log.append)
        self.assertEqual([r['status'] for r in rows], ['MATCH', 'DIFFER', 'NOT RUN'])
        text = '\n'.join(log)
        self.assertIn('case 1', text)
        self.assertIn('simulator', text)
        self.assertIn('console', text)
        self.assertIn('unsupported', text)

    def test_when_nothing_is_runnable_the_console_is_not_called(self):
        called = []
        rows = hwverify.verify(b'\x00\x09', 0x0C001000, 0x0C001000, [{"dump": "x"}], lambda c: {}, lambda s, b: called.append(1) or '', lambda m: None)
        self.assertEqual(called, [])
        self.assertEqual(rows[0]['status'], 'NOT RUN')



class DataWordsTest(unittest.TestCase):
    """The original reads the game's data (tables, globals) that the simulator has from the executable and the console
    does not: each word it read is poked on the console before every case, with what the simulator saw at the start (the
    executable's bytes inside the image, 0 in the rest of RAM). The stack and hardware registers are left out."""

    def test_words_read_get_the_image_value_or_zero(self):
        image = (0x0C010000, bytes(range(16)))
        reads = [0x0C010004, 0x0C010006, 0x0C500000, 0x0DFFFEF0, 0x005F810C]
        self.assertEqual(hwverify.data_words(reads, image), {0x8C010004: 0x07060504, 0x8C500000: 0})

    def test_the_program_area_is_left_out(self):
        self.assertEqual(hwverify.data_words([0x0CF00010, 0x0CFFFF00], (0x0C010000, b'')), {})

    def test_the_loader_below_8C010000_is_left_out(self):
        self.assertEqual(hwverify.data_words([0x0C004000, 0x0C00F3FC, 0x0C000100], (0x0C010000, b'')), {})

    def test_the_program_pokes_them_before_each_case(self):
        src = hwverify.render_harness(b'\x00\x09', 0x0C001000, 0x0C001000, [{'regs': {}, 'pokes': []}], [],
                                      data={0x8C500000: 7})
        self.assertIn('0x8C500000u', src)
        self.assertIn('0x00000007u', src)
        self.assertLess(src.index('datav[j]'), src.index('hw_enter(args'))


class StackRelativeTest(unittest.TestCase):
    """An argument that is an address in the caller's stack frame differs between the simulator (its stack starts at
    0DFFFF00) and the console (wherever the program's stack is): it is compared as an offset from each side's stack
    pointer at the function's entry."""

    SIM = {'to': 0x8C000000, 'args': [0x0DFFFE84, 0, 0, 0], 'chg': [True, False, False, False],
           'stack': 0x0DFFFE90, 'stackchg': True}

    def test_the_same_offset_matches(self):
        hw = {'to': 0x8C000000, 'args': [0x8CFFF82C, 0, 0, 0], 'stack': 0x8CFFF838}
        self.assertEqual(hwverify.compare_calls([self.SIM], [hw], 0x8CFFF8A8), [])

    def test_a_different_offset_differs(self):
        hw = {'to': 0x8C000000, 'args': [0x8CFFF830, 0, 0, 0], 'stack': 0x8CFFF838}
        self.assertTrue(hwverify.compare_calls([self.SIM], [hw], 0x8CFFF8A8))

    def test_the_console_stack_pointer_is_read_from_the_line(self):
        r = hwverify.parse_output("CASE 0 R0 00000000 S 8CFFF8A8 C 8C000000 8CFFF82C 00000000 00000000 00000000 00000000\n")[0]
        self.assertEqual(r['sp'], 0x8CFFF8A8)
        self.assertEqual(len(r['calls']), 1)


class ProgramPlaceTest(unittest.TestCase):
    """The program is linked high in RAM, under the stack, not at 8C010000 where the game's code is: a callee there
    would need its stub on top of the program."""

    def test_the_linker_script_is_moved(self):
        text = '  PROVIDE (__executable_start = 0x8c010000); . = 0x8c010000;\n'
        self.assertEqual(hwverify.moved_script(text), text.replace('0x8c010000', '0x%08x' % hwverify.PROGRAM_AT))

    def test_the_place_is_above_game_code_and_under_the_stack(self):
        self.assertTrue(0x8C800000 <= hwverify.PROGRAM_AT < 0x8D000000)

    def test_a_function_can_make_more_calls(self):
        self.assertGreaterEqual(hwverify.MAX_CALLS, 512)


class GapsTest(unittest.TestCase):
    def test_only_the_words_the_case_set_are_compared(self):
        # the program prints every word any case checks; a case that did not set one says nothing about it
        sim = {'r0': 0, 'mem': {0x0C000010: 1}, 'calls': []}
        hw = {'r0': 0, 'mem': {0x0C000010: 1, 0x0C000020: 0}, 'calls': []}
        self.assertEqual(hwverify.compare(sim, hw)[0], 'MATCH')

    def test_an_address_in_the_function_itself_compares_across_mirrors(self):
        # the code runs from the uncached mirror: a pc-relative address comes out AC.. on the console, 8C.. in the simulator
        sim = {'r0': 0x8C0EE90C, 'mem': {}, 'calls': []}
        self.assertEqual(hwverify.compare(sim, {'r0': 0xAC0EE90C, 'mem': {}, 'calls': []}, (0x8C0EE800, 0x8C0EEA00))[0], 'MATCH')
        self.assertEqual(hwverify.compare(sim, {'r0': 0xAC0EE90C, 'mem': {}, 'calls': []}, (0x8C000000, 0x8C000100))[0], 'DIFFER')

    def test_a_read_outside_ram_is_named(self):
        # the boot ROM, open bus: the simulator answers 0, the console the real bytes (a list header read at 18 hung it)
        self.assertIn('00000018', hwverify.outside_ram([0x0C010000, 0x00000018, 0x0DFFFEF0]))
        self.assertEqual(hwverify.outside_ram([0x0C010000, 0x0DFFFEF0, 0x8C800000]), '')

    def test_the_way_in_zeroes_the_stack_below_and_clears_t(self):
        src = hwverify.render_harness(b'\x00\x09', 0x0C001000, 0x0C001000, [{'regs': {}, 'pokes': []}], [])
        self.assertIn('_hw_enter', src)
        self.assertIn('clrt', src)
        self.assertIn('mov.l r0,@-r1', src)


if __name__ == '__main__':
    unittest.main()
