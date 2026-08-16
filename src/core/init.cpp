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
#include "core/manager/include/file_manager.h"
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

static bool sd_root_name_eq(const char *a, const char *b) {
  if (!a || !b) return false;
  while (*a && *b) {
    char ca = *a++;
    char cb = *b++;
    if (ca >= 'A' && ca <= 'Z') ca = (char)(ca - 'A' + 'a');
    if (cb >= 'A' && cb <= 'Z') cb = (char)(cb - 'A' + 'a');
    if (ca != cb) return false;
  }
  return *a == '\0' && *b == '\0';
}

static bool sd_root_entry_allowed(const FMCore_Entry *entry) {
  if (!entry || !entry->name[0]) return true;
  if (strcmp(entry->name, ".") == 0 || strcmp(entry->name, "..") == 0) {
    return true;
  }
#ifdef AM_VOL
  if ((entry->attr & AM_VOL) != 0U) return true;
#endif

  if (sd_root_name_eq(entry->name, "init")) {
    return entry->is_dir == 0U;
  }

  static const char *kAllowedDirs[] = {"data", "storage"};
  for (unsigned i = 0; i < sizeof(kAllowedDirs) / sizeof(kAllowedDirs[0]); ++i) {
    if (sd_root_name_eq(entry->name, kAllowedDirs[i])) {
      return entry->is_dir != 0U;
    }
  }
  return false;
}

static FRESULT sd_root_find_extra(char *path, size_t path_size,
                                  bool *out_found) {
  DIR dir;
  FILINFO fno;
  FMCore_Entry entry;
  FRESULT res;

  if (out_found) *out_found = false;
  if (!path || path_size == 0U || !out_found) return FR_INVALID_PARAMETER;
  path[0] = '\0';

  res = f_opendir(&dir, "0:");
  if (res != FR_OK) return res;

  while (1) {
    SysWatchdog_Tick();
    res = f_readdir(&dir, &fno);
    if (res != FR_OK) {
      (void)f_closedir(&dir);
      return res;
    }
    if (fno.fname[0] == '\0') break;

    strncpy(entry.name, fno.fname, FMCORE_NAME_MAX - 1U);
    entry.name[FMCORE_NAME_MAX - 1U] = '\0';
    entry.is_dir = (fno.fattrib & AM_DIR) ? 1U : 0U;
    entry.size = fno.fsize;
    entry.attr = fno.fattrib;
    if (sd_root_entry_allowed(&entry)) continue;

    if (!FMCore_JoinPath("0:", entry.name, path, path_size)) {
      (void)f_closedir(&dir);
      return FR_INVALID_NAME;
    }
    *out_found = true;
    break;
  }

  FRESULT close_res = f_closedir(&dir);
  return close_res == FR_OK ? res : close_res;
}

static FRESULT sd_delete_recursive_quiet(const char *path) {
  FILINFO info;
  FRESULT res;

  if (!path || !path[0]) return FR_INVALID_PARAMETER;
  SysWatchdog_Tick();

  res = f_stat(path, &info);
  if (res != FR_OK) return res;

#if _USE_CHMOD
  (void)f_chmod(path, 0, AM_RDO);
#endif
  if ((info.fattrib & AM_DIR) == 0U) {
    return f_unlink(path);
  }

  while (1) {
    DIR dir;
    FILINFO fno;
    char child[FMCORE_PATH_MAX];
    bool found = false;

    res = f_opendir(&dir, path);
    if (res != FR_OK) return res;
    while (1) {
      res = f_readdir(&dir, &fno);
      if (res != FR_OK || fno.fname[0] == '\0') break;
      if (strcmp(fno.fname, ".") == 0 || strcmp(fno.fname, "..") == 0) {
        continue;
      }
      if (!FMCore_JoinPath(path, fno.fname, child, sizeof(child))) {
        res = FR_INVALID_NAME;
        break;
      }
      found = true;
      break;
    }
    (void)f_closedir(&dir);

    if (res != FR_OK) return res;
    if (!found) break;

    res = sd_delete_recursive_quiet(child);
    if (res != FR_OK && res != FR_NO_FILE && res != FR_NO_PATH) return res;
    SysWatchdog_Tick();
  }

#if _USE_CHMOD
  (void)f_chmod(path, 0, AM_RDO);
#endif
  return f_unlink(path);
}

static void sd_cleanup_disable_for_boot(const char *reason, FRESULT res) {
  SysLog_DisableFileOutput();
  LOG_W("MAIN", "SD root cleanup disabled SD for this boot: %s => %s(%d)",
        reason ? reason : "?", FMCore_FResultName(res), (int)res);
  FMCore_Unmount();
  TSDIO_MarkHardDisabled();
}

