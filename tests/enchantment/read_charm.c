/* Reads a .charm bundle through charm_schema.h and prints what it finds, so
 * tests can compare the C view of a bundle with Witch's reader. */
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

#include "charm_schema.h"

static const uint8_t *data;
static const charm_section *sections;
static uint32_t section_count;

static const void *section(uint32_t tag, uint32_t *size)
{
    for (uint32_t i = 0; i < section_count; i++) {
        if (sections[i].tag == tag) {
            *size = sections[i].size;
            return data + sections[i].offset;
        }
    }
    fprintf(stderr, "missing section %.4s\n", (const char *)&tag);
    exit(1);
}

int main(int argc, char **argv)
{
    if (argc != 2)
        return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f)
        return 2;
    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *buf = malloc(len);
    if (fread(buf, 1, len, f) != (size_t)len)
        return 2;
    fclose(f);
    data = buf;

    const charm_header *h = (const charm_header *)data;
    if (h->magic != CHARM_MAGIC || h->major != CHARM_VERSION_MAJOR || h->file_size != (uint32_t)len)
        return 3;
    sections = (const charm_section *)(data + sizeof *h);
    section_count = h->section_count;

    uint32_t size;
    const char *strs = section(CHARM_TAG_STRS, &size);
    const uint32_t *args = section(CHARM_TAG_ARGS, &size);
    const charm_node *nodes = section(CHARM_TAG_NODE, &size);
    uint32_t node_count = size / sizeof *nodes;
    const charm_label_entry *labels = section(CHARM_TAG_LABL, &size);
    uint32_t label_count = size / sizeof *labels;

    printf("nodes %" PRIu32 "\n", node_count);
    for (uint32_t i = 0; i < label_count; i++)
        printf("label %s %s\n", strs + labels[i].name, charm_node_kind_names[nodes[labels[i].node].kind]);
    for (uint32_t i = 0; i < node_count; i++) {
        const charm_node *n = &nodes[i];
        if (n->kind == CHARM_NODE_KIND_SAY) {
            const charm_say *say = (const charm_say *)(args + n->args);
            printf("say %s interact=%d\n", strs + say->what, (n->flags & CHARM_SAY_INTERACT) != 0);
        } else if (n->kind == CHARM_NODE_KIND_MENU) {
            const charm_menu *menu = (const charm_menu *)(args + n->args);
            const charm_menu_item *items = (const charm_menu_item *)(args + menu->items.offset);
            for (uint32_t j = 0; j < menu->items.count; j++)
                printf("item %s block=%d\n", strs + items[j].label, items[j].block == CHARM_NONE ? -1 : (int)items[j].block);
        }
    }
    free(buf);
    return 0;
}
