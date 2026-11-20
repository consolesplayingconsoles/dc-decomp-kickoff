/* test_nlib.c: template/port/runtime/nlib.c, the NAOMI library's model kernel in C: a triangle's near-plane clip and the
   bounding-sphere culling. Run with the other C tests: make -C tests/c.

    front      a triangle wholly in front of the near plane goes out as it is: three vertices, each at x/W, y/W, 1/W
    clipped    a triangle with one corner behind the plane goes out as two (a fan of four vertices); the two new corners
               lie on the plane, 1/W = 1/near, as the original kernel gives them (displaypolygondata_sidx's clip)
    behind     a triangle wholly behind the plane goes out as nothing
    culled     a bounding sphere wholly behind the plane, or wholly off the screen, is culled; one across the plane or on the
               screen is drawn (drawing them all filled a stadium's translucent list)

   The game's addresses come from test_nlib_game.h; the kernel's output goes to a list buffer in mapped RAM. */
#include <string.h>

#include "check.h"
#include "test_nlib_game.h"
#include "nlib.c"

/* what nlib.c takes from the rest of the runtime: the list buffer is plain RAM here */
void hw_bus_write(uint32_t a, const void *src, uint32_t n) { memcpy((void *)(uintptr_t)a, src, n); }
static float xf[16];
float *interp_xf(void) { return xf; }
int32_t kmSetBorderColor(uint32_t argb) { (void)argb; return 0; }
int32_t kmSetWaitVsyncCallback(uint32_t fn, uint32_t arg) { (void)fn; (void)arg; return 0; }
int32_t nlPopMatrix(int32_t n) { (void)n; return 1; }
unsigned long port_frames;
void sa_ftrv(const float m[16], const float v[4], float out[4]) { (void)m; (void)v; memset(out, 0, 16); }
float test_log(float x) __asm__("nlLog");          /* the game's own, which nlPow calls: the host's here */
float test_log(float x) { return logf(x); }
float test_exp(float x) __asm__("nlExp");
float test_exp(float x) { return expf(x); }

#define LIST 0x8C100000u          /* list 0's buffer */
#define NEAR 0.3f

static void reset(void)
{
    U32(GAME_NL_LIST_PTRS) = 0x8C00F800u;          /* the list pointer array */
    for (int k = 0; k < 5; k++)
        U32(0x8C00F800u + 4u * k) = 0;
    U32(0x8C00F800u) = LIST;
    memset((void *)(uintptr_t)LIST, 0, 0x1000);
}

static int out_count(void) { return (int)((U32(0x8C00F800u) - LIST) / 32); }   /* 32-byte intensity vertices */
static float field(int v, int k) { return fbits(U32(LIST + 32u * v + 4u * k)); }

static struct mvert vert(float w, float xw, float yw)
{
    struct mvert m;
    memset(&m, 0, sizeof m);
    m.w = w;
    m.xw = xw;
    m.yw = yw;
    return m;
}

int main(void)
{
    console_map(0x8C000000u, 0x01000000u);

    reset();
    struct mvert a = vert(10, 1000, 500), b = vert(20, 4000, 1000), c = vert(40, 4000, 8000);
    emit_tri(0, 0, &a, &b, &c, NEAR);
    CHECK(out_count() == 3, "front: three vertices, got %d", out_count());
    CHECK(field(0, 1) == 100.0f && field(0, 2) == 50.0f && field(0, 3) == 0.1f, "front: x/W, y/W, 1/W of the first corner");
    CHECK((U32(LIST + 64) & 0x10000000u) && !(U32(LIST) & 0x10000000u), "front: the strip's end on the last vertex only");

    reset();
    struct mvert p = vert(10, 1000, 0), q = vert(10, 0, 1000), r = vert(-10, 0, 0);
    emit_tri(0, 0, &p, &q, &r, NEAR);
    CHECK(out_count() == 4, "clipped: a fan of four vertices, got %d", out_count());
    int on_plane = 0;
    for (int v = 0; v < out_count(); v++)
        on_plane += field(v, 3) > 3.3f && field(v, 3) < 3.34f;
    CHECK(on_plane == 2, "clipped: two corners on the plane at 1/W = 1/0.3, got %d", on_plane);

    reset();
    struct mvert s = vert(-1, 0, 0), t = vert(-2, 0, 0), u = vert(0.1f, 0, 0);
    emit_tri(0, 0, &s, &t, &u, NEAR);
    CHECK(out_count() == 0, "behind: nothing, got %d vertices", out_count());

    const float id[16] = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1};   /* W = x, screen x = y, screen y = z */
    CHECK(sphere_unseen(id, -5, 0, 0, 1, NEAR) == 1, "culled: a sphere wholly behind the plane");
    CHECK(sphere_unseen(id, 0.5f, 0, 0, 1, NEAR) == 0, "culled: a sphere across the plane is drawn (clipped, not culled)");
    CHECK(sphere_unseen(id, 10, 100000, 0, 1, NEAR) == 1, "culled: a sphere far off the screen's right");
    CHECK(sphere_unseen(id, 10, 3200, 2400, 1, NEAR) == 0, "culled: a sphere at the screen's middle is drawn");
    return check_done("test_nlib");
}
