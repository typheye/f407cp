/**
 ******************************************************************************
 * @file    network_manager.h
 * @author  Typheye
 * @brief   Network Manager interface.
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

#ifndef NETWORK_MANAGER_H
#define NETWORK_MANAGER_H

#include <stdbool.h>
#include <stdint.h>
#include "include/syshandle.h"
#include "core/sys/include/syslog.h"
#include "core/sys/include/syswatchdog.h"
#include <stdio.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief  Check whether the network subsystem is unavailable on this board.
 */
bool Net_IsHardDisabled(void);

/**
 * @brief  Prepare network layer for a client-mode request.
 */
void Net_PrepareClient(void);

/**
 * @brief  Apply station settings placeholder.
 */
void Net_ConfigureStationCompatibility(void);

/**
 * @brief  Lightweight cleanup placeholder.
 */
void Net_LightCleanup(void);

/**
 * @brief  Drop cached network state.
 */
void Net_ResetDnsCache(void);

/**
 * @brief  Check whether the station has a valid IP.
 */
bool Net_HasStationIP(void);

/**
 * @brief  Apply LED feedback for a successful network operation.
 */
void Net_LedSuccess(void);

/**
 * @brief  Apply LED feedback for a failed network operation.
 */
void Net_LedFailure(void);

/**
 * @brief  Perform an HTTP GET request through the network layer.
 * @param  host        Target hostname (e.g. "www.baidu.com")
 * @param  port        TCP port (usually 80)
 * @param  path        Request path (e.g. "/getSysTime.do")
 * @param  resp_buf    Output buffer for the raw response
 * @param  resp_sz     Size of resp_buf
 * @param  timeout_ms  Total timeout (typically 8000–15000)
 * @return true on success (valid response received), false on any error.
 */
bool Net_HttpGet(const char *host, uint16_t port, const char *path,
                 char *resp_buf, uint16_t resp_sz, uint32_t timeout_ms);

/**
 * @brief  Perform an HTTP POST request through the network layer.
 * @param  host        Target hostname
 * @param  port        TCP port
 * @param  path        Request path
 * @param  body        POST body (JSON, form data, etc.)
 * @param  body_len    Length of body in bytes
 * @param  resp_buf    Output buffer for the raw response
 * @param  resp_sz     Size of resp_buf
 * @param  timeout_ms  Total timeout
 * @return true on success, false on any error.
 */
bool Net_HttpPost(const char *host, uint16_t port, const char *path,
                  const char *body, uint16_t body_len,
                  char *resp_buf, uint16_t resp_sz, uint32_t timeout_ms);

typedef enum {
  NET_ASYNC_IDLE = 0,
  NET_ASYNC_BUSY,
  NET_ASYNC_DONE,
  NET_ASYNC_FAILED
} NetAsyncState_t;

/**
 * @brief  Start a non-blocking HTTP POST request.
 */
bool Net_AsyncHttpPostStart(const char *host, uint16_t port, const char *path,
                            const char *body, uint16_t body_len,
                            uint32_t timeout_ms);

/**
 * @brief  Advance the active async request state machine.
 */
void Net_AsyncTick(void);

/**
 * @brief  Current async request state.
 */
NetAsyncState_t Net_AsyncState(void);

/**
 * @brief  Raw HTTP response for a finished async request.
 *         Valid while state is NET_ASYNC_DONE.
 */
const char *Net_AsyncResponse(void);

/**
 * @brief  Clear a DONE/FAILED async request and return to IDLE.
 */
void Net_AsyncReset(void);

/**
 * @brief Consecutive failed async requests that received no transport bytes.
 */
uint8_t Net_AsyncNoRxFailStreak(void);

/** Clear async transport diagnostics. */
void Net_ResetTransportDiagnostics(void);

#ifdef __cplusplus
}
#endif

#endif /* NETWORK_MANAGER_H */
