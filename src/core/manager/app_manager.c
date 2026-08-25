#include "include/app_manager.h"
#include "core/manager/include/file_manager.h"
#include "core/sys/include/syslog.h"
#include "library/include/libjson.h"
#include "library/include/libcry.h"
#include "library/include/libtmp.h"
#include "dram.h"
#include "ff.h"
#include <stdio.h>
#include <string.h>

#define APP_DAT_PATH "0:/data/system/app.dat"
#define APP_JSON_CAP 4096U

static AppManager_App g_apps[APP_MANAGER_MAX];
static uint16_t g_count;
static bool g_ready;

static void app_defaults(void) {
  memset(g_apps, 0, sizeof(g_apps));
  g_count = 3U;

  strcpy(g_apps[0].name, "File Manager");
  strcpy(g_apps[0].version, "1.0");
  strcpy(g_apps[0].package_name, "tos.file");
  g_apps[0].special = 1U;
  g_apps[0].can_hide = 1U;

  strcpy(g_apps[1].name, "Settings");
  strcpy(g_apps[1].version, "1.0");
  strcpy(g_apps[1].package_name, "tos.settings");
  g_apps[1].special = 1U;

  strcpy(g_apps[2].name, "Demo");
  strcpy(g_apps[2].version, "1.0");
  strcpy(g_apps[2].package_name, "tos.demo");
  g_apps[2].special = 1U;
  g_apps[2].can_hide = 1U;

}

static bool read_file(char *buf, uint32_t cap) {
  uint8_t *sealed = (uint8_t *)SysDram_Alloc(APP_JSON_CAP + LIBCRY_OVERHEAD);
  if (!sealed) return false;
  uint32_t len = 0U;
  FRESULT res = FMCore_ReadFile(APP_DAT_PATH, sealed,
                               APP_JSON_CAP + LIBCRY_OVERHEAD, &len, false);
  if (res != FR_OK || len == 0U) {
    SysDram_Free(sealed);
    return false;
  }
  uint32_t plain_len = 0U;
  bool ok = LibCry_Open(sealed, len, buf, cap - 1U, &plain_len);
  SysDram_Free(sealed);
  if (!ok) return false;
  buf[plain_len] = '\0';
  return true;
}

static bool write_file(void) {
  char *json = (char *)SysDram_Alloc(APP_JSON_CAP);
  uint8_t *sealed =
      (uint8_t *)SysDram_Alloc(APP_JSON_CAP + LIBCRY_OVERHEAD);
  char tmp_path[48] = {0};
  if (!json || !sealed) {
    SysDram_Free(sealed);
    SysDram_Free(json);
    return false;
  }
  size_t used = 0U;
  int n = snprintf(json, APP_JSON_CAP, "{\n  \"schema\": 1,\n  \"count\": %u",
                   (unsigned)g_count);
  if (n < 0 || n >= (int)APP_JSON_CAP) goto fail;
  used = (size_t)n;
  for (uint16_t i = 0U; i < g_count; ++i) {
    n = snprintf(json + used, APP_JSON_CAP - used,
                 ",\n  \"app%u_name\": \"%s\",\n"
                 "  \"app%u_version\": \"%s\",\n"
                 "  \"app%u_package_name\": \"%s\",\n"
                 "  \"app%u_hidden\": %s",
                 (unsigned)i, g_apps[i].name, (unsigned)i, g_apps[i].version,
                 (unsigned)i, g_apps[i].package_name, (unsigned)i,
                 g_apps[i].hidden ? "true" : "false");
    if (n < 0 || (size_t)n >= APP_JSON_CAP - used) goto fail;
    used += (size_t)n;
  }
  n = snprintf(json + used, APP_JSON_CAP - used, "\n}\n");
  if (n < 0 || (size_t)n >= APP_JSON_CAP - used) goto fail;
  used += (size_t)n;
  uint32_t sealed_len = 0U;
  if (!LibCry_Seal(json, (uint32_t)used, sealed,
                   APP_JSON_CAP + LIBCRY_OVERHEAD, &sealed_len))
    goto fail;
  if (!LibTmp_CreatePath(tmp_path, sizeof(tmp_path))) goto fail;
  FRESULT res = FMCore_WriteFile(tmp_path, sealed, sealed_len, false);
  if (res != FR_OK) goto fail;
  (void)FMCore_Delete(APP_DAT_PATH, false, false);
  res = f_rename(tmp_path, APP_DAT_PATH);
  (void)FMCore_Delete(tmp_path, false, false);
  SysDram_Free(sealed);
  SysDram_Free(json);
  return res == FR_OK;
fail:
  if (tmp_path[0] != '\0') (void)FMCore_Delete(tmp_path, false, false);
  SysDram_Free(sealed);
  SysDram_Free(json);
  return false;
}

bool AppManager_Init(void) {
  if (g_ready) return true;
  app_defaults();
  if (FMCore_IsStorageMounted() && FMCore_IsInitialized()) {
    char *json = (char *)SysDram_Alloc(APP_JSON_CAP);
    if (json && read_file(json, APP_JSON_CAP)) {
      for (uint16_t i = 0U; i < g_count; ++i) {
        char key[24];
        snprintf(key, sizeof(key), "app%u_hidden", (unsigned)i);
        g_apps[i].hidden = json_get_bool(json, key, false) ? 1U : 0U;
      }
      g_apps[1].hidden = 0U;
    } else {
      (void)write_file();
    }
    SysDram_Free(json);
  }
  g_ready = true;
  return true;
}

uint16_t AppManager_Count(void) {
  (void)AppManager_Init();
  return g_count;
}

const AppManager_App *AppManager_Get(uint16_t index) {
  (void)AppManager_Init();
  return index < g_count ? &g_apps[index] : NULL;
}

bool AppManager_SetHidden(uint16_t index, bool hidden) {
  (void)AppManager_Init();
  if (index >= g_count || !g_apps[index].can_hide) return false;
  uint8_t previous = g_apps[index].hidden;
  g_apps[index].hidden = hidden ? 1U : 0U;
  if (write_file()) return true;
  g_apps[index].hidden = previous;
  return false;
}

bool AppManager_Uninstall(uint16_t index) {
  (void)AppManager_Init();
  if (index >= g_count || !g_apps[index].can_uninstall) return false;
  uint8_t previous = g_apps[index].hidden;
  g_apps[index].hidden = 1U;
  if (write_file()) return true;
  g_apps[index].hidden = previous;
  return false;
}
