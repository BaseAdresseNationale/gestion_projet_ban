#!/usr/bin/env python3
"""Calculate GitHub sprint velocity for a Project v2 'Sprint Ban' iteration."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

POINTS_MAP = {
    "point-1": 1, "points-1": 1,
    "point-2": 2, "points-2": 2,
    "point-3": 3, "points-3": 3,
    "point-5": 5, "points-5": 5,
    "point-8": 8, "points-8": 8,
    "point-13": 13, "points-13": 13,
    "point-21": 21, "points-21": 21,
    "point-34": 34, "points-34": 34,
    "point-55": 55, "points-55": 55,
}

API = "https://api.github.com"


def gh_graphql(query: str, variables: dict):
    payload = {"query": query, "variables": variables}
    req = request.Request(
        f"{API}/graphql",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN', '')}",
            "Content-Type": "application/json",
            "User-Agent": "velocity-report-generator",
        },
        method="POST",
    )
    try:
        with request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if "errors" in data:
            raise RuntimeError(f"GraphQL error: {data['errors']}")
        return data.get("data")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error: {exc.code} {body}") from exc


def fetch_sprint_iterations(org: str, project_number: int):
    """Fetch all Sprint Ban iterations from Project v2"""
    query = """
    query($org: String!, $projectNumber: Int!) {
      organization(login: $org) {
        projectV2(number: $projectNumber) {
          fields(first: 30) {
            nodes {
              ... on ProjectV2IterationField {
                id
                name
                configuration {
                  iterations {
                    id
                    title
                    startDate
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    data = gh_graphql(query, {"org": org, "projectNumber": project_number})
    project = data["organization"]["projectV2"]
    iterations = []
    for field in project["fields"]["nodes"]:
        if field and field.get("name") == "Sprint Ban":
            for iteration in field.get("configuration", {}).get("iterations", []):
                iterations.append({
                    "id": iteration["id"],
                    "title": iteration["title"],
                    "start_date": iteration.get("startDate"),
                })
    return iterations


def fetch_all_project_items(org: str, project_number: int):
    """Fetch ALL project items (no filtering in query)"""
    query = """
    query($org: String!, $projectNumber: Int!) {
      organization(login: $org) {
        projectV2(number: $projectNumber) {
          items(first: 100) {
            nodes {
              id
              content {
                __typename
                ... on Issue {
                  number
                  title
                  state
                  closed
                  closedAt
                  labels(first: 50) {
                    nodes { name }
                  }
                }
              }
              fieldValues(first: 30) {
                nodes {
                  ... on ProjectV2ItemFieldIterationValue {
                    field {
                      ... on ProjectV2IterationField {
                        name
                      }
                    }
                    iterationId
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    data = gh_graphql(query, {"org": org, "projectNumber": project_number})
    return data["organization"]["projectV2"]["items"]["nodes"]


def filter_items_by_iteration(items, iteration_id: str):
    """Filter items by iteration ID in Python"""
    filtered = []
    for item in items:
        for field_value in item.get("fieldValues", {}).get("nodes", []):
            if field_value.get("iterationId") == iteration_id:
                filtered.append(item)
                break
    return filtered


def extract_labels(content):
    """Extract labels from issue content"""
    labels = []
    if content and content.get("labels"):
        for label in content["labels"].get("nodes", []):
            labels.append(label["name"].lower())
    return labels


def compute_points(labels):
    """Sum points from Fibonacci labels"""
    total = 0
    for label in labels:
        if label in POINTS_MAP:
            total += POINTS_MAP[label]
    return total


def load_history(path: Path):
    """Load sprint history from JSON file"""
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def save_history(path: Path, history):
    """Save sprint history to JSON file"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def moving_average(history, window=3):
    """Calculate moving average over last N sprints"""
    if not history:
        return 0
    recent = history[-window:] if len(history) >= window else history
    return round(sum(item["points_completed"] for item in recent) / len(recent), 2)


def create_report_issue(org: str, repo: str, sprint_name: str, velocity: int, tickets_count: int, moving_avg: float, history):
    """Create a GitHub issue with velocity report"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    history_table = "| Sprint | Date | Points | Tickets | Moyenne 3 |\n| --- | --- | ---: | ---: | ---: |\n"
    for entry in history[-5:]:
        date = entry.get("date", "")[:10]
        history_table += f"| {entry.get('sprint', '-')} | {date} | {entry.get('points_completed', 0)} | {entry.get('tickets_completed', 0)} | {entry.get('moving_average_3', '-')} |\n"

    body = f"""## Rapport de vélocité - {sprint_name}

- Date de génération : **{now}**
- Points complétés : **{velocity}**
- Tickets fermés : **{tickets_count}**
- Moyenne mobile (3 sprints) : **{moving_avg}**

### Historique

{history_table}

---
*Rapport généré automatiquement par le workflow de vélocité.*
"""

    payload = {
        "title": f"📊 Rapport vélocité - {sprint_name}",
        "body": body,
        "labels": ["velocity-report", "automated"],
    }
    headers = {
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN', '')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "velocity-report-generator",
    }
    req = request.Request(
        f"{API}/repos/{org}/{repo}/issues",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("number")
    except error.HTTPError as exc:
        print(f"Warning: Could not create issue: {exc}")
        return None


def main():
    org = os.environ.get("ORG", "BaseAdresseNationale").strip()
    project_number = int(os.environ.get("PROJECT_NUMBER", "4").strip())
    sprint_name = os.environ.get("SPRINT_NAME", "").strip()
    history_path = Path(os.environ.get("HISTORY_PATH", "data/sprint_history.json"))
    create_issue = os.environ.get("CREATE_ISSUE", "true").lower() == "true"
    target_repo = os.environ.get("TARGET_REPO", "gestion_projet_ban").strip()

    print(f"Org: {org}, Project: {project_number}")
    
    # Fetch all iterations
    iterations = fetch_sprint_iterations(org, project_number)
    if not iterations:
        raise RuntimeError("No Sprint Ban iterations found in project")
    
    print(f"Found {len(iterations)} Sprint Ban iterations")

    # Select iteration
    if sprint_name:
        matching = [it for it in iterations if sprint_name.lower() in it["title"].lower()]
        if not matching:
            raise RuntimeError(f"No iteration found matching '{sprint_name}'")
        iteration = matching[0]
    else:
        # Get the most recent iteration
        iteration = sorted(iterations, key=lambda x: x.get("start_date") or "", reverse=True)[0]

    sprint_title = iteration["title"]
    iteration_id = iteration["id"]
    print(f"Processing sprint: {sprint_title} (ID: {iteration_id})")

    # Fetch ALL items first
    all_items = fetch_all_project_items(org, project_number)
    print(f"Fetched {len(all_items)} total items from project")
    
    # Filter by iteration in Python
    items = filter_items_by_iteration(all_items, iteration_id)
    print(f"Found {len(items)} items in sprint {sprint_title}")

    velocity = 0
    closed_issues = []

    for item in items:
        content = item.get("content")
        if not content or content.get("__typename") != "Issue":
            continue
        if not content.get("closed"):
            continue
        
        labels = extract_labels(content)
        points = compute_points(labels)
        
        if points <= 0:
            continue
        
        velocity += points
        closed_issues.append({
            "number": content["number"],
            "title": content["title"],
            "points": points,
        })

    print(f"Velocity: {velocity} points from {len(closed_issues)} closed tickets with points")

    # Update history
    history = load_history(history_path)
    record = {
        "sprint": sprint_title,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "points_completed": velocity,
        "tickets_completed": len(closed_issues),
    }

    # Replace if exists, otherwise append
    replace_idx = next((i for i, entry in enumerate(history) if entry.get("sprint") == sprint_title), None)
    if replace_idx is not None:
        history[replace_idx] = record
    else:
        history.append(record)

    # Calculate moving average for all entries
    for entry in history:
        entry["moving_average_3"] = moving_average(history, window=3)

    # Sort by date
    history = sorted(history, key=lambda x: x.get("date", ""))
    
    # Save history
    save_history(history_path, history)
    print(f"History saved to {history_path}")

    moving_avg = moving_average(history, window=3)
    print(f"Moving average (3 sprints): {moving_avg}")

    # Create report issue if requested
    issue_number = None
    if create_issue:
        issue_number = create_report_issue(org, target_repo, sprint_title, velocity, len(closed_issues), moving_avg, history)
        if issue_number:
            print(f"Issue report created: #{issue_number}")

    # Write GitHub Actions summary
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## ✅ Vélocité calculée : {sprint_title}\n\n")
            fh.write(f"- **Points complétés :** {velocity}\n")
            fh.write(f"- **Tickets fermés :** {len(closed_issues)}\n")
            fh.write(f"- **Moyenne mobile (3 sprints) :** {moving_avg}\n")
            if issue_number:
                fh.write(f"- **Rapport :** [#{issue_number}](../../issues/{issue_number})\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
