/**
 ******************************************************************************
 * @file    app.cpp
 * @author  Typheye
 * @brief   App implementation.
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

#include "include/app.h"
#include "dram.h"
#include "gui/components/include/alert.hpp"
#include "gui/components/include/confirm.hpp"
#include "library/include/libdly.h"
#include "library/include/libui.h"


extern KeyManager keyManager;
extern LCD boardLCD;

#define FM_MAX_ITEMS 32
#define FM_NAME_LEN 64
#define FM_PATH_LEN 192
#define FM_STACK_DEPTH 8
#define FM_DISPLAY_LIMIT 15

static bool fm_mounted = false;
static void fm_load_dir(void);

static char *fm_cur_path = nullptr;
static char (*fm_items)[FM_NAME_LEN] = nullptr;
static int *fm_is_dir = nullptr;
static uint32_t *fm_size = nullptr;
static uint8_t *fm_attr = nullptr;
static int fm_count = 0;

/* When entering a child directory, remember the selected child index in the
 * parent. When going back through "..", restore that selection instead of
 * jumping back to the top of the parent list. */
static int *fm_parent_sel_stack = nullptr;
static int fm_stack_depth = 0;

static bool fm_alloc_context(void) {
  if (fm_cur_path && fm_items && fm_is_dir && fm_size && fm_attr &&
      fm_parent_sel_stack)
    return true;

  fm_cur_path = (char *)SysDram_Alloc(FM_PATH_LEN);
  fm_items = (char (*)[FM_NAME_LEN])SysDram_Alloc(FM_MAX_ITEMS * FM_NAME_LEN);
  fm_is_dir = (int *)SysDram_Alloc(FM_MAX_ITEMS * sizeof(int));
  fm_size = (uint32_t *)SysDram_Alloc(FM_MAX_ITEMS * sizeof(uint32_t));
  fm_attr = (uint8_t *)SysDram_Alloc(FM_MAX_ITEMS * sizeof(uint8_t));
  fm_parent_sel_stack = (int *)SysDram_Alloc(FM_STACK_DEPTH * sizeof(int));

  if (fm_cur_path && fm_items && fm_is_dir && fm_size && fm_attr &&
      fm_parent_sel_stack) {
    strcpy(fm_cur_path, "0:");
    memset(fm_items, 0, FM_MAX_ITEMS * FM_NAME_LEN);
    memset(fm_is_dir, 0, FM_MAX_ITEMS * sizeof(int));
    memset(fm_size, 0, FM_MAX_ITEMS * sizeof(uint32_t));
    memset(fm_attr, 0, FM_MAX_ITEMS * sizeof(uint8_t));
    memset(fm_parent_sel_stack, 0, FM_STACK_DEPTH * sizeof(int));
    fm_count = 0;
    fm_stack_depth = 0;
    return true;
  }

  SysDram_Free(fm_cur_path);
  SysDram_Free(fm_items);
  SysDram_Free(fm_is_dir);
  SysDram_Free(fm_size);
  SysDram_Free(fm_attr);
  SysDram_Free(fm_parent_sel_stack);
  fm_cur_path = nullptr;
  fm_items = nullptr;
  fm_is_dir = nullptr;
  fm_size = nullptr;
  fm_attr = nullptr;
  fm_parent_sel_stack = nullptr;
  fm_count = 0;
  fm_stack_depth = 0;
  return false;
}

static void fm_free_context(void) {
  SysDram_Free(fm_parent_sel_stack);
  SysDram_Free(fm_is_dir);
  SysDram_Free(fm_size);
  SysDram_Free(fm_attr);
  SysDram_Free(fm_items);
  SysDram_Free(fm_cur_path);
  fm_parent_sel_stack = nullptr;
  fm_is_dir = nullptr;
  fm_size = nullptr;
  fm_attr = nullptr;
  fm_items = nullptr;
  fm_cur_path = nullptr;
  fm_count = 0;
  fm_stack_depth = 0;
}

