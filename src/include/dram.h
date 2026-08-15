#ifndef TOS_SYSTEM_DRAM_COMPAT_H
#define TOS_SYSTEM_DRAM_COMPAT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
  SYSDRAM_REGION_RAM = 0,
  SYSDRAM_REGION_CCM = 1,
} SysDramRegion_t;

typedef struct {
  uint32_t total;
  uint32_t used;
  uint32_t free;
  uint32_t largest_free;
  uint32_t alloc_count;
  uint32_t peak_used;
} SysDramStats_t;

void SysDram_Init(void);
void *SysDram_Alloc(size_t size);
void *SysDram_AllocFast(size_t size);
void *SysDram_AllocDma(size_t size);
void *SysDram_Calloc(size_t count, size_t size);
void *SysDram_Realloc(void *ptr, size_t size);
void SysDram_Free(void *ptr);

int SysDram_GetStats(SysDramRegion_t region, SysDramStats_t *out);
void SysDram_LogStats(void);
int SysDram_IsCcmPtr(const void *ptr);
int SysDram_IsRamPtr(const void *ptr);

#ifdef __cplusplus
}
#endif

#endif /* TOS_SYSTEM_DRAM_COMPAT_H */
