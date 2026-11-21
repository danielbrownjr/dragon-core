#!/usr/bin/env python3
"""Compile the real SPA handler with host HTTP stubs; no ESP-IDF required.

Run: python3 tests/check_portal.py (Python 3 and a C11 compiler named cc).
Only temporary files are written. Checks response status, Location, caching,
and SPA fallback in both network modes; this does not emulate the IDF router.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
portal = (root / 'components/dc_portal/dc_portal.c').read_text()
handler = portal.split('static esp_err_t spa_get(httpd_req_t *req)', 1)[1]
handler = 'static esp_err_t spa_get(httpd_req_t *req)' + handler.split(
    '\nstatic esp_err_t provisioning_get(', 1)[0]
harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef int esp_err_t;
#define ESP_OK 0
struct { const char *root_redirect; } s_config;
/* Kept visible so a future AP-specific condition is exercised too. */
bool s_ap_mode;
typedef struct { const char *uri; } httpd_req_t;
typedef struct { unsigned char app_elf_sha256[32]; } esp_app_desc_t;
typedef struct {
    const unsigned char *data;
    size_t len;
    const char *content_type, *content_encoding;
} dc_ui_asset_t;
static const unsigned char spa[] = "SPA";
static const char *status, *location, *cache, *body;
static int body_len;
static dc_ui_asset_t dc_ui_spa_asset(void) {
    return (dc_ui_asset_t){spa, 3, "text/html", "gzip"};
}
static const esp_app_desc_t *esp_app_get_description(void) { return NULL; }
static int httpd_req_get_hdr_value_str(httpd_req_t *r, const char *k,
                                      char *v, size_t n) {
    (void)r; (void)k; (void)v; (void)n; return -1;
}
static int httpd_resp_set_status(httpd_req_t *r, const char *v) {
    (void)r; status = v; return ESP_OK;
}
static int httpd_resp_set_hdr(httpd_req_t *r, const char *k, const char *v) {
    (void)r;
    if (!strcmp(k, "Location")) location = v;
    if (!strcmp(k, "Cache-Control")) cache = v;
    return ESP_OK;
}
static int httpd_resp_set_type(httpd_req_t *r, const char *v) {
    (void)r; assert(!strcmp(v, "text/html")); return ESP_OK;
}
static int httpd_resp_send(httpd_req_t *r, const char *v, int n) {
    (void)r; body = v; body_len = n; return ESP_OK;
}
'''
harness += handler
harness += r'''
int main(void) {
    const char *uris[] = {"/", "/?", "/?foo=bar", "/other", "/other?x=1",
                          "/setup", "/fw", "//", "/setup?x=1"};
    const char *redirects[] = {NULL, "", "/", "/home", "https://example.test/home"};
    unsigned count = 0;
    for (int ap = 0; ap < 2; ++ap) {
        s_ap_mode = ap;
        for (size_t d = 0; d < sizeof(redirects)/sizeof(*redirects); ++d) {
            s_config.root_redirect = redirects[d];
            for (size_t u = 0; u < sizeof(uris)/sizeof(*uris); ++u) {
                httpd_req_t req = {uris[u]};
                status = "200 OK"; location = cache = body = NULL; body_len = -1;
                assert(spa_get(&req) == ESP_OK);
                bool redirect = d >= 3 && u < 3;
                if (strcmp(status, redirect ? "302 Found" : "200 OK")) {
                    fprintf(stderr, "mode=%d uri=%s destination=%s status=%s\n",
                            ap, uris[u], redirects[d] ? redirects[d] : "NULL", status);
                    return 1;
                }
                if (redirect) {
                    assert(location && !strcmp(location, redirects[d]));
                    assert(!strcmp(cache, "no-store"));
                    assert(body == NULL && body_len == 0);
                } else {
                    assert(location == NULL);
                    assert(!strcmp(cache, "no-cache"));
                    assert(body == (const char *)spa && body_len == 3);
                }
                ++count;
            }
        }
    }
    printf("portal SPA handler: %u cases PASS\n", count);
}
'''
with tempfile.TemporaryDirectory(prefix='dc-portal-test-') as tmp:
    source = Path(tmp) / 'portal.c'
    binary = Path(tmp) / 'portal'
    source.write_text(harness)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
