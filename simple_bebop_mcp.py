# simple_bebop_mcp.py
# 간단한 비밥 솔로 MCP 서버

import sys
import time
from typing import List, Tuple, Dict
from mcp.server.fastmcp import FastMCP
import mido
from mido import Message

def debug_log(message):
    print(message, file=sys.stderr, flush=True)

class BebopSoloGenerator:
    """간단한 비밥 솔로 생성기"""
    
    def __init__(self):
        # 비밥 스케일 (반음 간격)
        self.scales = {
            'major': [0, 2, 4, 5, 7, 8, 9, 11],
            'dominant': [0, 2, 4, 5, 7, 9, 10, 11], 
            'minor': [0, 2, 3, 5, 7, 9, 10, 11]
        }
        
        # 코드 타입 → 스케일 매핑
        self.chord_scales = {
            'maj': 'major', 'min': 'minor', 'dom': 'dominant'
        }
        
        # 고정 패턴들 (일관성을 위해)
        self.patterns = {
            'major': [0, 1, 2, 3, 4, 5, 6, 7, 6, 5, 4, 3, 2, 1],     # 상승-하강
            'minor': [7, 6, 5, 4, 3, 2, 1, 0, 1, 2, 3, 4, 5, 6],     # 하강-상승  
            'dominant': [0, 2, 1, 3, 2, 4, 3, 5, 4, 6, 5, 7, 6, 4]   # 지그재그
        }
        
        # 고정 리듬 (8분음표 기반)
        self.rhythms = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    
    def detect_chord_type(self, notes: List[int]) -> str:
        """간단한 코드 타입 감지"""
        if len(notes) < 3:
            return 'maj'
        
        # 노트들을 반음 간격으로 정규화
        intervals = []
        root = min(notes) % 12
        for note in notes:
            intervals.append((note - root) % 12)
        intervals = sorted(list(set(intervals)))
        
        # 간단한 패턴 매칭
        if intervals[:3] == [0, 3, 7]:  # 마이너 트라이어드
            return 'min'
        elif intervals[:4] == [0, 4, 7, 10]:  # 도미넌트 7
            return 'dom'
        else:  # 기본 메이저
            return 'maj'
    
    def generate_solo(self, chord_notes: List[int], measures: int = 2) -> List[Tuple]:
        """코드에 맞는 비밥 솔로 생성"""
        # 코드 타입 감지
        chord_type = self.detect_chord_type(chord_notes)
        
        # 루트 노트 계산
        root = min(chord_notes) % 12
        
        # 스케일 선택
        scale_type = self.chord_scales.get(chord_type, 'major')
        scale = self.scales[scale_type]
        
        # 스케일 노트들 (C4 기준, 2옥타브)
        base_octave = 60  # C4
        scale_notes = []
        for octave in range(2):  # 2옥타브
            for interval in scale:
                note = base_octave + root + interval + (octave * 12)
                if 48 <= note <= 84:  # C3~C6 범위
                    scale_notes.append(note)
        
        # 패턴과 리듬 선택
        pattern = self.patterns[scale_type]
        rhythm = self.rhythms
        
        # 솔로 노트 생성
        notes = []
        current_pos = 0.0
        total_beats = measures * 4  # 4/4 박자
        
        pattern_idx = 0
        rhythm_idx = 0
        
        while current_pos < total_beats:
            # 스케일 음도 선택
            scale_degree = pattern[pattern_idx % len(pattern)]
            scale_degree = min(scale_degree, len(scale_notes) - 1)
            
            note = scale_notes[scale_degree]
            velocity = 90  # 고정 벨로시티
            length = rhythm[rhythm_idx % len(rhythm)]
            
            # 마디 경계 체크
            if current_pos + length > total_beats:
                length = total_beats - current_pos
            
            notes.append((note, velocity, length, current_pos))
            
            current_pos += length
            pattern_idx += 1
            rhythm_idx += 1
        
        debug_log(f"생성된 솔로: {len(notes)}개 노트, 코드타입: {chord_type}")
        return notes

