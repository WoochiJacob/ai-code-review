# app/poller.py
import json
import os
from typing import Any, Dict, List

from github_client import (
    get_pr,
    get_pr_files,
    post_issue_comment,
    list_issue_comments,
    update_issue_comment,
    REPO,
)
from reviewer import run_rules_on_pr, format_comment, AI_COMMENT_MARKER
from db import (
    init_db,
    already_processed,
    mark_processed,
    get_saved_comment_id,
    save_comment_id,
)

EXCLUDE_SUFFIXES = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml")
EXCLUDE_PREFIXES = ("dist/", "build/", ".next/", "out/")


def should_exclude(filename: str) -> bool:
    if filename.startswith(EXCLUDE_PREFIXES):
        return True
    if filename.endswith(EXCLUDE_SUFFIXES):
        return True
    return False


def find_ai_comment_id_by_marker(pr_number: int):
    comments = list_issue_comments(pr_number)
    for c in comments:
        body = c.get("body") or ""
        if AI_COMMENT_MARKER in body:
            return int(c["id"])
    return None


def upsert_ai_comment(pr_number: int, body: str) -> int:
    saved_id = get_saved_comment_id(REPO, pr_number)
    if saved_id:
        try:
            updated = update_issue_comment(saved_id, body)
            return int(updated["id"])
        except Exception:
            pass

    found_id = find_ai_comment_id_by_marker(pr_number)
    if found_id:
        updated = update_issue_comment(found_id, body)
        return int(updated["id"])

    created = post_issue_comment(pr_number, body)
    return int(created["id"])


def build_phase1_payload(pr_number: int, pr_detail: Dict[str, Any], files: List[Dict[str, Any]]) -> Dict[str, Any]:
    filtered: List[Dict[str, Any]] = []
    excluded = 0
    patch_null = 0

    for f in files:
        filename = f.get("filename") or ""
        if not filename:
            continue

        if should_exclude(filename):
            excluded += 1
            continue

        patch = f.get("patch")
        if patch is None:
            patch_null += 1
            continue

        filtered.append(
            {
                "filename": filename,
                "status": f.get("status"),
                "additions": f.get("additions"),
                "deletions": f.get("deletions"),
                "changes": f.get("changes"),
                "patch": patch,
            }
        )

    payload = {
        "repo": REPO,
        "pr_number": pr_number,
        "pr": {
            "title": pr_detail.get("title"),
            "user": (pr_detail.get("user") or {}).get("login"),
            "base": (pr_detail.get("base") or {}).get("ref"),
            "head": (pr_detail.get("head") or {}).get("ref"),
            "head_sha": (pr_detail.get("head") or {}).get("sha"),
            "html_url": pr_detail.get("html_url"),
        },
        "stats": {
            "total_files": len(files),
            "excluded_files": excluded,
            "patch_null_files": patch_null,
            "review_files": len(filtered),
        },
        "files": filtered,
    }
    return payload


def main():
    init_db()

    pr_number_raw = os.getenv("PR_NUMBER")
    if not pr_number_raw:
        raise RuntimeError("PR_NUMBER is missing (GitHub Actions env)")

    pr_number = int(pr_number_raw)

    pr_detail = get_pr(pr_number)
    title = pr_detail.get("title")
    head_sha = pr_detail["head"]["sha"]

    print("=== Phase 1: PR Diff Collection ===")
    print(f"- repo: {REPO}")
    print(f"- pr: #{pr_number}")
    print(f"- title: {title}")
    print(f"- head sha: {head_sha}")

    # 중복 처리 방지(커밋 SHA 기준)
    if already_processed(REPO, pr_number, head_sha):
        print("- skip: already processed this head sha")
        return

    # Phase 1 핵심: 파일/patch 수집
    files = get_pr_files(pr_number)
    payload = build_phase1_payload(pr_number, pr_detail, files)

    print(
        "- files:",
        f"total={payload['stats']['total_files']},",
        f"excluded={payload['stats']['excluded_files']},",
        f"patch_null={payload['stats']['patch_null_files']},",
        f"review={payload['stats']['review_files']}",
    )

    out_path = "pr_patches.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"- saved: {out_path}")

    # (임시) 기존 로직 유지: rules 기반 리뷰 실행 + 코멘트 업서트
    findings = run_rules_on_pr(pr_number)
    body = format_comment(pr_number, findings)

    comment_id = upsert_ai_comment(pr_number, body)
    save_comment_id(REPO, pr_number, comment_id)

    mark_processed(REPO, pr_number, head_sha)

    print(f"- comment upsert done (comment_id={comment_id}, findings={len(findings)})")


if __name__ == "__main__":
    main()
