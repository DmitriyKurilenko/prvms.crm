#!/bin/sh
set -eu

mkdir -p /opt/data/skills

if [ ! -f /opt/data/config.yaml ]; then
  cp /config/config.yaml /opt/data/config.yaml
fi

tmp_file="$(mktemp)"
awk '
  /^model:/ {
    in_model = 1
    print
    next
  }
  /^[^ ]/ {
    in_model = 0
  }
  in_model && /^  default:/ {
    print "  default: qwen3.6-plus"
    next
  }
  in_model && /^  provider:/ {
    print "  provider: opencode-go"
    next
  }
  in_model && /^  base_url:/ {
    print "  base_url: https://opencode.ai/zen/go/v1"
    next
  }
  { print }
' /opt/data/config.yaml > "$tmp_file"
cat "$tmp_file" > /opt/data/config.yaml
rm -f "$tmp_file"

cp /crm-skills/*.py /opt/data/skills/
