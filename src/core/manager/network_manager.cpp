#include "include/network_manager.h"

static bool g_net_hard_disabled = true;
static NetAsyncState_t g_async_state = NET_ASYNC_IDLE;
static char g_async_resp[16] = "";
static uint8_t g_async_fail_streak = 0U;

bool Net_IsHardDisabled(void) { return g_net_hard_disabled; }
void Net_PrepareClient(void) {}
void Net_ConfigureStationCompatibility(void) {}
void Net_LightCleanup(void) {}
void Net_ResetDnsCache(void) {}
bool Net_HasStationIP(void) { return false; }
void Net_LedSuccess(void) {}
void Net_LedFailure(void) {}
bool Net_HttpGet(const char *, uint16_t, const char *, char *, uint16_t, uint32_t) { return false; }
bool Net_HttpPost(const char *, uint16_t, const char *, const char *, uint16_t, char *, uint16_t, uint32_t) { return false; }
bool Net_AsyncHttpPostStart(const char *, uint16_t, const char *, const char *, uint16_t, uint32_t) {
  g_async_state = NET_ASYNC_FAILED;
  g_async_fail_streak++;
  return false;
}
void Net_AsyncTick(void) {}
NetAsyncState_t Net_AsyncState(void) { return g_async_state; }
const char *Net_AsyncResponse(void) { return g_async_resp; }
void Net_AsyncReset(void) { g_async_state = NET_ASYNC_IDLE; g_async_resp[0] = '\0'; }
uint8_t Net_AsyncNoRxFailStreak(void) { return g_async_fail_streak; }
void Net_ResetTransportDiagnostics(void) { g_async_fail_streak = 0U; }
