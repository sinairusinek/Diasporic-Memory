#!/bin/bash
# Batch driver: acquire -> tesseract -> classify for each pilot folder.
# Portable to bash 3.2 (no associative arrays). Edit PAIRS to add folders.
cd "$(dirname "$0")/../.."

PAIRS="
0113-41:1loyGgsVUdq5KOweB-6KjmcpnGwFTMTc4
0422-3:12Y2FwnHj8kqF1YGlnUwc3pafn-wT5u_q
0276-6:1MWkzFHOEpS9fQHq0kB88M1_72mYEFrJW
0047-2:1AI1PA5XTtDzmFCOTZwCA0n2mu0EUQCDC
0185-2:1CdAbq59wCF31zRUxQHes7nPKPH3Ses12
0047-4:1hiuDoM3tdfwviBM16AgQ3hscwBOs_GHH
"

for pair in $PAIRS; do
  folder="${pair%%:*}"
  id="${pair##*:}"
  [ -z "$folder" ] && continue
  echo "===== $folder ($id) ====="
  python3 code/recatalog/acquire.py --folder "$folder" --drive-folder-id "$id" --remote jeckedrive 2>&1 | tail -2
  n=$(ls "data/recatalog/$folder/scans/" 2>/dev/null | wc -l | tr -d ' ')
  echo "  $folder: $n pages, OCR..."
  python3 code/recatalog/ocr_tesseract.py --folder "$folder" --langs deu+heb+eng >/dev/null 2>&1
  python3 code/recatalog/classify.py --folder "$folder" 2>&1 | grep -E "escalation|print|handwriting|script:" | head -6
  echo "  $folder DONE"
done
echo "ALL DONE"
