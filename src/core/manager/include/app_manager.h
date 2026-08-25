#ifndef APP_MANAGER_H
#define APP_MANAGER_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define APP_MANAGER_MAX 18U

typedef struct {
  char name[24];
  char version[12];
  char package_name[32];
  uint8_t hidden;
  uint8_t special;
  uint8_t can_hide;
  uint8_t can_uninstall;
} AppManager_App;

bool AppManager_Init(void);
uint16_t AppManager_Count(void);
const AppManager_App *AppManager_Get(uint16_t index);
bool AppManager_SetHidden(uint16_t index, bool hidden);
bool AppManager_Uninstall(uint16_t index);

#ifdef __cplusplus
}
#endif

#endif
