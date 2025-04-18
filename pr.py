import requests
import datetime
import os

token = os.getenv("GITHUB_TOKEN") or input("Enter your GitHub token: ")
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json",
}

user_info = requests.get("https://api.github.com/user", headers=headers).json()
username = user_info["login"]

current_year = datetime.datetime.now().year
start_date = f"{current_year}-01-01"

search_url = "https://api.github.com/search/issues"
params = {"q": f"is:pr author:{username} created:>={start_date}", "per_page": 100}

all_prs = []
page = 1
while True:
    response = requests.get(search_url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        break

    data = response.json()
    all_prs.extend(data["items"])

    if "next" not in response.links:
        break

    search_url = response.links["next"]["url"]
    params = {}
    page += 1

if not all_prs:
    print("No PR records found")
    exit()

pr_data = []
for pr in all_prs:
    repo_url = pr["repository_url"]
    repo_name = "/".join(repo_url.split("/")[-2:])

    pr_details = requests.get(pr["pull_request"]["url"], headers=headers).json()

    created = datetime.datetime.strptime(
        pr["created_at"], "%Y-%m-%dT%H:%M:%SZ"
    ).strftime("%Y-%m-%d")
    merged = (
        datetime.datetime.strptime(
            pr_details["merged_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).strftime("%Y-%m-%d")
        if pr_details.get("merged_at")
        else "Not merged"
    )
    pr_data.append(
        (
            pr["title"],
            repo_name,
            "Merged" if pr_details.get("merged_at") else pr["state"],
            created,
            merged,
            pr["html_url"],
        )
    )

# sort by created time (column index 3), most recent first
pr_data.sort(key=lambda x: x[3])

filename = f"github_prs_{current_year}.md"
table_headers = ["Created", "Title", "Repository", "State", "Merged"]
lines = [
    "| " + " | ".join(table_headers) + " |",
    "|" + "|".join([" --- "] * len(table_headers)) + "|",
]
for title, repo, state, created, merged, url in pr_data:
    md_title = f"[{title}]({url})"
    lines.append(f"| {created} | {md_title} | {repo} | {state} | {merged} |")
with open(filename, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Found {len(pr_data)} PR records, saved to {filename}")
