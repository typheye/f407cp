/**
 ******************************************************************************
 * @file    libjson.c
 * @author  Typheye
 * @brief   Libjson implementation.
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

#include "include/libjson.h"


/* ── helpers ──────────────────────────────────────────────────── */

static void skip_ws(const char **p) {
  while (**p == ' ' || **p == '\t' || **p == '\r' || **p == '\n')
    ++(*p);
}

/* ── public API ───────────────────────────────────────────────── */

const char *json_extract_body(const char *http) {
  if (!http || !*http) return http;

  /* Some transport responses may prepend text such as:
   *   Recv ...\r\n\r\nSEND OK\r\n\r\n+IPD,N:HTTP/1.1 ...
   * The first CRLFCRLF is not the HTTP header boundary.  Search for HTTP/
   * first, then strip the real HTTP headers.
   */
  const char *h = strstr(http, "HTTP/");
  const char *body = NULL;
  if (h) {
    body = strstr(h, "\r\n\r\n");
    if (body) return body + 4;
    body = strchr(h, '{');
    return body ? body : h;
  }

  body = strchr(http, '{');
  return body ? body : http;
}

const char *json_find(const char *buf, const char *key) {
  if (!buf || !key) return NULL;

  char search[48];
  int n = snprintf(search, sizeof(search), "\"%s\"", key);
  if (n <= 0 || n >= (int)sizeof(search)) return NULL;

  const char *p = strstr(buf, search);
  if (!p) return NULL;

  p += n;           /* skip past "\"key\"" */
  skip_ws(&p);
  if (*p != ':') return NULL;
  ++p;              /* skip ':' */
  skip_ws(&p);
  return p;
}

int json_get_int(const char *buf, const char *key, int default_val) {
  const char *p = json_find(buf, key);
  if (!p) return default_val;
  return atoi(p);
}

bool json_get_str(const char *buf, const char *key, char *out, int outsz) {
  if (!out || outsz <= 0) return false;
  out[0] = '\0';

  const char *p = json_find(buf, key);
  if (!p) return false;
  if (*p != '"') return false;
  ++p; /* skip opening quote */

  int i = 0;
  while (*p && *p != '"' && i < outsz - 1) {
    if (*p == '\\' && p[1]) {
      ++p;
      switch (*p) {
      case 'n':  out[i++] = '\n'; break;
      case 'r':  out[i++] = '\r'; break;
      case 't':  out[i++] = '\t'; break;
      case '\\': out[i++] = '\\'; break;
      case '"':  out[i++] = '"';  break;
      default:   out[i++] = *p;   break;
      }
      ++p;
    } else {
      out[i++] = *p++;
    }
  }
  out[i] = '\0';
  return true;
}

bool json_get_bool(const char *buf, const char *key, bool default_val) {
  const char *p = json_find(buf, key);
  if (!p) return default_val;
  return (*p == 't' || *p == 'T');
}

static bool jw_append(JsonWriter_t *w, const char *s) {
  if (!w || !w->buf || !s || w->cap <= 0 || w->error) return false;
  int n = (int)strlen(s);
  if (w->len + n >= w->cap) {
    w->error = true;
    if (w->cap > 0) w->buf[w->cap - 1] = '\0';
    return false;
  }
  memcpy(&w->buf[w->len], s, (size_t)n);
  w->len += n;
  w->buf[w->len] = '\0';
  return true;
}

static bool jw_field(JsonWriter_t *w, const char *key) {
  if (!w || !key) return false;
  if (!w->first && !jw_append(w, ",\n")) return false;
  w->first = false;
  return jw_append(w, "  \"") && jw_append(w, key) && jw_append(w, "\": ");
}

void json_writer_begin(JsonWriter_t *w, char *buf, int cap) {
  if (!w) return;
  w->buf = buf;
  w->cap = cap;
  w->len = 0;
  w->first = true;
  w->error = false;
  if (!buf || cap <= 0) {
    w->error = true;
    return;
  }
  buf[0] = '\0';
  (void)jw_append(w, "{\n");
}

bool json_writer_add_int(JsonWriter_t *w, const char *key, int value) {
  char num[16];
  snprintf(num, sizeof(num), "%d", value);
  return jw_field(w, key) && jw_append(w, num);
}

bool json_writer_add_bool(JsonWriter_t *w, const char *key, bool value) {
  return jw_field(w, key) && jw_append(w, value ? "true" : "false");
}

bool json_writer_end(JsonWriter_t *w) {
  return jw_append(w, "\n}\n");
}

bool json_writer_ok(const JsonWriter_t *w) {
  return w && !w->error && w->buf && w->cap > 0 && w->len < w->cap;
}