static void fm_copy_limited(char *out, size_t out_sz, const char *src,
                            size_t max_chars) {
  if (out_sz == 0) {
    return;
  }
  size_t i = 0;
  while (i + 1U < out_sz && i < max_chars && src[i] != '\0') {
    out[i] = src[i];
    i++;
  }
  out[i] = '\0';
}

static void fm_make_display_name(const char *name, bool is_dir, char *out,
                                 size_t out_sz) {
  if (out_sz == 0) {
    return;
  }
  out[0] = '\0';

  if (strcmp(name, "..") == 0) {
    fm_copy_limited(out, out_sz, "..", 2U);
    return;
  }

  const bool append_slash = is_dir;
  const size_t suffix_len = append_slash ? 1U : 0U;
  const size_t name_len = strlen(name);

  if (name_len + suffix_len <= FM_DISPLAY_LIMIT) {
    size_t i = 0;
    while (i + 1U < out_sz && name[i] != '\0') {
      out[i] = name[i];
      i++;
    }
    if (append_slash && i + 1U < out_sz) {
      out[i++] = '/';
    }
    out[i] = '\0';
    return;
  }

  /* Visible ASCII length <= 15. Folder: 11 + "..." + "/" = 15.
   * File  : 12 + "..."       = 15. Avoid snprintf here because gcc is
   * rightfully conservative about truncation warnings. */
  const size_t keep = append_slash ? 11U : 12U;
  size_t i = 0;
  while (i + 1U < out_sz && i < keep && name[i] != '\0') {
    out[i] = name[i];
    i++;
  }
  const char dots[] = "...";
  for (size_t d = 0; d < 3U && i + 1U < out_sz; ++d) {
    out[i++] = dots[d];
  }
  if (append_slash && i + 1U < out_sz) {
    out[i++] = '/';
  }
  out[i] = '\0';
}

static void draw_card(int idx, int sel, int cy, const char *text, bool is_dir) {
  bool s = (idx == sel);
  PD_DrawAngledCard(14, cy, 212, 20, 5, s ? TOS_ACCENT : TOS_CARD_BG);
  PD_SetColor(s ? TOS_TEXT : TOS_TEXT_SEC);

  char buf[FM_DISPLAY_LIMIT + 2];
  fm_make_display_name(text, is_dir, buf, sizeof(buf));
  PD_DrawString(26, cy + 2, buf);
}

static void fm_fatal_if_storage_error(FRESULT res, uint32_t fallback) {
  SysHandle_FatalFResult(res, fallback);
}

static FRESULT fm_mount_result(void) {
  if (!fm_mounted) {
    FRESULT res = FMCore_MountStorage(NULL, false);
    if (res == FR_OK) {
      fm_mounted = true;
    }
    return res;
  }
  return FR_OK;
}

static void fm_mount(void) {
  FRESULT res = fm_mount_result();
  fm_fatal_if_storage_error(res, SYS_ERR_SD_BROWSER_FAILED);
}

static void fm_unmount(void) {
  if (fm_mounted) {
    /* The system owns the shared FatFs mount; the browser only borrows it. */
    fm_mounted = false;
  }
}

static void fm_wait_keys_released(uint32_t timeout_ms) {
  uint32_t start = HAL_GetTick();
  while ((HAL_GetTick() - start) < timeout_ms) {
    keyManager._collisionA8.tick();
    keyManager._collisionD0.tick();
    keyManager._btnEnter.tick();
    if (keyManager._collisionA8.getState() != KEY_PRESSED &&
        keyManager._collisionD0.getState() != KEY_PRESSED &&
        keyManager._btnEnter.getState() != KEY_PRESSED) {
      return;
    }
    JPDelay(5);
  }
}

static bool fm_prepare_storage(void) {
  FRESULT res = fm_mount_result();
  LOG_I("FILE", "mount result: %s(%d)", SFHD_FResultName(res), (int)res);
  if (res != FR_OK) {
    fm_fatal_if_storage_error(res, SYS_ERR_SD_BROWSER_FAILED);
    return false;
  }
  return true;
}

static void fm_build_full_path(const char *name, char *out, size_t out_sz) {
  if (!FMCore_JoinPath(fm_cur_path, name, out, out_sz)) {
    fm_copy_limited(out, out_sz, "Path too long", strlen("Path too long"));
  }
}

