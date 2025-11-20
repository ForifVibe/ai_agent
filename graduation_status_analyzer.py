"""
CSV \uae30\ubc18 \uc878\uc5c5\uc0ac\uc815 \uc694\uc57d\uae30.\n\uc774\ubbf8\uc9c0(\uc0ac\uc9c4) \uc778\uc2dd \uc5c6\uc774 CSV \ub370\uc774\ud130\ub9cc \uc77d\uc5b4 \ud604\uc7ac \ucda9\uc871/\ubbf8\ucda9\uc871 \uc0c1\ud0dc\ub97c \uacc4\uc0b0\ud569\ub2c8\ub2e4.\n"""

import csv
from dataclasses import dataclass, field
from typing import List, Optional

# CSV \uceec\ub7fc\uba85
COL_NAME = "\uc774\uc218\uba85"        # \uc774\uc218\uba85
COL_REQUIRED = "\ubc30\ub2f9"    # \ubc30\ub2f9
COL_COMPLETED = "\ucde8\ub4dd"   # \ucde8\ub4dd
COL_STATUS = "\uc774\uc218"      # \uc774\uc218


@dataclass
class RequirementStatus:
    category: str
    required: Optional[int] = None
    completed: Optional[int] = None
    satisfied: bool = False
    details: List[str] = field(default_factory=list)


@dataclass
class TotalCredits:
    required: Optional[int] = None
    completed: Optional[int] = None
    remaining: Optional[int] = None


@dataclass
class GraduationAnalysis:
    requirements: List[RequirementStatus]
    total_credits: TotalCredits
    unsatisfied: List[str]


class GraduationStatusAnalyzer:
    """CSV\ub9cc \uc0ac\uc6a9\ud574 \uc878\uc5c5\uc0ac\uc815 \uc0c1\ud0dc\ub97c \ubd84\uc11d\ud569\ub2c8\ub2e4."""

    def analyze_csv(self, csv_path: str) -> GraduationAnalysis:
        rows = self._read_csv_rows(csv_path)

        requirements: List[RequirementStatus] = []
        unsatisfied: List[str] = []
        total = self._extract_total_credits(rows)

        for row in rows:
            name = row.get(COL_NAME) or row.get("name") or ""
            required = self._to_int(row.get(COL_REQUIRED))
            completed = self._to_int(row.get(COL_COMPLETED))
            satisfied = self._is_satisfied(row.get(COL_STATUS))

            req = RequirementStatus(
                category=name,
                required=required,
                completed=completed,
                satisfied=satisfied,
                details=[],
            )
            requirements.append(req)
            if not satisfied:
                unsatisfied.append(name)

        return GraduationAnalysis(
            requirements=requirements,
            total_credits=total,
            unsatisfied=unsatisfied,
        )

    def _extract_total_credits(self, rows: List[dict]) -> TotalCredits:
        # "\uc878\uc5c5\ud559\uc810" \ud589\uc744 \uc6b0\uc120\uc801\uc73c\ub85c \ucc3e\uace0, \uc5c6\uc73c\uba74 \ucc98 \ud589\uc758 \uc22b\uc790\ub97c \uc0ac\uc6a9
        target = None
        for row in rows:
            name = (row.get(COL_NAME) or "").strip()
            if name == "\uc878\uc5c5\ud559\uc810":
                target = row
                break
        if target is None and rows:
            target = rows[0]

        required = self._to_int(target.get(COL_REQUIRED) if target else None)
        completed = self._to_int(target.get(COL_COMPLETED) if target else None)
        remaining = None
        if required is not None and completed is not None:
            remaining = max(required - completed, 0)

        return TotalCredits(required=required, completed=completed, remaining=remaining)

    def _is_satisfied(self, value: Optional[str]) -> bool:
        if value is None:
            return False
        return str(value).strip().lower() in {"y", "yes", "true", "1"}

    def _to_int(self, value: Optional[str]) -> Optional[int]:
        try:
            return int(float(str(value).replace(",", "").strip()))
        except (TypeError, ValueError):
            return None

    def _read_csv_rows(self, path: str) -> List[dict]:
        # utf-8 \uc6b0\uc120, \uc2e4\ud328 \uc2dc cp949 \uc2dc\ub3c4
        for encoding in ("utf-8", "utf-8-sig", "cp949"):
            try:
                with open(path, "r", encoding=encoding) as fp:
                    reader = csv.DictReader(fp)
                    return [row for row in reader]
            except UnicodeDecodeError:
                continue
        raise UnicodeDecodeError("codec", b"", 0, 1, "CSV \ub514\ucf54\ub529 \uc2e4\ud328")


__all__ = [
    "GraduationStatusAnalyzer",
    "GraduationAnalysis",
    "RequirementStatus",
    "TotalCredits",
]
