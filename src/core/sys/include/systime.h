/**
 ****************************************************************************** 
 * @file    systime.h
 * @author  Typheye
 * @brief   Systime interface.
 ****************************************************************************** 
 */

#ifndef SYSTIME_H
#define SYSTIME_H

#include <stdbool.h>
#include "core/manager/include/settings_manager.h"
#ifdef __cplusplus
#include "hardware/include/trtc.hpp"
#endif
#include "core/sys/include/syslog.h"
#include <stdio.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

bool SysTime_Sync(void);
bool SysTime_SyncQuick(void);
void SysTime_Fmt(char *buf, int sz, int h24, int m);
void SysTime_FmtStyle(char *buf, int sz, int h24, int m, bool style_24h);

#ifdef __cplusplus
}
#endif

#endif