static void request_rec_init_if_needed(void) {
  FILINFO info;
  FIL marker;
  uint8_t marker_buf[512];
  UINT br = 0U;
  FRESULT res;
  bool needs_init = false;

  if (TSDIO_IsHardDisabled() || !TSDIO_IsInitialized()) {
    LOG_W("MAIN", "SD unavailable; skip REC INIT and continue boot");
    return;
  } else if ((res = FMCore_MountStorage(NULL, false)) == FR_NO_FILESYSTEM) {
    needs_init = true;
  } else if (res != FR_OK) {
    sd_cleanup_disable_for_boot("mount init check", res);
    return;
  } else {
    res = f_stat("0:/init", &info);
    if (res == FR_OK) {
      needs_init = (info.fattrib & AM_DIR) != 0U ||
                   info.fsize != TOS_SD_INIT_FILE_SIZE;
      if (!needs_init) {
        res = f_open(&marker, "0:/init", FA_READ);
        if (res != FR_OK) {
          needs_init = true;
        } else {
          uint32_t checked = 0U;
          while (checked < TOS_SD_INIT_FILE_SIZE && !needs_init) {
            res = f_read(&marker, marker_buf, sizeof(marker_buf), &br);
            if (res != FR_OK || br != sizeof(marker_buf)) {
              needs_init = true;
              break;
            }
            for (uint32_t i = 0U; i < br; ++i) {
              if (marker_buf[i] != 0xFFU) {
                needs_init = true;
                break;
              }
            }
            checked += br;
            SysWatchdog_Tick();
          }
          (void)f_close(&marker);
        }
      }
    } else if (res == FR_NO_FILE || res == FR_NO_PATH) {
      needs_init = true;
    } else {
      sd_cleanup_disable_for_boot("stat /init", res);
      return;
    }
  }

  if (!needs_init) return;

  LOG_W("MAIN", "SD storage is not initialized; entering REC INIT");
  FMCore_Unmount();
  if (!Flash_BL_RecoveryAvailable()) {
    sd_cleanup_disable_for_boot("REC unavailable for init", FR_NOT_READY);
    return;
  }
  SysWatchdog_FeedNow();
  if (Flash_BL_SetBootTarget(FLASH_BL_BOOT_RECOVERY_INIT) != FLASH_OK) {
    sd_cleanup_disable_for_boot("set REC INIT target", FR_INT_ERR);
    return;
  }
  __DSB();
  __ISB();
  NVIC_SystemReset();
  while (1) {
    __NOP();
  }
}

static void cleanup_sd_root_whitelist(void) {
  if (TSDIO_IsHardDisabled() || !TSDIO_IsInitialized() ||
      !FMCore_IsInitialized()) {
    return;
  }

  FRESULT mount_res = FMCore_Mount(NULL, false);
  if (mount_res != FR_OK) {
    sd_cleanup_disable_for_boot("mount root", mount_res);
    return;
  }

  while (true) {
    char path[FMCORE_PATH_MAX];
    bool found = false;
    FRESULT list_res = sd_root_find_extra(path, sizeof(path), &found);
    if (list_res != FR_OK) {
      sd_cleanup_disable_for_boot("list root", list_res);
      return;
    }
    if (!found) return;

    SysWatchdog_FeedNow();
    FRESULT del_res = sd_delete_recursive_quiet(path);
    SysWatchdog_FeedNow();
    if (del_res != FR_OK && del_res != FR_NO_FILE && del_res != FR_NO_PATH) {
      sd_cleanup_disable_for_boot(path, del_res);
      return;
    }

    LOG_I("MAIN", "Removed SD root extra: %s", path);
  }
}

static void cleanup_legacy_storage_dirs(void) {
  FILINFO info;

  if (TSDIO_IsHardDisabled() || !TSDIO_IsInitialized() ||
      !FMCore_IsInitialized()) {
    return;
  }

  if (f_stat("0:/storage/tos/_", &info) == FR_OK) {
    SysWatchdog_FeedNow();
    FRESULT res = sd_delete_recursive_quiet("0:/storage/tos/_");
    SysWatchdog_FeedNow();
    if (res == FR_OK || res == FR_NO_FILE || res == FR_NO_PATH) {
      LOG_I("MAIN", "Removed legacy SD path: 0:/storage/tos/_");
    } else {
      LOG_W("MAIN", "Cannot remove legacy SD path: %s(%d)",
            FMCore_FResultName(res), (int)res);
    }
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
  FRESULT internal_mount = FMCore_MountInternal();
  if (internal_mount != FR_OK) {
    LOG_W("MAIN", "Internal /data and /tmp unavailable: %s(%d)",
          FMCore_FResultName(internal_mount), (int)internal_mount);
  }

  if (boardSDIO.init() != SD_CARD_OK) {
    LOG_W("SDIO", "SD card unavailable at boot");
  }
  request_rec_init_if_needed();
  SM_Mount();
  if (!TSDIO_IsHardDisabled()) {
    cleanup_sd_root_whitelist();
    cleanup_legacy_storage_dirs();
  } else {
    LOG_W("MAIN", "SD card is hard-disabled - SD features unavailable");
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
  SysUI_DebugOverlaySetEnabled(SM_Debug_Dashboard() ? 1U : 0U);

  SysUI::setActivity(UI_PET);
}
