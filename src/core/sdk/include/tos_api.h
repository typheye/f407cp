#ifndef TOS_API_H
#define TOS_API_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

void TosApi_Init(void);
void TosApi_Tick(void);
void TosApi_SetPaused(bool paused);

typedef struct {
  bool has_update;
  char latest_version[24];
  char latest_build[24];
  char latest_patch[48];
  int latest_size;
} TosUpgradeInfo;

bool TosApi_CheckUpgrade(TosUpgradeInfo *info);

#ifdef __cplusplus
}
#endif

#endif
