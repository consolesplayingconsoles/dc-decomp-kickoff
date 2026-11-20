/* test_bios.c: template/port/runtime/bios.c, the boot ROM's system calls. Run with the other C tests: make -C tests/c.

    sysinfo    the system information block (0x8C000068) holds the console ID, then the region bytes "11010": [3] '1' is the
               default language, English (with it at '0' the game's menus came up in Japanese)
    vectors    the install points the ROM's vectors in RAM at the addresses the dispatch table answers
    flash      reading the factory partition gives the region bytes; a write only clears bits, as flash does; an erase
               sets the partition back to 0xFF
    bounds     a read past the flash's end is refused (-1), nothing copied */
#include <string.h>

#include "check.h"
#include "bios.c"

int main(void)
{
    console_map(0x8C000000u, 0x10000);
    port_bios_install();

    CHECK(memcmp((const void *)0x8C000070u, "11010", 5) == 0, "sysinfo: the region bytes \"11010\" after the ID");
    CHECK(((const char *)0x8C000070u)[3] == '1', "sysinfo: the default language is English ('1')");
    CHECK(bios_sysinfo(0, 0, 0, 3) == (int32_t)0x8C000068u, "sysinfo: call 3 gives the block's address");
    CHECK(U32(0x8C0000B0u) == 0x8C000F00u && U32(0x8C0000B8u) == 0x8C000F20u && U32(0x8C0000BCu) == 0x8C000F30u,
          "vectors: system information, flash and GD-ROM at 0x8C000F00, F20, F30");

    uint32_t part = 0x8C002000u, buf = 0x8C003000u;
    CHECK(bios_flash(0, (int)part, 0, 0) == 0 && U32(part) == 0x1A000 && U32(part + 4) == 0x2000,
          "flash: partition 0 (factory) at 0x1A000, 0x2000 bytes");
    CHECK(bios_flash(0x1A000, (int)buf, 5, 1) == 5 && memcmp((const void *)(uintptr_t)buf, "11010", 5) == 0,
          "flash: the factory partition starts with the region bytes");

    uint32_t off = 0x10000;                            /* the game's partition, erased */
    *(volatile uint8_t *)(uintptr_t)buf = 0x0F;
    bios_flash((int)off, (int)buf, 1, 2);
    *(volatile uint8_t *)(uintptr_t)buf = 0xF3;
    bios_flash((int)off, (int)buf, 1, 2);
    bios_flash((int)off, (int)buf, 1, 1);
    CHECK(*(volatile uint8_t *)(uintptr_t)buf == 0x03, "flash: two writes leave the bits both cleared (0x0F & 0xF3 = 0x03), got %#x",
          *(volatile uint8_t *)(uintptr_t)buf);
    CHECK(bios_flash((int)off, 0, 0, 3) == 0, "flash: erase of the game's partition");
    bios_flash((int)off, (int)buf, 1, 1);
    CHECK(*(volatile uint8_t *)(uintptr_t)buf == 0xFF, "flash: erased back to 0xFF, got %#x", *(volatile uint8_t *)(uintptr_t)buf);

    memset((void *)(uintptr_t)buf, 0xAA, 16);
    CHECK(bios_flash(0x1FFF8, (int)buf, 16, 1) == -1, "bounds: a read past the end is refused");
    CHECK(*(volatile uint8_t *)(uintptr_t)buf == 0xAA, "bounds: nothing copied");
    return check_done("test_bios");
}
