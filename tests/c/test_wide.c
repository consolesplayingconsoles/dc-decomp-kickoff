/* test_wide.c: template/port/runtime/draw.c with PORT_WIDESCREEN=1 (built at 16:9): which of a frame's 2D draws are drawn
   edge to edge, moved out to the left edge or pinned to a side. Run with the other C tests: make -C tests/c. The pieces are
   Crazy Taxi's, as its menus, driver select, result screen and races drew them (screen x, y in its 640x480 frame); no
   window is opened: these rules work on the frame's draws before they are drawn.

    band       a menu header of 240 tiles of one small texture, together 0-640 x 0-96, is drawn edge to edge; no single
               tile spans it
    sliding    the same kind of tiles sliding in past the screen's edges (-24 to 752, a menu's entry) are not
    fill       an untextured draw that alone covers the width (the register screen's dimming) is drawn edge to edge, even
               with other untextured pieces elsewhere; a full-screen picture of a large texture keeps its 4:3 shape
    extend     the checker bar's left piece (0-32) goes out to the wider screen's left edge, every copy of its corners (a quad
               is two triangles: taken triangle by triangle, one copy moved and the other stayed, a dent in the checker),
               its texture carried along so the pattern repeats; a piece sliding in from the left (x < 0) is not moved
    hud        in a race (the play mode, with a city's 3D: 4,000 vertices or more), a HUD piece at the top wholly in the left
               half is pinned left and one in the right half right; a picture mid-screen is not (the driver select, "time
               up" and result screens share the play mode, and their pictures came apart in three); nothing is pinned
               with little 3D on screen (the driver select) or in another mode */
#include <math.h>
#include <string.h>

#include "check.h"
#include "test_draw_game.h"
#include "draw.c"

#define MODE (*(volatile int32_t *)(uintptr_t)GAME_MAIN_MODE)

static struct rdraw flat(unsigned texture, int fill)
{
    struct rdraw d;
    memset(&d, 0, sizeof d);
    d.flat2d = 1, d.fill = (uint8_t)fill, d.texture = texture, d.textured = texture != 0, d.blend = 2;
    return d;
}

/* a quad as two triangles (the console's sprite: corners A B C D, then A C D), u and v 0-1 across it */
static void quad(float x0, float y0, float x1, float y1, struct rdraw d)
{
    struct rvert v[6];
    float c[4][4] = {{x0, y0, 0, 0}, {x1, y0, 1, 0}, {x1, y1, 1, 1}, {x0, y1, 0, 1}};
    int order[6] = {0, 1, 3, 1, 2, 3};
    memset(v, 0, sizeof v);
    for (int i = 0; i < 6; i++)
        v[i].x = c[order[i]][0], v[i].y = c[order[i]][1], v[i].u = c[order[i]][2], v[i].v = c[order[i]][3], v[i].z = 1.0f;
    render_tris(v, 6, &d);
}

static void world(unsigned triangles)                  /* the city: 3D (group bit set), three vertices a triangle */
{
    struct rdraw d;
    memset(&d, 0, sizeof d);
    struct rvert v[3];
    memset(v, 0, sizeof v);
    v[0].x = 100, v[1].x = 200, v[2].y = 100, v[0].z = 10, v[1].z = 20, v[2].z = 30;
    for (unsigned i = 0; i < triangles; i++)
        render_tris(v, 3, &d);
}

static struct rdraw *last(void) { return &draws[ndraws - 1]; }

static void frame(void) { nverts = ndraws = 0; scr_w = 640.0f; }

int main(void)
{
    console_map(GAME_MAIN_MODE, 4);
    verts = malloc(sizeof *verts * MAX_VERTS);
    draws = malloc(sizeof *draws * MAX_DRAWS);
    CHECK(fabsf(PORT_WIDE - 4.0f / 3.0f) < 1e-6f, "built at 16:9: PORT_WIDE %g", PORT_WIDE);

    frame();
    for (int col = 0; col < 40; col++)
        for (int row = 0; row < 6; row++)
            quad(col * 16.0f, row * 16.0f, col * 16.0f + 16, row * 16.0f + 16, flat(7, 1));
    quad(32, 416, 288, 448, flat(8, 0));
    mark_bars();
    int bars = 0;
    for (unsigned i = 0; i < ndraws; i++)
        bars += draws[i].texture == 7 && draws[i].bar;
    CHECK(bars > 0 && !last()->bar, "band: the header's tiles edge to edge, the bar's middle piece not (%d draws)", bars);

    frame();
    quad(-24, 187, 400, 363, flat(9, 1));
    quad(400, 187, 752, 363, flat(9, 1));
    mark_bars();
    CHECK(!draws[0].bar && !last()->bar, "sliding: tiles past the edges are not a band");

    frame();
    quad(-40, 300, 10, 310, flat(0, 1));                          /* another untextured piece, past the left edge */
    quad(200, 200, 260, 220, flat(16, 0));                        /* a piece between: draws of one mode in a row merge */
    quad(0, 0, 640, 480, flat(0, 1));
    struct rdraw *dim = last();
    quad(0, 0, 640, 480, flat(10, 0));                            /* a full-screen picture, a large texture */
    mark_bars();
    CHECK(dim->bar, "fill: the screen-wide dimming edge to edge");
    CHECK(!last()->bar, "fill: a full-screen picture keeps its 4:3 shape");

    frame();
    quad(0, 416, 32, 448, flat(11, 0));
    quad(-576, 416, -544, 448, flat(12, 0));
    mark_bars();
    extend_left();
    const float edge = 320.0f - 320.0f * PORT_WIDE;
    int moved = 0, left = 0;
    for (unsigned v = draws[0].first; v < draws[0].first + draws[0].count; v++)
        if (verts[v].x < 16.0f) {
            left++;
            moved += fabsf(verts[v].x - edge) < 0.01f && fabsf(verts[v].u - edge / 32.0f) < 1e-4f;
        }
    CHECK(left == 3 && moved == 3, "extend: all %d copies of the left corners at x %.2f, u %.3f (%d moved)", left, edge, edge / 32.0f,
          moved);
    CHECK(draws[0].extended && !draws[1].extended && verts[draws[1].first].x == -576.0f, "extend: a piece sliding in is not moved");

    frame();
    MODE = 1;
    world(1400);                                                  /* 4,200 vertices */
    quad(6, 20, 70, 84, flat(13, 0));
    struct rdraw *hl = last();
    quad(404, 22, 532, 54, flat(14, 0));
    struct rdraw *hr = last();
    quad(140, 200, 500, 300, flat(15, 0));                        /* a picture mid-screen */
    struct rdraw *mid = last();
    mark_bars();
    extend_left();
    mark_hud();
    CHECK(hl->anchor == 1 && hr->anchor == 2, "hud: left piece pinned left (%d), right piece right (%d)", hl->anchor, hr->anchor);
    CHECK(mid->anchor == 0, "hud: a picture mid-screen stays in the middle, got %d", mid->anchor);

    frame();
    world(500);                                                   /* the driver select: 1,500 vertices of 3D */
    quad(6, 20, 70, 84, flat(13, 0));
    mark_hud();
    CHECK(last()->anchor == 0, "hud: little 3D on screen, nothing pinned");

    frame();
    MODE = 3;
    world(1400);
    quad(6, 20, 70, 84, flat(13, 0));
    mark_hud();
    CHECK(last()->anchor == 0, "hud: another mode, nothing pinned");
    return check_done("test_wide");
}
