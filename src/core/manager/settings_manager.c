/**
 ******************************************************************************
 * @file    settings_manager.c
 * @brief   Settings Manager implementation (SD card storage).
 ******************************************************************************
 */

#include "include/settings_manager.h"
#include "ff.h"
#include <stddef.h>

#define CCMRAM __attribute__((section(".ccmram")))

static CCMRAM Settings_t g_settings;
static bool g_sd_available = false;
static bool g_have_saved_crc = false;
static uint32_t g_last_saved_crc = 0U;

static uint32_t settings_crc(const Settings_t *settings) {
  const uint8_t *bytes = (const uint8_t *)settings;
  uint32_t crc = 0xFFFFFFFFU;
  for (size_t i = 0U; i < sizeof(*settings); ++i) {
    uint8_t value = (i >= offsetof(Settings_t, crc) &&
                     i < offsetof(Settings_t, crc) + sizeof(settings->crc))
                        ? 0U : bytes[i];
    crc ^= value;
    for (uint32_t bit = 0U; bit < 8U; ++bit) {
      crc = (crc >> 1) ^ (0xEDB88320U & (0U - (crc & 1U)));
    }
  }
  return ~crc;
}

static uint8_t disp_sleep_delay_idx(void) {
  return (uint8_t)((g_settings.disp_sleep_cfg >> 1U) & 0x07U);
}

static void sanitize(void) {
  if (g_settings.disp_bright < 1U || g_settings.disp_bright > 10U) {
    g_settings.disp_bright = 10U;
  }
  if (disp_sleep_delay_idx() > 5U) {
    g_settings.disp_sleep_cfg = 0x04U;
  }
  g_settings.debug_dashboard = g_settings.debug_dashboard ? 1U : 0U;
  g_settings.debug_log_com = g_settings.debug_log_com ? 1U : 0U;
  g_settings.time_style_24h = g_settings.time_style_24h ? true : false;
  g_settings.boot_gfx = g_settings.boot_gfx ? true : false;
  g_settings.sound_mute = g_settings.sound_mute ? true : false;
  g_settings._reserved = 0U;
}

static void defaults(void) {
  memset(&g_settings, 0, sizeof(g_settings));
  g_settings.magic = SM_MAGIC;
  g_settings.disp_bright = 10U;
  g_settings.disp_sleep_cfg = 0x04U;
  g_settings.debug_dashboard = 0U;
  g_settings.debug_log_com = 0U;
  g_settings.time_style_24h = true;
  g_settings.boot_gfx = true;
  g_settings.sound_mute = true;
  LOG_D("SMGR", "Defaults loaded");
}

static bool load(void) {
  FIL file;
  UINT br = 0U;
  Settings_t tmp;

  if (f_open(&file, "0:/data/settings.bin", FA_READ) != FR_OK) {
    return false;
  }
  memset(&tmp, 0, sizeof(tmp));
  if (f_read(&file, &tmp, sizeof(tmp), &br) != FR_OK) {
    f_close(&file);
    return false;
  }
  f_close(&file);

  if (br != sizeof(tmp)) {
    LOG_W("SMGR", "Settings size mismatch: %lu/%lu; rebuilding",
          (unsigned long)br, (unsigned long)sizeof(tmp));
    return false;
  }
  if (tmp.magic != SM_MAGIC) {
    LOG_W("SMGR", "Settings schema mismatch 0x%08lX; rebuilding",
          (unsigned long)tmp.magic);
    return false;
  }
  if (tmp.crc != settings_crc(&tmp)) {
    LOG_W("SMGR", "Settings CRC mismatch; rebuilding");
    return false;
  }

  memcpy(&g_settings, &tmp, sizeof(g_settings));
  sanitize();
  g_last_saved_crc = settings_crc(&g_settings);
  g_have_saved_crc = true;
  LOG_I("SMGR", "Loaded from SD OK (%luB)", (unsigned long)br);
  return true;
}

bool SM_SdAvailable(void) { return g_sd_available; }

void SM_Init(void) {
  defaults();
  g_have_saved_crc = false;
  g_last_saved_crc = 0U;
}

void SM_Mount(void) {
  FIL file;
  FRESULT res;

  g_sd_available = false;
  res = f_mkdir("0:/data");
  if (res != FR_OK && res != FR_EXIST) {
    LOG_W("SMGR", "Cannot create data directory (%d)", (int)res);
    return;
  }

  res = f_open(&file, "0:/data/settings.bin", FA_OPEN_EXISTING);
  if (res == FR_OK) {
    g_sd_available = true;
    f_close(&file);
  } else if (res == FR_NO_FILE || res == FR_NO_PATH) {
    g_sd_available = true;
  } else {
    LOG_W("SMGR", "SD not available for settings (%d)", (int)res);
    return;
  }

  if (!load()) {
    LOG_W("SMGR", "Load failed, using defaults");
    SM_Save();
  }
}

