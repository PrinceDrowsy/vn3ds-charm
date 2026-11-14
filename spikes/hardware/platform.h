#ifndef SPIKE_PLATFORM_H
#define SPIKE_PLATFORM_H

#include <stdint.h>

// Microseconds since platform_init.
uint64_t platform_ticks_us(void);

#endif
