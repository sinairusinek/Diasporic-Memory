"""Re-class items currently using dctype:Collection (23):
- True family collections (identifier G-F-NNNN or no identifier with 'אוסף' title) -> arkivo:Fonds (1028)
- Sub-folder mis-tags (identifier G-F-NNNN-MMM) -> arkivo:File (1026)
- 2 edge cases reported but left alone

Class label of 1028 is renamed to 'Family Collection' so the badge reads correctly.
"""
from __future__ import annotations
import json, os, re, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "jecke-cli/1.0"}
OLD_CLASS = 23
FONDS_CLASS = 1028  # arkivo:Fonds = "Family Collection"
FOLDER_CLASS = 1026  # arkivo:File = "Folder"

FAMILY_IDENT = re.compile(r"^IL-MTFN-001-G-F-\d{4}$")
SUBFOLDER_IDENT = re.compile(r"^IL-MTFN-001-G-F-\d{4}-\d+$")


def env():
    if "OMEKA_BASE_URL" not in os.environ:
        for line in (ROOT / ".env").read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")
    return (os.environ["OMEKA_BASE_URL"],
            os.environ["OMEKA_KEY_IDENTITY"],
            os.environ["OMEKA_KEY_CREDENTIAL"])


def auth_qs() -> str:
    _, ki, kc = env()
    return urllib.parse.urlencode({"key_identity": ki, "key_credential": kc})


def main():
    base, _, _ = env()
    items_data: list[dict] = []
    page = 1
    while True:
        q = auth_qs() + "&" + urllib.parse.urlencode({
            "resource_class_id": OLD_CLASS, "per_page": 100, "page": page})
        req = urllib.request.Request(f"{base}/items?{q}", headers=UA)
        data = json.load(urllib.request.urlopen(req, timeout=60))
        if not data:
            break
        items_data.extend(data)
        if len(data) < 100:
            break
        page += 1
    print(f"Found {len(items_data)} items with class 23")

    to_fonds: list[dict] = []
    to_folder: list[dict] = []
    edge: list[dict] = []
    for it in items_data:
        ident = ""
        for v in it.get("dcterms:identifier") or []:
            if isinstance(v, dict) and v.get("@value"):
                ident = v["@value"]
                break
        title = ""
        for v in it.get("dcterms:title") or []:
            if isinstance(v, dict) and v.get("@value"):
                title = v["@value"]
                break
        if FAMILY_IDENT.match(ident):
            to_fonds.append(it)
        elif SUBFOLDER_IDENT.match(ident):
            to_folder.append(it)
        elif not ident and ("אוסף" in title or "משפח" in title):
            to_fonds.append(it)
        else:
            edge.append(it)
    print(f"To Family Collection (1028): {len(to_fonds)}")
    print(f"To Folder (1026): {len(to_folder)}")
    print(f"Edge cases (left alone): {len(edge)}")
    for it in edge:
        ident = (it.get("dcterms:identifier") or [{}])[0].get("@value", "")
        title = (it.get("dcterms:title") or [{}])[0].get("@value", "")
        print(f"  o:id={it['o:id']} ident={ident!r} title={title[:60]!r}")

    def reclass(it: dict, new_class: int) -> bool:
        body = {"o:resource_class": {"o:id": new_class}}
        for preserve in ("dcterms:identifier", "dcterms:isPartOf"):
            if it.get(preserve):
                body[preserve] = it[preserve]
        try:
            req = urllib.request.Request(
                f"{base}/items/{it['o:id']}?{auth_qs()}",
                data=json.dumps(body).encode(), method="PATCH",
                headers={**UA, "Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=30)
            return True
        except urllib.error.HTTPError as e:
            print(f"  o:id={it['o:id']}: HTTP {e.code}")
            return False

    succ = fail = 0
    for i, it in enumerate(to_fonds):
        if reclass(it, FONDS_CLASS):
            succ += 1
        else:
            fail += 1
        if (i + 1) % 50 == 0:
            print(f"  fonds: {i+1}/{len(to_fonds)}")
    print(f"Fonds done. ok={succ} fail={fail}")
    succ2 = fail2 = 0
    for it in to_folder:
        if reclass(it, FOLDER_CLASS):
            succ2 += 1
        else:
            fail2 += 1
    print(f"Folder done. ok={succ2} fail={fail2}")


if __name__ == "__main__":
    main()
