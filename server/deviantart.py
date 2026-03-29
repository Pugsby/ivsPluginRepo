import requests
import json
import os
import re
import time
import subprocess
import glob
import sys

_this = sys.modules[__name__]

def setting(*names, default=None):
    for n in names:
        if hasattr(_this, n):
            return getattr(_this, n)
    return default

clientId = setting("clientId", default="63721")
clientSecret = setting("clientSecret", default="2f71c2ccb4fedde4a025c46901ed8f2b")
username = setting("username", default="pugsbyp")

baseUrl = "https://www.deviantart.com/api/v1/oauth2/"
outputDir = "images/deviantart/"

headers = {
    "User-Agent": "ivsClient/1.0",
    "Accept-Language": "en-US,en;q=0.9",
}

tokenCache = {"token": None, "expires_at": 0}

def getAccessToken():
    if tokenCache["token"] and time.time() < tokenCache["expires_at"] - 60:
        return tokenCache["token"]
    resp = requests.post(
        "https://www.deviantart.com/oauth2/token",
        data={
            "grant_type":    "client_credentials",
            "client_id":     clientId,
            "client_secret": clientSecret,
        },
        headers=headers,
    )
    resp.raise_for_status()
    data = resp.json()
    tokenCache["token"]      = data["access_token"]
    tokenCache["expires_at"] = time.time() + data.get("expires_in", 3600)
    return tokenCache["token"]


def apiGet(endpoint, params=None):
    params = params or {}
    params["access_token"]   = getAccessToken()
    params["mature_content"] = "true"
    resp = requests.get(baseUrl + endpoint, params=params, headers=headers)
    resp.raise_for_status()
    return resp.json()


def downloadViaGalleryDl(pageUrl, devId):
    result = subprocess.run(
        [
            "gallery-dl",
            "--dest", outputDir,
            "--no-part",
            "-o", f"filename={devId}_{{num}}.{{extension}}",
            "-o", "directory=[]",
            pageUrl,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"    gallery-dl stderr: {result.stderr.strip()}")
        return False

    matches = [f for f in glob.glob(os.path.join(outputDir, f"{devId}_*.*"))
               if not f.endswith(".json")]

    if not matches:
        print(f"    gallery-dl ran but no file found for {devId}")
        return False

    return True


def alreadyDownloaded(devId):
    flat = glob.glob(os.path.join(outputDir, f"{devId}_*.*"))
    nested = glob.glob(os.path.join(outputDir, devId, f"{devId}_*.*"))
    return any(not f.endswith(".json") for f in flat + nested)


def fetchMetadataBatch(devIds):
    results = {}
    for i in range(0, len(devIds), 50):
        batch = devIds[i:i + 50]
        params = [("access_token", getAccessToken()), ("mature_content", "true")]
        for did in batch:
            params.append(("deviationids[]", did))
        resp = requests.get(
            baseUrl + "deviation/metadata",
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        for item in resp.json().get("metadata", []):
            results[item["deviationid"]] = item
        time.sleep(0.25)
    return results


def saveMetadata(deviation, meta):
    devId = deviation["deviationid"]
    data = {
        "name":   deviation.get("title", f"Deviation {devId}"),
        "artist": deviation.get("author", {}).get("username", "unknown"),
        "tags":   [t["tag_name"] for t in meta.get("tags", [])],
    }
    desc = meta.get("description", "").strip()
    if desc:
        data["description"] = desc
    with open(os.path.join(outputDir, f"{devId}.json"), "w") as f:
        json.dump(data, f, indent=4)


def fetchAllFavourites(username):
    deviations = []
    offset = 0
    limit  = 24

    while True:
        data = apiGet("collections/all", {
            "username": username,
            "offset":   offset,
            "limit":    limit,
        })
        batch = data.get("results", [])
        deviations.extend(batch)
        print(f"  Fetched {len(deviations)} so far...")
        if not data.get("has_more") or not batch:
            break
        offset += len(batch)
        time.sleep(0.25)

    return deviations


def mergeMultiImagePosts():
    print("\nChecking for multi-image posts...")

    from collections import defaultdict
    groups = defaultdict(list)

    for filepath in glob.glob(os.path.join(outputDir, "*.*")):
        filename = os.path.basename(filepath)
        if filename.endswith(".json"):
            continue
        match = re.match(r'^(.+)_(\d+)(\.[^.]+)$', filename)
        if match:
            groups[match.group(1)].append(filepath)

    merged = renamed = 0
    for devId, files in groups.items():
        if len(files) == 1:
            src = files[0]
            ext = os.path.splitext(src)[1]
            dest = os.path.join(outputDir, f"{devId}{ext}")
            os.replace(src, dest)
            renamed += 1
        else:
            folder = os.path.join(outputDir, devId)
            os.makedirs(folder, exist_ok=True)
            for src in files:
                os.replace(src, os.path.join(folder, os.path.basename(src)))
            print(f"  Merged {len(files)} images for {devId} into folder")
            merged += 1

    print(f"  Renamed {renamed} single-image post(s), merged {merged} multi-image post(s).")


def run():
    print("Scraping Favourites from DeviantArt")
    os.makedirs(outputDir, exist_ok=True)

    deviations = fetchAllFavourites(USERNAME)
    print(f"Found {len(deviations)} favourites.\n")

    devIds = [dev["deviationid"] for dev in deviations]
    print("Fetching metadata (tags + descriptions)...")
    metadataMap = fetchMetadataBatch(devIds)
    print(f"Metadata fetched for {len(metadataMap)} deviations.\n")

    downloaded = skipped = failed = 0

    for dev in deviations:
        devId = dev["deviationid"]
        title = dev.get("title", str(devId))
        pageUrl = dev.get("url", "")

        saveMetadata(dev, metadataMap.get(devId, {}))

        if alreadyDownloaded(devId):
            print(f"  Skipping '{title}' (already downloaded)")
            skipped += 1
            continue

        if not pageUrl:
            print(f"  Skipping '{title}' — no page URL")
            failed += 1
            continue

        print(f"  Downloading '{title}'...")
        if downloadViaGalleryDl(pageUrl, devId):
            downloaded += 1
        else:
            print(f"  Failed '{title}'")
            failed += 1

    print(f"\nDone. Downloaded: {downloaded}, Skipped: {skipped}, Failed: {failed}")
    mergeMultiImagePosts()


if __name__ == "__main__":
    run()