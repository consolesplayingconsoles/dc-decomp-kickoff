/* test_pvr.c: template/port/runtime/pvr.c, the tile accelerator's parameter position and its overflow. Run with the other C
   tests: make -C tests/c.

   Kamui reads TA_ITP_CURRENT (0xA05F8138) after a frame's lists (kmiFinalizeRender, with its flags' bit 0 set, as Crazy
   Taxi's are) to put the background plane right after the frame's parameters and point the render at it. The port left it
   at 0: every frame's background went to the start of video memory. Past TA_ISP_LIMIT the console's TA reports a parameter
   overflow (SB_ISTERR bit 2), which Kamui handles (kmiErrorISR04); the port never did.

    start      a list init puts the position at TA_ISP_BASE
    moves      the TA's input moves it up by the bytes taken in
    overflow   passing TA_ISP_LIMIT raises error bit 2, once for the frame however much more comes
    next       the next list init starts again: a new overflow is raised again
    below      a limit under the base (between frames, as Kamui leaves them) raises nothing

   And a render into a texture (Crazy Taxi's pause: the race drawn into a 512x512 RGB565 texture, then shown over the
   screen), with the registers read at it:
    kind       a polygon whose control word has the group bit (23) clear is the game's 2D (flat2d: the HUD, menus, their
               text); one with it set is 3D, the camera-facing models included (the passengers' dollar marker); an
               untextured one is a plain fill
    texture    every pixel of the clip area is written, 512 wide and 481 high, whatever the region array holds (there,
               an entry early in it had other words, with the last-entry bit: the pause was black past 96 pixels) */
#include <string.h>

#include "check.h"
#include "test_platform_game.h"
#include "pvr.c"

/* what pvr.c takes from the rest of the runtime */
static int err_bit2;
void hw_raise_err(int bit) { err_bit2 += bit == 2; }
void hw_raise_later(int bit, unsigned us) { (void)bit; (void)us; }
void port_frame_end(void) {}
int port_headless = 1;
unsigned port_host_fp_enter(void) { return 0; }
void port_host_fp_leave(unsigned game) { (void)game; }
void port_render_to(uint32_t *out, int w, int h)  /* the picture: all white */
{
    for (int i = 0; i < w * h; i++)
        out[i] = 0xFFFFFFFFu;
}
void render_set_background(float r, float g, float b) { (void)r; (void)g; (void)b; }
void render_tris(const struct rvert *v, unsigned n, const struct rdraw *mode) { (void)v; (void)n; (void)mode; }

#define CURRENT REG(PVR + 0x138)

static void feed(int params)                     /* user tile clips: parameters the TA takes and draws nothing from */
{
    uint32_t w[8] = {0x20000000u};
    for (int i = 0; i < params; i++)
        pvr_ta_write(w, 32);
}

static void frame(uint32_t base, uint32_t limit)
{
    REG(PVR + 0x124) = base;
    REG(PVR + 0x130) = limit;
    pvr_ta_list_init();
}

int main(void)
{
    console_map(0xA05F8000u, 0x2000);

    frame(0x100000, 0x200000);
    CHECK(CURRENT == 0x100000, "start: TA_ISP_BASE, got %06X", CURRENT);
    feed(3);
    CHECK(CURRENT == 0x100000 + 96, "moves: up by the 96 bytes taken in, got %06X", CURRENT);
    CHECK(err_bit2 == 0, "moves: no overflow under the limit");

    frame(0x100000, 0x100040);                    /* room for two parameters */
    feed(3);
    CHECK(err_bit2 == 1, "overflow: error bit 2 once past the limit, got %d", err_bit2);
    feed(5);
    CHECK(err_bit2 == 1, "overflow: once for the frame, got %d", err_bit2);

    frame(0x100000, 0x100040);
    CHECK(CURRENT == 0x100000, "next: back at the base, got %06X", CURRENT);
    feed(3);
    CHECK(err_bit2 == 2, "next: a new frame's overflow is raised again, got %d", err_bit2);

    frame(0x4BBC80, 0x49FB00);                    /* the registers as read in the frozen race */
    feed(4);
    CHECK(err_bit2 == 2, "below: a limit under the base raises nothing, got %d", err_bit2);
    struct poly p2d = {0}, p3d = {0};
    struct rdraw d;
    p2d.pcw = 0x82000000u, p2d.list = 2;                         /* the pause text's word, untextured */
    p3d.pcw = 0x828C0024u, p3d.list = 2;                         /* the dollar marker's word, untextured */
    mode_of(&p2d, &d);
    CHECK(d.flat2d && d.fill, "kind: group bit clear, 2D (%d), untextured, a fill (%d)", d.flat2d, d.fill);
    mode_of(&p3d, &d);
    CHECK(!d.flat2d, "kind: group bit set, 3D");

    console_map(0xA4000000u, 0x800000);               /* video memory, 64- and 32-bit paths */
    console_map(0xA5000000u, 0x800000);
    REG(PVR + 0x02C) = 0x4D33C8;                     /* the region array, as read at the pause */
    uint32_t *ra = (uint32_t *)(uintptr_t)(0xA5000000u + 0x4D33C8);
    ra[0] = 0x10000000u;
    ra[6] = 0x80800000u;                             /* the second entry: other words, the last-entry bit set */
    REG(PVR + 0x068) = 0x01FF0000u;                  /* FB_X_CLIP 0..511 */
    REG(PVR + 0x06C) = 0x01E00000u;                  /* FB_Y_CLIP 0..480 */
    REG(PVR + 0x04C) = 0x80;                         /* 1024 bytes a line */
    REG(PVR + 0x048) = 9;                            /* FB_W_CTRL: RGB565 */
    render_to_texture(0x530080);
    const uint16_t *tex = (const uint16_t *)(uintptr_t)(0xA4000000u + 0x530080);
    CHECK(tex[0] == 0xFFFF && tex[511] == 0xFFFF, "texture: the first line, 512 wide, got %04X %04X", tex[0], tex[511]);
    CHECK(tex[480 * 512 + 511] == 0xFFFF, "texture: the last pixel, line 480, got %04X", tex[480 * 512 + 511]);
    CHECK(tex[481 * 512] == 0, "texture: nothing past the clip area, got %04X", tex[481 * 512]);
    return check_done("test_pvr");
}
