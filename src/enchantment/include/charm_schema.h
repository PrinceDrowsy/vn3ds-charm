/* Generated from src/witch/bundle/schema.py by `python -m witch.bundle.cgen`. Do not edit. */
#ifndef CHARM_SCHEMA_H
#define CHARM_SCHEMA_H

#include <stddef.h>
#include <stdint.h>

#define CHARM_VERSION_MAJOR 0
#define CHARM_VERSION_MINOR 2
#define CHARM_MAGIC 0x4d524843u
#define CHARM_NONE 0xffffffffu
#define CHARM_ALIGN 16

#define CHARM_TAG_STRS 0x53525453u
#define CHARM_TAG_ARGS 0x53475241u
#define CHARM_TAG_NODE 0x45444f4eu
#define CHARM_TAG_NAME 0x454d414eu
#define CHARM_TAG_LOCS 0x53434f4cu
#define CHARM_TAG_LABL 0x4c42414cu
#define CHARM_TAG_CODE 0x45444f43u
#define CHARM_TAG_MPYB 0x4259504du
#define CHARM_TAG_ASST 0x54535341u
#define CHARM_TAG_DATA 0x41544144u
#define CHARM_TAG_IMGS 0x53474d49u
#define CHARM_TAG_DISP 0x50534944u

typedef struct { uint32_t offset; uint32_t count; } charm_list; /* words into ARGS */

enum charm_node_kind {
    CHARM_NODE_KIND_UNKNOWN = 0,
    CHARM_NODE_KIND_LABEL = 1,
    CHARM_NODE_KIND_SAY = 2,
    CHARM_NODE_KIND_SHOW = 3,
    CHARM_NODE_KIND_SCENE = 4,
    CHARM_NODE_KIND_HIDE = 5,
    CHARM_NODE_KIND_WITH = 6,
    CHARM_NODE_KIND_JUMP = 7,
    CHARM_NODE_KIND_JUMP_EXPRESSION = 8,
    CHARM_NODE_KIND_CALL = 9,
    CHARM_NODE_KIND_CALL_EXPRESSION = 10,
    CHARM_NODE_KIND_RETURN = 11,
    CHARM_NODE_KIND_MENU = 12,
    CHARM_NODE_KIND_IF = 13,
    CHARM_NODE_KIND_WHILE = 14,
    CHARM_NODE_KIND_PYTHON = 15,
    CHARM_NODE_KIND_PASS = 16,
    CHARM_NODE_KIND_USER_STATEMENT = 17,
    CHARM_NODE_KIND_TRANSLATE = 18,
    CHARM_NODE_KIND_END_TRANSLATE = 19,
    CHARM_NODE_KIND_SHOW_LAYER = 20,
    CHARM_NODE_KIND_CAMERA = 21,
    CHARM_NODE_KIND_INIT = 22,
    CHARM_NODE_KIND_EARLY_PYTHON = 23,
    CHARM_NODE_KIND_DEFINE = 24,
    CHARM_NODE_KIND_DEFAULT = 25,
    CHARM_NODE_KIND_IMAGE = 26,
    CHARM_NODE_KIND_TRANSFORM = 27,
    CHARM_NODE_KIND_STYLE = 28,
    CHARM_NODE_KIND_SCREEN = 29,
    CHARM_NODE_KIND_TESTCASE = 30,
    CHARM_NODE_KIND_TRANSLATE_STRING = 31,
    CHARM_NODE_KIND_TRANSLATE_PYTHON = 32,
    CHARM_NODE_KIND_TRANSLATE_BLOCK = 33,
};
#define CHARM_NODE_KIND_COUNT 34
#define CHARM_SAY_INTERACT (1u << 0)
#define CHARM_SHOW_ATL (1u << 0)
#define CHARM_SCENE_ATL (1u << 0)
#define CHARM_PYTHON_HIDE (1u << 0)
#define CHARM_SHOW_LAYER_ATL (1u << 0)
#define CHARM_CAMERA_ATL (1u << 0)
#define CHARM_EARLY_PYTHON_HIDE (1u << 0)
#define CHARM_IMAGE_ATL (1u << 0)
#define CHARM_TRANSFORM_ATL (1u << 0)
#define CHARM_TRANSLATE_BLOCK_EARLY (1u << 0)
static const char *const charm_node_kind_names[] = {"unknown", "label", "say", "show", "scene", "hide", "with", "jump", "jump_expression", "call", "call_expression", "return", "menu", "if", "while", "python", "pass", "user_statement", "translate", "end_translate", "show_layer", "camera", "init", "early_python", "define", "default", "image", "transform", "style", "screen", "testcase", "translate_string", "translate_python", "translate_block"};

