#include "include/libvideo.h"

#include "core/sys/include/syswatchdog.h"
#include "ff.h"
#include "hardware/include/lcd.h"
#include "stm32f4xx_hal.h"
#include <cstdint>
#include <cstring>

namespace {
constexpr uint16_t kVersion = 1U;
constexpr uint16_t kHeaderSize = 40U;
constexpr uint16_t kFlagLoop = 0x0001U;
constexpr uint8_t kCodecRaw = 1U;
constexpr uint8_t kCodecRle = 2U;

#pragma pack(push, 1)
struct FileHeader {
  char magic[4];
  uint16_t version;
  uint16_t header_size;
  uint16_t width;
  uint16_t height;
  uint16_t fps;
  uint16_t flags;
  uint32_t frame_count;
  uint32_t codec;
  uint32_t reserved[4];
};

struct FrameHeader {
  char magic[4];
  uint32_t timestamp_ms;
  uint8_t codec;
  uint8_t flags;
  uint16_t reserved;
  uint32_t payload_size;
  uint32_t pixel_count;
};
#pragma pack(pop)

static_assert(sizeof(FileHeader) == 40U, "TVID file header layout mismatch");
static_assert(sizeof(FrameHeader) == 20U, "TVID frame header layout mismatch");

bool pumped(LibVideoPumpFn pump, void *user) {
  SysWatchdog_Tick();
  return pump && pump(user) != 0;
}

bool read_exact(FIL *file, void *dst, UINT size) {
  UINT read = 0U;
  return f_read(file, dst, size, &read) == FR_OK && read == size;
}

LibVideoResult render_raw(FIL *file, const FrameHeader &frame,
                          LibVideoPumpFn pump, void *user) {
  const uint32_t expected = LCD_WIDTH * LCD_HEIGHT * 2U;
  if (frame.payload_size != expected)
    return LIBVIDEO_INVALID;

  for (uint16_t y = 0U; y < LCD_HEIGHT; y += TILE_HEIGHT) {
    const uint16_t h = static_cast<uint16_t>(
        (y + TILE_HEIGHT <= LCD_HEIGHT) ? TILE_HEIGHT : LCD_HEIGHT - y);
    LCD_BeginTileRender(y, h);
    uint16_t *pixels = LCD_GetFrameBuffer();
    const UINT bytes = static_cast<UINT>(LCD_WIDTH * h * 2U);
    if (!read_exact(file, pixels, bytes))
      return LIBVIDEO_IO_ERROR;

    const uint32_t count = static_cast<uint32_t>(LCD_WIDTH) * h;
    const uint8_t *raw = reinterpret_cast<const uint8_t *>(pixels);
    for (uint32_t i = 0U; i < count; ++i) {
      const uint8_t hi = raw[i * 2U];
      const uint8_t lo = raw[i * 2U + 1U];
      pixels[i] = static_cast<uint16_t>((static_cast<uint16_t>(hi) << 8U) | lo);
    }
    LCD_EndTileRender();
    if (pumped(pump, user))
      return LIBVIDEO_ABORTED;
  }
  return LIBVIDEO_OK;
}

LibVideoResult render_rle(FIL *file, const FrameHeader &frame,
                          LibVideoPumpFn pump, void *user) {
  uint32_t payload_read = 0U;
  uint32_t pixels_done = 0U;
  uint16_t run_left = 0U;
  uint16_t run_color = 0U;

  for (uint16_t y = 0U; y < LCD_HEIGHT; y += TILE_HEIGHT) {
    const uint16_t h = static_cast<uint16_t>(
        (y + TILE_HEIGHT <= LCD_HEIGHT) ? TILE_HEIGHT : LCD_HEIGHT - y);
    LCD_BeginTileRender(y, h);
    uint16_t *pixels = LCD_GetFrameBuffer();
    const uint32_t tile_pixels = static_cast<uint32_t>(LCD_WIDTH) * h;
    uint32_t out = 0U;

    while (out < tile_pixels) {
      if (run_left == 0U) {
        uint8_t run[4];
        if (payload_read + sizeof(run) > frame.payload_size ||
            !read_exact(file, run, sizeof(run)))
          return LIBVIDEO_IO_ERROR;
        payload_read += sizeof(run);
        run_left = static_cast<uint16_t>(run[0] | (run[1] << 8U));
        run_color = static_cast<uint16_t>((run[2] << 8U) | run[3]);
        if (run_left == 0U)
          return LIBVIDEO_INVALID;
      }
      const uint32_t room = tile_pixels - out;
      const uint16_t take = run_left < room ? run_left : static_cast<uint16_t>(room);
      for (uint16_t i = 0U; i < take; ++i)
        pixels[out++] = run_color;
      run_left = static_cast<uint16_t>(run_left - take);
      pixels_done += take;
    }
    LCD_EndTileRender();
    if (pumped(pump, user))
      return LIBVIDEO_ABORTED;
  }

  if (pixels_done != frame.pixel_count || pixels_done != LCD_WIDTH * LCD_HEIGHT ||
      run_left != 0U || payload_read != frame.payload_size)
    return LIBVIDEO_INVALID;
  return LIBVIDEO_OK;
}

LibVideoResult wait_until(uint32_t deadline, LibVideoPumpFn pump, void *user) {
  while (static_cast<int32_t>(HAL_GetTick() - deadline) < 0) {
    if (pumped(pump, user))
      return LIBVIDEO_ABORTED;
    HAL_Delay(1U);
  }
  return LIBVIDEO_OK;
}
} // namespace

