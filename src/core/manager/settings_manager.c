/**
 ******************************************************************************
 * @file    settings_manager.c
 * @brief   Settings Manager implementation (JSON on SD card).
 ******************************************************************************
 */

#include "include/settings_manager.h"
#include "core/manager/include/file_manager.h"
#include "ff.h"
#include "library/include/libjson.h"
#include <stdarg.h>
#include <stddef.h>

#define CCMRAM __attribute__((section(".ccmram")))

#define SM_JSON_PATH "0:/data/settings.json"
#define SM_JSON_TMP "0:/data/settings.tmp"
#define SM_JSON_MAX 384U
#define SM_SELFTEST_TMP "0:/data/_sm_probe.tmp"
#define SM_SELFTEST_PATH "0:/data/_sm_probe.json"

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
                        ? 0U
                        : bytes[i];
    crc ^= value;
    for (uint32_t bit = 0U; bit < 8U; ++bit) {
      crc = (crc >> 1) ^ (0xEDB88320U & (0U - (crc & 1U)));
    }
  }
  return ~crc;
}

static void sm_trace(const char *fmt, ...) {
  va_list ap;
  printf("%s [SMGR] ", SysLog_Ts());
  va_start(ap, fmt);
  vprintf(fmt, ap);
  va_end(ap);
  printf("\r\n");
}

static FRESULT ensure_ready(void) {
  FRESULT res = FMCore_MountStorage(NULL, false);
  if (res != FR_OK) {
    sm_trace("mount storage failed: %d", (int)res);
    return res;
  }
  if (!FMCore_IsInitialized()) {
    sm_trace("0:/init marker invalid");
    return FR_NOT_READY;
  }
  res = f_mkdir("0:/data");
  if (res != FR_OK && res != FR_EXIST) {
    sm_trace("mkdir 0:/data failed: %d", (int)res);
    return res;
  }
  return FR_OK;
}

static FRESULT remount_ready(void) {
  FMCore_Unmount();
  return ensure_ready();
}

static bool retryable_fs_error(FRESULT res) {
  return res == FR_NOT_READY || res == FR_NOT_ENABLED ||
         res == FR_INVALID_OBJECT || res == FR_INVALID_DRIVE ||
         res == FR_DISK_ERR || res == FR_TIMEOUT;
}

static uint8_t disp_sleep_delay_idx(void) {
  return (uint8_t)((g_settings.disp_sleep_cfg >> 1U) & 0x07U);
}

