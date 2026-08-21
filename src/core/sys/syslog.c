/**
 ******************************************************************************
 * @file    syslog.c
 * @author  Typheye
 * @brief   Syslog implementation.
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

#include "include/syslog.h"
#include "file_manager.h"
#include "core/manager/include/settings_manager.h"

extern RTC_HandleTypeDef hrtc;

static uint8_t g_syslog_file_guard = 0;
static uint8_t g_syslog_file_disabled = 0;
static uint8_t g_syslog_file_failures = 0;

#define SYSLOG_OLED_LINES 9U
#define SYSLOG_OLED_COLS  32U
static char g_oled_lines[SYSLOG_OLED_LINES][SYSLOG_OLED_COLS];
static uint32_t g_oled_seq = 0U;

static const char *syslog_level_name(SysLog_Level_t level) {
  switch (level) {
  case SYSLOG_FATAL:
    return "FATAL";
  case SYSLOG_ERROR:
    return "ERROR";
  case SYSLOG_WARN:
    return "WARN ";
  case SYSLOG_INFO:
    return "INFO ";
  case SYSLOG_DEBUG:
    return "DEBUG";
  default:
    return "LOG  ";
  }
}

static char syslog_level_letter(SysLog_Level_t level) {
  switch (level) {
  case SYSLOG_FATAL: return 'F';
  case SYSLOG_ERROR: return 'E';
  case SYSLOG_WARN:  return 'W';
  case SYSLOG_INFO:  return 'I';
  case SYSLOG_DEBUG: return 'D';
  default: return '?';
  }
}

static void syslog_oled_push(SysLog_Level_t level, const char *mod,
                             const char *msg) {
  char compact[SYSLOG_OLED_COLS];
  char clean[224];
  const char *m = msg ? msg : "";
  size_t clean_len = 0U;
  size_t pos = 0U;

  /*
   * The OLED is a single-line log tail.  Flatten CR/LF/TAB and all other
   * control bytes here, before the line reaches the renderer.  This also
   * prevents a multi-line printf message from corrupting the OLED layout.
   */
  while (*m != '\0' && clean_len < sizeof(clean) - 1U) {
    unsigned char ch = (unsigned char)*m++;
    if (ch < 0x20U || ch == 0x7FU) {
      clean[clean_len++] = ' ';
    } else {
      clean[clean_len++] = (char)ch;
    }
  }
  clean[clean_len] = '\0';
  if (clean_len > 24U) {
    memmove(clean, clean + clean_len - 24U, 24U);
    clean[24U] = '\0';
  }

  memset(compact, ' ', sizeof(compact));
  compact[sizeof(compact) - 1U] = '\0';

  compact[pos++] = syslog_level_letter(level);
  compact[pos++] = ' ';
  if (mod) {
    for (uint8_t i = 0U; i < 5U && mod[i] != '\0' && pos < sizeof(compact) - 1U;
         ++i) {
      compact[pos++] = mod[i];
    }
  }
  compact[pos++] = ' ';
  for (uint8_t i = 0U; clean[i] != '\0' && pos < sizeof(compact) - 1U; ++i) {
    compact[pos++] = clean[i];
  }
  compact[pos] = '\0';
  strncpy(g_oled_lines[g_oled_seq % SYSLOG_OLED_LINES], compact,
          SYSLOG_OLED_COLS - 1U);
  g_oled_lines[g_oled_seq % SYSLOG_OLED_LINES][SYSLOG_OLED_COLS - 1U] = '\0';
  g_oled_seq++;
}

/* Hand-rolled uint32→dec (avoids newlib-nano snprintf issues) */
static int u32dec(uint32_t v, char *b) {
  if (!v) {
    b[0] = '0';
    return 1;
  }
  char t[12];
  int n = 0;
  while (v) {
    t[n++] = '0' + (v % 10);
    v /= 10;
  }
  for (int i = 0; i < n; i++)
    b[i] = t[n - 1 - i];
  return n;
}

/* Return a fixed digit-budget timestamp.
 * 0..99999s  : "[sssss.mmm]"
 * 100000s+   : "[ssssss.mm]", then "[sssssss.m]"
 * The bracket field keeps 8 numeric digits; the dot moves right when uptime
 * needs more integer digits.
 */
const char *SysLog_Ts(void) {
  static char buf[16];
  uint32_t t = SysLog_GetTick();
  uint32_t sec = t / 1000u;
  uint32_t ms = t % 1000u;
  int p = 0;
  buf[p++] = '[';
  char ts[12];
  int n = u32dec(sec, ts);

  int frac_digits = 8 - n;
  if (frac_digits > 3)
    frac_digits = 3;
  if (frac_digits < 0)
    frac_digits = 0;

  for (int i = n; i < 5; i++)
    buf[p++] = ' ';
  for (int i = 0; i < n; i++)
    buf[p++] = ts[i];
  if (frac_digits > 0) {
    buf[p++] = '.';
    if (frac_digits >= 1)
      buf[p++] = '0' + (ms / 100);
    if (frac_digits >= 2)
      buf[p++] = '0' + ((ms / 10) % 10);
    if (frac_digits >= 3)
      buf[p++] = '0' + (ms % 10);
  }
  buf[p++] = ']';
  buf[p] = '\0';
  return buf;
}