enum charm_disp_kind {
    CHARM_DISP_KIND_UNKNOWN = 0,
    CHARM_DISP_KIND_IMAGE = 1,
};
#define CHARM_DISP_KIND_COUNT 2
static const char *const charm_disp_kind_names[] = {"unknown", "image"};

enum charm_asset_type {
    CHARM_ASSET_TYPE_OTHER = 0,
    CHARM_ASSET_TYPE_IMAGE = 1,
    CHARM_ASSET_TYPE_AUDIO = 2,
    CHARM_ASSET_TYPE_FONT = 3,
    CHARM_ASSET_TYPE_VIDEO = 4,
};
#define CHARM_ASSET_TYPE_COUNT 5

enum charm_asset_format {
    CHARM_ASSET_FORMAT_SOURCE = 0,
};
#define CHARM_ASSET_FORMAT_COUNT 1

enum charm_code_mode {
    CHARM_CODE_MODE_EVAL = 0,
    CHARM_CODE_MODE_EXEC = 1,
    CHARM_CODE_MODE_HIDE = 2,
    CHARM_CODE_MODE_PARAMETERS = 3,
    CHARM_CODE_MODE_ARGUMENTS = 4,
};
#define CHARM_CODE_MODE_COUNT 5

typedef struct {
    uint32_t magic;
    uint16_t major;
    uint16_t minor;
    uint32_t section_count;
    uint32_t file_size;
} charm_header;
typedef struct {
    uint32_t tag;
    uint32_t chunk;
    uint32_t offset;
    uint32_t size;
} charm_section;
typedef struct {
    uint16_t kind;
    uint16_t flags;
    uint32_t next; /* NODE */
    uint32_t args;
} charm_node;
typedef struct {
    uint32_t name; /* STRS */
} charm_node_name;
typedef struct {
    uint32_t file; /* STRS */
    uint32_t line;
} charm_node_loc;
typedef struct {
    uint32_t name; /* STRS */
    uint32_t node; /* NODE */
} charm_label_entry;
typedef struct {
    uint32_t source; /* STRS */
    uint32_t mode;
    uint32_t mpy;
    uint32_t mpy_size;
} charm_code;
typedef struct {
    uint32_t path; /* STRS */
    uint32_t type;
    uint32_t format;
    uint32_t offset;
    uint32_t size;
    uint32_t width;
    uint32_t height;
} charm_asset;
typedef struct {
    uint32_t name; /* STRS */
    uint32_t disp; /* DISP */
} charm_image_entry;
typedef struct {
    uint16_t kind;
    uint16_t flags;
    uint32_t args;
} charm_disp;
typedef struct {
    uint32_t classname; /* STRS */
} charm_unknown;
typedef struct {
    uint32_t name; /* STRS */
    uint32_t parameters; /* CODE */
} charm_label;
typedef struct {
    uint32_t who; /* CODE */
    uint32_t what; /* STRS */
    charm_list attributes; /* of STRS */
    charm_list temporary_attributes; /* of STRS */
    uint32_t with; /* CODE */
    uint32_t arguments; /* CODE */
    uint32_t identifier; /* STRS */
} charm_say;
typedef struct {
    charm_list name; /* of STRS */
    uint32_t expression; /* CODE */
    uint32_t tag; /* STRS */
    charm_list at; /* of CODE */
    uint32_t layer; /* STRS */
    uint32_t zorder; /* CODE */
    charm_list behind; /* of STRS */
} charm_show;
typedef struct {
    charm_list name; /* of STRS */
    uint32_t expression; /* CODE */
    uint32_t tag; /* STRS */
    charm_list at; /* of CODE */
    uint32_t layer; /* STRS */
    uint32_t zorder; /* CODE */
    charm_list behind; /* of STRS */
} charm_scene;
typedef struct {
    charm_list name; /* of STRS */
    uint32_t expression; /* CODE */
    uint32_t tag; /* STRS */
    charm_list at; /* of CODE */
    uint32_t layer; /* STRS */
    uint32_t zorder; /* CODE */
    charm_list behind; /* of STRS */
} charm_hide;
typedef struct {
    uint32_t expr; /* CODE */
    uint32_t paired; /* CODE */
} charm_with;
typedef struct {
    uint32_t target; /* STRS */
} charm_jump;
typedef struct {
    uint32_t target; /* CODE */
} charm_jump_expression;
typedef struct {
    uint32_t label; /* STRS */
    uint32_t arguments; /* CODE */
} charm_call;
typedef struct {
    uint32_t label; /* CODE */
    uint32_t arguments; /* CODE */
} charm_call_expression;
typedef struct {
    uint32_t expression; /* CODE */
} charm_return;
typedef struct {
    uint32_t label; /* STRS */
    uint32_t condition; /* CODE */
    uint32_t block; /* NODE */
    uint32_t arguments; /* CODE */
} charm_menu_item;
typedef struct {
    charm_list items; /* of charm_menu_item */
    uint32_t set; /* CODE */
    uint32_t with; /* CODE */
    uint32_t arguments; /* CODE */
} charm_menu;
typedef struct {
    uint32_t condition; /* CODE */
    uint32_t block; /* NODE */
} charm_if_entry;
typedef struct {
    charm_list entries; /* of charm_if_entry */
} charm_if;
typedef struct {
    uint32_t condition; /* CODE */
    uint32_t block; /* NODE */
} charm_while;
typedef struct {
    uint32_t code; /* CODE */
    uint32_t store; /* STRS */
} charm_python;
typedef struct {
    uint32_t name; /* STRS */
    uint32_t line; /* STRS */
} charm_user_statement;
typedef struct {
    uint32_t identifier; /* STRS */
    uint32_t language; /* STRS */
    uint32_t block; /* NODE */
} charm_translate;
typedef struct {
    uint32_t layer; /* STRS */
    charm_list at; /* of CODE */
} charm_show_layer;
typedef struct {
    uint32_t layer; /* STRS */
    charm_list at; /* of CODE */
} charm_camera;
typedef struct {
    int32_t priority;
    uint32_t block; /* NODE */
} charm_init;
typedef struct {
    uint32_t code; /* CODE */
    uint32_t store; /* STRS */
} charm_early_python;
typedef struct {
    uint32_t store; /* STRS */
    uint32_t varname; /* STRS */
    uint32_t operator; /* STRS */
    uint32_t index; /* CODE */
    uint32_t code; /* CODE */
} charm_define;
typedef struct {
    uint32_t store; /* STRS */
    uint32_t varname; /* STRS */
    uint32_t code; /* CODE */
} charm_default;
typedef struct {
    charm_list name; /* of STRS */
    uint32_t code; /* CODE */
} charm_image;
typedef struct {
    uint32_t store; /* STRS */
    uint32_t varname; /* STRS */
    uint32_t parameters; /* CODE */
} charm_transform;
typedef struct {
    uint32_t name; /* STRS */
    uint32_t parent; /* STRS */
} charm_style;
typedef struct {
    uint32_t name; /* STRS */
} charm_screen;
typedef struct {
    uint32_t label; /* STRS */
} charm_testcase;
typedef struct {
    uint32_t language; /* STRS */
    uint32_t old; /* STRS */
    uint32_t new; /* STRS */
} charm_translate_string;
typedef struct {
    uint32_t language; /* STRS */
    uint32_t code; /* CODE */
} charm_translate_python;
typedef struct {
    uint32_t language; /* STRS */
    uint32_t block; /* NODE */
} charm_translate_block;
typedef struct {
    uint32_t classname; /* STRS */
} charm_disp_unknown;
typedef struct {
    uint32_t asset; /* ASST */
} charm_disp_image;

