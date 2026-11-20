/* test_boot.c: template/port/runtime/boot.c, the debug log a watcher follows (tools/10-port/capture.sh waits for its
   "main mode M, sub-mode S" line). Run with the other C tests: make -C tests/c.

    first      the first frame prints the game's mode and sub-mode, with the frame
    quiet      a frame where neither changed prints nothing
    change     a change of either prints a new line, with that frame's number

   The game's two words sit at addresses this test maps (test_boot_game.h stands in for the game's game.h). */
#include <stdlib.h>
#include <string.h>

#include "check.h"


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
    console_map(GAME_MAIN_MODE, 8);
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
    return check_done("test_boot");
}