__attribute__((weak)) uint32_t SysLog_GetTick(void) { return HAL_GetTick(); }

void SysLog_DisableFileOutput(void) { g_syslog_file_disabled = 1U; }

bool SysLog_IsFileOutputDisabled(void) { return g_syslog_file_disabled != 0U; }

static void syslog_handle_file_result(FRESULT res) {
  if (res == FR_OK) {
    g_syslog_file_failures = 0U;
    return;
  }

  /* Logging starts before SDIO/FatFs is mounted.  Those early messages are
   * expected to return a transient readiness/path result and must not disable
   * file logging for the rest of the boot. */
  if (res == FR_NOT_READY || res == FR_NOT_ENABLED || res == FR_INVALID_DRIVE ||
      res == FR_NO_FILESYSTEM || res == FR_NO_PATH) {
    return;
  }

  if (g_syslog_file_failures < 255U) {
    g_syslog_file_failures++;
  }
  if (g_syslog_file_failures >= 3U) {
    g_syslog_file_disabled = 1U;
    printf("%s [WARN ] [SYS  ] SD log write failed: %d; disabled after %u "
           "consecutive errors\r\n",
           SysLog_Ts(), (int)res, (unsigned)g_syslog_file_failures);
  } else {
    printf("%s [WARN ] [SYS  ] SD log write failed: %d; retrying (%u/3)\r\n",
           SysLog_Ts(), (int)res, (unsigned)g_syslog_file_failures);
  }
}

static void syslog_emit_v(SysLog_Level_t level, const char *mod,
                          const char *fmt, va_list ap) {
  char msg[224];
  char line[320];
  int n;
  size_t len;

  if (!fmt)
    fmt = "";
  if (!mod)
    mod = "SYS";

  n = vsnprintf(msg, sizeof(msg), fmt, ap);
  if (n < 0) {
    strcpy(msg, "(log format error)");
  } else {
    msg[sizeof(msg) - 1U] = '\0';
  }

  n = snprintf(line, sizeof(line) - 2U, "%s [%s] [%-5s] %s", SysLog_Ts(),
               syslog_level_name(level), mod, msg);
  if (n < 0)
    return;
  line[sizeof(line) - 3U] = '\0';
  len = strlen(line);
  if (len + 2U < sizeof(line)) {
    line[len++] = '\r';
    line[len++] = '\n';
    line[len] = '\0';
  }

  syslog_oled_push(level, mod, msg);

  if (SM_Debug_LogCom()) {
    printf("%s", line);
  }

  if (level <= SYSLOG_FILE_MAX_LEVEL && !g_syslog_file_guard &&
      !g_syslog_file_disabled) {
    FRESULT res;
    g_syslog_file_guard = 1U;
    res = FMCore_AppendBootLog(line, (uint32_t)len);
    g_syslog_file_guard = 0U;
    syslog_handle_file_result(res);
  }
}

uint32_t SysLog_OledSnapshot(char lines[][32], uint32_t max_lines) {
  if (!lines || max_lines == 0U) return 0U;
  uint32_t available = g_oled_seq < SYSLOG_OLED_LINES ? g_oled_seq
                                                      : SYSLOG_OLED_LINES;
  uint32_t count = available < max_lines ? available : max_lines;
  uint32_t start = g_oled_seq - count;
  for (uint32_t i = 0U; i < count; ++i) {
    uint32_t idx = (start + i) % SYSLOG_OLED_LINES;
    strncpy(lines[i], g_oled_lines[idx], SYSLOG_OLED_COLS - 1U);
    lines[i][SYSLOG_OLED_COLS - 1U] = '\0';
  }
  return count;
}

uint32_t SysLog_OledSequence(void) { return g_oled_seq; }

void SysLog_Print(SysLog_Level_t level, const char *mod, const char *fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  syslog_emit_v(level, mod, fmt, ap);
  va_end(ap);
}

void SysLog_Write(SysLog_Level_t level, const char *mod, const char *task,
                  const char *file, int line_no, const char *fmt, ...) {
  (void)task;
  (void)file;
  (void)line_no;
  va_list ap;
  va_start(ap, fmt);
  syslog_emit_v(level, mod, fmt, ap);
  va_end(ap);
}

void SysLog_WriteFatalDump(uint32_t code, const char *name) {
  RTC_TimeTypeDef t;
  RTC_DateTypeDef d;
  char rtc_line[48];
  char extra[256];

  strcpy(rtc_line, "rtc=unknown\r\n");
  if (hrtc.Instance == RTC) {
    if (HAL_RTC_GetTime(&hrtc, &t, RTC_FORMAT_BIN) == HAL_OK &&
        HAL_RTC_GetDate(&hrtc, &d, RTC_FORMAT_BIN) == HAL_OK) {
      snprintf(rtc_line, sizeof(rtc_line),
               "rtc=20%02u-%02u-%02u %02u:%02u:%02u wd=%u\r\n", d.Year, d.Month,
               d.Date, t.Hours, t.Minutes, t.Seconds, d.WeekDay);
    }
  }

  snprintf(extra, sizeof(extra),
           "tick_ms=%lu\r\n"
           "%s"
           "network_transport=usb_cdc\r\n"
           "external_network_module=none\r\n",
           (unsigned long)HAL_GetTick(), rtc_line);

  (void)FMCore_WriteSystemDump(code, name, extra);
}
