# 모듈화된 FL Studio MCP 서버

## 프로젝트 구조

```
flstudio-mcp/
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── bebop_solo_generator.py  # 메인 솔로 생성기
│   │   └── rag_analyzer.py          # RAG 시스템
│   ├── music_theory/
│   │   ├── __init__.py
│   │   └── bebop_theory.py          # 비밥 음악 이론
│   └── midi/
│       ├── __init__.py
│       └── midi_handler.py          # MIDI 입출력 관리
├── main_mcp_server.py               # 새로운 메인 서버
├── simple_bebop_mcp.py             # 기존 단일 파일 (백업용)
└── midi_data/                       # MIDI 파일들
```

## 모듈 설명

### 1. `src/music_theory/bebop_theory.py`
- 비밥 음악 이론 엔진
- 스케일, 리듬, 화성 분석
- 솔로라인 생성 로직

### 2. `src/midi/midi_handler.py`
- MIDI 입출력 관리
- 포트 설정 및 연결
- 실시간 MIDI 처리

### 3. `src/core/rag_analyzer.py`
- MIDI 파일 분석
- RAG 데이터베이스 구축
- 유사 멜로디 검색

### 4. `src/core/bebop_solo_generator.py`
- 메인 솔로 생성기
- 모든 컴포넌트 조합
- 실시간 처리 로직

### 5. `main_mcp_server.py`
- 새로운 모듈화된 MCP 서버
- 모든 MCP 도구 정의
- 서버 초기화 및 실행

## 사용법

### 새로운 모듈화된 서버 실행
```bash
python main_mcp_server.py
```

### 기존 서버 (백업용)
```bash
python simple_bebop_mcp.py
```

## 장점

1. **코드 분리**: 각 기능이 독립적인 모듈로 분리
2. **유지보수성**: 각 모듈을 독립적으로 수정 가능
3. **테스트 용이성**: 각 모듈을 개별적으로 테스트 가능
4. **확장성**: 새로운 기능 추가가 쉬움
5. **재사용성**: 모듈을 다른 프로젝트에서 재사용 가능

## 마이그레이션

기존의 `simple_bebop_mcp.py`는 백업으로 유지되며, 새로운 `main_mcp_server.py`가 동일한 기능을 모듈화된 구조로 제공합니다.