# GradPath AI Agent 구현 계획

프로젝트 문서(`forif_project/project_root/기획.md`)를 바탕으로 AI Agent 서비스를 어떻게 구현할지 정리했습니다. 현재 `ai_agent` 폴더의 CSV 기반 분석 스크립트를 LangChain 기반 마이크로서비스로 확장하는 것을 목표로 합니다.

## 1. 목표/범위
- GPT-4o/4o-mini + GPT-4o-vision을 사용해 졸업요건 이미지(OCR)와 텍스트 질의 모두 처리.
- 코스 데이터 RAG 검색, 학점 계산, 학기별 수강계획 생성 도구 제공.
- FastAPI 기반으로 백엔드에서 호출 가능한 API 제공, Supabase/Redis와 연동.

## 2. 서비스 인터랙션 (요약)
- Frontend → Nginx(API Gateway) → Backend(FastAPI) → AI Agent Service → Supabase/파일저장소.
- Backend는 세션 토큰/사용자 UID를 포함한 요청을 AI Agent로 프록시하고, Agent는 필요 시 Supabase에서 대화/분석 결과를 조회/갱신.

## 3. 디렉터리/모듈 구조 제안 (`ai_agent`)
- `app/main.py`: FastAPI 엔트리포인트, 헬스체크 및 라우터 등록.
- `app/config.py`: 환경변수(OPENAI_API_KEY, SUPABASE_URL, REDIS_URL 등) 로딩.
- `app/prompts/
    - system.py`: 시스템 프롬프트, few-shot 예시, 출력 스키마 정의.
    - templates.py`: 역할별 템플릿(챗, 계획 설명, 질의응답 등).
- `app/tools/
    - course_rag.py`: `courses.csv` 적재 → 임베딩 → FAISS 벡터스토어 생성/캐시.
    - analyzers.py`: GPT-4o-vision 기반 스크린샷 해석, JSON 스키마 검증.
    - credits.py`: 졸업요건/미충족 요건 계산 유틸(현재 `GraduationStatusAnalyzer` 로직 이관/확장).
- `app/agent/
    - factory.py`: LangChain Agent 생성(LLM, Tools, Memory 결합).
    - memory.py`: ConversationBufferMemory + Redis 백업.
    - workflow.py`: 상태 기반 플로우(초기→정보수집→분석→계획→QA) 구현.
- `app/api/
    - routes_chat.py`: `/api/chat/message` (텍스트), `/api/chat/history`.
    - routes_upload.py`: `/api/upload/image` → OCR 분석 비동기 큐 트리거.
    - routes_analyze.py`: `/api/analyze/status`, `/api/recommendation`.
- `app/models.py`: Pydantic 요청/응답 스키마(기획.md의 `GraduationAnalysis`, `ChatResponse` 반영).
- `app/tasks.py`: Celery/RQ 작업(이미지 OCR, RAG 프리로딩) 정의.
- `app/store/`: Supabase, Redis, S3(S3 key만 관리) 클라이언트 래퍼.

## 4. 핵심 기능 설계
1) **이미지(OCR) 분석**
- 입력: Base64 PNG/JPEG, 사용자 UID, 세션 ID.
- 처리: GPT-4o-vision에 시스템 프롬프트 포함(요구사항 추출, 총/이수/미이수 학점, 미충족 리스트).
- 출력: `{"requirements": [...], "total_credits": {...}, "unsatisfied": [...]}` 스키마 강제 → 실패 시 재시도/에러 태그.

2) **졸업요건 계산**
- 기존 `GraduationStatusAnalyzer`를 통합: CSV/DB 레코드 모두 지원하도록 수정.
- 필요 필드: `category`, `required`, `completed`, `satisfied`, `details`.
- `TotalCredits`는 `remaining = max(required-completed, 0)` 계산 후, 미이수 항목 묶음으로 반환.

3) **RAG 코스 검색**
- 데이터: `courses.csv`(기획.md 예시) → pandas 로드 → 자연어 묘사 텍스트 구성 → FAISS 인덱스.
- 툴: `course_search(query, filters)`로 LangChain Tool 등록, `top_k=10` 기본, 필터(학년/학기/이수구분) 적용.

4) **수강계획 생성**
- 입력: 사용자 메타(학번, 학년, 전공/부전공, 목표 졸업시점), `unsatisfied` 리스트, 총 학기 수.
- 알고리즘: 우선순위(필수 → 전공핵심 → 전공선택 → 교양)로 배분, 학기당 최대 21학점, 학기 균형화.
- 출력 예: `{semester: '2025-1', courses: [...], totalCredits: 18}` 형태 배열.

5) **대화 플로우/메모리**
- 상태: `initial → collecting_info → analyzing → planning → qa`.
- 메모리: LangChain `ConversationBufferMemory` + Redis 스냅샷(`session:{id}` 키).
- 각 상태별 응답 템플릿과 guardrails(JSON 스키마 검증) 적용.

## 5. API 스펙 초안 (FastAPI)
- `POST /api/session/init`: uid, session_token 반환(백엔드와 동일 스펙 유지).
- `POST /api/upload/image`: {image: base64, session_id} → {image_id, task_id, status}.
- `POST /api/analyze/status`: {image_id or base64, user_meta} → `GraduationAnalysis`.
- `POST /api/recommendation`: {analysis, target_graduation} → 학기별 추천 플랜.
- `POST /api/chat/message`: {session_id, message, attachments?} → `ChatResponse`(message, suggestions, attachments).
- 내부용: `POST /internal/cache/rag/rebuild`: 코스 CSV 변경 시 인덱스 재빌드.

## 6. 프롬프트 전략
- 시스템 프롬프트: 기획.md의 목표/제약(학기당 21학점, 전공/교양 구분, 친절+정확 톤) 반영.
- Few-shot: `FEW_SHOT_EXAMPLES`를 LangChain의 `FewShotPromptTemplate`로 관리, 분석/계획/QA 용으로 분리.
- 출력 포맷: JSON 스키마 우선, 사용자 노출 메시지는 Markdown 블록으로 변환.

## 7. 데이터/스토리지
- Supabase: users, chats, graduation_status, courses 테이블 사용(기획.md 스키마 준수).
- Redis: 세션 메모리/큐 상태 캐싱.
- S3: 스크린샷 저장, key만 DB에 저장. OCR 완료 시 상태 플래그 업데이트.

## 8. 배포/운영
- Docker 이미지로 패키징, docker-compose에서 `ai_agent` 서비스 추가(backend와 동일 네트워크).
- 헬스체크: `/healthz`에서 Redis/Supabase/LLM Key 존재 여부 확인.
- 로깅/모니터링: JSON 로그 + Sentry 훅 + 프롬프트/응답 샘플링(PII 마스킹 필수).

## 9. 우선 구현 순서
1. `app` 스켈레톤 + Pydantic 스키마 + 환경설정 작성.
2. `GraduationStatusAnalyzer` 리팩터링 → FastAPI 엔드포인트 `POST /api/analyze/status` 연결.
3. 코스 CSV 로딩/FAISS 인덱스 + LangChain Tool `course_search` 구현.
4. Vision 기반 `analyze_screenshot` Tool 구현 + Celery 작업자.
5. Agent Factory(LLM + Tools + Memory) 및 `/api/chat/message` 라우트 완성.
6. 통합 테스트: 텍스트만 → OCR+RAG 조합 순으로 확장.
7. Dockerfile/compose 서비스 추가 및 기본 모니터링 설정.
