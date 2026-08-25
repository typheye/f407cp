/** Core startup orchestration. */

#include "include/init.hpp"
#include "core/manager/include/emotion_manager.h"
#include "core/manager/include/app_manager.h"
#include "core/manager/include/file_manager.h"
#include "core/manager/include/settings_manager.h"
#include "core/sdk/include/tos_api.h"
#include "core/sys/include/syswatchdog.h"
#include "gui/include/sysui.hpp"
#include "hardware/include/cdc_bridge.h"
#include "hardware/include/key.hpp"
#include "hardware/include/lcd.hpp"
#include "hardware/include/oled12864.hpp"
#include "hardware/include/sfhd.h"
#include "hardware/include/tsdio.hpp"
#include "library/include/libdly.h"
#include "library/include/libpd.h"

extern LED boardLed;
extern Buzzer buzzer1;

static void request_storage_init(void) {
  if (!Flash_BL_RecoveryAvailable()) {
    LOG_E("SDIO", "0:/init invalid and REC unavailable");
    return;
  }
  FMCore_Unmount();
  SysWatchdog_FeedNow();
  if (Flash_BL_SetBootTarget(FLASH_BL_BOOT_RECOVERY_INIT) != FLASH_OK) {
    LOG_E("SDIO", "failed to request REC storage initialization");
    return;
  }
  LOG_W("SDIO", "0:/init invalid; rebooting to REC initialization");
  __DSB();
  __ISB();
  NVIC_SystemReset();
  while (1) __NOP();
}

void APP::init() {
  boardLed.init();
  redLed.init();
  greenLed.init();
  blueLed.init();
  whiteLed.init();
  redLed.off();
  greenLed.off();
  blueLed.off();
  whiteLed.off();

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
  (void)FMCore_MountInternal();

  SDCard_Status_t sd_status = boardSDIO.init();
  if (sd_status == SD_CARD_OK) {
    FRESULT mount_res = FMCore_MountStorage(NULL, true);
    if (mount_res == FR_OK) {
      if (!FMCore_IsInitialized()) {
        request_storage_init();
      }
      FRESULT prepare_res = FMCore_PrepareSystemStorage();
      if (prepare_res != FR_OK) {
        LOG_W("SDIO", "directory setup failed: %s(%d)",
              FMCore_FResultName(prepare_res), (int)prepare_res);
      }
    } else {
      LOG_W("SDIO", "mount failed: %s(%d)",
            FMCore_FResultName(mount_res), (int)mount_res);
    }
  } else {
    LOG_W("SDIO", "card initialization failed (%d)", (int)sd_status);
  }

  SM_Mount();
  (void)AppManager_Init();

  if (SM_BootGfx() && !SM_SoundMute()) buzzer1.beepSuccess();
  EmotionManager_Init();
  TosApi_Init();
  SysUI::init();
  CDC_Bridge_Start();
  _initialized = true;

  LOG_I("MAIN", "System initialized, CPU:168MHz, SD=%s",
        SM_SdAvailable() ? "ready" : "offline");
  SysWatchdog_FeedNow();
  JPDelay(250);
  PD_SplashFinish(220U);
  boardLCD.setBrightness((uint16_t)SM_Disp_Bright() * 100U);
  Oled12864_Init();
  SysUI_DebugOverlaySetEnabled(SM_Debug_Dashboard() ? 1U : 0U);
  SysUI::setActivity(UI_PET);
}
