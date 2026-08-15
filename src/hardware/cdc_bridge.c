#include "include/cdc_bridge.h"

#include "usart.h"
#include "usbd_cdc_if.h"

#define CDC_BRIDGE_CAPACITY 256U

static uint8_t uartRxByte;
static uint8_t uartToUsb[CDC_BRIDGE_CAPACITY];
static volatile uint16_t writeIndex;
static volatile uint16_t readIndex;

void CDC_Bridge_Start(void) {
  writeIndex = 0U;
  readIndex = 0U;
  (void)HAL_UART_Receive_IT(&huart1, &uartRxByte, 1U);
}

void CDC_Bridge_UsbReceived(const uint8_t *data, uint32_t size) {
  if (data != 0 && size != 0U)
    (void)HAL_UART_Transmit(&huart1, (uint8_t *)data, (uint16_t)size, 100U);
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *uart) {
  if (uart != &huart1)
    return;
  const uint16_t next = (uint16_t)((writeIndex + 1U) % CDC_BRIDGE_CAPACITY);
  if (next != readIndex) {
    uartToUsb[writeIndex] = uartRxByte;
    writeIndex = next;
  }
  (void)HAL_UART_Receive_IT(&huart1, &uartRxByte, 1U);
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *uart) {
  if (uart == &huart1)
    (void)HAL_UART_Receive_IT(&huart1, &uartRxByte, 1U);
}

void CDC_Bridge_Tick(void) {
  static uint8_t packet[64];
  uint16_t count = 0U;
  while (readIndex != writeIndex && count < sizeof(packet)) {
    packet[count++] = uartToUsb[readIndex];
    readIndex = (uint16_t)((readIndex + 1U) % CDC_BRIDGE_CAPACITY);
  }
  if (count != 0U && CDC_Transmit_FS(packet, count) != USBD_OK) {
    /* Preserve ordering when the endpoint is busy. A later UART burst may be
     * dropped once the bounded ring is full, but the main loop never blocks. */
    for (uint16_t i = count; i > 0U; --i) {
      readIndex = (uint16_t)((readIndex + CDC_BRIDGE_CAPACITY - 1U) %
                             CDC_BRIDGE_CAPACITY);
      uartToUsb[readIndex] = packet[i - 1U];
    }
  }
}
