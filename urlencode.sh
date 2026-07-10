#!/usr/bin/env bash
# urlencode.sh: percent-encode a string for use in URLs
#
# ⚠️ DEPRECATED for use with this project's `url` glance.yml parameter.
# Glance's custom-api widget already percent-encodes parameter values
# before calling this service, so pre-encoding the URL with this script
# and pasting the result into glance.yml causes DOUBLE encoding (e.g.
# Google Calendar's "%40" becomes "%2540"), which breaks the fetch.
# See issue #29. Just use the raw ICS URL in glance.yml instead.

set -euo pipefail
IFS=

urlencode() {
  local string="${1}"
  local strlen=${#string}
  local encoded=""
  local pos c o

  # use C locale so byte values are predictable
  LC_ALL=C

  for (( pos=0; pos<strlen; pos++ )); do
    c=${string:pos:1}
    case "$c" in
      [a-zA-Z0-9.~_-]) 
        # safe characters
        encoded+="$c"
        ;;
      *)
        # percent-encode others
        printf -v o '%%%02X' "'$c"
        encoded+="$o"
        ;;
    esac
  done

  printf '%s\n' "$encoded"
}

# if called with an argument, encode and print it
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <string>" >&2
    exit 1
  fi
  urlencode "$1"
fi