static void fm_wrap_for_alert(const char *path, char *out, size_t out_sz) {
  if (out_sz == 0) {
    return;
  }

  const size_t width = 22U; /* alert.cpp truncates each line at 22 chars */
  size_t op = 0;
  size_t col = 0;

  const char *prefix = "[Path]\n";
  for (const char *p = prefix; *p && op + 1 < out_sz; ++p) {
    out[op++] = *p;
  }

  col = 0;
  for (const char *p = path; *p && op + 1 < out_sz; ++p) {
    if (col >= width) {
      out[op++] = '\n';
      col = 0;
      if (op + 1 >= out_sz) {
        break;
      }
    }
    out[op++] = *p;
    col++;
  }
  out[op] = '\0';
}

static void fm_format_permission(int idx, char *out, size_t out_sz) {
  if (out_sz == 0)
    return;
  const char *name = fm_items[idx];
  if (strcmp(fm_cur_path, "/") == 0) {
    if (strcmp(name, "init") == 0) {
      fm_copy_limited(out, out_sz, "rx", 2);
      return;
    }
    if (strcmp(name, "data") == 0) {
      fm_copy_limited(out, out_sz, "r", 1);
      return;
    }
    if (strcmp(name, "storage") == 0) {
      fm_copy_limited(out, out_sz, "rwx", 3);
      return;
    }
    if (strcmp(name, "tmp") == 0) {
      fm_copy_limited(out, out_sz, "rw", 2);
      return;
    }
  }
  size_t n = 0;
  if (n + 1 < out_sz)
    out[n++] = 'r';
  if ((fm_attr[idx] & AM_RDO) == 0 && n + 1 < out_sz)
    out[n++] = 'w';
  if (fm_is_dir[idx] && n + 1 < out_sz)
    out[n++] = 'x';
  out[n] = '\0';
}

static bool fm_is_protected(int idx) {
  if (idx < 0 || idx >= fm_count)
    return true;
  if (strcmp(fm_items[idx], "..") == 0)
    return true;
  if (strcmp(fm_cur_path, "/") != 0)
    return false;
  return strcmp(fm_items[idx], "init") == 0 ||
         strcmp(fm_items[idx], "data") == 0 ||
         strcmp(fm_items[idx], "storage") == 0 ||
         strcmp(fm_items[idx], "tmp") == 0;
}

static void fm_show_information(int idx) {
  char msg[256];
  if (strcmp(fm_items[idx], "..") == 0) {
    char full_path[FM_PATH_LEN + 3];
    snprintf(full_path, sizeof(full_path), "0:%s", fm_cur_path);
    fm_wrap_for_alert(full_path, msg, sizeof(msg));
  } else {
    char perm[8];
    fm_format_permission(idx, perm, sizeof(perm));
    if (fm_is_dir[idx]) {
      snprintf(msg, sizeof(msg), "[Folder Name]\n%s\n[Folder Permission]\n%s",
               fm_items[idx], perm);
    } else {
      snprintf(msg, sizeof(msg),
               "[File Name]\n%s\n[File Size]\n%lu B\n[File Permission]\n%s",
               fm_items[idx], (unsigned long)fm_size[idx], perm);
    }
  }
  fm_wait_keys_released(120);
  alert_show("FILE", msg);
  fm_wait_keys_released(120);
}

static void fm_show_menu_frame(int sel, const char *const *items, int count) {
  LCD_FLUSH({
    UI_DrawFrameTitle("FILE");
    PD_SetFont(FONT_ASCII_16);
    for (int i = 0; i < count; ++i)
      UI_DrawMenuCard(i, sel, 33 + i * 25, items[i]);
    PD_DrawFooterCenter("ENTER", NULL, "UP/DOWN");
  });
}

