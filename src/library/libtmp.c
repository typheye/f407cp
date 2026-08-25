#include "include/libtmp.h"
#include "stm32f4xx_hal.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define LIBTMP_DIR "0:/data/temp"
#define LIBTMP_NAME_LEN 12U

static uint32_t g_state = 0x7A31C5E9U;

static uint32_t next_u32(void) {
  g_state ^= g_state << 13;
  g_state ^= g_state >> 17;
  g_state ^= g_state << 5;
  return g_state;
}

static FRESULT remove_tree(const char *path) {
  FILINFO info;
  FRESULT res = f_stat(path, &info);
  if (res != FR_OK) return res;
  if ((info.fattrib & AM_DIR) == 0U) return f_unlink(path);
  for (;;) {
    DIR dir;
    FILINFO child;
    char child_path[96];
    bool found = false;
    res = f_opendir(&dir, path);
    if (res != FR_OK) return res;
    while ((res = f_readdir(&dir, &child)) == FR_OK && child.fname[0] != '\0') {
      if (strcmp(child.fname, ".") == 0 || strcmp(child.fname, "..") == 0)
        continue;
      if (snprintf(child_path, sizeof(child_path), "%s/%s", path,
                   child.fname) >= (int)sizeof(child_path))
        res = FR_INVALID_NAME;
      else
        found = true;
      break;
    }
    (void)f_closedir(&dir);
    if (res != FR_OK) return res;
    if (!found) break;
    res = remove_tree(child_path);
    if (res != FR_OK) return res;
  }
  return f_unlink(path);
}

FRESULT LibTmp_Cleanup(void) {
  DIR dir;
  FILINFO info;
  FRESULT res = f_opendir(&dir, LIBTMP_DIR);
  if (res == FR_NO_PATH) return FR_OK;
  if (res != FR_OK) return res;
  for (;;) {
    res = f_readdir(&dir, &info);
    if (res != FR_OK || info.fname[0] == '\0') break;
    char path[96];
    if (snprintf(path, sizeof(path), "%s/%s", LIBTMP_DIR, info.fname) >=
        (int)sizeof(path)) {
      res = FR_INVALID_NAME;
      break;
    }
    res = remove_tree(path);
    if (res != FR_OK) break;
  }
  (void)f_closedir(&dir);
  return res == FR_OK ? FR_OK : res;
}

bool LibTmp_CreatePath(char *out, size_t out_sz) {
  static const char alphabet[] = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  FILINFO info;
  if (!out || out_sz < sizeof("0:/data/temp/xxxxxxxxxxxx.tmp")) return false;
  g_state ^= HAL_GetTick() + (uint32_t)(uintptr_t)out;
  for (unsigned attempt = 0U; attempt < 16U; ++attempt) {
    char name[LIBTMP_NAME_LEN + 1U];
    for (unsigned i = 0U; i < LIBTMP_NAME_LEN; ++i)
      name[i] = alphabet[next_u32() % (sizeof(alphabet) - 1U)];
    name[LIBTMP_NAME_LEN] = '\0';
    snprintf(out, out_sz, "%s/%s.tmp", LIBTMP_DIR, name);
    if (f_stat(out, &info) == FR_NO_FILE) return true;
  }
  out[0] = '\0';
  return false;
}
