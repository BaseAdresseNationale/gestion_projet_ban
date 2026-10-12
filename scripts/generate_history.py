#!/usr/bin/env python3
"""Generate velocity history for Sprint Ban 62 to 79 from Project v2"""
import json
import os
import re
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


def fetch_all_iterations(org: str, project_number: int):
    """Fetch all Sprint Ban iterations"""
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
    """Fetch ALL project items - pagination support"""
    all_items = []
    cursor = None
    
    while True:
        query = """
        query($org: String!, $projectNumber: Int!, $cursor: String) {
          organization(login: $org) {
            projectV2(number: $projectNumber) {
              items(first: 100, after: $cursor) {
                pageInfo {
                  hasNextPage
                  endCursor
                }
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
        data = gh_graphql(query, {"org": org, "projectNumber": project_number, "cursor": cursor})
        items = data["organization"]["projectV2"]["items"]["nodes"]
        all_items.extend(items)
        
        page_info = data["organization"]["projectV2"]["items"]["pageInfo"]
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
    
    return all_items


def extract_labels(content):
    labels = []
    if content and content.get("labels"):
        for label in content["labels"].get("nodes", []):
            labels.append(label["name"].lower())
    return labels


def compute_points(labels):
    total = 0
    for label in labels:
        if label in POINTS_MAP:
            total += POINTS_MAP[label]
    return total


def filter_items_by_iteration(items, iteration_id: str):
    """Filter items by iteration ID"""
    filtered = []
    for item in items:
        for field_value in item.get("fieldValues", {}).get("nodes", []):
            if field_value.get("iterationId") == iteration_id:
                filtered.append(item)
                break
    return filtered


def extract_sprint_number(title: str):
    """Extract the sprint number from a title like 'Sprint Ban 62', 'Sprint Ban 62 (2026)', etc."""
    match = re.search(r"Sprint Ban\s*(\d+)", title, re.IGNORECASE)
    print(repr(title))
    if not match:
        return None
    return int(match.group(1))


def calculate_velocity_for_iteration(items):
    """Calculate velocity for a specific iteration"""
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
    
    return velocity, len(closed_issues)


def main():
    org = "BaseAdresseNationale"
    project_number = 4
    
    print("Fetching all iterations...")
    iterations = fetch_all_iterations(org, project_number)
    print(f"Found {len(iterations)} total iterations")
    
    print("\nAll iteration titles found:")
    for it in iterations:
        print(f"  - {it['title']}")
    
    sprint_numbers = []
    for it in iterations:
        title = it["title"]
        sprint_num = extract_sprint_number(title)
        if sprint_num is not None:
            if 62 <= sprint_num <= 79:
                sprint_numbers.append((sprint_num, it))
                print(f"  ✓ {title} -> sprint {sprint_num} matches filter")
            else:
                print(f"  - {title} -> sprint {sprint_num} outside filter")
        else:
            print(f"  ✗ {title} -> no sprint number matched")
    
    if not sprint_numbers:
        print("\n⚠️ No sprint found between Sprint Ban 62 and Sprint Ban 79")
        print("Check the exact iteration titles displayed above.")
        return
    
    sprint_numbers.sort(key=lambda x: x[0])
    filtered_iterations = [it for _, it in sprint_numbers]
    
    print(f"\n✅ Processing {len(filtered_iterations)} sprints: {[s[0] for s in sprint_numbers]}")
    print(f"\nFetching all project items...")
    all_items = fetch_all_project_items(org, project_number)
    print(f"Fetched {len(all_items)} total items")
    
    history = []
    for sprint_num, iteration in sprint_numbers:
        print(f"\nProcessing sprint {sprint_num} ({iteration['title']})...")
        items = filter_items_by_iteration(all_items, iteration["id"])
        print(f"  Found {len(items)} items in this sprint")
        
        velocity, tickets_count = calculate_velocity_for_iteration(items)
        record = {
            "sprint": iteration["title"],
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "points_completed": velocity,
            "tickets_completed": tickets_count,
        }
        history.append(record)
        print(f"  Velocity: {velocity} points ({tickets_count} tickets)")
    
    for i, entry in enumerate(history):
        if i < 2:
            entry["moving_average_3"] = round(sum(h["points_completed"] for h in history[:i+1]) / (i+1), 2)
        else:
            entry["moving_average_3"] = round(sum(h["points_completed"] for h in history[i-2:i+1]) / 3, 2)
    
    history_path = Path("data/sprint_history.json")
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    
    print(f"\n✅ History saved to {history_path}")
    if history:
        velocities = [h['points_completed'] for h in history]
        print(f"- Min velocity: {min(velocities)} points")
        print(f"- Max velocity: {max(velocities)} points")
        print(f"- Average velocity: {round(sum(velocities) / len(velocities), 2)} points")
        print(f"- Latest moving average (3): {history[-1]['moving_average_3']} points")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        import traceback
        traceback.print_exc()
        exit(1)
