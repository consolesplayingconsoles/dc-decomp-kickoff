/* test_vmu.c: template/port/runtime/vmu.c, the memory card as a folder of files. Run with the other C tests: make -C tests/c.

    ready      before buInit no card answers; after it the card in drive 0 is ready, formatted and mounted for both the
               backup library and the file system (buIsReady, buIsFormat, vmsio_isready, vmsio_ismount): the SDK's own C
               asked a Maple driver the port does not have, and Crazy Taxi said "LOAD failed"
    other      another drive has no card
    save       a save writes a file in the card's folder, its bytes the game's, and a load gives them back
    missing    loading a file that is not there says so (file not found) */
#include <string.h>
#include <unistd.h>

#include "check.h"
#include "vmu.c"

const struct port_entry *port_lookup(uint32_t addr) { (void)addr; return 0; }   /* no game callbacks in the test */

int main(void)
{
    console_map(0x8C000000u, 0x10000);
    char folder[] = "build/test_vmu.XXXXXX";
    CHECK(mkdtemp(folder) != 0, "a temp folder for the card");
    port_vmu_dir = folder;

    CHECK(bu_is_ready(0) == 0, "ready: no card before buInit");
    bu_init(0, 1, 0, 0);
    CHECK(bu_is_ready(0) == 1 && bu_is_format(0) == 1, "ready: buIsReady and buIsFormat say yes for drive 0");
    CHECK(vmsio_is_ready(0) == 1 && vmsio_is_mount(0) == 1, "ready: vmsio_isready and vmsio_ismount say yes for drive 0");
    CHECK(bu_is_ready(1) == 0 && bu_last_error(1) == BUD_ERR_NO_DISK, "other: drive 1 has no card");

    uint32_t name = 0x8C001000u, buf = 0x8C002000u, back = 0x8C004000u;
    strcpy((char *)(uintptr_t)name, "CRZTAXI.SYS");
    for (int i = 0; i < 2 * BLOCK; i++)
        ((uint8_t *)(uintptr_t)buf)[i] = (uint8_t)(i * 7);
    bu_save(0, name, buf, 2, 0, 0);
    CHECK(bu_last_error(0) == BUD_ERR_OK, "save: no error, got %d", bu_last_error(0));
    char path[1100];
    snprintf(path, sizeof path, "%s/CRZTAXI.SYS", folder);
    CHECK(access(path, F_OK) == 0, "save: the file is in the card's folder (%s)", path);
    CHECK(bu_file_size(0, name) == 2, "save: 2 blocks");
    bu_load(0, name, back, 2);
    CHECK(bu_last_error(0) == BUD_ERR_OK && memcmp((void *)(uintptr_t)back, (void *)(uintptr_t)buf, 2 * BLOCK) == 0,
          "save: the load gives the saved bytes back");

    strcpy((char *)(uintptr_t)name, "NOTHERE");
    bu_load(0, name, back, 1);
    CHECK(bu_last_error(0) == BUD_ERR_FILE_NOT_FOUND, "missing: file not found, got %d", bu_last_error(0));

    unlink(path);
    rmdir(folder);
    return check_done("test_vmu");
}
