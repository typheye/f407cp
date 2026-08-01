/**
 ******************************************************************************
 * @file    file_manager.c
 * @author  Typheye
 * @brief   SD card file manager: mounts the volume, ensures the log directory
 *          and appends boot log / system dump records.
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

#include "file_manager.h"

#include <stdio.h>
#include <string.h>

#include "fatfs.h" /* SDPath / SDFatFS from FATFS/App/fatfs.c */

#define FM_LOG_DIR "0:/system/log"
#define FM_LOG_FILE "0:/system/log/boot.log"
#define FM_DUMP_PREFIX "=== SYSTEM DUMP ==="

static FATFS *g_fm_fs = NULL;
static uint8_t g_fm_mounted = 0;
static uint8_t g_fm_log_dir_ok = 0;

static FRESULT fm_ensure_ready(void) {
  FRESULT res;

  if (g_fm_fs == NULL) {
    g_fm_fs = &SDFatFS;
  }

  if (!g_fm_mounted) {
    res = f_mount(g_fm_fs, SDPath, 1);
    if (res != FR_OK) {
      /* SD not ready / card absent: caller keeps retrying silently. */
      return res;
    }
    g_fm_mounted = 1;
  }

  if (!g_fm_log_dir_ok) {
    res = f_mkdir(FM_LOG_DIR);
    if (res != FR_OK && res != FR_EXIST) {
      /* f_mount can succeed while the media is still spinning up; treat the
       * transient states as not-ready so the caller retries. */
      if (res == FR_NOT_READY || res == FR_NO_FILESYSTEM ||
          res == FR_INVALID_DRIVE || res == FR_NO_PATH) {
        return res;
      }
      return res;
    }
    g_fm_log_dir_ok = 1;
  }

  return FR_OK;
}

static FRESULT fm_append(const char *text, uint32_t len) {
  FRESULT res;
  FIL file;
  unsigned bw = 0;

  res = f_open(&file, FM_LOG_FILE, FA_OPEN_ALWAYS | FA_WRITE);
  if (res != FR_OK) {
    return res;
  }

  res = f_lseek(&file, f_size(&file)); /* append at end of file */
  if (res == FR_OK) {
    res = f_write(&file, text, len, &bw);
  }

  f_close(&file);
  return res;
}

FRESULT FMCore_AppendBootLog(const char *line, uint32_t len) {
  FRESULT res;

  if (line == NULL || len == 0U) {
    return FR_OK;
  }

  res = fm_ensure_ready();
  if (res != FR_OK) {
    return res;
  }

  return fm_append(line, len);
}

FRESULT FMCore_WriteSystemDump(uint32_t code, const char *name,
                               const char *extra) {
  char record[320];
  int n;

  if (name == NULL) {
    name = "?";
  }
  if (extra == NULL) {
    extra = "";
  }

  n = snprintf(record, sizeof(record), "\r\n%s code=%lu name=%s\r\n%s",
               FM_DUMP_PREFIX, (unsigned long)code, name, extra);
  if (n < 0) {
    return FR_INT_ERR;
  }
  if ((size_t)n >= sizeof(record)) {
    n = (int)sizeof(record) - 1;
  }

  return FMCore_AppendBootLog(record, (uint32_t)n);
}