extern "C" LibVideoResult LibVideo_Play(const char *path, LibVideoPumpFn pump,
                                          void *user) {
  FIL file{};
  FRESULT fr = f_open(&file, path, FA_READ);
  if (fr == FR_NO_FILE || fr == FR_NO_PATH)
    return LIBVIDEO_NOT_FOUND;
  if (fr != FR_OK)
    return LIBVIDEO_IO_ERROR;

  FileHeader header{};
  if (!read_exact(&file, &header, sizeof(header))) {
    f_close(&file);
    return LIBVIDEO_IO_ERROR;
  }
  if (std::memcmp(header.magic, "TVID", 4U) != 0 ||
      header.version != kVersion || header.header_size != kHeaderSize ||
      header.width != LCD_WIDTH || header.height != LCD_HEIGHT ||
      header.fps == 0U || header.fps > 60U || header.frame_count == 0U ||
      (header.codec != kCodecRaw && header.codec != kCodecRle)) {
    f_close(&file);
    return LIBVIDEO_INVALID;
  }

  const FSIZE_t first_frame = header.header_size;
  do {
    if (f_lseek(&file, first_frame) != FR_OK) {
      f_close(&file);
      return LIBVIDEO_IO_ERROR;
    }
    const uint32_t loop_start = HAL_GetTick();
    for (uint32_t index = 0U; index < header.frame_count; ++index) {
      FrameHeader frame{};
      if (!read_exact(&file, &frame, sizeof(frame))) {
        f_close(&file);
        return LIBVIDEO_IO_ERROR;
      }
      if (std::memcmp(frame.magic, "FRM1", 4U) != 0 ||
          frame.pixel_count != LCD_WIDTH * LCD_HEIGHT ||
          (frame.codec != kCodecRaw && frame.codec != kCodecRle)) {
        f_close(&file);
        return LIBVIDEO_INVALID;
      }

      LibVideoResult result =
          wait_until(loop_start + frame.timestamp_ms, pump, user);
      if (result != LIBVIDEO_OK) {
        f_close(&file);
        return result;
      }
      result = frame.codec == kCodecRaw
                                  ? render_raw(&file, frame, pump, user)
                                  : render_rle(&file, frame, pump, user);
      if (result != LIBVIDEO_OK) {
        f_close(&file);
        return result;
      }
    }
  } while ((header.flags & kFlagLoop) != 0U);

  f_close(&file);
  return LIBVIDEO_OK;
}

extern "C" const char *LibVideo_ResultText(LibVideoResult result) {
  switch (result) {
  case LIBVIDEO_OK: return "PLAYBACK COMPLETE";
  case LIBVIDEO_ABORTED: return "ABORTED";
  case LIBVIDEO_NOT_FOUND: return "TEST.TVID NOT FOUND";
  case LIBVIDEO_INVALID: return "INVALID TEST.TVID";
  case LIBVIDEO_IO_ERROR: return "VIDEO IO ERROR";
  case LIBVIDEO_NO_MEMORY: return "OUT OF MEMORY";
  default: return "VIDEO ERROR";
  }
}