void SM_Save(void) {
  FIL file;
  UINT bw = 0U;
  FRESULT res;
  uint32_t start_ms = HAL_GetTick();

  sanitize();
  g_settings.magic = SM_MAGIC;
  g_settings.crc = settings_crc(&g_settings);
  if (g_sd_available && g_have_saved_crc && g_settings.crc == g_last_saved_crc) {
    return;
  }

  res = f_open(&file, "0:/data/settings.bin", FA_CREATE_ALWAYS | FA_WRITE);
  g_sd_available = false;
  if (res == FR_OK) {
    if (f_write(&file, &g_settings, sizeof(g_settings), &bw) == FR_OK &&
        bw == sizeof(g_settings)) {
      res = f_sync(&file);
      if (res == FR_OK) {
        g_sd_available = true;
        g_last_saved_crc = g_settings.crc;
        g_have_saved_crc = true;
        LOG_I("SMGR", "Saved to SD OK (%luB)",
              (unsigned long)sizeof(g_settings));
      } else {
        LOG_E("SMGR", "Save: sync failed (%d)", (int)res);
      }
    } else {
      LOG_E("SMGR", "Save: write failed (%lu/%lu)",
            (unsigned long)bw, (unsigned long)sizeof(g_settings));
    }
    res = f_close(&file);
    if (res != FR_OK) {
      g_sd_available = false;
      LOG_E("SMGR", "Save: close failed (%d)", (int)res);
    }
  } else {
    LOG_W("SMGR", "Save: open failed (%d)", (int)res);
  }

  {
    uint32_t elapsed = HAL_GetTick() - start_ms;
    if (elapsed > 150U) {
      LOG_W("SMGR", "Save took %lums", (unsigned long)elapsed);
    }
  }
}

Settings_t *SM_Get(void) { return &g_settings; }

uint8_t SM_Disp_Bright(void) { return g_settings.disp_bright; }
void SM_Disp_SetBright(uint8_t v) {
  if (v < 1U) v = 1U;
  if (v > 10U) v = 10U;
  if (g_settings.disp_bright != v) {
    g_settings.disp_bright = v;
    SM_Save();
  }
}

bool SM_Debug_Dashboard(void) { return g_settings.debug_dashboard != 0U; }
void SM_Debug_SetDashboard(bool v) {
  uint8_t next = v ? 1U : 0U;
  if (g_settings.debug_dashboard != next) {
    g_settings.debug_dashboard = next;
    SM_Save();
  }
}

bool SM_Debug_LogCom(void) { return g_settings.debug_log_com != 0U; }
void SM_Debug_SetLogCom(bool v) {
  uint8_t next = v ? 1U : 0U;
  if (g_settings.debug_log_com != next) {
    g_settings.debug_log_com = next;
    SM_Save();
  }
}

bool SM_Time_Style24h(void) { return g_settings.time_style_24h; }
void SM_Time_SetStyle24h(bool v) {
  v = v ? true : false;
  if (g_settings.time_style_24h != v) {
    g_settings.time_style_24h = v;
    SM_Save();
  }
}

bool SM_BootGfx(void) { return g_settings.boot_gfx; }
void SM_SetBootGfx(bool v) {
  v = v ? true : false;
  if (g_settings.boot_gfx != v) {
    g_settings.boot_gfx = v;
    SM_Save();
  }
}

bool SM_SoundMute(void) { return g_settings.sound_mute; }
void SM_SetSoundMute(bool v) {
  v = v ? true : false;
  if (g_settings.sound_mute != v) {
    g_settings.sound_mute = v;
    SM_Save();
  }
}

bool SM_Disp_AutoClose(void) {
  return (g_settings.disp_sleep_cfg & 0x01U) != 0U;
}

void SM_Disp_SetAutoClose(bool v) {
  uint8_t next = (uint8_t)((disp_sleep_delay_idx() << 1U) | (v ? 1U : 0U));
  if (g_settings.disp_sleep_cfg != next) {
    g_settings.disp_sleep_cfg = next;
    SM_Save();
  }
}

uint8_t SM_Disp_CloseDelay(void) { return disp_sleep_delay_idx(); }

void SM_Disp_SetCloseDelay(uint8_t v) {
  if (v > 5U) v = 2U;
  uint8_t next = (uint8_t)((v << 1U) | (g_settings.disp_sleep_cfg & 0x01U));
  if (g_settings.disp_sleep_cfg != next) {
    g_settings.disp_sleep_cfg = next;
    SM_Save();
  }
}
