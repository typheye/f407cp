#include "include/tos_api.h"

#include "core/sys/include/syswatchdog.h"
#include "hardware/include/cdc_bridge.h"
#include "hardware/include/key.hpp"
#include "hardware/include/secondary_clock.hpp"

namespace {
bool paused;
}

void TosApi_Init(void) { paused = false; }

void TosApi_SetPaused(bool value) { paused = value; }

bool TosApi_CheckUpgrade(TosUpgradeInfo *info) {
  if (info != nullptr) {
    info->has_update = false;
    info->latest_version[0] = '\0';
    info->latest_build[0] = '\0';
    info->latest_patch[0] = '\0';
    info->latest_size = 0;
  }
  return false;
}

void TosApi_Tick(void) {
  keyManager.tick();
  CDC_Bridge_Tick();
  SecondaryClock_Tick();
  SysWatchdog_Tick();
  (void)paused;
}
