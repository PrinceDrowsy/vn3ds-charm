// Phase H runner: MicroPython timings from bench.py, then SD and memory
// measurements, printed and saved to a results file. Builds for the 3DS and
// for the desktop, where the numbers only check the code works.
#include <malloc.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "port/micropython_embed.h"
#include "py/mphal.h"
#include "py/persistentcode.h"
#include "py/runtime.h"
#include "py/stackctrl.h"

#include "mpy_blobs.h"
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

static void memory_report(void) {
#ifdef __3DS__
    bool is_new = false;
    APT_CheckNew3DS(&is_new);
    out("model: %s 3DS, %s\n", is_new ? "New" : "Old", envIsHomebrew() ? "3dsx" : "CIA");
    metric("app memory region", osGetMemRegionSize(MEMREGION_APPLICATION) / 1048576.0, "MB");
    metric("app memory free", osGetMemRegionFree(MEMREGION_APPLICATION) / 1048576.0, "MB");
    metric("linear heap free", linearSpaceFree() / 1048576.0, "MB");
    // libctru reserves the whole app heap up front; this is what malloc
    // has left inside it.
    struct mallinfo mi = mallinfo();
    metric("malloc heap", envGetHeapSize() / 1048576.0, "MB");
    metric("malloc heap free", (envGetHeapSize() - mi.arena + mi.fordblks) / 1048576.0, "MB");
#endif
}

#if MICROPY_EMIT_ARM
#ifdef __3DS__
#define PAGE 0x1000
static Handle process;
#endif

// Native functions get their own pages, since a page can't be writable for
// the next function's load once it has been made executable.
void charm_alloc_exec(size_t min_size, void **ptr, size_t *size) {
#ifdef __3DS__
    *size = (min_size + PAGE - 1) & ~(PAGE - 1);
    *ptr = memalign(PAGE, *size);
#else
    *size = min_size;
    *ptr = malloc(min_size);
#endif
    if (!*ptr)
        mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("no memory for native code"));
}

void *charm_commit_exec(void *fun_data, size_t len, void *reloc) {
    if (reloc)
        mp_native_relocate(reloc, fun_data, (uintptr_t)fun_data);
#ifdef __3DS__
    u32 size = (len + PAGE - 1) & ~(PAGE - 1);
    svcFlushProcessDataCache(process, (u32)fun_data, size);
    Result rc = svcControlProcessMemory(process, (u32)fun_data, 0, size, MEMOP_PROT, MEMPERM_READEXECUTE);
    if (R_FAILED(rc))
        mp_raise_msg_varg(&mp_type_OSError, MP_ERROR_TEXT("can't make native code executable: %08x"), (unsigned)rc);
#endif
    return fun_data;
}
#endif

static void run_python(int heap_mb, const char *prelude, const uint8_t *mpy, size_t mpy_len) {
    size_t heap_size = (size_t)heap_mb * 1024 * 1024;
    void *heap = malloc(heap_size);
    if (!heap) {
        out("python: no memory for a %d MB heap\n", heap_mb);
        return;
    }
    int stack_top;
    mp_embed_init(heap, heap_size, &stack_top);
    mp_stack_set_limit(STACK_SIZE - 32 * 1024);
    mp_embed_exec_str(prelude);
    uint64_t t0 = platform_ticks_us();
    mp_embed_exec_mpy(mpy, mpy_len);
    metric("python run", (platform_ticks_us() - t0) / 1000.0, "ms");
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
    out("VN3DS-CHARM phase H spike, MicroPython %d.%d.%d%s\n", MICROPY_VERSION_MAJOR, MICROPY_VERSION_MINOR,
        MICROPY_VERSION_MICRO, CHARM_NANBOX ? ", nanbox" : "");
    memory_report();
    run_python(16, "MODE = 'full'", bench_mpy, sizeof bench_mpy);
    sd_benchmark();
    run_python(8, "MODE = 'gc'", bench_mpy, sizeof bench_mpy);
    run_python(4, "MODE = 'gc'", bench_mpy, sizeof bench_mpy);
    run_python(4, "NATIVE = False", frames_bc_mpy, sizeof frames_bc_mpy);
    out("done; saved to %s\n", RESULTS_PATH);
#ifdef __3DS__
#if MICROPY_EMIT_ARM
    // Native code is opt-in and last: if the kernel won't make memory
    // executable for this process, the console can freeze.
    printf("A: try native code (may freeze;\n   hold POWER to recover)\n");
#endif
    printf("START: exit\n");
    while (aptMainLoop()) {
        hidScanInput();
        u32 keys = hidKeysDown();
        if (keys & KEY_START)
            break;
#if MICROPY_EMIT_ARM
        if (keys & KEY_A) {
            svcDuplicateHandle(&process, CUR_PROCESS_HANDLE);
            run_python(4, "NATIVE = True", frames_native_mpy, sizeof frames_native_mpy);
            out("native done\n");
            printf("START: exit\n");
        }
#endif
        gspWaitForVBlank();
    }
#endif
    if (results)
        fclose(results);
#ifdef __3DS__
    gfxExit();
#endif
    return 0;
}
