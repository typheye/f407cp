#ifndef LIBTMP_H
#define LIBTMP_H

#include <stdbool.h>
#include <stddef.h>
#include "ff.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Removes all files left in data/temp from an earlier boot. */
FRESULT LibTmp_Cleanup(void);

/* Returns a unique 0:/data/temp/<12 alnum>.tmp path. */
bool LibTmp_CreatePath(char *out, size_t out_sz);

#ifdef __cplusplus
}
#endif
#endif
