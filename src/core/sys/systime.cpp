#include "include/systime.h"

#include <stdio.h>

bool SysTime_Sync(void) { return false; }
bool SysTime_SyncQuick(void) { return false; }

void SysTime_Fmt(char *buf, int sz, int h24, int m) {
  SysTime_FmtStyle(buf, sz, h24, m, SM_Time_Style24h());
}

void SysTime_FmtStyle(char *buf, int sz, int h24, int m, bool style_24h) {
  if (buf == NULL || sz <= 0) return;
  if (style_24h) {
    snprintf(buf, (size_t)sz, "%02d:%02d", h24, m);
  } else {
    int hh = h24 % 12;
    if (hh == 0) hh = 12;
    snprintf(buf, (size_t)sz, "%02d:%02d", hh, m);
  }
}
