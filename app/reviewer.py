from typing import List, Dict, Any
from github_client import get_pr_files
from rules_secrets import scan_patch_for_secrets, Finding

AI_COMMENT_MARKER = "<!-- AI_CODE_REVIEW_POC -->"


def run_rules_on_pr(pr_number: int) -> List[Finding]:
    """
    PR 변경 파일들을 가져와 룰을 적용하고 Finding 리스트를 반환
    """
    files: List[Dict[str, Any]] = get_pr_files(pr_number)
    all_findings: List[Finding] = []

    for f in files:
        filename = f.get("filename", "")
        patch = f.get("patch")  # None 가능
        all_findings.extend(scan_patch_for_secrets(filename, patch))

    return all_findings


def format_comment(pr_number: int, findings: List[Finding]) -> str:
    """
    PR 코멘트 마크다운 생성
    - 정책: BLOCK은 보안/라이선스만
    """
    blocks = [x for x in findings if x.severity == "BLOCK"]
    
    header = AI_COMMENT_MARKER + "\n## AI Code Review (PoC)\n"
    header += f"- PR: #{pr_number}\n"
    header += "- Mode: Polling\n\n"

    if not blocks:
        body = (
            header
            + "### [INFO] 차단 항목 없음\n"
            + "- 현재 적용된 보안/라이선스 차단 룰 기준으로, 명백한 위반은 발견되지 않았습니다.\n\n"
            + "> 참고: PoC 초기 단계로 ‘토큰/키 하드코딩’ 등 일부 룰만 적용 중입니다."
        )
        return body

    lines = [header, "### [BLOCK] 보안 차단 항목 발견\n"]
    for i, b in enumerate(blocks, start=1):
        lines.append(f"{i}. **{b.rule_id}** in `{b.file}`")
        lines.append(f"   - 사유: {b.message}")
        lines.append(f"   - 증거(일부): `{b.evidence}`")
        lines.append("   - 조치: 해당 값은 코드에서 제거하고 안전한 Secret 저장 방식으로 대체하세요.\n")

    lines.append("---")
    lines.append("#### 처리 가이드")
    lines.append("- 본 항목은 정책상 **차단(Blocking) 후보**입니다. PR 머지 전 반드시 제거/대체가 필요합니다.")
    lines.append("- 오탐이라고 판단되면 근거와 함께 코멘트로 남겨주세요(룰 개선에 반영).")

    return "\n".join(lines)
