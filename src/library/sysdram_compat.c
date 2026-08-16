#include "include/dram.h"

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "core/sys/include/syslog.h"

typedef struct {
  size_t size;
  uint32_t magic;
} SysDramAllocHdr_t;

#define SYSDRAM_ALLOC_MAGIC 0x4452414DU /* 'DRAM' */

extern char _sccmram;
extern char _eccmram;

static uint32_t g_alloc_count;
static size_t g_ram_used_bytes;
static size_t g_ram_peak_bytes;

void SysDram_Free(void *ptr);

static void *dram_alloc(size_t size) {
  if (size == 0U) {
    size = 1U;
  }
  size_t total = sizeof(SysDramAllocHdr_t) + size;
  SysDramAllocHdr_t *hdr = (SysDramAllocHdr_t *)malloc(total);
  if (!hdr) {
    return NULL;
  }
  hdr->size = size;
  hdr->magic = SYSDRAM_ALLOC_MAGIC;
  g_ram_used_bytes += size;
  if (g_ram_used_bytes > g_ram_peak_bytes) {
    g_ram_peak_bytes = g_ram_used_bytes;
  }
  g_alloc_count++;
  return (void *)(hdr + 1);
}

static SysDramAllocHdr_t *dram_hdr_from_ptr(const void *ptr) {
  if (!ptr) {
    return NULL;
  }
  SysDramAllocHdr_t *hdr = ((SysDramAllocHdr_t *)ptr) - 1;
  if (hdr->magic != SYSDRAM_ALLOC_MAGIC) {
    return NULL;
  }
  return hdr;
}

void SysDram_Init(void) {}

void *SysDram_Alloc(size_t size) { return dram_alloc(size); }

void *SysDram_AllocFast(size_t size) { return dram_alloc(size); }

void *SysDram_AllocDma(size_t size) { return dram_alloc(size); }

void *SysDram_Calloc(size_t count, size_t size) {
  if (count != 0U && size > SIZE_MAX / count) {
    return NULL;
  }
  size_t total = count * size;
  void *p = dram_alloc(total);
  if (p) {
    memset(p, 0, total);
  }
  return p;
}

void *SysDram_Realloc(void *ptr, size_t size) {
  if (!ptr) {
    return dram_alloc(size);
  }
  if (size == 0U) {
    SysDram_Free(ptr);
    return NULL;
  }

  SysDramAllocHdr_t *old_hdr = dram_hdr_from_ptr(ptr);
  if (!old_hdr) {
    return dram_alloc(size);
  }

  void *next = dram_alloc(size);
  if (!next) {
    return NULL;
  }
  size_t copy_size = old_hdr->size < size ? old_hdr->size : size;
  memcpy(next, ptr, copy_size);
  SysDram_Free(ptr);
  return next;
}

void SysDram_Free(void *ptr) {
  if (!ptr) {
    return;
  }
  SysDramAllocHdr_t *hdr = dram_hdr_from_ptr(ptr);
  if (!hdr) {
    free(ptr);
    return;
  }
  if (g_ram_used_bytes >= hdr->size) {
    g_ram_used_bytes -= hdr->size;
  } else {
    g_ram_used_bytes = 0U;
  }
  hdr->magic = 0U;
  free(hdr);
}

int SysDram_GetStats(SysDramRegion_t region, SysDramStats_t *out) {
  if (!out) {
    return 0;
  }

  memset(out, 0, sizeof(*out));
  if (region == SYSDRAM_REGION_RAM) {
    out->total = 128U * 1024U;
    out->used = (uint32_t)(g_ram_used_bytes > out->total ? out->total
                                                         : g_ram_used_bytes);
    out->free = out->total - out->used;
    out->largest_free = out->free;
    out->alloc_count = g_alloc_count;
    out->peak_used = (uint32_t)(g_ram_peak_bytes > out->total ? out->total
                                                              : g_ram_peak_bytes);
    return 1;
  }

  out->total = 64U * 1024U;
  out->used = (uint32_t)((uintptr_t)&_eccmram - (uintptr_t)&_sccmram);
  if (out->used > out->total) {
    out->used = out->total;
  }
  out->free = out->total - out->used;
  out->largest_free = out->free;
  out->alloc_count = 0U;
  out->peak_used = out->used;
  return 1;
}

void SysDram_LogStats(void) {
  LOG_I("DRAM", "compat heap used=%lu peak=%lu alloc_count=%lu",
        (unsigned long)g_ram_used_bytes, (unsigned long)g_ram_peak_bytes,
        (unsigned long)g_alloc_count);
}

int SysDram_IsCcmPtr(const void *ptr) {
  const uintptr_t p = (uintptr_t)ptr;
  const uintptr_t s = (uintptr_t)&_sccmram;
  const uintptr_t e = (uintptr_t)&_eccmram;
  return ptr != NULL && p >= s && p < e;
}

int SysDram_IsRamPtr(const void *ptr) { return ptr != NULL && !SysDram_IsCcmPtr(ptr); }
