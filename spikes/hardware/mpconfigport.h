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
