#include "include/tos_api.h"

#include "core/manager/include/settings_manager.h"
#include "core/sys/include/syswatchdog.h"
#include "hardware/include/cdc_bridge.h"
#include "hardware/include/key.hpp"
#include "hardware/include/lcd.hpp"
#include "hardware/include/secondary_clock.hpp"

namespace {
bool api_initialized;
bool paused;
bool screen_sleeping;
bool wake_key_suppressed;
bool power_key_raw_last;
bool power_key_stable_down;
uint32_t power_key_raw_changed_ms;
uint32_t power_key_last_action_ms;
uint32_t wake_guard_until_ms;
uint32_t last_user_activity_ms;

constexpr uint32_t kPowerKeyDebounceMs = 35U;
constexpr uint32_t kPowerKeyCooldownMs = 250U;

static uint32_t disp_sleep_timeout_ms(void) {
  switch (SM_Disp_CloseDelay()) {
  case 0: return 15000U;
  case 1: return 30000U;
  case 2: return 60000U;
  case 3: return 120000U;
  case 4: return 300000U;
  case 5: return 600000U;
  default: return 60000U;
  }
}

static bool any_user_key_pressed(void) {
  return keyManager._collisionA8.isPressed() ||
         keyManager._collisionD0.isPressed() ||
         keyManager._btnEnter.isPressed() ||
         keyManager.up.isPressed() ||
         keyManager.down.isPressed() ||
         keyManager.confirm.isPressed() ||
         keyManager.spare.isPressed();
}

static bool power_key_pressed_edge(uint32_t now, bool raw_down) {
  if (raw_down != power_key_raw_last) {
    power_key_raw_last = raw_down;
    power_key_raw_changed_ms = now;
  }

  if ((uint32_t)(now - power_key_raw_changed_ms) < kPowerKeyDebounceMs) {
    return false;
  }

  if (raw_down == power_key_stable_down) {
    return false;
  }

  power_key_stable_down = raw_down;
  if (!power_key_stable_down) {
    return false;
  }

  if ((uint32_t)(now - power_key_last_action_ms) < kPowerKeyCooldownMs) {
    return false;
  }

  power_key_last_action_ms = now;
  return true;
}
}

void TosApi_Init(void) {
  api_initialized = true;
  paused = false;
  screen_sleeping = false;
  wake_key_suppressed = false;
  power_key_raw_last = false;
  power_key_stable_down = false;
  power_key_raw_changed_ms = HAL_GetTick();
  power_key_last_action_ms = 0U;
  wake_guard_until_ms = 0U;
  last_user_activity_ms = HAL_GetTick();
}

void TosApi_SetPaused(bool value) { paused = value; }

bool TosApi_IsScreenSleeping(void) { return screen_sleeping; }
bool TosApi_IsWakeKeySuppressed(void) { return wake_key_suppressed; }
bool TosApi_IsWakeGuardActive(void) {
  return (int32_t)(HAL_GetTick() - wake_guard_until_ms) < 0;
}

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
  if (!api_initialized) {
    SysWatchdog_Tick();
    return;
  }
  keyManager.tick();
  CDC_Bridge_Tick();
  SecondaryClock_Tick();
  uint32_t now = HAL_GetTick();
  bool key1_raw_down = keyManager.spare.isPressed();
  bool key1_pressed_edge = power_key_pressed_edge(now, key1_raw_down);
  if (screen_sleeping) {
    if (wake_key_suppressed) {
      if (!power_key_stable_down) {
        wake_key_suppressed = false;
      }
    } else if (key1_pressed_edge) {
      boardLCD.wake();
      screen_sleeping = false;
      wake_key_suppressed = true;
      wake_guard_until_ms = now + 150U;
      last_user_activity_ms = now;
    }
  } else {
    if (key1_pressed_edge) {
      boardLCD.sleep();
      screen_sleeping = true;
      wake_key_suppressed = true;
      wake_guard_until_ms = now + 150U;
      last_user_activity_ms = now;
    } else if (any_user_key_pressed()) {
      last_user_activity_ms = now;
    } else if (SM_Disp_AutoClose() &&
        (uint32_t)(now - last_user_activity_ms) >= disp_sleep_timeout_ms()) {
      boardLCD.sleep();
      screen_sleeping = true;
      wake_key_suppressed = power_key_stable_down;
    }
  }
  SysWatchdog_Tick();
  (void)paused;
}