# MCP 서버 초기화
try:
    debug_log("비밥 솔로 MCP 서버 시작...")
    
    # MIDI 포트 설정
    available_ports = mido.get_output_names()
    if not available_ports:
        debug_log("MIDI 출력 포트를 찾을 수 없습니다!")
        sys.exit(1)
    
    midi_port = available_ports[0]
    output_port = mido.open_output(midi_port)
    debug_log(f"MIDI 포트 연결: {midi_port}")
    
    # FastMCP 서버 생성
    mcp = FastMCP("bebop_solo")
    
    # 비밥 생성기 인스턴스
    bebop_generator = BebopSoloGenerator()
    
    def send_midi_note(note: int, velocity: int = 100, duration: float = 0.01):
        """MIDI 노트 전송"""
        note_on = Message('note_on', note=note, velocity=velocity)
        output_port.send(note_on)
        time.sleep(duration)
        note_off = Message('note_off', note=note, velocity=0)
        output_port.send(note_off)
    
    def send_solo_to_fl(notes_data: List[Tuple]):
        """FL Studio로 솔로 데이터 전송"""
        # 시작 신호 (노트 0)
        send_midi_note(0)
        time.sleep(0.1)
        
        # 노트 개수 전송
        send_midi_note(min(127, len(notes_data)))
        time.sleep(0.1)
        
        # 각 노트의 6개 값 전송
        for note, velocity, length, position in notes_data:
            # 1. 노트 값
            send_midi_note(int(note))
            # 2. 벨로시티
            send_midi_note(int(velocity))
            # 3. 길이 정수부
            length_whole = int(length)
            send_midi_note(length_whole)
            # 4. 길이 소수부
            length_decimal = int((length - length_whole) * 10) % 10
            send_midi_note(length_decimal)
            # 5. 위치 정수부
            position_whole = int(position)
            send_midi_note(position_whole)
            # 6. 위치 소수부
            position_decimal = int((position - position_whole) * 10) % 10
            send_midi_note(position_decimal)
            
            time.sleep(0.01)
        
        # 종료 신호 (노트 127)
        send_midi_note(127)
        time.sleep(0.1)
        
        # 자동 녹음 (노트 10)
        send_midi_note(10)
    
    @mcp.tool()
    def generate_bebop_solo(chord_notes_str: str, measures: int = 2):
        """
        코드 노트로부터 비밥 솔로 생성 및 FL Studio 전송
        
        Args:
            chord_notes_str: 쉼표로 구분된 MIDI 노트 번호 (예: "60,64,67")
            measures: 생성할 마디 수 (기본: 2)
        """
        try:
            # 코드 노트 파싱
            chord_notes = [int(n.strip()) for n in chord_notes_str.split(',')]
            
            if len(chord_notes) < 2:
                return "최소 2개 이상의 노트가 필요합니다."
            
            # 비밥 솔로 생성
            solo_notes = bebop_generator.generate_solo(chord_notes, measures)
            
            # FL Studio로 전송
            send_solo_to_fl(solo_notes)
            
            return f"비밥 솔로 생성 완료: {len(solo_notes)}개 노트, {measures}마디"
            
        except Exception as e:
            return f"오류 발생: {e}"
    
    @mcp.tool()
    def test_chord_types():
        """다양한 코드 타입 테스트"""
        test_chords = {
            'C major': [60, 64, 67],      # C, E, G
            'C minor': [60, 63, 67],      # C, Eb, G  
            'C7': [60, 64, 67, 70],       # C, E, G, Bb
            'D minor': [62, 65, 69],      # D, F, A
            'G7': [67, 71, 74, 77]        # G, B, D, F
        }
        
        results = []
        for chord_name, notes in test_chords.items():
            chord_type = bebop_generator.detect_chord_type(notes)
            results.append(f"{chord_name}: {chord_type}")
        
        return "\n".join(results)
    
    @mcp.tool()
    def quick_solo(chord_name: str):
        """
        코드 이름으로 빠른 솔로 생성
        
        Args:
            chord_name: 코드 이름 (예: "Cmaj", "Gmin", "F7")
        """
        # 간단한 코드 이름 파싱
        chord_map = {
            'C': 60, 'D': 62, 'E': 64, 'F': 65, 'G': 67, 'A': 69, 'B': 71,
            'Cmaj': [60, 64, 67], 'Cmin': [60, 63, 67], 'C7': [60, 64, 67, 70],
            'Gmaj': [67, 71, 74], 'Gmin': [67, 70, 74], 'G7': [67, 71, 74, 77],
            'Fmaj': [65, 69, 72], 'Fmin': [65, 68, 72], 'F7': [65, 69, 72, 75],
            'Dmaj': [62, 66, 69], 'Dmin': [62, 65, 69], 'D7': [62, 66, 69, 72]
        }
        
        chord_notes = chord_map.get(chord_name)
        if not chord_notes:
            return f"알 수 없는 코드: {chord_name}"
        
        # 솔로 생성 및 전송
        solo_notes = bebop_generator.generate_solo(chord_notes, 2)
        send_solo_to_fl(solo_notes)
        
        return f"{chord_name} 코드에 대한 비밥 솔로 생성 완료"
    
    @mcp.tool()
    def list_midi_ports():
        """사용 가능한 MIDI 포트 목록"""
        input_ports = mido.get_input_names()
        output_ports = mido.get_output_names()
        
        return {
            "input_ports": input_ports,
            "output_ports": output_ports,
            "current_output": midi_port
        }
    
    if __name__ == "__main__":
        debug_log("비밥 솔로 MCP 서버 실행 중...")
        mcp.run(transport='stdio')

except Exception as e:
    debug_log(f"서버 초기화 오류: {e}")
    sys.exit(1)