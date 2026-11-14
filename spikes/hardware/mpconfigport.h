#include <port/mpconfigport_common.h>

// newlib (devkitARM) has no SSIZE_MAX; ssize_t is pointer-sized on both targets.
#define MP_SSIZE_MAX                            (INTPTR_MAX)

// Close to the feature set games will need: full Python data types, double
// floats (Ren'Py's are doubles), big ints, and .mpy loading as in §6.
#define MICROPY_CONFIG_ROM_LEVEL                (MICROPY_CONFIG_ROM_LEVEL_EXTRA_FEATURES)
#define MICROPY_ENABLE_COMPILER                 (1)
#define MICROPY_ENABLE_GC                       (1)
#define MICROPY_PERSISTENT_CODE_LOAD            (1)
#define MICROPY_FLOAT_IMPL                      (MICROPY_FLOAT_IMPL_DOUBLE)
#define MICROPY_LONGINT_IMPL                    (MICROPY_LONGINT_IMPL_MPZ)
#define MICROPY_STACK_CHECK                     (1)
#define MICROPY_PY_GC                           (1)
#define MICROPY_PY_SYS_STDFILES                 (0)
#define MICROPY_PY_SYS_PLATFORM                 "charm"

// No console on the device: input() would need readline, and there's no
// keyboard to send Ctrl-C.
#define MICROPY_PY_BUILTINS_INPUT               (0)
#define MICROPY_KBD_EXCEPTION                   (0)

// No filesystem from Python: game modules will be imported from the bundle
// through the engine (R2), not from files.
#define MICROPY_ENABLE_EXTERNAL_IMPORT          (0)
#define MICROPY_PY_BUILTINS_EXECFILE            (0)
#define MICROPY_PY_IO                           (0)
#define MICROPY_PY_UCTYPES                      (0)

#include "charm_variant.h"  // written by build.py

#if CHARM_NANBOX
// NaN-boxing: doubles live inside the 64-bit object word, so float math
// doesn't allocate. MicroPython's native emitters don't support it.
#define MICROPY_OBJ_REPR                        (MICROPY_OBJ_REPR_D)
#else
// Native ARM code from `mpy-cross -march=armv6 -X emit=native`. The GC heap
// isn't executable on the 3DS, so the runner places native code on its own
// pages and marks them executable when MicroPython commits them.
#define MICROPY_EMIT_ARM                        (1)
#include <stddef.h>
void charm_alloc_exec(size_t min_size, void **ptr, size_t *size);
void *charm_commit_exec(void *fun_data, size_t len, void *reloc);
#define MP_PLAT_ALLOC_EXEC(min_size, ptr, size) charm_alloc_exec(min_size, (void **)(ptr), size)
#define MP_PLAT_FREE_EXEC(ptr, size)            ((void)(ptr), (void)(size))
#define MP_PLAT_COMMIT_EXEC(fun_data, len, reloc) charm_commit_exec(fun_data, len, reloc)
#define MP_STATE_PORT                           MP_STATE_VM
// Without this hook MicroPython flushes caches with CP15 instructions, which
// are privileged and fault in a 3DS app. charm_commit_exec has already
// flushed through the kernel by the time this would run.
#define MP_HAL_CLEAN_DCACHE(addr, size)         ((void)(addr), (void)(size))
#endif
