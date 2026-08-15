#ifndef TOS_SYSWATCHDOG_H
#define TOS_SYSWATCHDOG_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

void SysWatchdog_Init(void);
void SysWatchdog_FeedNow(void);
void SysWatchdog_Tick(void);
uint32_t SysWatchdog_GetBootCode(void);
const char *SysWatchdog_GetBootText(void);

#ifdef __cplusplus
}
#endif

#endif
