import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Finding:
    rule_id: str
    severity: str   # "BLOCK" | "WARN" | "INFO"
    file: str
    message: str
    evidence: str


# PoC용: 명백하고 오탐이 적은 대표 패턴만 우선 적용
# (조직별 토큰 포맷이 있으면 여기에 추가하면 됩니다)
SECRET_PATTERNS = [
    ("github_pat", r"github_pat_[A-Za-z0-9_]{20,}"),
    ("github_classic", r"ghp_[A-Za-z0-9]{36}"),
    ("google_api_key", r"AIza[0-9A-Za-z\-_]{35}"),
    ("slack_token", r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    ("aws_access_key", r"AKIA[0-9A-Z]{16}"),
    # JWT는 오탐 가능성이 있어 PoC 초반엔 보수적으로(필요 시 추가)
    # ("jwt", r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
]


def scan_patch_for_secrets(filename: str, patch: Optional[str]) -> List[Finding]:
    """
    PR file patch(변경 diff 일부)에서 토큰/키 하드코딩 패턴 탐지
    - patch가 None이면 검사 불가 -> finding 없음(추후 파일 내용 조회로 보완 가능)
    """
    if not patch:
        return []

    findings: List[Finding] = []

    # diff에서 추가된 라인("+")만 검사하면 오탐이 줄어듭니다.
    added_lines = []
    for line in patch.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:])  # "+" 제거

    text = "\n".join(added_lines)

    for name, pattern in SECRET_PATTERNS:
        m = re.search(pattern, text)
        if m:
            evidence = m.group(0)
            findings.append(
                Finding(
                    rule_id=f"SECRET_{name.upper()}",
                    severity="BLOCK",
                    file=filename,
                    message="비밀키/토큰으로 의심되는 문자열이 코드에 추가되었습니다. 하드코딩은 금지이며 안전한 저장소(.env/Secret Manager 등)로 이동해야 합니다.",
                    evidence=evidence[:80] + ("..." if len(evidence) > 80 else ""),
                )
            )

    return findings
