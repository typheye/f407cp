/**
 ******************************************************************************
 * @file    file_manager.h
 * @author  Typheye
 * @brief   SD card file manager interface (boot log / system dump).
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

#ifndef FILE_MANAGER_H
#define FILE_MANAGER_H

#include "ff.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief  Append one formatted log line to the SD boot log.
 * @param  line  NUL-terminated log line (CRLF already appended by caller)
 * @param  len   Byte length of @p line
 * @retval FRESULT; FR_NOT_READY / FR_NO_FILESYSTEM while the SD card is not
 *         ready so early-boot messages are silently retried by the caller.
 */
FRESULT FMCore_AppendBootLog(const char *line, uint32_t len);

/**
 * @brief  Write a fatal system dump record to the SD card.
 */
FRESULT FMCore_WriteSystemDump(uint32_t code, const char *name,
                               const char *extra);

#ifdef __cplusplus
}
#endif

#endif /* FILE_MANAGER_H */
