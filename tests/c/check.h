/* check.h: what the C tests share. CHECK(condition, "what was wanted ...") prints the file, the line and the message when
   the condition is false, and the test goes on; check_done(name) prints the test's result and is its exit code (0 every
   check passed, 1 one failed). console_map(address, size) maps memory at a console address the runtime's C reads and
   writes (RAM at 0x8C000000, the registers at 0xA05F8000 ...): on macOS the tests are linked with a small page zero
   (tests/c/Makefile) so that the low 4 GB can be mapped. */
#ifndef CHECK_H
#define CHECK_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>

static int check_failures;

#define CHECK(cond, ...)                                                                                               \
    do {                                                                                                               \
        if (!(cond)) {                                                                                                 \
            check_failures++;                                                                                          \
            printf("FAIL %s:%d: ", __FILE__, __LINE__);                                                                \
            printf(__VA_ARGS__);                                                                                       \
            printf("\n");                                                                                              \
        }                                                                                                              \
    } while (0)

static inline int check_done(const char *name)
{
    printf("%s: %s\n", name, check_failures ? "FAILED" : "OK");
    return check_failures ? 1 : 0;
}

/* maps [address, address + size) zero-filled; exits with 2 (the test could not run) when it cannot */
static inline void console_map(uintptr_t address, size_t size)
{
    uintptr_t page = address & ~(uintptr_t)0xFFF;
    size_t len = (size + (address - page) + 0xFFF) & ~(size_t)0xFFF;
    if (mmap((void *)page, len, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON | MAP_FIXED, -1, 0) == MAP_FAILED) {
        perror("console_map");
        _Exit(2);
    }
}

#endif
