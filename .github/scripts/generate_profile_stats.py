import json
import os
import urllib.request
from collections import Counter
from datetime import date
from html import escape

USERNAME = "nasif-xy"
TOKEN = os.environ["GH_TOKEN"]
OUT = "assets"
os.makedirs(OUT, exist_ok=True)

def api(url, graphql=False):
    data = None
    if graphql:
        data = json.dumps({"query": url}).encode()
        url = "https://api.github.com/graphql"
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-stats-generator",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())

def svg_card(title, lines, width=495, height=180):
    rows = "".join(
        f'<text x="28" y="{78 + i*29}" fill="#a9b1d6" font-size="14">{escape(str(label))}</text>'
        f'<text x="{width-28}" y="{78 + i*29}" fill="#7aa2f7" font-size="14" text-anchor="end" font-weight="600">{escape(str(value))}</text>'
        for i, (label, value) in enumerate(lines)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1a1b2e"/><stop offset="1" stop-color="#24283b"/></linearGradient></defs>
<rect width="100%" height="100%" rx="14" fill="url(#bg)" stroke="#414868"/>
<circle cx="{width-28}" cy="25" r="4" fill="#9ece6a"/><text x="28" y="37" fill="#7dcfff" font-size="17" font-weight="700">{escape(title)}</text>
<path d="M28 51 H{width-28}" stroke="#414868"/>{rows}
</svg>'''

user = api(f"https://api.github.com/users/{USERNAME}")
repos = []
page = 1
while page <= 10:
    batch = api(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}&type=owner")
    if not batch:
        break
    repos.extend(batch)
    if len(batch) < 100:
        break
    page += 1

public_repos = [r for r in repos if not r.get("fork")]
stars = sum(r.get("stargazers_count", 0) for r in repos)
forks = sum(r.get("forks_count", 0) for r in repos)
languages = Counter()
for repo in public_repos:
    try:
        data = api(repo["languages_url"])
        for lang, amount in data.items():
            languages[lang] += amount
    except Exception:
        pass

query = '''query($login:String!){ user(login:$login){ contributionsCollection { totalCommitContributions totalIssueContributions totalPullRequestContributions totalRepositoryContributions contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } } } } }'''
graphql = api(query, graphql=True)
collection = graphql.get("data", {}).get("user", {}).get("contributionsCollection", {})
calendar = collection.get("contributionCalendar", {})
days = [d for week in calendar.get("weeks", []) for d in week.get("contributionDays", [])]
active = [d["contributionCount"] > 0 for d in days]
longest = current = 0
for on in active:
    current = current + 1 if on else 0
    longest = max(longest, current)
current_streak = 0
for d in reversed(days):
    if d["date"] > date.today().isoformat():
        continue
    if d["contributionCount"] > 0:
        current_streak += 1
    else:
        break

stats = [
    ("Public repositories", user.get("public_repos", 0)),
    ("Followers", user.get("followers", 0)),
    ("Stars across public repos", stars),
    ("Forks across public repos", forks),
]
top_langs = [(name, f"{amount:,} bytes") for name, amount in languages.most_common(6)]
streak_lines = [
    ("Contributions (last year)", calendar.get("totalContributions", 0)),
    ("Current contribution streak", f"{current_streak} days"),
    ("Longest streak in displayed year", f"{longest} days"),
    ("Commits (last year)", collection.get("totalCommitContributions", 0)),
]
for name, lines in [
    ("github-stats.svg", ("GitHub overview", stats)),
    ("top-langs.svg", ("Most used languages (by code size)", top_langs or [("No language data yet", "—")])),
    ("streak.svg", ("Contribution activity", streak_lines)),
]:
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(svg_card(lines[0], lines[1]))
print("Generated profile cards in assets/.")
