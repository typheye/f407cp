#include "include/systime.h"

#include <stdio.h>

bool SysTime_Sync(void) { return false; }
bool SysTime_SyncQuick(void) { return false; }

void SysTime_Fmt(char *buf, int sz, int h24, int m) {
  if (buf == NULL || sz <= 0) return;
  if (h24) {
    snprintf(buf, (size_t)sz, "%02d:%02d", h24, m);
  } else {
    int hh = h24 % 12;
    if (hh == 0) hh = 12;
    snprintf(buf, (size_t)sz, "%02d:%02d", hh, m);
  }
}
