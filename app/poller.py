from github_client import get_open_prs, get_pr, post_issue_comment, list_issue_comments, update_issue_comment
from reviewer import run_rules_on_pr, format_comment
from reviewer import AI_COMMENT_MARKER
from db import init_db, already_processed, mark_processed, get_saved_comment_id, save_comment_id
from github_client import REPO  # github_client.py에 REPO가 전역 변수로 있어야 함


def find_ai_comment_id_by_marker(pr_number: int):
    comments = list_issue_comments(pr_number)
    for c in comments:
        body = c.get("body") or ""
        if AI_COMMENT_MARKER in body:
            return int(c["id"])
    return None


def upsert_ai_comment(pr_number: int, body: str) -> int:
    """
    (1) DB에 저장된 comment_id가 있으면 먼저 update 시도
    (2) 없거나 실패하면 marker로 검색 후 update
    (3) 그래도 없으면 새로 생성
    """
    # 1) DB 기반 시도
    saved_id = get_saved_comment_id(REPO, pr_number)
    if saved_id:
        try:
            updated = update_issue_comment(saved_id, body)
            return int(updated["id"])
        except Exception:
            # 코멘트가 삭제됐거나 권한 문제 등 -> fallback
            pass

    # 2) marker 검색 기반
    found_id = find_ai_comment_id_by_marker(pr_number)
    if found_id:
        updated = update_issue_comment(found_id, body)
        return int(updated["id"])

    # 3) 새로 생성
    created = post_issue_comment(pr_number, body)
    return int(created["id"])


def main():
    init_db()

    prs = get_open_prs()
    if not prs:
        print("열린 PR 없음")
        return

    print(f"열린 PR: {len(prs)}개")

    for pr in prs:
        pr_number = int(pr["number"])
        title = pr["title"]

        pr_detail = get_pr(pr_number)
        head_sha = pr_detail["head"]["sha"]

        print(f"\n=== PR #{pr_number}: {title} ===")
        print(f"- head sha: {head_sha}")

        # 1) 동일 커밋 중복 처리 방지
        if already_processed(REPO, pr_number, head_sha):
            print("- skip: 이미 처리된 커밋 SHA")
            continue

        # 2) 리뷰 실행
        findings = run_rules_on_pr(pr_number)
        body = format_comment(pr_number, findings)

        # 3) 코멘트 1개 유지(upsert)
        comment_id = upsert_ai_comment(pr_number, body)
        save_comment_id(REPO, pr_number, comment_id)

        # 4) 처리 완료 기록
        mark_processed(REPO, pr_number, head_sha)

        print(f"- 코멘트 upsert 완료 (comment_id={comment_id}, findings={len(findings)})")


if __name__ == "__main__":
    main()
