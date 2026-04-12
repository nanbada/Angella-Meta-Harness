# SOP: Multi-Modal Ingestion (ingest_ops)
Last updated: 2026-04-12

Angella는 이제 텍스트, 이미지, 클립보드, 트위터(X) 형태의 원시(Raw) 데이터를 쉽게 LLM-Wiki 지식 베이스로 유입할 수 있습니다. `ingest_ops.py` MCP 서버를 통해 수집된 데이터는 `knowledge/sources/raw`에 보관되며 이후 Archivist 에이전트가 LLM 분류 태깅을 거쳐 정식 지식(`knowledge/sources/`)으로 편입합니다.

## 1. 도구 사용 권한
이 도구들은 기본적으로 `.gemini/agents/angella-archivist.md` 에이전트에 마운트되어 있습니다. 사용자가 직접 수집을 명하거나, Archivist가 필요에 따라 자율적으로 호출합니다.

```yaml
mcpServers:
  ingest-ops:
    command: "python"
    args:
      - "mcp-servers/ingest_ops.py"
```

## 2. 도구별 사용 가이드

### 1) 클립보드 수집 (`ingest_clipboard`)
- **설명**: 현재 macOS 클립보드에 복사된 내용을 마크다운 형태로 추출하여 파일로 덤프합니다.
- **주요 용도**: 화면 캡처 텍스트 복사, 긴 에러 로그 클립보드 복사, 특정 코드 스니펫 즉시 저장.
- **예시 프롬프트**: *"현재 클립보드에 있는 노션 메모 복사본을 긁어와줘."*
- **보안 유의점**: 패스워드나 중요 토큰을 복사한 상태에서 자동 수집되지 않도록, 사용자가 명시적으로 지시할 때 1회성으로만 사용하는 구조입니다.

### 2) 트위터/X 아티클 수집 (`ingest_x_article`)
- **설명**: 트위터나 X의 URL을 입력하면, 브리지 API(`vxtwitter`)를 통해 본문 텍스트, 해시태그, 이미지 URL을 포함한 마크다운으로 깔끔하게 디코딩합니다.
- **주요 용도**: 외부 업계 뉴스 브리핑 저장, 연구 서적 링크 스크랩.
- **사용 방법**: 
  - `url`: `https://x.com/username/status/12345` 또는 `https://twitter.com/username/status/12345`
- **예시 프롬프트**: *"다음 트위터 쓰레드를 참고자료로 수집해 줘: https://x.com/..."*

### 3) 이미지 분석 수집 (`ingest_image_vision`)
- **설명**: 로컬 디렉토리에 위치한 이미지 파일의 경로를 기반으로 **Gemini 3.1 Pro Vision**을 호출하여 이미지의 다이어그램이나 텍스트를 상세히 분석한 보고서를 생성합니다.
- **사용 방법**:
  - `image_path`: 로컬의 이미지 상대 경로 (e.g., `knowledge/sources/assets/architecture.png`)
  - `context`: 모델에게 지시할 추가 프롬프트 (e.g., "이 아키텍처 다이어그램에서 데이터 흐름만 추출해")
- **사전 제약 조건**: 시스템에 유효한 `GOOGLE_API_KEY` 환경변수가 설정되어 있어야 합니다.

## 3. 정제(Distill) 워크플로우
이렇게 `ingest_ops` 도구를 통해 수집된 파일들은 `knowledge/sources/raw/` 경로에 덤프됩니다.
이후 `Archivist` 에이전트는 `archivist_distill`을 사용하여, 이 파일들의 본문을 분석하고 적절한 카테고리와 태그를 Frontmatter에 주입시킨 후 메인 인덱스 구조로 병합합니다.
