#include "include/app_manager.h"
#include "core/manager/include/file_manager.h"
#include "core/sys/include/syslog.h"
#include "library/include/libjson.h"
#include "ff.h"
#include <stdio.h>
#include <string.h>

#define APP_JSON_PATH "0:/data/app.json"
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
  uint32_t len = 0U;
  FRESULT res = FMCore_ReadFile(APP_JSON_PATH, buf, cap - 1U, &len, false);
  if (res != FR_OK || len >= cap) return false;
  buf[len] = '\0';
  return true;
}

static bool write_file(void) {
  char json[APP_JSON_CAP];
  size_t used = 0U;
  int n = snprintf(json, sizeof(json), "{\n  \"schema\": 1,\n  \"count\": %u",
                   (unsigned)g_count);
  if (n < 0 || (size_t)n >= sizeof(json)) return false;
  used = (size_t)n;
  for (uint16_t i = 0U; i < g_count; ++i) {
    n = snprintf(json + used, sizeof(json) - used,
                 ",\n  \"app%u_name\": \"%s\",\n"
                 "  \"app%u_version\": \"%s\",\n"
                 "  \"app%u_package_name\": \"%s\",\n"
                 "  \"app%u_hidden\": %s",
                 (unsigned)i, g_apps[i].name, (unsigned)i, g_apps[i].version,
                 (unsigned)i, g_apps[i].package_name, (unsigned)i,
                 g_apps[i].hidden ? "true" : "false");
    if (n < 0 || (size_t)n >= sizeof(json) - used) return false;
    used += (size_t)n;
  }
  n = snprintf(json + used, sizeof(json) - used, "\n}\n");
  if (n < 0 || (size_t)n >= sizeof(json) - used) return false;
  used += (size_t)n;
  return FMCore_WriteFile(APP_JSON_PATH, json, (uint32_t)used, false) == FR_OK;
}

bool AppManager_Init(void) {
  if (g_ready) return true;
  app_defaults();
  if (FMCore_IsStorageMounted() && FMCore_IsInitialized()) {
    char json[APP_JSON_CAP];
    if (read_file(json, sizeof(json))) {
      for (uint16_t i = 0U; i < g_count; ++i) {
        char key[24];
        snprintf(key, sizeof(key), "app%u_hidden", (unsigned)i);
        g_apps[i].hidden = json_get_bool(json, key, false) ? 1U : 0U;
      }
      /* Migrate the first version of app.json. */
      if (!json_find(json, "app0_hidden"))
        g_apps[0].hidden = json_get_bool(json, "explorer_hidden", false) ? 1U : 0U;
      if (!json_find(json, "app1_hidden"))
        g_apps[1].hidden = json_get_bool(json, "settings_hidden", false) ? 1U : 0U;
      if (!json_find(json, "app2_hidden"))
        g_apps[2].hidden = json_get_bool(json, "demo_hidden", false) ? 1U : 0U;
      g_apps[1].hidden = 0U;
    } else {
      (void)write_file();
    }
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
