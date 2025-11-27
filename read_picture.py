"""
sample.png를 pytesseract로 OCR 처리해 mystatus.csv를 생성하는 유틸리티.
- 입력: ai_agent/sample.png (기본), 출력: ai_agent/mystatus.csv (기본)
- 의존성: pillow, pytesseract, Tesseract OCR 실행 파일

사용 예시)
  python read_picture.py               # 기본 입력/출력 경로
  python read_picture.py input.png out.csv
"""

from __future__ import annotations

import csv
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

try:
    from PIL import Image
except ImportError as exc:  # pillow가 없을 때 명확한 메시지 제공
        raise SystemExit(
            "Pillow가 필요합니다. `pip install pillow`로 설치 후 다시 실행하세요."
        ) from exc

try:
    import pytesseract
    from pytesseract import Output
except ImportError as exc:  # pytesseract가 없을 때 명확한 메시지 제공
    raise SystemExit(
        "pytesseract가 필요합니다. `pip install pytesseract`로 설치하고 "
        "Tesseract OCR 실행 파일이 PATH에 있는지 확인하세요."
    ) from exc


def _configure_tesseract_cmd() -> None:
    """Tesseract 실행 파일이 PATH에 없을 때 기본 설치 경로를 자동 설정."""
    if os.environ.get("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
        return

    if shutil.which("tesseract"):
        return  # 이미 PATH에 있음

    candidates = [
        Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
        Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    ]
    for path in candidates:
        if path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(path)
            return

    # 찾지 못하면 이후 pytesseract가 기본 에러를 던지게 둠

# 기본 헤더: analyzer가 기대하는 열(이수명/배당/취득/이수)을 포함해 확장 컬럼도 함께 기록
DEFAULT_HEADERS: List[str] = ["분류", "이수명", "배당", "취득", "이수", "학점", "비고"]
HEADER_ALIASES = {
    "이수명": ["이수명", "과목", "항목", "교과목"],
    "배당": ["배당", "필요", "요구", "필수"],
    "취득": ["취득", "이수학점", "이수학"],
    "이수": ["이수", "완료", "여부"],
}

MIN_CONFIDENCE = 40.0  # OCR 신뢰도 필터
COLUMN_TOLERANCE = 28  # 좌표 기반 컬럼 클러스터링 허용 오차(px)
OCR_CONFIG = "--psm 6"  # 표/단락 형태 텍스트에 적합한 PSM


def normalize_header(text: str) -> str:
    """OCR로 읽힌 헤더를 analyzer가 기대하는 이름으로 정규화."""
    cleaned = text.strip()
    lower = cleaned.lower()
    for canonical, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if alias in cleaned or alias in lower:
                return canonical
    return cleaned


def cluster_positions(xs: Iterable[int], tolerance: int = COLUMN_TOLERANCE) -> List[int]:
    """x 좌표를 이용해 컬럼 중심값을 추정."""
    centers: List[int] = []
    for x in sorted(xs):
        if not centers or x - centers[-1] > tolerance:
            centers.append(int(x))
        else:
            centers[-1] = int((centers[-1] + x) / 2)
    return centers


def read_ocr_records(image_path: Path) -> List[Dict[str, int | float | str]]:
    """이미지를 OCR하여 bounding box + 텍스트 기록을 반환."""
    _configure_tesseract_cmd()
    img = Image.open(image_path)
    data = pytesseract.image_to_data(
        img,
        lang="kor+eng",
        config=OCR_CONFIG,
        output_type=Output.DICT,
    )

    records: List[Dict[str, int | float | str]] = []
    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        try:
            conf = float(data["conf"][i])
        except ValueError:
            conf = -1.0

        if not text or conf < MIN_CONFIDENCE:
            continue

        records.append(
            {
                "page": int(data["page_num"][i]),
                "block": int(data["block_num"][i]),
                "par": int(data["par_num"][i]),
                "line": int(data["line_num"][i]),
                "left": int(data["left"][i]),
                "top": int(data["top"][i]),
                "text": text,
            }
        )
    return records


def collect_lines(
    records: Sequence[Dict[str, int | float | str]]
) -> List[Tuple[Tuple[int, int, int, int], int, List[Dict[str, int | float | str]]]]:
    """라인 단위로 텍스트를 그룹핑."""
    grouped: Dict[Tuple[int, int, int, int], List[Dict[str, int | float | str]]] = {}
    for rec in records:
        key = (rec["page"], rec["block"], rec["par"], rec["line"])
        grouped.setdefault(key, []).append(rec)

    lines: List[Tuple[Tuple[int, int, int, int], int, List[Dict[str, int | float | str]]]] = []
    for key, words in grouped.items():
        sorted_words = sorted(words, key=lambda w: int(w["left"]))
        top = min(int(w["top"]) for w in sorted_words)
        lines.append((key, top, sorted_words))

    lines.sort(key=lambda item: item[1])
    return lines


def estimate_columns(header_words: Sequence[Dict[str, int | float | str]]) -> List[int]:
    """헤더 라인의 x 좌표를 기반으로 컬럼 중심값을 추정."""
    positions = [int(w["left"]) for w in header_words]
    return cluster_positions(positions)


def words_to_row(
    words: Sequence[Dict[str, int | float | str]],
    column_centers: Sequence[int],
) -> List[str]:
    """라인의 단어들을 가장 가까운 컬럼에 배치해 셀 리스트로 변환."""
    row = ["" for _ in column_centers]
    for word in words:
        left = int(word["left"])
        column_idx = min(range(len(column_centers)), key=lambda i: abs(column_centers[i] - left))
        text = str(word["text"])
        row[column_idx] = f"{row[column_idx]} {text}".strip() if row[column_idx] else text
    return row


def build_headers(candidate_row: Sequence[str], column_count: int) -> List[str]:
    """헤더 후보를 이용해 최종 헤더를 생성하고 부족하면 기본 헤더로 보완."""
    headers: List[str] = []
    for idx in range(column_count):
        candidate = candidate_row[idx].strip() if idx < len(candidate_row) else ""
        normalized = normalize_header(candidate) if candidate else ""
        if normalized:
            headers.append(normalized)
        elif idx < len(DEFAULT_HEADERS):
            headers.append(DEFAULT_HEADERS[idx])
        else:
            headers.append(f"col_{idx + 1}")
    return headers


def write_csv(headers: Sequence[str], rows: Sequence[Sequence[str]], output_path: Path) -> None:
    """CSV를 UTF-8 with BOM으로 기록."""
    with output_path.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.writer(fp)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


def process_image(image_path: Path, output_path: Path) -> Path:
    """이미지를 OCR해 mystatus.csv를 생성."""
    records = read_ocr_records(image_path)
    if not records:
        raise RuntimeError("OCR 결과가 비어 있습니다. 이미지/언어 설정을 확인하세요.")

    lines = collect_lines(records)
    header_candidates = lines[0][2]
    column_centers = estimate_columns(header_candidates)

    # 헤더 OCR이 실패했을 때 전체 좌표로라도 컬럼을 추정
    if not column_centers:
        column_centers = cluster_positions([int(rec["left"]) for rec in records])

    rows: List[List[str]] = []
    for _, _, words in lines:
        rows.append(words_to_row(words, column_centers))

    headers = build_headers(rows[0], len(column_centers))
    data_rows = [row for row in rows[1:] if any(cell.strip() for cell in row)]
    write_csv(headers, data_rows, output_path)
    return output_path


def resolve_paths(args: Sequence[str]) -> Tuple[Path, Path]:
    """CLI 인자로부터 입력/출력 경로를 계산."""
    base_dir = Path(__file__).parent
    image_path = Path(args[0]) if len(args) >= 1 else base_dir / "sample.png"
    output_path = Path(args[1]) if len(args) >= 2 else base_dir / "mystatus.csv"
    return image_path, output_path


def main() -> None:
    image_path, output_path = resolve_paths(sys.argv[1:])
    if not image_path.exists():
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")

    created = process_image(image_path, output_path)
    print(f"mystatus.csv 생성 완료: {created}")


if __name__ == "__main__":
    main()
