/* test_system.c: template/port/runtime/system.c, the system calls the game makes that the host answers. Run with the other
   C tests: make -C tests/c.

    language   syBtCfgSet leaves the language byte (0x8C00007D) at 1, English: as a no-op it stayed 0 and Crazy Taxi's
               menus came up in Japanese
    clock      a clock count turns into a date and back to the same count
    epoch      count 0 is 1950-01-01 00:00, the console clock's start
    strcmp     the C runtime's strcmp compares signed bytes: a byte of 0xFF is below 'a' */
#include <string.h>

#include "check.h"
#include "system.c"

int main(void)
{
    console_map(0x8C000000u, 0x10000);

    *(volatile signed char *)0x8C00007Du = 0;
    sy_bt_cfg_set();
    CHECK(*(volatile signed char *)0x8C00007Du == 1, "language: English (1) at 0x8C00007D, got %d", *(volatile signed char *)0x8C00007Du);

    uint32_t date = 0x8C001000u;
    int32_t count = 1574000000;                       /* 1999-11-17 */
    sy_rtc_count_to_date((uint32_t)count, date);
    const uint8_t *d = (const uint8_t *)(uintptr_t)date;
    CHECK(sy_rtc_date_to_count(date) == count, "clock: the date back to the count %d, got %d", count, sy_rtc_date_to_count(date));

    sy_rtc_count_to_date(0, date);
    CHECK(*(const int16_t *)d == 1950 && d[2] == 1 && d[3] == 1 && d[4] == 0 && d[5] == 0 && d[6] == 0,
          "epoch: count 0 is 1950-01-01 00:00:00, got %d-%d-%d %d:%d:%d", *(const int16_t *)d, d[2], d[3], d[4], d[5], d[6]);

    char *a = (char *)0x8C002000u, *b = (char *)0x8C002100u;
    strcpy(a, "abc");
    strcpy(b, "abc");
    CHECK(slow_strcmp((uint32_t)(uintptr_t)a, (uint32_t)(uintptr_t)b) == 0, "strcmp: equal strings give 0");
    strcpy(b, "\xff");
    CHECK(slow_strcmp((uint32_t)(uintptr_t)a, (uint32_t)(uintptr_t)b) > 0, "strcmp: 'a' is above a signed 0xFF (-1)");
    return check_done("test_system");
}
