#ifndef TOS_CDC_BRIDGE_H
#define TOS_CDC_BRIDGE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

void CDC_Bridge_Start(void);
void CDC_Bridge_Tick(void);
void CDC_Bridge_UsbReceived(const uint8_t *data, uint32_t size);

#ifdef __cplusplus
}
#endif

#endif