static void sanitize(void) {
  if (g_settings.disp_bright > 10U) {
    g_settings.disp_bright = 0U;
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
  g_settings.magic = SM_MAGIC;
  g_settings.crc = settings_crc(&g_settings);
}

static void defaults(void) {
  memset(&g_settings, 0, sizeof(g_settings));
  g_settings.magic = SM_MAGIC;
  g_settings.disp_bright = 0U;
  g_settings.disp_sleep_cfg = 0x04U;
  g_settings.debug_dashboard = 0U;
  g_settings.debug_log_com = 1U;
  g_settings.time_style_24h = true;
  g_settings.boot_gfx = true;
  g_settings.sound_mute = false;
  sanitize();
  LOG_D("SMGR", "Defaults loaded");
}

static bool settings_to_json(char *out, uint32_t out_sz) {
  JsonWriter_t w;
  json_writer_begin(&w, out, (int)out_sz);
  json_writer_add_int(&w, "schema", 1);
  json_writer_add_int(&w, "disp_bright", (int)g_settings.disp_bright);
  json_writer_add_int(&w, "disp_sleep_cfg", (int)g_settings.disp_sleep_cfg);
  json_writer_add_int(&w, "debug_dashboard", (int)g_settings.debug_dashboard);
  json_writer_add_int(&w, "debug_log_com", (int)g_settings.debug_log_com);
  json_writer_add_bool(&w, "time_style_24h", g_settings.time_style_24h);
  json_writer_add_bool(&w, "boot_gfx", g_settings.boot_gfx);
  json_writer_add_bool(&w, "sound_mute", g_settings.sound_mute);
  json_writer_end(&w);
  return json_writer_ok(&w);
}

static void settings_from_json(const char *json) {
  g_settings.disp_bright =
      (uint8_t)json_get_int(json, "disp_bright", g_settings.disp_bright);
  g_settings.disp_sleep_cfg =
      (uint8_t)json_get_int(json, "disp_sleep_cfg", g_settings.disp_sleep_cfg);
  g_settings.debug_dashboard = (uint8_t)json_get_int(
      json, "debug_dashboard", g_settings.debug_dashboard);
  g_settings.debug_log_com =
      (uint8_t)json_get_int(json, "debug_log_com", g_settings.debug_log_com);
  g_settings.time_style_24h =
      json_get_bool(json, "time_style_24h", g_settings.time_style_24h);
  g_settings.boot_gfx = json_get_bool(json, "boot_gfx", g_settings.boot_gfx);
  g_settings.sound_mute =
      json_get_bool(json, "sound_mute", g_settings.sound_mute);
  sanitize();
}

static bool read_json_file(char *buf, uint32_t cap, uint32_t *out_len) {
  FIL file;
  FILINFO info;
  UINT br = 0U;
  FRESULT res;

  if (!buf || cap < 2U)
    return false;
  if (out_len)
    *out_len = 0U;
  buf[0] = '\0';

  res = f_stat(SM_JSON_PATH, &info);
  if (res != FR_OK) {
    sm_trace("json stat failed: %d", (int)res);
    return false;
  }
  if (info.fsize == 0U || info.fsize >= cap) {
    sm_trace("json size invalid: %lu", (unsigned long)info.fsize);
    return false;
  }

  res = f_open(&file, SM_JSON_PATH, FA_READ);
  if (res != FR_OK) {
    sm_trace("json open failed: %d", (int)res);
    return false;
  }
  res = f_read(&file, buf, info.fsize, &br);
  (void)f_close(&file);
  if (res != FR_OK || br != info.fsize) {
    sm_trace("json read failed: res=%d %lu/%lu", (int)res, (unsigned long)br,
             (unsigned long)info.fsize);
    return false;
  }
  buf[br] = '\0';
  if (out_len)
    *out_len = br;
  return true;
}

static bool read_file_exact(const char *path, char *buf, uint32_t cap,
                            uint32_t *out_len) {
  FIL file;
  FILINFO info;
  UINT br = 0U;
  FRESULT res;

  if (!path || !buf || cap < 2U)
    return false;
  if (out_len)
    *out_len = 0U;
  buf[0] = '\0';

  res = f_stat(path, &info);
  if (res != FR_OK || info.fsize == 0U || info.fsize >= cap) {
    sm_trace("probe stat failed: path=%s res=%d size=%lu", path ? path : "?",
             (int)res, (unsigned long)info.fsize);
    return false;
  }
  res = f_open(&file, path, FA_READ);
  if (res != FR_OK) {
    sm_trace("probe open-read failed: path=%s res=%d", path, (int)res);
    return false;
  }
  res = f_read(&file, buf, info.fsize, &br);
  (void)f_close(&file);
  if (res != FR_OK || br != info.fsize) {
    sm_trace("probe read failed: path=%s res=%d %lu/%lu", path, (int)res,
             (unsigned long)br, (unsigned long)info.fsize);
    return false;
  }
  buf[br] = '\0';
  if (out_len)
    *out_len = br;
  return true;
}

static void sm_json_selftest(void) {
  static bool ran = false;
  const char *body = "{\n"
                     "  \"schema\": 1,\n"
                     "  \"probe\": 407,\n"
                     "  \"ok\": true\n"
                     "}\n";
  char buf[128];
  FIL file;
  UINT bw = 0U;
  FRESULT res;

  if (ran)
    return;
  ran = true;

  sm_trace("probe start");
  (void)f_unlink(SM_SELFTEST_TMP);
  (void)f_unlink(SM_SELFTEST_PATH);

  res = f_open(&file, SM_SELFTEST_TMP, FA_CREATE_ALWAYS | FA_WRITE);
  if (res != FR_OK) {
    sm_trace("probe tmp open failed: %d", (int)res);
    return;
  }
  res = f_write(&file, body, (UINT)strlen(body), &bw);
  if (res == FR_OK && bw == strlen(body)) {
    res = f_sync(&file);
  }
  {
    FRESULT close_res = f_close(&file);
    if (res == FR_OK)
      res = close_res;
  }
  if (res != FR_OK || bw != strlen(body)) {
    sm_trace("probe tmp write failed: res=%d %lu/%lu", (int)res,
             (unsigned long)bw, (unsigned long)strlen(body));
    return;
  }
  if (!read_file_exact(SM_SELFTEST_TMP, buf, sizeof(buf), NULL) ||
      json_get_int(buf, "probe", 0) != 407 ||
      !json_get_bool(buf, "ok", false)) {
    sm_trace("probe tmp verify failed");
    return;
  }
  sm_trace("probe tmp verified");

  res = f_rename(SM_SELFTEST_TMP, SM_SELFTEST_PATH);
  if (res != FR_OK) {
    sm_trace("probe rename failed: %d", (int)res);
    return;
  }
  if (!read_file_exact(SM_SELFTEST_PATH, buf, sizeof(buf), NULL) ||
      json_get_int(buf, "probe", 0) != 407 ||
      !json_get_bool(buf, "ok", false)) {
    sm_trace("probe final verify failed");
    return;
  }
  sm_trace("probe final verified");

  res = f_unlink(SM_SELFTEST_PATH);
  sm_trace("probe delete %s: %d", res == FR_OK ? "ok" : "failed", (int)res);
}

static bool load(void) {
  char json[SM_JSON_MAX];
  uint32_t len = 0U;

  if (!read_json_file(json, sizeof(json), &len)) {
    return false;
  }

  if (json_get_int(json, "schema", 0) != 1) {
    sm_trace("json schema mismatch");
    return false;
  }

  settings_from_json(json);
  g_last_saved_crc = g_settings.crc;
  g_have_saved_crc = true;
  LOG_I("SMGR", "Loaded JSON from SD OK (%luB)", (unsigned long)len);
  sm_trace("json loaded: bright=%u sleep=0x%02X dash=%u log=%u 24h=%u boot=%u "
           "mute=%u",
           g_settings.disp_bright, g_settings.disp_sleep_cfg,
           g_settings.debug_dashboard, g_settings.debug_log_com,
           g_settings.time_style_24h ? 1U : 0U, g_settings.boot_gfx ? 1U : 0U,
           g_settings.sound_mute ? 1U : 0U);
  return true;
}

bool SM_SdAvailable(void) { return g_sd_available; }

void SM_Init(void) {
  defaults();
  g_have_saved_crc = false;
  g_last_saved_crc = 0U;
}

void SM_Mount(void) {
  FRESULT res;

  g_sd_available = false;
  res = ensure_ready();
  if (res != FR_OK) {
    LOG_W("SMGR", "Settings storage unavailable (%d)", (int)res);
    return;
  }
  g_sd_available = true;
  sm_json_selftest();

  if (!load()) {
    LOG_W("SMGR", "Load JSON failed, using defaults");
    SM_Save();
  }
}

void SM_Save(void) {
  FIL file;
  char json[SM_JSON_MAX];
  char verify[SM_JSON_MAX];
  UINT bw = 0U;
  FRESULT res = FR_OK;
  uint8_t attempt = 0U;
  uint32_t start_ms = HAL_GetTick();

  sanitize();
  if (g_sd_available && g_have_saved_crc &&
      g_settings.crc == g_last_saved_crc) {
    return;
  }

  if (!settings_to_json(json, sizeof(json))) {
    sm_trace("json build failed");
    return;
  }

  g_sd_available = false;
  for (attempt = 0U; attempt < 2U; ++attempt) {
    res = attempt == 0U ? ensure_ready() : remount_ready();
    if (res != FR_OK) {
      sm_trace("save ready failed: attempt=%u res=%d", attempt + 1U, (int)res);
      if (!retryable_fs_error(res))
        return;
      continue;
    }

    (void)f_unlink(SM_JSON_TMP);
    res = f_open(&file, SM_JSON_TMP, FA_CREATE_ALWAYS | FA_WRITE);
    if (res != FR_OK) {
      sm_trace("json tmp open failed: attempt=%u res=%d", attempt + 1U,
               (int)res);
      if (!retryable_fs_error(res))
        break;
      continue;
    }

    bw = 0U;
    res = f_write(&file, json, (UINT)strlen(json), &bw);
    if (res == FR_OK && bw == strlen(json)) {
      res = f_sync(&file);
    }
    {
      FRESULT close_res = f_close(&file);
      if (res == FR_OK)
        res = close_res;
    }
    if (res != FR_OK || bw != strlen(json)) {
      sm_trace("json write failed: res=%d %lu/%lu", (int)res, (unsigned long)bw,
               (unsigned long)strlen(json));
      if (!retryable_fs_error(res))
        break;
      continue;
    }

    (void)f_unlink(SM_JSON_PATH);
    res = f_rename(SM_JSON_TMP, SM_JSON_PATH);
    if (res != FR_OK) {
      sm_trace("json rename failed: %d", (int)res);
      if (!retryable_fs_error(res))
        break;
      continue;
    }

    if (read_json_file(verify, sizeof(verify), NULL) &&
        json_get_int(verify, "schema", 0) == 1 &&
        json_get_int(verify, "disp_bright", -1) == g_settings.disp_bright &&
        json_get_int(verify, "disp_sleep_cfg", -1) ==
            g_settings.disp_sleep_cfg) {
      g_sd_available = true;
      g_last_saved_crc = g_settings.crc;
      g_have_saved_crc = true;
      sm_trace("json saved+verified ok: %luB", (unsigned long)strlen(json));
      break;
    }

    sm_trace("json verify failed");
  }

  {
    uint32_t elapsed = HAL_GetTick() - start_ms;
    if (elapsed > 150U) {
      LOG_W("SMGR", "JSON save took %lums", (unsigned long)elapsed);
    }
  }
}

Settings_t *SM_Get(void) { return &g_settings; }

uint8_t SM_Disp_Bright(void) { return g_settings.disp_bright; }
void SM_Disp_SetBright(uint8_t v) {
  if (v > 10U)
    v = 10U;
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
  if (v > 5U)
    v = 2U;
  uint8_t next = (uint8_t)((v << 1U) | (g_settings.disp_sleep_cfg & 0x01U));
  if (g_settings.disp_sleep_cfg != next) {
    g_settings.disp_sleep_cfg = next;
    SM_Save();
  }
}

void SM_Disp_SetConfig(uint8_t bright, bool auto_close, uint8_t delay_idx) {
  if (bright > 10U)
    bright = 10U;
  if (delay_idx > 5U)
    delay_idx = 2U;
  uint8_t next_sleep_cfg =
      (uint8_t)((delay_idx << 1U) | (auto_close ? 1U : 0U));
  if (g_settings.disp_bright != bright ||
      g_settings.disp_sleep_cfg != next_sleep_cfg) {
    g_settings.disp_bright = bright;
    g_settings.disp_sleep_cfg = next_sleep_cfg;
    SM_Save();
  }
}
