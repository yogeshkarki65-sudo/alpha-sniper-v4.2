#!/usr/bin/env bash
set -euo pipefail; set +H
svc=alpha-sniper-async.service
log="$(journalctl -u "$svc" --since "10 min ago" -o cat || true)"

thr="$(awk '/EAGER_THRESHOLDS/{l=$0} END{print l}' <<<"$log")"
sum="$(grep -Eo '\[EAGER_SUMMARY\].*' <<<"$log" || true)"
fsg="$(awk '/EAGER_FILTER_SUMMARY/{l=$0} END{print l}' <<<"$log")"
act="$(grep -E 'EAGER_PLACE|EAGER_FILLED|EAGER_CANCEL|SKIP_AFTER_PASS' <<<"$log" || true)"

echo "Last thresholds: ${thr:-'(none)'}"
echo "Last filter summary: ${fsg:-'(none)'}"
echo; echo "Summaries:"; echo "${sum:-(none)}"
echo; echo "Actions:"; echo "${act:-(none)}"