static int fm_open_folder_menu(int idx) {
  static const char *folder_items[] = {"00 Open", "01 Information",
                                       "02 Cancel"};
  static const char *upper_items[] = {"00 Upper", "01 Information",
                                      "02 Cancel"};
  const char *const *items =
      strcmp(fm_items[idx], "..") == 0 ? upper_items : folder_items;
  int sel = 0;
  uint8_t enter_seen = 0;
  uint32_t lu = 0;
  while (1) {
    TosApi_Tick();
    keyManager._collisionA8.tick();
    keyManager._collisionD0.tick();
    keyManager._btnEnter.tick();
    if (keyManager._collisionA8.getState() == KEY_PRESSED) {
      sel = (sel + 1) % 3;
      JPDelay(2);
    }
    if (keyManager._collisionD0.getState() == KEY_PRESSED) {
      sel = (sel + 2) % 3;
      JPDelay(2);
    }
    uint8_t ce = keyManager._btnEnter.getState() == KEY_PRESSED;
    if (ce && !enter_seen) {
      enter_seen = 1;
      if (sel == 0)
        return 0;
      if (sel == 2)
        return -1;
      fm_show_information(idx);
      return -1;
    } else if (!ce) {
      enter_seen = 0;
    }
    if (HAL_GetTick() - lu > 80U) {
      lu = HAL_GetTick();
      fm_show_menu_frame(sel, items, 3);
    }
    JPDelay(1);
  }
}

static void fm_open_menu(int idx, int *sel_io) {
  static const char *full[] = {"00 Return", "01 Open/Run", "02 Information",
                               "03 Delete"};
  static const char *protected_items[] = {"00 Return", "01 Information"};
  const char *const *items = fm_is_protected(idx) ? protected_items : full;
  int count = fm_is_protected(idx) ? 2 : 4;
  int sel = 0;
  uint8_t enter_seen = 0;
  uint32_t lu = 0;
  while (1) {
    TosApi_Tick();
    keyManager._collisionA8.tick();
    keyManager._collisionD0.tick();
    keyManager._btnEnter.tick();
    if (keyManager._collisionA8.getState() == KEY_PRESSED) {
      sel = (sel + 1) % count;
      JPDelay(2);
    }
    if (keyManager._collisionD0.getState() == KEY_PRESSED) {
      sel = (sel + count - 1) % count;
      JPDelay(2);
    }
    uint8_t ce = keyManager._btnEnter.getState() == KEY_PRESSED;
    if (ce && !enter_seen) {
      enter_seen = 1;
      if (sel == 0)
        return;
      if ((fm_is_protected(idx) && sel == 1) ||
          (!fm_is_protected(idx) && sel == 2)) {
        fm_show_information(idx);
        return;
      } else if (!fm_is_protected(idx) && sel == 1) {
        fm_wait_keys_released(120);
        alert_show("FILE", "Stay tuned");
        return;
      } else if (!fm_is_protected(idx) && sel == 3) {
        char perm[8];
        fm_format_permission(idx, perm, sizeof(perm));
        if (strchr(perm, 'w') == NULL) {
          fm_wait_keys_released(120);
          alert_show("FILE", "Permission denied");
          return;
        } else {
          fm_wait_keys_released(120);
          if (confirm_show("FILE", "Confirm to delete the file or folder?")) {
            char full_path[FM_PATH_LEN + FM_NAME_LEN];
            fm_build_full_path(fm_items[idx], full_path, sizeof(full_path));
            FRESULT res = FMCore_Delete(full_path, true, false);
            if (res == FR_OK) {
              fm_load_dir();
              if (sel_io && *sel_io >= fm_count)
                *sel_io = fm_count > 0 ? fm_count - 1 : 0;
              return;
            }
            char err[48];
            snprintf(err, sizeof(err), "Delete failed (%d)", (int)res);
            alert_show("FILE", err);
            return;
          }
          return;
        }
      }
      fm_wait_keys_released(120);
    } else if (!ce) {
      enter_seen = 0;
    }
    if (HAL_GetTick() - lu > 80U) {
      lu = HAL_GetTick();
      fm_show_menu_frame(sel, items, count);
    }
    JPDelay(1);
  }
}

