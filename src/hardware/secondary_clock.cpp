#include "include/secondary_clock.hpp"

#include "include/ssd1315.hpp"
#include "core/sys/include/syslog.h"
#include "library/include/liboledgfx.h"
#include <cstdio>
#include <cstring>

namespace {
uint8_t frameBuffer[LIBOLEDGFX_BUFFER_SIZE];
uint32_t lastFrameMs = 0U;
uint32_t lastSeenSeq = 0U;
uint32_t lastForceRefreshMs = 0U;
uint8_t pendingPage = 8U;
uint8_t pageRetry = 0U;
bool running = false;
bool displayEnabled = false;

bool displayFullBlocking() {
  return oled.display(frameBuffer, sizeof(frameBuffer));
}

void startPagedRefresh() {
  pendingPage = 0U;
  pageRetry = 0U;
}

void servicePagedRefresh() {
  if (pendingPage >= 8U)
    return;
  if (oled.busy())
    return;
  /* Use the blocking page transaction here. The DMA path depends on the
   * generated I2C callback chain and can leave the panel permanently busy
   * after a regenerated CubeMX project; a 1 KB page takes only a few ms at
   * 400 kHz and is deterministic. */
  if (oled.displayPage(pendingPage, &frameBuffer[pendingPage * 128U])) {
    pendingPage++;
    pageRetry = 0U;
  } else if (++pageRetry > 8U) {
    pendingPage = 8U;
    pageRetry = 0U;
  }
}

void drawLogScreen(uint32_t seq) {
  (void)seq;
  char lines[9][32];
  uint32_t count = SysLog_OledSnapshot(lines, 9U);

  LibOledGfx_Clear(frameBuffer, 0U);

  uint32_t first = count > 9U ? count - 9U : 0U;
  for (uint32_t i = first; i < count; ++i) {
    uint8_t y = static_cast<uint8_t>((i - first) * 7U);
    LibOledGfx_DrawText3x5(frameBuffer, 0U, y, lines[i]);
  }
}
} // namespace

void SecondaryClock_Init() {
  running = false;
  displayEnabled = false;
  lastFrameMs = 0U;
  lastSeenSeq = 0U;
  lastForceRefreshMs = 0U;
  pendingPage = 8U;
  pageRetry = 0U;

  if (!oled.init()) {
    LOG_W("OLED", "SSD1315 not found at 0x3C/0x3D");
    return;
  }

  LibOledGfx_Clear(frameBuffer, 0U);
  (void)oled.display(frameBuffer, sizeof(frameBuffer));
  running = true;
  LOG_I("OLED", "SSD1315 log display ready at 0x%02X", oled.address());
  lastSeenSeq = SysLog_OledSequence();
  drawLogScreen(lastSeenSeq);
  (void)displayFullBlocking();
  (void)oled.setDisplayOn(true);
  displayEnabled = true;
  startPagedRefresh();
}

void SecondaryClock_Tick() {
  if (!running || !displayEnabled)
    return;

  servicePagedRefresh();
  if (pendingPage < 8U)
    return;

  uint32_t now = HAL_GetTick();
  if ((uint32_t)(now - lastFrameMs) < 150U)
    return;
  lastFrameMs = now;

  uint32_t seq = SysLog_OledSequence();
  bool changed = seq != lastSeenSeq;
  bool force = (uint32_t)(now - lastForceRefreshMs) >= 1000U;
  if (!changed && !force)
    return;
  lastSeenSeq = seq;
  lastForceRefreshMs = now;
  drawLogScreen(seq);
  startPagedRefresh();
}

void SecondaryClock_SetDisplayOn(bool enabled) {
  if (!running || displayEnabled == enabled)
    return;
  if (!oled.setDisplayOn(enabled))
    return;
  displayEnabled = enabled;
  if (enabled) {
    lastFrameMs = 0U;
    lastForceRefreshMs = 0U;
    lastSeenSeq = SysLog_OledSequence();
    drawLogScreen(lastSeenSeq);
    startPagedRefresh();
  } else {
    pendingPage = 8U;
    pageRetry = 0U;
  }
}
