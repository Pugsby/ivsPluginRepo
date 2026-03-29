def run():
    import os
    import hashlib
    from pathlib import Path
    from itertools import combinations
    from PIL import Image
    import imagehash

    imageExtensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
    similarityThreshold = 97

    def getImages(root: str):
        images = []
        for path in Path(root).rglob('*'):
            if path.suffix.lower() in imageExtensions:
                images.append(path)
        return images

    def computeHash(path: Path):
        try:
            img = Image.open(path).convert('RGB')
            return imagehash.phash(img, hash_size=16)
        except Exception:
            return None

    def similarity(h1, h2) -> float:
        max_bits = len(h1.hash) ** 2
        diff = h1 - h2
        return (1 - diff / max_bits) * 100

    def imageQualityScore(path: Path) -> tuple:
        """Score by resolution then file size — higher is better."""
        try:
            with Image.open(path) as img:
                w, h = img.size
            size = path.stat().st_size
            return (w * h, size)
        except Exception:
            return (0, 0)

    print("Scanning ./images recursively...")
    images = getImages('./images')
    print(f"Found {len(images)} image(s).")

    hashes = {}
    for imgPath in images:
        h = computeHash(imgPath)
        if h is not None:
            hashes[imgPath] = h

    visited = set()
    duplicateGroups = []

    paths = list(hashes.keys())
    for i, a in enumerate(paths):
        if a in visited:
            continue
        group = [a]
        for b in paths[i + 1:]:
            if b in visited:
                continue
            sim = similarity(hashes[a], hashes[b])
            if sim >= similarityThreshold:
                group.append(b)
                visited.add(b)
        if len(group) > 1:
            visited.add(a)
            duplicateGroups.append(group)

    if not duplicateGroups:
        print("No duplicate images found.")
        return

    print(f"\nFound {len(duplicateGroups)} duplicate group(s).")

    deleted = 0
    freedBytes = 0

    for group in duplicateGroups:
        ranked = sorted(group, key=imageQualityScore, reverse=True)
        keeper = ranked[0]
        toDelete = ranked[1:]

        print(f"\n  Keeping:  {keeper}  {imageQualityScore(keeper)}")
        for path in toDelete:
            size = path.stat().st_size
            print(f"  Deleting: {path}  {imageQualityScore(path)}")
            try:
                path.unlink()
                deleted += 1
                freedBytes += size
            except Exception as e:
                print(f"    ERROR deleting {path}: {e}")

    print(f"\nDone. Deleted {deleted} file(s), freed {freedBytes / 1024:.1f} KB.")