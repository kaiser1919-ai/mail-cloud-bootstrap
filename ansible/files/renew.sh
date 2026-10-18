#!/bin/sh
set -eu
nginx -t
systemctl reload nginx
if systemctl is-active --quiet dovecot; then systemctl reload dovecot; fi
if systemctl is-active --quiet postfix; then postfix reload; fi
