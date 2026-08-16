/**
 ******************************************************************************
 * @file    settings_manager.h
 * @brief   Settings Manager interface.
 ******************************************************************************
 */

#ifndef SETTINGS_MANAGER_H
#define SETTINGS_MANAGER_H

#include <stdint.h>
#include <stdbool.h>
#include "core/sys/include/syslog.h"
#include <stdio.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SM_MAGIC 0x544F5302u

typedef struct __attribute__((packed, aligned(4))) {
  uint32_t magic;
  uint32_t crc;
  uint8_t  disp_bright;
  uint8_t  disp_sleep_cfg;
  uint8_t  debug_dashboard;
  uint8_t  debug_log_com;
  bool     time_style_24h;
  bool     boot_gfx;
  bool     sound_mute;
  uint8_t  _reserved;
} Settings_t;

void SM_Init(void);
void SM_Mount(void);
void SM_Save(void);
bool SM_SdAvailable(void);
Settings_t *SM_Get(void);

uint8_t SM_Disp_Bright(void);
void    SM_Disp_SetBright(uint8_t v);
bool    SM_Disp_AutoClose(void);
void    SM_Disp_SetAutoClose(bool v);
uint8_t SM_Disp_CloseDelay(void);
void    SM_Disp_SetCloseDelay(uint8_t v);

bool SM_Debug_Dashboard(void);
void SM_Debug_SetDashboard(bool v);
bool SM_Debug_LogCom(void);
void SM_Debug_SetLogCom(bool v);

bool SM_Time_Style24h(void);
void SM_Time_SetStyle24h(bool v);

bool SM_BootGfx(void);
void SM_SetBootGfx(bool v);
bool SM_SoundMute(void);
void SM_SetSoundMute(bool v);

#ifdef __cplusplus
}
#endif

#endif
