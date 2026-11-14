// Phase H runner: MicroPython timings from bench.py, then SD and memory
// measurements, printed and saved to a results file. Builds for the 3DS and
// for the desktop, where the numbers only check the code works.
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "port/micropython_embed.h"
#include "py/mphal.h"
#include "py/stackctrl.h"

#include "bench_mpy.h"
#include "platform.h"

#ifdef __3DS__
#include <3ds.h>
#define RESULTS_PATH "sdmc:/charm-spike-h.txt"
#define SCRATCH_PATH "sdmc:/charm-spike-h.bin"
#define STACK_SIZE (256 * 1024)
u32 __stacksize__ = STACK_SIZE;
#else
#include <time.h>
#define RESULTS_PATH "charm-spike-h.txt"
#define SCRATCH_PATH "charm-spike-h.bin"
#define STACK_SIZE (1024 * 1024)
#endif

#define GC_HEAP_MB 16
#define SD_FILE_MB 16
#define SD_CHUNK (256 * 1024)
#define SD_SMALL_READS 256
#define SD_SMALL (4 * 1024)

static FILE *results;
static uint64_t start_us;

uint64_t platform_ticks_us(void) {
#ifdef __3DS__
    return svcGetSystemTick() / (SYSCLOCK_ARM11 / 1000000) - start_us;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000 + ts.tv_nsec / 1000 - start_us;
#endif
}

static void emit(const char *s, size_t len) {
    fwrite(s, 1, len, stdout);
    if (results) {
        fwrite(s, 1, len, results);
        fflush(results);
    }
}

void mp_hal_stdout_tx_strn_cooked(const char *str, size_t len) {
    emit(str, len);
}

static void out(const char *fmt, ...) {
    char buf[256];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    emit(buf, n < (int)sizeof buf ? (size_t)n : sizeof buf - 1);
}

static void metric(const char *name, double value, const char *unit) {
    out("%-24s%9.3f %s\n", name, value, unit);
}

static void sd_benchmark(void) {
    uint8_t *buf = malloc(SD_CHUNK);
    if (!buf) {
        out("sd: no memory for the buffer\n");
        return;
    }
    memset(buf, 0xA5, SD_CHUNK);
    FILE *f = fopen(SCRATCH_PATH, "wb");
    if (!f) {
        out("sd: can't create %s\n", SCRATCH_PATH);
        free(buf);
        return;
    }
    uint64_t t0 = platform_ticks_us();
    for (int i = 0; i < SD_FILE_MB * (1024 * 1024 / SD_CHUNK); i++)
        fwrite(buf, 1, SD_CHUNK, f);
    fclose(f);
    uint64_t t1 = platform_ticks_us();
    metric("sd write", SD_FILE_MB / ((t1 - t0) / 1e6), "MB/s");

    f = fopen(SCRATCH_PATH, "rb");
    t0 = platform_ticks_us();
    size_t total = 0, got;
    while ((got = fread(buf, 1, SD_CHUNK, f)) > 0)
        total += got;
    t1 = platform_ticks_us();
    metric("sd read 256K chunks", total / 1048576.0 / ((t1 - t0) / 1e6), "MB/s");

    uint32_t seed = 1, worst = 0;
    t0 = platform_ticks_us();
    for (int i = 0; i < SD_SMALL_READS; i++) {
        seed = seed * 1103515245 + 12345;
        long pos = (long)(seed % (SD_FILE_MB * 1024 * 1024 / SD_SMALL)) * SD_SMALL;
        uint64_t r0 = platform_ticks_us();
        fseek(f, pos, SEEK_SET);
        fread(buf, 1, SD_SMALL, f);
        uint32_t dt = (uint32_t)(platform_ticks_us() - r0);
        if (dt > worst)
            worst = dt;
    }
    t1 = platform_ticks_us();
    metric("sd 4K random read, mean", (t1 - t0) / 1000.0 / SD_SMALL_READS, "ms");
    metric("sd 4K random read, max", worst / 1000.0, "ms");
    fclose(f);
    remove(SCRATCH_PATH);
    free(buf);
}

// The largest single block malloc can still hand out, to 1 MB.
static size_t largest_malloc_mb(void) {
    size_t lo = 0, hi = 512;
    while (lo < hi) {
        size_t mid = (lo + hi + 1) / 2;
        void *p = malloc(mid * 1024 * 1024);
        if (p) {
            free(p);
            lo = mid;
        } else {
            hi = mid - 1;
        }
    }
    return lo;
}

static void memory_report(void) {
#ifdef __3DS__
    bool is_new = false;
    APT_CheckNew3DS(&is_new);
    out("model: %s 3DS, %s\n", is_new ? "New" : "Old", envIsHomebrew() ? "3dsx" : "CIA");
    metric("app memory region", osGetMemRegionSize(MEMREGION_APPLICATION) / 1048576.0, "MB");
    metric("app memory free", osGetMemRegionFree(MEMREGION_APPLICATION) / 1048576.0, "MB");
    metric("linear heap free", linearSpaceFree() / 1048576.0, "MB");
#endif
    metric("largest malloc", (double)largest_malloc_mb(), "MB");
}

static void run_python(void) {
    size_t heap_size = GC_HEAP_MB * 1024 * 1024;
    void *heap = malloc(heap_size);
    if (!heap) {
        out("python: no memory for a %d MB heap\n", GC_HEAP_MB);
        return;
    }
    int stack_top;
    mp_embed_init(heap, heap_size, &stack_top);
    mp_stack_set_limit(STACK_SIZE - 32 * 1024);
    uint64_t t0 = platform_ticks_us();
    mp_embed_exec_mpy(bench_mpy, sizeof bench_mpy);
    metric("python total", (platform_ticks_us() - t0) / 1000.0, "ms");
    mp_embed_deinit();
    free(heap);
}

int main(void) {
#ifdef __3DS__
    gfxInitDefault();
    consoleInit(GFX_TOP, NULL);
#endif
    start_us = 0;
    start_us = platform_ticks_us();
    results = fopen(RESULTS_PATH, "w");
    out("VN3DS-CHARM phase H spike, MicroPython %d.%d.%d\n", MICROPY_VERSION_MAJOR, MICROPY_VERSION_MINOR,
        MICROPY_VERSION_MICRO);
    memory_report();
    run_python();
    sd_benchmark();
    out("done; saved to %s\n", RESULTS_PATH);
    if (results)
        fclose(results);
    results = NULL;
#ifdef __3DS__
    printf("Press START to exit.\n");
    while (aptMainLoop()) {
        hidScanInput();
        if (hidKeysDown() & KEY_START)
            break;
        gspWaitForVBlank();
    }
    gfxExit();
#endif
    return 0;
}
