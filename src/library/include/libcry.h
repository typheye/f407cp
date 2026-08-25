#ifndef LIBCRY_H
#define LIBCRY_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define LIBCRY_OVERHEAD 28U

uint32_t LibCry_SealedSize(uint32_t plain_len);
bool LibCry_Seal(const void *plain, uint32_t plain_len, void *sealed,
                 uint32_t sealed_cap, uint32_t *sealed_len);
bool LibCry_Open(const void *sealed, uint32_t sealed_len, void *plain,
                 uint32_t plain_cap, uint32_t *plain_len);

#ifdef __cplusplus
}
#endif

#endif