static void fm_push_parent_selection(int sel) {
  if (fm_stack_depth < FM_STACK_DEPTH) {
    fm_parent_sel_stack[fm_stack_depth++] = sel;
  } else {
    /* Keep the newest navigation history if the user enters very deeply. */
    for (int i = 1; i < FM_STACK_DEPTH; ++i) {
      fm_parent_sel_stack[i - 1] = fm_parent_sel_stack[i];
    }
    fm_parent_sel_stack[FM_STACK_DEPTH - 1] = sel;
  }
}

static int fm_pop_parent_selection(void) {
  if (fm_stack_depth <= 0) {
    return 0;
  }
  return fm_parent_sel_stack[--fm_stack_depth];
}

static void fm_trim_to_parent(void) {
  if (strcmp(fm_cur_path, "/") == 0) {
    return;
  }

  char *p = strrchr(fm_cur_path, '/');
  if (p == NULL || p == fm_cur_path) {
    strcpy(fm_cur_path, "/");
  } else {
    *p = '\0';
  }
}

static void fm_load_dir(void) {
  fm_count = 0;
  if (!fm_mounted)
    fm_mount();
  if (!fm_mounted)
    return;

  /* Always show .. for navigation/exit. Keep it at index 0. */
  strcpy(fm_items[0], "..");
  fm_is_dir[0] = 1;
  fm_size[0] = 0;
  fm_attr[0] = AM_DIR;
  fm_count = 1;

  FMCore_Entry entries[FM_MAX_ITEMS - 1];
  uint16_t n = 0;
  FRESULT res =
      FMCore_ListDir(fm_cur_path, entries, FM_MAX_ITEMS - 1, &n, true);
  if (res != FR_OK) {
    fm_fatal_if_storage_error(res, SYS_ERR_SD_BROWSER_FAILED);
    return;
  }

  for (uint16_t i = 0; i < n && fm_count < FM_MAX_ITEMS; ++i) {
    int idx = fm_count++;
    strncpy(fm_items[idx], entries[i].name, FM_NAME_LEN - 1);
    fm_items[idx][FM_NAME_LEN - 1] = '\0';
    fm_is_dir[idx] = entries[i].is_dir ? 1 : 0;
    fm_size[idx] = entries[i].size;
    fm_attr[idx] = entries[i].attr;
  }

  /* Sort: directories first, then case-insensitive alphabetical order.
   * Start at 1 so ".." is never sorted into the list. */
  for (int i = 1; i < fm_count - 1; i++) {
    for (int j = i + 1; j < fm_count; j++) {
      bool swap = false;
      if (fm_is_dir[i] && !fm_is_dir[j])
        continue;
      if (!fm_is_dir[i] && fm_is_dir[j])
        swap = true;
      else if (strcasecmp(fm_items[i], fm_items[j]) > 0)
        swap = true;
      if (swap) {
        char tn[FM_NAME_LEN];
        int td;
        uint32_t tsz;
        uint8_t ta;
        memcpy(tn, fm_items[i], FM_NAME_LEN);
        td = fm_is_dir[i];
        tsz = fm_size[i];
        ta = fm_attr[i];
        memcpy(fm_items[i], fm_items[j], FM_NAME_LEN);
        fm_is_dir[i] = fm_is_dir[j];
        fm_size[i] = fm_size[j];
        fm_attr[i] = fm_attr[j];
        memcpy(fm_items[j], tn, FM_NAME_LEN);
        fm_is_dir[j] = td;
        fm_size[j] = tsz;
        fm_attr[j] = ta;
      }
    }
  }
}

static bool fm_enter(int idx, int *sel_io) {
  if (idx < 0 || idx >= fm_count) {
    return false;
  }

  if (!fm_is_dir[idx]) {
    fm_open_menu(idx, sel_io);
    return false;
  }

  if (strcmp(fm_items[idx], "..") == 0) {
    fm_open_menu(idx, sel_io);
    return false;
  }

  char next_path[FM_PATH_LEN];
  if (!FMCore_JoinPath(fm_cur_path, fm_items[idx], next_path,
                       sizeof(next_path))) {
    fm_wait_keys_released(600);
    alert_show("FILE", "Path too long");
    return false;
  }

  fm_push_parent_selection(idx);
  strncpy(fm_cur_path, next_path, FM_PATH_LEN - 1);
  fm_cur_path[FM_PATH_LEN - 1] = '\0';
  fm_load_dir();

  if (sel_io != NULL) {
    *sel_io = 0;
  }
  return false;
}

