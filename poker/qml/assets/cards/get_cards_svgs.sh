#!/bin/bash
# Downloads SVG playing cards into this directory (assets/cards/).
# Re-run only when refreshing deck art; update application.qrc if filenames change.

set -euo pipefail
cd "$(dirname "$0")"

URL="https://tekeye.uk/playing_cards/images/svg_playing_cards/"
SUITE_ENUM=("clubs" "spades" "hearts" "diamonds")
RANK_ENUM=("2" "3" "4" "5" "6" "7" "8" "9" "10" "jack" "queen" "king" "ace")

for suite in "${SUITE_ENUM[@]}"; do
  for rank in "${RANK_ENUM[@]}"; do
    wget -q -O "${suite}_${rank}.svg" "${URL}fronts/${suite}_${rank}.svg"
  done
done

wget -q -O blue2.svg "${URL}backs/blue2.svg"
