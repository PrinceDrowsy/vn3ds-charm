// The embed port's glue (ports/embed/port/embed_util.c, MicroPython, MIT,
// Copyright (c) 2022-2023 Damien P. George), with object/pointer conversions
// that also hold under NaN-boxing, where mp_obj_t is a 64-bit integer.
#include <string.h>

#include "port/micropython_embed.h"
#include "py/compile.h"
#include "py/gc.h"
#include "py/persistentcode.h"
#include "py/runtime.h"
#include "py/stackctrl.h"
#include "shared/runtime/gchelper.h"

void mp_embed_init(void *gc_heap, size_t gc_heap_size, void *stack_top) {
    mp_stack_set_top(stack_top);
    gc_init(gc_heap, (uint8_t *)gc_heap + gc_heap_size);
    mp_init();
}

void mp_embed_deinit(void) {
    mp_deinit();
}

void mp_embed_exec_str(const char *src) {
    nlr_buf_t nlr;
    if (nlr_push(&nlr) == 0) {
        mp_lexer_t *lex = mp_lexer_new_from_str_len(MP_QSTR__lt_stdin_gt_, src, strlen(src), 0);
        qstr source_name = lex->source_name;
        mp_parse_tree_t parse_tree = mp_parse(lex, MP_PARSE_FILE_INPUT);
        mp_obj_t module_fun = mp_compile(&parse_tree, source_name, true);
        mp_call_function_0(module_fun);
        nlr_pop();
    } else {
        mp_obj_print_exception(&mp_plat_print, MP_OBJ_FROM_PTR(nlr.ret_val));
    }
}

void mp_embed_exec_mpy(const uint8_t *mpy, size_t len) {
    nlr_buf_t nlr;
    if (nlr_push(&nlr) == 0) {
        mp_module_context_t *ctx = m_new_obj(mp_module_context_t);
        ctx->module.globals = mp_globals_get();
        mp_compiled_module_t cm;
        cm.context = ctx;
        mp_raw_code_load_mem(mpy, len, &cm);
        mp_obj_t f = mp_make_function_from_proto_fun(cm.rc, ctx, NULL);
        mp_call_function_0(f);
        nlr_pop();
    } else {
        mp_obj_print_exception(&mp_plat_print, MP_OBJ_FROM_PTR(nlr.ret_val));
    }
}

void gc_collect(void) {
    gc_collect_start();
    gc_helper_collect_regs_and_stack();
    gc_collect_end();
}

void nlr_jump_fail(void *val) {
    for (;;) {
    }
}
