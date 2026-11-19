/* test_draw.c: template/port/runtime/draw.c, the port's renderer, with an OpenGL 3.3 context and a 640x480 target.
   Run with the other C tests: make -C tests/c (in the port image; see tests/c/Makefile).

   Each case is one triangle as the console's tile accelerator takes it (screen x, y in pixels, and W per vertex), drawn
   as an opaque polygon with depth writes. The depth read back at every pixel must be the triangle's own: 1/W is linear
   in screen space, so the plane through the three vertices in (x, y, 1/W) gives each pixel's W exactly.

    covered    every pixel well inside the triangle is drawn, none well outside it
    depth      the W the depth buffer holds is the plane's, within 0.01%
    far        a triangle wholly off the screen draws nothing

   The triangles are from a Crazy Taxi race frame (the port's renderer, frame 1263). "far corner" is a far translucent
   triangle (the sky, W 3900-5700) across the screen's bottom-left corner: OpenGL cut it at the screen's edge and the
   renderer's 1/W, passed to the pixel without perspective, came out wrong there, so it wrote the nearest possible depth
   and the sky covered the road (W 10) and the HUD. */
#define GL_GLEXT_PROTOTYPES
#include <GL/gl.h>
#include <GL/glext.h>
#include <SDL3/SDL.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>

#include "render.h"

extern int render_target_w, render_target_h;

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

struct tri {
    const char *name;
    float v[3][3]; /* x, y, W */
};

static const struct tri cases[] = {
    /* the road, one corner clipped at the near plane (W 0.3) 33,000 px off the screen */
    {"road", {{248.3f, 362.6f, 36.8f}, {684.9f, 372.4f, 28.58f}, {-32584.2f, 4481.6f, 0.3f}}},
    /* the sky, wholly above the screen, its clipped corner 12 million px away */
    {"sky", {{2026.9f, -2645.2f, 1182.0f}, {-2206.8f, -4073.7f, 798.2f}, {6404848.5f, -11713090.0f, 0.3f}}},
    {"plain", {{100.0f, 100.0f, 10.0f}, {500.0f, 120.0f, 20.0f}, {300.0f, 400.0f, 40.0f}}},
    {"far corner", {{33.2f, 571.9f, 5426.0f}, {-363.8f, 665.0f, 3924.0f}, {47.5f, 382.8f, 5711.0f}}},
};

static float depth[480][640];

static void draw(const struct tri *t)
{
    glViewport(0, 0, 640, 480);
    glClearDepth(0.0);
    glClear(GL_DEPTH_BUFFER_BIT | GL_COLOR_BUFFER_BIT);
    struct rvert v[3];
    memset(v, 0, sizeof v);
    for (int k = 0; k < 3; k++) {
        v[k].x = t->v[k][0];
        v[k].y = t->v[k][1];
        v[k].z = t->v[k][2];
        v[k].argb = 0xFFFFFFFFu;
    }
    struct rdraw m;
    memset(&m, 0, sizeof m);
    m.depth_func = 4; /* the ISP's "greater", as these polygons have it (0x93000000) */
    m.depth_write = 1;
    render_target_w = 640;
    render_target_h = 480;
    render_tris(v, 3, &m);
    render_flush(640, 480);
    render_target_w = render_target_h = 0;
    glReadPixels(0, 0, 640, 480, GL_DEPTH_COMPONENT, GL_FLOAT, depth);
}

static void test_case(const struct tri *t)
{
    draw(t);
    double x1 = t->v[0][0], y1 = t->v[0][1], z1 = 1.0 / t->v[0][2];
    double x2 = t->v[1][0], y2 = t->v[1][1], z2 = 1.0 / t->v[1][2];
    double x3 = t->v[2][0], y3 = t->v[2][1], z3 = 1.0 / t->v[2][2];
    double det = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1);
    long inside = 0, missing = 0, stray = 0;
    double worst = 0, worst_drawn = 0, worst_true = 0;
    int wx = -1, wy = -1;
    for (int row = 0; row < 480; row++)
        for (int x = 0; x < 640; x++) {
            double px = x + 0.5, py = 480 - row - 0.5; /* GL's rows bottom first; the console's y down */
            double l1 = ((x2 - px) * (y3 - py) - (x3 - px) * (y2 - py)) / det;
            double l2 = ((x3 - px) * (y1 - py) - (x1 - px) * (y3 - py)) / det;
            double l3 = 1.0 - l1 - l2;
            int in = l1 > 1e-3 && l2 > 1e-3 && l3 > 1e-3, out = l1 < -1e-3 || l2 < -1e-3 || l3 < -1e-3;
            float g = depth[row][x];
            inside += in;
            if (g == 0.0f) {
                missing += in;
                continue;
            }
            if (out) {
                stray++;
                continue;
            }
            double w_true = 1.0 / (l1 * z1 + l2 * z2 + l3 * z3);
            double w_drawn = pow(2.0, 20.0 - 40.0 * g); /* draw.c's depth: (20 - log2 W) / 40 */
            double e = fabs(w_drawn - w_true) / w_true;
            if (e > worst) {
                worst = e;
                worst_drawn = w_drawn;
                worst_true = w_true;
                wx = x;
                wy = 479 - row;
            }
        }
    CHECK(missing == 0, "%s: %ld of %ld pixels inside the triangle not drawn", t->name, missing, inside);
    CHECK(stray == 0, "%s: %ld pixels drawn outside the triangle", t->name, stray);
    CHECK(worst < 1e-4, "%s: depth at %d,%d is W %g, the triangle's is W %g", t->name, wx, wy, worst_drawn, worst_true);
    printf("%-11s %6ld pixels, depth within %.2g\n", t->name, inside - missing, worst);
}

int main(void)
{
    /* PT_ALPHA_REF, which draw.c reads at its console address */
    if (mmap((void *)0xA05F8000ul, 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0) == MAP_FAILED) {
        perror("mmap");
        return 2;
    }
    if (!SDL_Init(SDL_INIT_VIDEO)) {
        printf("SDL_Init: %s\n", SDL_GetError());
        return 2;
    }
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    SDL_Window *win = SDL_CreateWindow("test_draw", 640, 480, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    if (!win || !SDL_GL_CreateContext(win)) {
        printf("OpenGL context: %s\n", SDL_GetError());
        return 2;
    }
    render_setup();
    GLuint fbo, rb[2];
    glGenFramebuffers(1, &fbo);
    glGenRenderbuffers(2, rb);
    glBindRenderbuffer(GL_RENDERBUFFER, rb[0]);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, 640, 480);
    glBindRenderbuffer(GL_RENDERBUFFER, rb[1]);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, 640, 480); /* as the game's window asks for */
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, rb[0]);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, rb[1]);
    for (unsigned c = 0; c < sizeof cases / sizeof cases[0]; c++)
        test_case(&cases[c]);
    printf("test_draw: %s\n", failures ? "FAILED" : "OK");
    return failures ? 1 : 0;
}