static bool fm_go_parent(int *sel_io) {
  if (strcmp(fm_cur_path, "/") == 0) {
    fm_unmount();
    return true;
  }
  fm_trim_to_parent();
  fm_load_dir();
  int restored = fm_pop_parent_selection();
  if (restored < 0)
    restored = 0;
  if (restored >= fm_count)
    restored = fm_count > 0 ? fm_count - 1 : 0;
  if (sel_io)
    *sel_io = restored;
  return false;
}

void file_manager_run(void) {
  if (!fm_alloc_context()) {
    alert_show("FILE", "Memory failed");
    return;
  }

  if (!fm_prepare_storage()) {
    fm_free_context();
    return;
  }

  strcpy(fm_cur_path, "/");
  fm_stack_depth = 0;
  fm_load_dir();

  int n = fm_count, sel = 0;
  uint32_t lu = 0;
  uint32_t last_probe = 0;

  while (1) {
    TosApi_Tick();
    keyManager._collisionA8.tick();
    keyManager._collisionD0.tick();
    keyManager._btnEnter.tick();

    if (n <= 0) {
      fm_load_dir();
      n = fm_count;
      sel = 0;
    }

    if (n > 0 && keyManager._collisionA8.getState() == KEY_PRESSED) {
      sel = (sel + 1) % n;
      JPDelay(2);
    }
    if (n > 0 && keyManager._collisionD0.getState() == KEY_PRESSED) {
      sel = (sel - 1 + n) % n;
      JPDelay(2);
    }

    if ((HAL_GetTick() - last_probe) > 1200U && fm_mounted &&
        FMCore_IsInitialized()) {
      last_probe = HAL_GetTick();
      FILINFO ping;
      FRESULT pr = FMCore_Stat("/init", &ping, false);
      if (SysHandle_IsStorageFatal(pr)) {
        SysHandle_FatalFResult(pr, SYS_ERR_SD_LOST);
      }
    }
    KeyState_t enter_state = keyManager._btnEnter.getState();
    if (enter_state == KEY_PRESSED) {
      if (n == 0) {
        fm_unmount();
        fm_free_context();
        return;
      }
      bool exit_requested = false;
      if (fm_is_dir[sel]) {
        int action = fm_open_folder_menu(sel);
        if (action == 0) {
          if (strcmp(fm_items[sel], "..") == 0)
            exit_requested = fm_go_parent(&sel);
          else
            exit_requested = fm_enter(sel, &sel);
        }
      } else {
        exit_requested = fm_enter(sel, &sel);
      }
      if (exit_requested || !fm_mounted) {
        fm_free_context();
        return; /* exit via .. at root */
      }
      n = fm_count;
      if (sel < 0) {
        sel = 0;
      }
      if (sel >= n) {
        sel = n > 0 ? n - 1 : 0;
      }
      lu = 0;
      JPDelay(2);
    }

    if (HAL_GetTick() - lu > 80U) {
      lu = HAL_GetTick();
      LCD_FLUSH({
        UI_DrawFrameTitle("FILE");
        PD_SetFont(FONT_ASCII_16);
        int vis = n < 7 ? n : 7;
        if (n == 0)
          vis = 1;
        int start = sel - vis / 2;
        if (start < 0)
          start = 0;
        if (start + vis > n)
          start = n - vis;
        if (start < 0)
          start = 0;

        if (n == 0) {
          draw_card(0, 0, 33, "   No files", false);
        } else {
          for (int i = 0; i < vis; i++) {
            int idx = start + i;
            if (idx >= n)
              break;
            draw_card(idx, sel, 33 + i * 25, fm_items[idx], fm_is_dir[idx]);
          }
        }
        PD_DrawFooterCenter("ENTER", NULL, "UP/DOWN");
      });
    }
    TosApi_Tick();
    JPDelay(1);
  }
}
