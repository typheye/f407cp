#include "include/syswatchdog.h"

#include "stm32f4xx_hal.h"

enum { TOS_RESET_NORMAL = 0U, TOS_RESET_IWDG = 1U, TOS_RESET_WWDG = 2U };

static uint32_t bootCode;
static uint32_t lastFeed;

void SysWatchdog_Init(void) {
  if (__HAL_RCC_GET_FLAG(RCC_FLAG_IWDGRST) != RESET)
    bootCode = TOS_RESET_IWDG;
  else if (__HAL_RCC_GET_FLAG(RCC_FLAG_WWDGRST) != RESET)
    bootCode = TOS_RESET_WWDG;
  else
    bootCode = TOS_RESET_NORMAL;
  __HAL_RCC_CLEAR_RESET_FLAGS();
  lastFeed = HAL_GetTick();
  SysWatchdog_FeedNow();
}

void SysWatchdog_FeedNow(void) {
  /* Refresh an already-running hardware watchdog without forcing one on in a
   * build where CubeMX has not enabled IWDG yet. */
  IWDG->KR = 0xAAAAU;
  lastFeed = HAL_GetTick();
}

void SysWatchdog_Tick(void) {
  if ((uint32_t)(HAL_GetTick() - lastFeed) >= 200U)
    SysWatchdog_FeedNow();
}

uint32_t SysWatchdog_GetBootCode(void) { return bootCode; }

const char *SysWatchdog_GetBootText(void) {
  if (bootCode == TOS_RESET_IWDG)
    return "Previous reset: IWDG";
  if (bootCode == TOS_RESET_WWDG)
    return "Previous reset: WWDG";
  return "Reset status: normal";
}
