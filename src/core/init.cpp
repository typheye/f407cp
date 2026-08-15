/**
 ******************************************************************************
 * @file    init.cpp
 * @author  Typheye
 * @brief   Core startup orchestration implementation.
 ******************************************************************************
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 *
 */

#include "include/init.hpp"
#include "core/sys/include/syswatchdog.h"
#include "gui/include/sysui.hpp"
#include "core/manager/include/emotion_manager.h"
#include "core/sdk/include/tos_api.h"
#include "hardware/include/cdc_bridge.h"
#include "hardware/include/key.hpp"
#include "hardware/include/lcd.hpp"
#include "hardware/include/sfhd.h"
#include "hardware/include/secondary_clock.hpp"
#include "hardware/include/tsdio.hpp"
#include "core/manager/include/settings_manager.h"
#include "library/include/libdly.h"
#include "library/include/libpd.h"
#include "manifest.h"
#include "rtc.h"

extern "C" {}

extern LED boardLed;
extern Buzzer buzzer1;

static void request_recovery_init(void) {
  LOG_W("MAIN", "Requesting RECOVERY_INIT");
  if (Flash_BL_SetBootTarget(FLASH_BL_BOOT_RECOVERY_INIT) == FLASH_OK) {
    SysWatchdog_FeedNow();
    NVIC_SystemReset();
  } else {
    LOG_E("MAIN", "Failed to set RECOVERY_INIT");
  }
}

void APP::init() {

  boardLed.init();
  redLed.init();
  greenLed.init();
  blueLed.init();
  whiteLed.init();
  HAL_GPIO_WritePin(GPIOF, GPIO_PIN_6 | GPIO_PIN_7 | GPIO_PIN_8 | GPIO_PIN_9,
                    GPIO_PIN_RESET);

  buzzer1.init();
  JPDelay(50);

  SysWatchdog_Init();
  SysWatchdog_FeedNow();
  boardLCD.init();
  SysWatchdog_FeedNow();
  JPDelay(50);

  PD_ShowSplashFadeStart(650U);

  keyManager.init();
  SM_Init();
  if (boardSDIO.init() == SD_CARD_OK) {
    if (!SM_Mount()) {
      request_recovery_init();
      return;
    }
  } else {
    LOG_W("SDIO", "SD card unavailable at boot");
  }
  if (SM_BootGfx() && !SM_SoundMute()) {
    buzzer1.beepSuccess();
  }

  EmotionManager_Init();
  TosApi_Init();
  SysUI::init();
  CDC_Bridge_Start();

  _initialized = true;

  LOG_I("MAIN", "System initialized, CPU:168MHz");

  SysWatchdog_FeedNow();
  JPDelay(250);

  PD_SplashFinish(220U);

  /* ELF left the secondary panel off and cleared. Enable it only after the
   * complete SYSTEM UI and primary display stack are ready. */
  SecondaryClock_Init();

  SysUI::setActivity(UI_PET);
}
