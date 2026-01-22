import os
import requests
from dotenv import load_dotenv
from typing import Final

load_dotenv(override=False)

TOKEN = os.getenv("GITHUB_TOKEN")
REPO: Final[str] = os.getenv("REPO")  # type: ignore


if not TOKEN:
    raise RuntimeError("GITHUB_TOKEN is missing in .env")
if not REPO or "/" not in REPO:
    raise RuntimeError("REPO is missing or invalid in .env (format: owner/repo)")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def get_open_prs():
    """
    열린 PR 목록 조회
    GET /repos/{owner}/{repo}/pulls?state=open
    """
    url = f"https://api.github.com/repos/{REPO}/pulls"
    r = requests.get(url, headers=HEADERS, params={"state": "open"}, timeout=30)
    r.raise_for_status()
    return r.json()


def get_pr_files(pr_number: int):
    """
    PR에서 변경된 파일 목록 조회
    GET /repos/{owner}/{repo}/pulls/{pull_number}/files
    - 페이지네이션 필요할 수 있음 (기본 30개)
    """
    files = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/repos/{REPO}/pulls/{pr_number}/files"
        r = requests.get(
            url,
            headers=HEADERS,
            params={"page": page, "per_page": per_page},
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json()
        files.extend(batch)

        if len(batch) < per_page:
            break
        page += 1

    return files

def post_issue_comment(pr_number: int, body: str):
    """
    PR에 Issue comment로 코멘트 달기
    """
    url = f"https://api.github.com/repos/{REPO}/issues/{pr_number}/comments"
    r = requests.post(url, headers=HEADERS, json={"body": body}, timeout=30)
    r.raise_for_status()
    return r.json()

def get_pr(pr_number: int):
    """
    PR 상세 조회 (head sha 얻기 위해)
    GET /repos/{owner}/{repo}/pulls/{pull_number}
    """
    url = f"https://api.github.com/repos/{REPO}/pulls/{pr_number}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def list_issue_comments(pr_number: int, per_page: int = 100):
    """
    PR(=issue)의 코멘트 목록 조회
    GET /repos/{owner}/{repo}/issues/{issue_number}/comments
    """
    url = f"https://api.github.com/repos/{REPO}/issues/{pr_number}/comments"
    r = requests.get(url, headers=HEADERS, params={"per_page": per_page}, timeout=30)
    r.raise_for_status()
    return r.json()


def update_issue_comment(comment_id: int, body: str):
    """
    코멘트 수정
    PATCH /repos/{owner}/{repo}/issues/comments/{comment_id}
    """
    url = f"https://api.github.com/repos/{REPO}/issues/comments/{comment_id}"
    r = requests.patch(url, headers=HEADERS, json={"body": body}, timeout=30)
    r.raise_for_status()
    return r.json()
