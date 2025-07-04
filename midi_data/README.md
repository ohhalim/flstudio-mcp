# MIDI RAG 데이터베이스 폴더

이 폴더에 MIDI 파일들을 넣으면 RAG 시스템이 자동으로 분석하여 데이터베이스를 구축합니다.

## 사용 방법

1. **MIDI 파일 추가**: 이 폴더에 `.mid` 또는 `.midi` 파일들을 복사해 넣으세요.

2. **데이터베이스 구축**: MCP 도구 `build_midi_database()` 를 호출하여 데이터베이스를 구축하세요.

3. **RAG 모드 사용**: 외부 키보드에서 화성을 연주하면 자동으로 유사한 멜로디가 검색되어 재생됩니다.

## MCP 도구 사용법

- `build_midi_database()` - MIDI 파일들을 분석하여 RAG 데이터베이스 구축
- `toggle_rag_mode(true/false)` - RAG 모드 온/오프 전환  
- `search_similar_melodies("60,64,67")` - 특정 화성과 유사한 멜로디 검색
- `get_database_info()` - 현재 데이터베이스 상태 확인

## 지원하는 파일 형식

- `.mid` 파일
- `.midi` 파일

## 예시 파일

시스템이 처음 실행되면 다음 예시 파일들이 자동으로 생성됩니다:
- `cmajor_scale.mid` - C메이저 스케일
- `blues_pattern.mid` - 블루스 패턴
- `jazz_ii_v_i.mid` - 재즈 II-V-I 진행

이 파일들을 참고하여 원하는 MIDI 파일들을 추가하세요.