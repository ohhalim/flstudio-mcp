import sys
from mcp.server.fastmcp import FastMCP
from src.core.bebop_solo_generator import BebopSoloGenerator


def debug_log(message):
    print(message, file=sys.stderr, flush=True)


# MCP 서버 초기화
try:
    debug_log("비밥 솔로라인 MCP 서버 시작...")
    
    # FastMCP 서버 생성
    mcp = FastMCP("bebop_solo")
    
    # 비밥 솔로 생성기 인스턴스 (RAG 기능 포함)
    bebop_generator = BebopSoloGenerator("./midi_data")
    
    # RAG 데이터베이스 초기화
    debug_log("RAG 데이터베이스 초기화 중...")
    if not bebop_generator.rag_analyzer.load_database():
        debug_log("기존 데이터베이스가 없어 새로 구축합니다...")
        bebop_generator.rag_analyzer.build_database()
    
    @mcp.tool()
    def list_midi_ports():
        """사용 가능한 MIDI 포트 목록"""
        port_info = bebop_generator.midi_handler.get_port_info()
        return port_info
    
    @mcp.tool()
    def start_bebop_listening(input_port: str = None, output_port: str = None):
        """외부 키보드에서 화성 입력을 듣고 비밥 솔로라인 생성 시작"""
        try:
            # MIDI 포트 설정
            if bebop_generator.setup_midi_ports(input_port, output_port):
                bebop_generator.start_listening()
                return f"비밥 솔로라인 생성 시작됨 (입력: {input_port or 'auto'}, 출력: {output_port or 'auto'})"
            else:
                return "MIDI 포트 설정 실패"
        except Exception as e:
            return f"오류: {e}"
    
    @mcp.tool()
    def stop_bebop_listening():
        """비밥 솔로라인 생성 중지"""
        try:
            bebop_generator.stop_listening()
            return "비밥 솔로라인 생성 중지됨"
        except Exception as e:
            return f"오류: {e}"
    
    @mcp.tool()
    def get_bebop_status():
        """현재 비밥 솔로라인 생성 상태"""
        return bebop_generator.get_status()
    
    @mcp.tool()
    def test_bebop_solo(chord_notes_str: str, pattern: str = 'ascending_run'):
        """비밥 솔로라인 테스트 (실시간 모드가 아닐 때)"""
        try:
            chord_notes = set(int(n.strip()) for n in chord_notes_str.split(','))
            solo_note_list = bebop_generator.test_bebop_solo(chord_notes, pattern)
            return f"테스트 비밥 솔로라인 생성 ({pattern}): {solo_note_list}"
        except Exception as e:
            return f"오류: {e}"
    
    @mcp.tool()
    def build_midi_database(midi_folder: str = "./midi_data"):
        """지정된 폴더의 MIDI 파일들로 RAG 데이터베이스 구축"""
        try:
            bebop_generator.build_midi_database(midi_folder)
            return f"데이터베이스 구축 완료: {midi_folder}"
        except Exception as e:
            return f"데이터베이스 구축 오류: {e}"
    
    @mcp.tool()
    def toggle_rag_mode(use_rag: bool = True):
        """RAG 모드 온/오프 전환"""
        mode = bebop_generator.toggle_rag_mode(use_rag)
        return f"{mode}로 전환됨"
    
    @mcp.tool()
    def search_similar_melodies(chord_notes_str: str, top_k: int = 3):
        """입력 화성과 유사한 멜로디 검색"""
        try:
            chord_notes = set(int(n.strip()) for n in chord_notes_str.split(','))
            similar_melodies = bebop_generator.search_similar_melodies(chord_notes, top_k)
            
            if not similar_melodies:
                return "유사한 멜로디를 찾을 수 없습니다."
            
            results = []
            for i, (melody, similarity) in enumerate(similar_melodies):
                melody_notes = [note_data['note'] for note_data in melody[:8]]
                results.append(f"{i+1}. 유사도: {similarity:.3f}, 노트: {melody_notes}")
            
            return "\n".join(results)
        except Exception as e:
            return f"오류: {e}"
    
    @mcp.tool() 
    def get_database_info():
        """RAG 데이터베이스 정보 확인"""
        return bebop_generator.get_database_info()
    
    # 사용자 학습 관련 도구들
    @mcp.tool()
    def rate_melody(rating: float):
        """현재 멜로디에 평점 주기 (1-5점)"""
        return bebop_generator.rate_current_melody(rating)
    
    @mcp.tool()
    def skip_melody():
        """현재 멜로디 스킵"""
        return bebop_generator.skip_current_melody()
    
    @mcp.tool()
    def repeat_melody():
        """현재 멜로디 반복 재생"""
        return bebop_generator.repeat_current_melody()
    
    @mcp.tool()
    def toggle_learning(use_learning: bool = True):
        """학습 모드 온/오프 전환"""
        mode = bebop_generator.toggle_learning_mode(use_learning)
        return f"{mode}로 전환됨"
    
    @mcp.tool()
    def get_user_profile():
        """사용자 선호도 프로필 확인"""
        return bebop_generator.get_user_profile()
    
    @mcp.tool()
    def reset_preferences():
        """사용자 선호도 초기화"""
        return bebop_generator.reset_user_preferences()
    
    @mcp.tool()
    def adjust_learning_rate(learning_rate: float):
        """학습률 조정 (0.01-1.0)"""
        return bebop_generator.adjust_learning_rate(learning_rate)
    
    if __name__ == "__main__":
        debug_log("비밥 솔로라인 MCP 서버 실행 중... (RAG 및 사용자 학습 기능 포함)")
        mcp.run(transport='stdio')

except Exception as e:
    debug_log(f"서버 초기화 오류: {e}")
    sys.exit(1)