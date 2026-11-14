#include "py/runtime.h"
#include "py/smallint.h"

#include "platform.h"

// Microseconds since the runner started, so the value stays a small int
// (no heap allocation) for the length of a run.
static mp_obj_t charm_ticks_us(void) {
    return MP_OBJ_NEW_SMALL_INT((mp_int_t)(platform_ticks_us() & MP_SMALL_INT_POSITIVE_MASK));
}
static MP_DEFINE_CONST_FUN_OBJ_0(charm_ticks_us_obj, charm_ticks_us);

static const mp_rom_map_elem_t charm_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_charm) },
    { MP_ROM_QSTR(MP_QSTR_ticks_us), MP_ROM_PTR(&charm_ticks_us_obj) },
};
static MP_DEFINE_CONST_DICT(charm_globals, charm_globals_table);

const mp_obj_module_t charm_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&charm_globals,
};

MP_REGISTER_MODULE(MP_QSTR_charm, charm_module);
