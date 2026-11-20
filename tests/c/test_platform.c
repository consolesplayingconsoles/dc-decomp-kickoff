/* test_platform.c: template/port/runtime/platform.c, Katana's peripheral API as the port answers it: the pad's record.
   Run with the other C tests: make -C tests/c.

   The game reads the pad's record (PDS_PERIPHERAL) from pdGetPeripheral. Crazy Taxi's ConvertSwitch tells the pads apart
   by the letters of the device's name, through the record's name pointer: left at 0, the game read address 0 and crashed
   right after "Now Loading".

    name       port A's record names the device: a pointer to "Dreamcast Controller"
    info       its info pointer leads to the device's record, a controller (function bit 1)
    connected  port A is connected (a nonzero type: padUnplugCheck pauses the game on 0) and supports the pad's buttons
    empty      port B (pdGetPeripheral(6)) holds no device: type 0 */
#include <string.h>

#include "check.h"
#include "test_platform_game.h"
#include "platform.c"

/* what platform.c takes from the rest of the runtime: none of it runs in these calls */
volatile int port_host_depth;
void hw_deliver(void) {}
void port_mix(int16_t *out, int frames) { (void)out; (void)frames; }
unsigned long aica_key_ons(void) { return 0; }
uint32_t aica_arm_pc(void) { return 0; }
int aica_arm_running(void) { return 0; }
void port_render_init(void) {}
void port_render_frame(int w, int h) { (void)w; (void)h; }
void port_boot_step(void) {}
int port_dump_polys, port_dump_models;
void port_models_frame_end(void) {}
void port_vmu_deliver(void) {}

int main(void)
{
    struct pds_peripheral *a = pdGetPeripheral(0);
    const char *name = (const char *)(uintptr_t)a->name;
    CHECK(a->name != 0, "name: port A's record has a name pointer");
    CHECK(a->name != 0 && strcmp(name, "Dreamcast Controller") == 0, "name: it names the controller, got \"%s\"", a->name ? name : "(null)");

    const struct pds_peripheral_info *info = (const struct pds_peripheral_info *)(uintptr_t)a->info;
    CHECK(info != 0 && (info->type & 1), "info: the device's record says controller (bit 1), got %#x", info ? info->type : 0);
    CHECK(a->id != 0 && a->support == PAD_SUPPORT, "connected: id %u, support %#x", a->id, a->support);

    struct pds_peripheral *b = pdGetPeripheral(6);
    CHECK(b->id == 0, "empty: port B holds no device, got id %u", b->id);
    return check_done("test_platform");
}
