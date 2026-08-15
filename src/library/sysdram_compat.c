#include "include/dram.h"

#include <stdlib.h>
#include <string.h>

#include "core/sys/include/syslog.h"

static uint32_t g_alloc_count;

void SysDram_Init(void) {}

void *SysDram_Alloc(size_t size) {
  void *p = malloc(size);
  if (p) {
    g_alloc_count++;
  }
  return p;
}

void *SysDram_AllocFast(size_t size) { return SysDram_Alloc(size); }

void *SysDram_AllocDma(size_t size) { return SysDram_Alloc(size); }

void *SysDram_Calloc(size_t count, size_t size) {
  void *p = calloc(count, size);
  if (p) {
    g_alloc_count++;
  }
  return p;
}

void *SysDram_Realloc(void *ptr, size_t size) {
  void *p = realloc(ptr, size);
  if (p && !ptr) {
    g_alloc_count++;
  }
  return p;
}

void SysDram_Free(void *ptr) { free(ptr); }

int SysDram_GetStats(SysDramRegion_t region, SysDramStats_t *out) {
  if (!out) {
    return 0;
  }
  memset(out, 0, sizeof(*out));
  if (region == SYSDRAM_REGION_RAM) {
    out->total = 128U * 1024U;
    out->alloc_count = g_alloc_count;
  } else {
    out->total = 64U * 1024U;
  }
  out->free = out->total;
  out->largest_free = out->free;
  return 1;
}

void SysDram_LogStats(void) {
  LOG_I("DRAM", "compat heap, alloc_count=%lu",
        (unsigned long)g_alloc_count);
}

int SysDram_IsCcmPtr(const void *ptr) {
  (void)ptr;
  return 0;
}

int SysDram_IsRamPtr(const void *ptr) { return ptr != NULL; }
