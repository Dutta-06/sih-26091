"""Constants shared by the Python data-pack builder and the on-device generator (src/core/localgen.ts).

Writes mobile/src/core/data/gen_content.json. Run: python mobile/scripts/export_gen_content.py
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from datapack_content import DAYS, REG_RATE, SUPPLIERS, TAG_LABELS, _GENERIC_HQ, _GENERIC_VILLAGE_SUPPLIERS  # noqa: E402

out = {
    "days": DAYS,
    "regRate": REG_RATE,
    "suppliers": {k: [en, hi, tags] for k, (en, hi, tags) in SUPPLIERS.items()},
    "tagLabels": TAG_LABELS,
    "genericHqSuppliers": _GENERIC_HQ,
    "genericVillageSuppliers": _GENERIC_VILLAGE_SUPPLIERS,
}
(HERE.parent / "src" / "core" / "data" / "gen_content.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("gen_content.json written")
