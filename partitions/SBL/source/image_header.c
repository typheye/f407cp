/**
 ******************************************************************************
 * @file    image_header.c
 * @author  Typheye
 * @brief   SBL image header verification implementation.
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

#include <stdint.h>

/* Size of the TOS image header, in bytes. Must match the host signing tooling
 * (scripts/sign.ps1: HeaderSize = 0x80) and the linker ASSERT in SBL.ld. */
#ifndef TOS_IMAGE_HEADER_SIZE
#define TOS_IMAGE_HEADER_SIZE 0x80U
#endif

/* The host signing step replaces this section in exported ELF and BIN files. */
__attribute__((section(".tos_image_header"), used, aligned(4)))
const uint8_t g_tos_image_header_placeholder[TOS_IMAGE_HEADER_SIZE] = {
    [0 ... TOS_IMAGE_HEADER_SIZE - 1] = 0xFFU,
};
