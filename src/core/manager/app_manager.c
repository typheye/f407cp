#include "include/app_manager.h"
#include "core/manager/include/file_manager.h"
#include "core/sys/include/syslog.h"
#include "library/include/libjson.h"
#include "ff.h"
#include <stdio.h>
#include <string.h>

#define APP_JSON_PATH "0:/data/app.json"
#define APP_JSON_CAP 1536U

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
  int used = snprintf(json, sizeof(json),
      "{\n  \"schema\": 1,\n  \"count\": 3,\n"
      "  \"app0_name\": \"File Manager\",\n"
      "  \"app0_version\": \"1.0\",\n"
      "  \"app0_package_name\": \"tos.file\",\n"
      "  \"explorer_hidden\": %s,\n"
      "  \"app1_name\": \"Settings\",\n"
      "  \"app1_version\": \"1.0\",\n"
      "  \"app1_package_name\": \"tos.settings\",\n"
      "  \"settings_hidden\": %s,\n"
      "  \"app2_name\": \"Demo\",\n"
      "  \"app2_version\": \"1.0\",\n"
      "  \"app2_package_name\": \"tos.demo\",\n"
      "  \"demo_hidden\": %s\n}\n",
      g_apps[0].hidden ? "true" : "false",
      g_apps[1].hidden ? "true" : "false",
      g_apps[2].hidden ? "true" : "false");
  if (used <= 0 || (size_t)used >= sizeof(json)) return false;
  return FMCore_WriteFile(APP_JSON_PATH, json, (uint32_t)used, false) == FR_OK;
}

bool AppManager_Init(void) {
  if (g_ready) return true;
  app_defaults();
  if (FMCore_IsStorageMounted() && FMCore_IsInitialized()) {
    char json[APP_JSON_CAP];
    if (read_file(json, sizeof(json))) {
      g_apps[0].hidden = json_get_bool(json, "explorer_hidden", false) ? 1U : 0U;
      g_apps[1].hidden = json_get_bool(json, "settings_hidden", false) ? 1U : 0U;
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
  return false;
}