_Static_assert(sizeof(charm_header) == 16, "charm_header size");
_Static_assert(offsetof(charm_header, magic) == 0, "charm_header.magic");
_Static_assert(offsetof(charm_header, major) == 4, "charm_header.major");
_Static_assert(offsetof(charm_header, minor) == 6, "charm_header.minor");
_Static_assert(offsetof(charm_header, section_count) == 8, "charm_header.section_count");
_Static_assert(offsetof(charm_header, file_size) == 12, "charm_header.file_size");
_Static_assert(sizeof(charm_section) == 16, "charm_section size");
_Static_assert(offsetof(charm_section, tag) == 0, "charm_section.tag");
_Static_assert(offsetof(charm_section, chunk) == 4, "charm_section.chunk");
_Static_assert(offsetof(charm_section, offset) == 8, "charm_section.offset");
_Static_assert(offsetof(charm_section, size) == 12, "charm_section.size");
_Static_assert(sizeof(charm_node) == 12, "charm_node size");
_Static_assert(offsetof(charm_node, kind) == 0, "charm_node.kind");
_Static_assert(offsetof(charm_node, flags) == 2, "charm_node.flags");
_Static_assert(offsetof(charm_node, next) == 4, "charm_node.next");
_Static_assert(offsetof(charm_node, args) == 8, "charm_node.args");
_Static_assert(sizeof(charm_node_name) == 4, "charm_node_name size");
_Static_assert(offsetof(charm_node_name, name) == 0, "charm_node_name.name");
_Static_assert(sizeof(charm_node_loc) == 8, "charm_node_loc size");
_Static_assert(offsetof(charm_node_loc, file) == 0, "charm_node_loc.file");
_Static_assert(offsetof(charm_node_loc, line) == 4, "charm_node_loc.line");
_Static_assert(sizeof(charm_label_entry) == 8, "charm_label_entry size");
_Static_assert(offsetof(charm_label_entry, name) == 0, "charm_label_entry.name");
_Static_assert(offsetof(charm_label_entry, node) == 4, "charm_label_entry.node");
_Static_assert(sizeof(charm_code) == 16, "charm_code size");
_Static_assert(offsetof(charm_code, source) == 0, "charm_code.source");
_Static_assert(offsetof(charm_code, mode) == 4, "charm_code.mode");
_Static_assert(offsetof(charm_code, mpy) == 8, "charm_code.mpy");
_Static_assert(offsetof(charm_code, mpy_size) == 12, "charm_code.mpy_size");
_Static_assert(sizeof(charm_asset) == 28, "charm_asset size");
_Static_assert(offsetof(charm_asset, path) == 0, "charm_asset.path");
_Static_assert(offsetof(charm_asset, type) == 4, "charm_asset.type");
_Static_assert(offsetof(charm_asset, format) == 8, "charm_asset.format");
_Static_assert(offsetof(charm_asset, offset) == 12, "charm_asset.offset");
_Static_assert(offsetof(charm_asset, size) == 16, "charm_asset.size");
_Static_assert(offsetof(charm_asset, width) == 20, "charm_asset.width");
_Static_assert(offsetof(charm_asset, height) == 24, "charm_asset.height");
_Static_assert(sizeof(charm_image_entry) == 8, "charm_image_entry size");
_Static_assert(offsetof(charm_image_entry, name) == 0, "charm_image_entry.name");
_Static_assert(offsetof(charm_image_entry, disp) == 4, "charm_image_entry.disp");
_Static_assert(sizeof(charm_disp) == 8, "charm_disp size");
_Static_assert(offsetof(charm_disp, kind) == 0, "charm_disp.kind");
_Static_assert(offsetof(charm_disp, flags) == 2, "charm_disp.flags");
_Static_assert(offsetof(charm_disp, args) == 4, "charm_disp.args");
_Static_assert(sizeof(charm_unknown) == 4, "charm_unknown size");
_Static_assert(offsetof(charm_unknown, classname) == 0, "charm_unknown.classname");
_Static_assert(sizeof(charm_label) == 8, "charm_label size");
_Static_assert(offsetof(charm_label, name) == 0, "charm_label.name");
_Static_assert(offsetof(charm_label, parameters) == 4, "charm_label.parameters");
_Static_assert(sizeof(charm_say) == 36, "charm_say size");
_Static_assert(offsetof(charm_say, who) == 0, "charm_say.who");
_Static_assert(offsetof(charm_say, what) == 4, "charm_say.what");
_Static_assert(offsetof(charm_say, attributes) == 8, "charm_say.attributes");
_Static_assert(offsetof(charm_say, temporary_attributes) == 16, "charm_say.temporary_attributes");
_Static_assert(offsetof(charm_say, with) == 24, "charm_say.with");
_Static_assert(offsetof(charm_say, arguments) == 28, "charm_say.arguments");
_Static_assert(offsetof(charm_say, identifier) == 32, "charm_say.identifier");
_Static_assert(sizeof(charm_show) == 40, "charm_show size");
_Static_assert(offsetof(charm_show, name) == 0, "charm_show.name");
_Static_assert(offsetof(charm_show, expression) == 8, "charm_show.expression");
_Static_assert(offsetof(charm_show, tag) == 12, "charm_show.tag");
_Static_assert(offsetof(charm_show, at) == 16, "charm_show.at");
_Static_assert(offsetof(charm_show, layer) == 24, "charm_show.layer");
_Static_assert(offsetof(charm_show, zorder) == 28, "charm_show.zorder");
_Static_assert(offsetof(charm_show, behind) == 32, "charm_show.behind");
_Static_assert(sizeof(charm_scene) == 40, "charm_scene size");
_Static_assert(offsetof(charm_scene, name) == 0, "charm_scene.name");
_Static_assert(offsetof(charm_scene, expression) == 8, "charm_scene.expression");
_Static_assert(offsetof(charm_scene, tag) == 12, "charm_scene.tag");
_Static_assert(offsetof(charm_scene, at) == 16, "charm_scene.at");
_Static_assert(offsetof(charm_scene, layer) == 24, "charm_scene.layer");
_Static_assert(offsetof(charm_scene, zorder) == 28, "charm_scene.zorder");
_Static_assert(offsetof(charm_scene, behind) == 32, "charm_scene.behind");
_Static_assert(sizeof(charm_hide) == 40, "charm_hide size");
_Static_assert(offsetof(charm_hide, name) == 0, "charm_hide.name");
_Static_assert(offsetof(charm_hide, expression) == 8, "charm_hide.expression");
_Static_assert(offsetof(charm_hide, tag) == 12, "charm_hide.tag");
_Static_assert(offsetof(charm_hide, at) == 16, "charm_hide.at");
_Static_assert(offsetof(charm_hide, layer) == 24, "charm_hide.layer");
_Static_assert(offsetof(charm_hide, zorder) == 28, "charm_hide.zorder");
_Static_assert(offsetof(charm_hide, behind) == 32, "charm_hide.behind");
_Static_assert(sizeof(charm_with) == 8, "charm_with size");
_Static_assert(offsetof(charm_with, expr) == 0, "charm_with.expr");
_Static_assert(offsetof(charm_with, paired) == 4, "charm_with.paired");
_Static_assert(sizeof(charm_jump) == 4, "charm_jump size");
_Static_assert(offsetof(charm_jump, target) == 0, "charm_jump.target");
_Static_assert(sizeof(charm_jump_expression) == 4, "charm_jump_expression size");
_Static_assert(offsetof(charm_jump_expression, target) == 0, "charm_jump_expression.target");
_Static_assert(sizeof(charm_call) == 8, "charm_call size");
_Static_assert(offsetof(charm_call, label) == 0, "charm_call.label");
_Static_assert(offsetof(charm_call, arguments) == 4, "charm_call.arguments");
_Static_assert(sizeof(charm_call_expression) == 8, "charm_call_expression size");
_Static_assert(offsetof(charm_call_expression, label) == 0, "charm_call_expression.label");
_Static_assert(offsetof(charm_call_expression, arguments) == 4, "charm_call_expression.arguments");
_Static_assert(sizeof(charm_return) == 4, "charm_return size");
_Static_assert(offsetof(charm_return, expression) == 0, "charm_return.expression");
_Static_assert(sizeof(charm_menu_item) == 16, "charm_menu_item size");
_Static_assert(offsetof(charm_menu_item, label) == 0, "charm_menu_item.label");
_Static_assert(offsetof(charm_menu_item, condition) == 4, "charm_menu_item.condition");
_Static_assert(offsetof(charm_menu_item, block) == 8, "charm_menu_item.block");
_Static_assert(offsetof(charm_menu_item, arguments) == 12, "charm_menu_item.arguments");
_Static_assert(sizeof(charm_menu) == 20, "charm_menu size");
_Static_assert(offsetof(charm_menu, items) == 0, "charm_menu.items");
_Static_assert(offsetof(charm_menu, set) == 8, "charm_menu.set");
_Static_assert(offsetof(charm_menu, with) == 12, "charm_menu.with");
_Static_assert(offsetof(charm_menu, arguments) == 16, "charm_menu.arguments");
_Static_assert(sizeof(charm_if_entry) == 8, "charm_if_entry size");
_Static_assert(offsetof(charm_if_entry, condition) == 0, "charm_if_entry.condition");
_Static_assert(offsetof(charm_if_entry, block) == 4, "charm_if_entry.block");
_Static_assert(sizeof(charm_if) == 8, "charm_if size");
_Static_assert(offsetof(charm_if, entries) == 0, "charm_if.entries");
_Static_assert(sizeof(charm_while) == 8, "charm_while size");
_Static_assert(offsetof(charm_while, condition) == 0, "charm_while.condition");
_Static_assert(offsetof(charm_while, block) == 4, "charm_while.block");
_Static_assert(sizeof(charm_python) == 8, "charm_python size");
_Static_assert(offsetof(charm_python, code) == 0, "charm_python.code");
_Static_assert(offsetof(charm_python, store) == 4, "charm_python.store");
_Static_assert(sizeof(charm_user_statement) == 8, "charm_user_statement size");
_Static_assert(offsetof(charm_user_statement, name) == 0, "charm_user_statement.name");
_Static_assert(offsetof(charm_user_statement, line) == 4, "charm_user_statement.line");
_Static_assert(sizeof(charm_translate) == 12, "charm_translate size");
_Static_assert(offsetof(charm_translate, identifier) == 0, "charm_translate.identifier");
_Static_assert(offsetof(charm_translate, language) == 4, "charm_translate.language");
_Static_assert(offsetof(charm_translate, block) == 8, "charm_translate.block");
_Static_assert(sizeof(charm_show_layer) == 12, "charm_show_layer size");
_Static_assert(offsetof(charm_show_layer, layer) == 0, "charm_show_layer.layer");
_Static_assert(offsetof(charm_show_layer, at) == 4, "charm_show_layer.at");
_Static_assert(sizeof(charm_camera) == 12, "charm_camera size");
_Static_assert(offsetof(charm_camera, layer) == 0, "charm_camera.layer");
_Static_assert(offsetof(charm_camera, at) == 4, "charm_camera.at");
_Static_assert(sizeof(charm_init) == 8, "charm_init size");
_Static_assert(offsetof(charm_init, priority) == 0, "charm_init.priority");
_Static_assert(offsetof(charm_init, block) == 4, "charm_init.block");
_Static_assert(sizeof(charm_early_python) == 8, "charm_early_python size");
_Static_assert(offsetof(charm_early_python, code) == 0, "charm_early_python.code");
_Static_assert(offsetof(charm_early_python, store) == 4, "charm_early_python.store");
_Static_assert(sizeof(charm_define) == 20, "charm_define size");
_Static_assert(offsetof(charm_define, store) == 0, "charm_define.store");
_Static_assert(offsetof(charm_define, varname) == 4, "charm_define.varname");
_Static_assert(offsetof(charm_define, operator) == 8, "charm_define.operator");
_Static_assert(offsetof(charm_define, index) == 12, "charm_define.index");
_Static_assert(offsetof(charm_define, code) == 16, "charm_define.code");
_Static_assert(sizeof(charm_default) == 12, "charm_default size");
_Static_assert(offsetof(charm_default, store) == 0, "charm_default.store");
_Static_assert(offsetof(charm_default, varname) == 4, "charm_default.varname");
_Static_assert(offsetof(charm_default, code) == 8, "charm_default.code");
_Static_assert(sizeof(charm_image) == 12, "charm_image size");
_Static_assert(offsetof(charm_image, name) == 0, "charm_image.name");
_Static_assert(offsetof(charm_image, code) == 8, "charm_image.code");
_Static_assert(sizeof(charm_transform) == 12, "charm_transform size");
_Static_assert(offsetof(charm_transform, store) == 0, "charm_transform.store");
_Static_assert(offsetof(charm_transform, varname) == 4, "charm_transform.varname");
_Static_assert(offsetof(charm_transform, parameters) == 8, "charm_transform.parameters");
_Static_assert(sizeof(charm_style) == 8, "charm_style size");
_Static_assert(offsetof(charm_style, name) == 0, "charm_style.name");
_Static_assert(offsetof(charm_style, parent) == 4, "charm_style.parent");
_Static_assert(sizeof(charm_screen) == 4, "charm_screen size");
_Static_assert(offsetof(charm_screen, name) == 0, "charm_screen.name");
_Static_assert(sizeof(charm_testcase) == 4, "charm_testcase size");
_Static_assert(offsetof(charm_testcase, label) == 0, "charm_testcase.label");
_Static_assert(sizeof(charm_translate_string) == 12, "charm_translate_string size");
_Static_assert(offsetof(charm_translate_string, language) == 0, "charm_translate_string.language");
_Static_assert(offsetof(charm_translate_string, old) == 4, "charm_translate_string.old");
_Static_assert(offsetof(charm_translate_string, new) == 8, "charm_translate_string.new");
_Static_assert(sizeof(charm_translate_python) == 8, "charm_translate_python size");
_Static_assert(offsetof(charm_translate_python, language) == 0, "charm_translate_python.language");
_Static_assert(offsetof(charm_translate_python, code) == 4, "charm_translate_python.code");
_Static_assert(sizeof(charm_translate_block) == 8, "charm_translate_block size");
_Static_assert(offsetof(charm_translate_block, language) == 0, "charm_translate_block.language");
_Static_assert(offsetof(charm_translate_block, block) == 4, "charm_translate_block.block");
_Static_assert(sizeof(charm_disp_unknown) == 4, "charm_disp_unknown size");
_Static_assert(offsetof(charm_disp_unknown, classname) == 0, "charm_disp_unknown.classname");
_Static_assert(sizeof(charm_disp_image) == 4, "charm_disp_image size");
_Static_assert(offsetof(charm_disp_image, asset) == 0, "charm_disp_image.asset");

#endif
