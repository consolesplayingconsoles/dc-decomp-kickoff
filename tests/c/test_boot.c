/* test_boot.c: template/port/runtime/boot.c, the debug log a watcher follows (tools/10-port/capture.sh waits for its
   "main mode M, sub-mode S" line). Run with the other C tests: make -C tests/c (in the port image).

    first      the first frame prints the game's mode and sub-mode, with the frame
    quiet      a frame where neither changed prints nothing
    change     a change of either prints a new line, with that frame's number

   The game's two words sit at addresses this test maps (test_boot_game.h stands in for the game's game.h). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>

static int failures;
#define CHECK(cond, ...)                                                                                               \
    do {                                                                                                               \
        if (!(cond)) {                                                                                                 \
            failures++;                                                                                                \
            printf("FAIL %s:%d: ", __FILE__, __LINE__);                                                                \
            printf(__VA_ARGS__);                                                                                       \
            printf("\n");                                                                                              \
        }                                                                                                              \
    } while (0)

unsigned long port_frames;
void port_boot_step(void);

static char out[4096];

/* one frame: the words set, port_boot_step run with stderr into a file; what it printed */
static const char *frame(unsigned long n, int mode, int sub)
{
    *(volatile int *)GAME_MAIN_MODE = mode;
    *(volatile int *)GAME_SUB_MODE = sub;
    port_frames = n;
    fflush(stderr);
    FILE *f = freopen("build/test_boot.err", "w+", stderr);
    port_boot_step();
    fflush(stderr);
    memset(out, 0, sizeof out);
    rewind(f);
    size_t got = fread(out, 1, sizeof out - 1, f);
    out[got] = 0;
    return out;
}

int main(void)
{
    if (mmap((void *)(GAME_MAIN_MODE & ~0xFFFul), 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0) == MAP_FAILED) {
        perror("mmap");
        return 2;
    }
    setenv("PORT_BOOT_LOG", "1", 1);
    const char *s = frame(4, 3, 0);
    CHECK(strcmp(s, "test: boot: frame 4, main mode 3, sub-mode 0\n") == 0, "first: the first frame's state, got \"%s\"", s);
    s = frame(5, 3, 0);
    CHECK(s[0] == 0, "quiet: nothing when neither word changed, got \"%s\"", s);
    s = frame(798, 1, 4);
    CHECK(strcmp(s, "test: boot: frame 798, main mode 1, sub-mode 4\n") == 0, "change: the mode's change, got \"%s\"", s);
    s = frame(942, 1, 1);
    CHECK(strcmp(s, "test: boot: frame 942, main mode 1, sub-mode 1\n") == 0, "change: the sub-mode's change, got \"%s\"", s);
    remove("build/test_boot.err");
    printf("test_boot: %s\n", failures ? "FAILED" : "OK");
    return failures ? 1 : 0;
}
