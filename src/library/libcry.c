#include "include/libcry.h"
#include "main.h"
#include <string.h>

#define LIBCRY_MAGIC 0x31595243UL /* CRY1 */
#define LIBCRY_VERSION 1UL

static const uint32_t g_key[4] = {
    0x27A4C1D3UL, 0xB6905E2FUL, 0x41FC837AUL, 0x9D12E5B8UL};
static uint32_t g_nonce_seq;

static uint32_t load32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8U) |
         ((uint32_t)p[2] << 16U) | ((uint32_t)p[3] << 24U);
}

static void store32(uint8_t *p, uint32_t v) {
  p[0] = (uint8_t)v;
  p[1] = (uint8_t)(v >> 8U);
  p[2] = (uint8_t)(v >> 16U);
  p[3] = (uint8_t)(v >> 24U);
}

static void xtea(uint32_t block[2]) {
  uint32_t v0 = block[0], v1 = block[1], sum = 0U;
  const uint32_t delta = 0x9E3779B9UL;
  for (uint32_t i = 0U; i < 32U; ++i) {
    v0 += (((v1 << 4U) ^ (v1 >> 5U)) + v1) ^
          (sum + g_key[sum & 3U]);
    sum += delta;
    v1 += (((v0 << 4U) ^ (v0 >> 5U)) + v0) ^
          (sum + g_key[(sum >> 11U) & 3U]);
  }
  block[0] = v0;
  block[1] = v1;
}

static void crypt_ctr(uint8_t *data, uint32_t len, uint32_t nonce0,
                      uint32_t nonce1) {
  for (uint32_t off = 0U, counter = 0U; off < len; off += 8U, ++counter) {
    uint32_t stream[2] = {nonce0 ^ counter, nonce1 + counter};
    uint8_t bytes[8];
    xtea(stream);
    store32(bytes, stream[0]);
    store32(bytes + 4U, stream[1]);
    uint32_t n = len - off < 8U ? len - off : 8U;
    for (uint32_t i = 0U; i < n; ++i) data[off + i] ^= bytes[i];
  }
}

static void mac_update(uint32_t state[2], const uint8_t *data, uint32_t len) {
  for (uint32_t off = 0U; off < len; off += 8U) {
    uint8_t block[8] = {0};
    uint32_t n = len - off < 8U ? len - off : 8U;
    memcpy(block, data + off, n);
    state[0] ^= load32(block);
    state[1] ^= load32(block + 4U);
    xtea(state);
  }
}

static void make_mac(const uint8_t *header, const uint8_t *cipher,
                     uint32_t len, uint32_t mac[2]) {
  uint32_t state[2] = {0x6D61632DUL ^ g_key[0], 0x63727931UL ^ g_key[1]};
  mac_update(state, header, 20U);
  mac_update(state, cipher, len);
  state[0] ^= len;
  state[1] ^= 0x80000000UL;
  xtea(state);
  mac[0] = state[0];
  mac[1] = state[1];
}

uint32_t LibCry_SealedSize(uint32_t plain_len) {
  return plain_len <= UINT32_MAX - LIBCRY_OVERHEAD
             ? plain_len + LIBCRY_OVERHEAD
             : 0U;
}

bool LibCry_Seal(const void *plain, uint32_t plain_len, void *sealed,
                 uint32_t sealed_cap, uint32_t *sealed_len) {
  uint8_t *out = (uint8_t *)sealed;
  uint32_t total = LibCry_SealedSize(plain_len);
  if (!plain || !out || total == 0U || sealed_cap < total) return false;
  uint32_t nonce0 = HAL_GetTick() ^ HAL_GetUIDw0() ^ ++g_nonce_seq;
  uint32_t nonce1 = HAL_GetUIDw1() ^ HAL_GetUIDw2() ^ (plain_len << 7U);
  store32(out, LIBCRY_MAGIC);
  store32(out + 4U, LIBCRY_VERSION);
  store32(out + 8U, nonce0);
  store32(out + 12U, nonce1);
  store32(out + 16U, plain_len);
  memset(out + 20U, 0, 8U);
  memcpy(out + LIBCRY_OVERHEAD, plain, plain_len);
  crypt_ctr(out + LIBCRY_OVERHEAD, plain_len, nonce0, nonce1);
  uint32_t mac[2];
  make_mac(out, out + LIBCRY_OVERHEAD, plain_len, mac);
  store32(out + 20U, mac[0]);
  store32(out + 24U, mac[1]);
  if (sealed_len) *sealed_len = total;
  return true;
}

bool LibCry_Open(const void *sealed, uint32_t sealed_len, void *plain,
                 uint32_t plain_cap, uint32_t *plain_len) {
  const uint8_t *in = (const uint8_t *)sealed;
  uint8_t *out = (uint8_t *)plain;
  if (!in || !out || sealed_len < LIBCRY_OVERHEAD ||
      load32(in) != LIBCRY_MAGIC || load32(in + 4U) != LIBCRY_VERSION)
    return false;
  uint32_t len = load32(in + 16U);
  if (len > plain_cap || LibCry_SealedSize(len) != sealed_len) return false;
  uint32_t mac[2];
  make_mac(in, in + LIBCRY_OVERHEAD, len, mac);
  if (mac[0] != load32(in + 20U) || mac[1] != load32(in + 24U)) return false;
  memcpy(out, in + LIBCRY_OVERHEAD, len);
  crypt_ctr(out, len, load32(in + 8U), load32(in + 12U));
  if (plain_len) *plain_len = len;
  return true;
}
