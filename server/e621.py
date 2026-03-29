import sys
import requests
import json
import os

_this = sys.modules[__name__]

def setting(*names, default=None):
    for n in names:
        if hasattr(_this, n):
            return getattr(_this, n)
    return default

baseUrl = 'https://e621.net/'

headers = {
    'User-Agent': 'ivsClient/1.0 (by Pugsby on e621)',
    'Accept-Language': 'en-US,en;q=0.9'
}

def cleanExistingFiles(postId, correctExt, fileUrl):
    folder = "images/e621/"
    sourceFilename = fileUrl.split("/")[-1].split("?")[0]
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        name, ext = os.path.splitext(filename)
        if ext == ".json":
            continue
        if name == str(postId) and ext != correctExt:
            print(f"  Deleting: {filename}")
            os.remove(filepath)

        elif filename == sourceFilename:
            print(f"  Deleting: {filename}")
            os.remove(filepath)

def postAlreadyDownloaded(postId, correctExt):
    path = os.path.join("images/e621/", str(postId) + correctExt)
    return os.path.isfile(path)

def run():
    apiKey = setting("apiKey", default=None)
    username = setting("username", default=None)
    
    print("Getting favorites for " + username)
    url = baseUrl + "posts.json?tags=fav:" + username + "&login=" + username + "&api_key=" + apiKey
    print(url)
    response = requests.get(url, headers=headers)
    data = json.loads(response.text)
    print("Found " + str(len(data["posts"])) + " posts.")
    os.makedirs("images/e621/", exist_ok=True)

    skipped = 0
    downloaded = 0
    saved = 0

    for post in data["posts"]:
        postData = {}
        postData["name"] = "Post: " + str(post["id"])
        postData["artist"] = ", ".join(post["tags"]["artist"])
        if post["description"] != "":
            postData["description"] = post["description"]
        postData["tags"] = (post["tags"]["general"] + post["tags"]["contributor"] + post["tags"]["copyright"] +
                            post["tags"]["character"] + post["tags"]["species"] + post["tags"]["invalid"] +
                            post["tags"]["meta"] + post["tags"]["lore"])
        with open("images/e621/" + str(post["id"]) + ".json", 'w') as json_file:
            json.dump(postData, json_file, indent=4)

        file_url = post["file"]["url"]
        correct_ext = "." + file_url.split(".")[-1].split("?")[0]

        if postAlreadyDownloaded(post["id"], correct_ext):
            print(f"  Skipping post {post['id']} (already downloaded)")
            skipped += 1
            continue

        cleanExistingFiles(post["id"], correct_ext, file_url)

        downloadImage = requests.get(file_url, headers=headers, stream=True)
        downloadImage.raise_for_status()
        with open("images/e621/" + str(post["id"]) + correct_ext, 'wb') as file:
            for chunk in downloadImage.iter_content(chunk_size=8192):
                file.write(chunk)

        print(f"  Downloaded post {post['id']}{correct_ext}")
        downloaded += 1

    print(f"\nDone. Downloaded: {downloaded}, Skipped: {saved}: {skipped}")