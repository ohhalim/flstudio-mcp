# realtime_harmony_mcp.py

import sys
import time
import threading
from typing import List, Tuple, Dict, Set
from mcp.server.fastmcp import FastMCP
import mido
from mido import Message

def debug_log(message):
    print(message, file=sys.stderr, flush=True)

class RealTimeHarmonyGenerator:
    """실시간 화성 멜로디 생성기"""
    
    def __init__(self):
        self.current_chord_notes = set()  # 현재 눌린 노트들
        self.harmony_notes = []  # 생성된 화성 노트들
        self.is_listening = False
        self.input_port = None
        self.output_port = None
        
        # 화성 스케일 정의
        self.scales = {
            'major': [0, 2, 4, 5, 7, 9, 11],
            'minor': [0, 2, 3, 5, 7, 8, 10], 
            'dominant': [0, 2, 4, 5, 7, 9, 10],
            'diminished': [0, 2, 3, 5, 6, 8, 9, 11]
        }
        
        # 화성 패턴 (루트 기준 상대음정)
        self.harmony_patterns = {
            'major': [2, 4, 6, 9],      # 3rd, 5th, 7th, 9th
            'minor': [3, 5, 7, 10],     # minor 3rd, 5th, 7th, 9th  
            'dominant': [4, 7, 10, 14], # 5th, 7th, 9th, 11th
            'arpeggio': [12, 19, 24],   # 옥타브, 5th, 2옥타브
        }
        
        # 멜로디 패턴
        self.melody_patterns = {
            'ascending': [0, 2, 4, 5, 7, 9, 11, 12],
            'descending': [12, 11, 9, 7, 5, 4, 2, 0],
            'wave': [0, 4, 2, 5, 3, 7, 4, 9],
            'chromatic': [0, 1, 2, 3, 4, 5, 6, 7]
        }
    
    def setup_midi_ports(self, input_port_name=None, output_port_name=None):
        """MIDI 포트 설정"""
        try:
            # 입력 포트 설정 (외부 키보드)
            input_ports = mido.get_input_names()
            if input_port_name and input_port_name in input_ports:
                self.input_port = mido.open_input(input_port_name, callback=self.on_midi_input)
            elif input_ports:
                # 첫 번째 사용가능한 입력 포트 사용
                self.input_port = mido.open_input(input_ports[0], callback=self.on_midi_input)
                debug_log(f"입력 포트 연결: {input_ports[0]}")
            
            # 출력 포트 설정 (FL Studio로)
            output_ports = mido.get_output_names()
            if output_port_name and output_port_name in output_ports:
                self.output_port = mido.open_output(output_port_name)
            elif output_ports:
                self.output_port = mido.open_output(output_ports[0])
                debug_log(f"출력 포트 연결: {output_ports[0]}")
                
            return True
        except Exception as e:
            debug_log(f"MIDI 포트 설정 오류: {e}")
            return False
    
    def on_midi_input(self, message):
        """외부 키보드에서 MIDI 입력 받을 때"""
        if not self.is_listening:
            return
            
        if message.type == 'note_on' and message.velocity > 0:
            # 노트 온: 코드에 추가
            self.current_chord_notes.add(message.note)
            debug_log(f"노트 추가: {message.note}, 현재 코드: {sorted(self.current_chord_notes)}")
            
            # 화성 멜로디 생성 및 전송
            if len(self.current_chord_notes) >= 2:  # 최소 2개 노트
                self.generate_and_send_harmony()
                
        elif message.type == 'note_off' or (message.type == 'note_on' and message.velocity == 0):
            # 노트 오프: 코드에서 제거
            self.current_chord_notes.discard(message.note)
            debug_log(f"노트 제거: {message.note}, 현재 코드: {sorted(self.current_chord_notes)}")
            
            # 남은 노트가 있으면 다시 화성 생성
            if len(self.current_chord_notes) >= 2:
                self.generate_and_send_harmony()
            else:
                # 모든 화성 노트 끄기
                self.stop_all_harmony_notes()
    
    def detect_chord_type(self, notes: Set[int]) -> str:
        """코드 타입 감지"""
        if len(notes) < 2:
            return 'major'
        
        notes_list = sorted(list(notes))
        root = notes_list[0] % 12
        
        # 루트 기준 상대 음정 계산
        intervals = [(note - root) % 12 for note in notes_list]
        intervals = sorted(list(set(intervals)))
        
        # 패턴 매칭
        if 3 in intervals:  # 단3도 포함
            return 'minor'
        elif 10 in intervals:  # 단7도 포함
            return 'dominant'
        elif len(intervals) >= 4:  # 복잡한 코드
            return 'diminished'
        else:
            return 'major'
    
    def generate_harmony_melody(self, chord_notes: Set[int], pattern_type='major') -> List[int]:
        """화성 멜로디 생성"""
        if not chord_notes:
            return []
        
        root = min(chord_notes) % 12
        chord_type = self.detect_chord_type(chord_notes)
        
        # 화성 패턴 선택
        harmony_pattern = self.harmony_patterns.get(chord_type, self.harmony_patterns['major'])
        melody_pattern = self.melody_patterns.get(pattern_type, self.melody_patterns['ascending'])
        
        # 베이스 옥타브 설정 (입력된 코드보다 한 옥타브 위)
        base_octave = max(chord_notes) + 12
        
        # 화성 노트 생성
        harmony_notes = []
        for interval in harmony_pattern[:4]:  # 최대 4개 화성 노트
            note = base_octave + interval
            if 48 <= note <= 96:  # C3~C7 범위
                harmony_notes.append(note)
        
        return harmony_notes
    
    def generate_and_send_harmony(self):
        """화성 생성 및 FL Studio 전송"""
        if not self.current_chord_notes or not self.output_port:
            return
        
        # 이전 화성 노트들 끄기
        self.stop_all_harmony_notes()
        
        # 새 화성 생성
        self.harmony_notes = self.generate_harmony_melody(self.current_chord_notes)
        
        # FL Studio로 화성 노트 전송
        self.send_harmony_to_fl(self.harmony_notes)
        
        debug_log(f"화성 전송: {self.harmony_notes}")
    
    def send_harmony_to_fl(self, harmony_notes: List[int]):
        """FL Studio로 화성 노트 전송"""
        if not self.output_port:
            return
        
        # 시작 신호
        self.send_midi_note(1)  # 화성 모드 신호
        time.sleep(0.01)
        
        # 노트 개수
        self.send_midi_note(len(harmony_notes))
        time.sleep(0.01)
        
        # 각 화성 노트 전송
        for note in harmony_notes:
            self.send_midi_note(note)
            time.sleep(0.01)
        
        # 종료 신호
        self.send_midi_note(126)
        time.sleep(0.01)
    
    def stop_all_harmony_notes(self):
        """모든 화성 노트 끄기"""
        if not self.output_port:
            return
        
        # 정지 신호
        self.send_midi_note(2)  # 화성 정지 신호
        time.sleep(0.01)
    
    def send_midi_note(self, note: int, velocity: int = 100):
        """MIDI 노트 전송"""
        if self.output_port:
            note_on = Message('note_on', note=note, velocity=velocity)
            self.output_port.send(note_on)
            time.sleep(0.01)
            note_off = Message('note_off', note=note, velocity=0)
            self.output_port.send(note_off)
    
    def start_listening(self):
        """외부 키보드 듣기 시작"""
        self.is_listening = True
        debug_log("실시간 화성 생성 시작")
    
    def stop_listening(self):
        """외부 키보드 듣기 중지"""
        self.is_listening = False
        self.stop_all_harmony_notes()
        self.current_chord_notes.clear()
        debug_log("실시간 화성 생성 중지")

# MCP 서버 초기화
try:
    debug_log("실시간 화성 MCP 서버 시작...")
    
    # FastMCP 서버 생성
    mcp = FastMCP("realtime_harmony")
    
    # 화성 생성기 인스턴스
    harmony_generator = RealTimeHarmonyGenerator()
    
    @mcp.tool()
    def list_midi_ports():
        """사용 가능한 MIDI 포트 목록"""
        input_ports = mido.get_input_names()
        output_ports = mido.get_output_names()
        
        return {
            "input_ports": input_ports,
            "output_ports": output_ports,
            "status": "listening" if harmony_generator.is_listening else "stopped"
        }
    
    @mcp.tool()
    def start_harmony_listening(input_port: str = None, output_port: str = None):
        """실시간 화성 생성 시작"""
        try:
            # MIDI 포트 설정
            if harmony_generator.setup_midi_ports(input_port, output_port):
                harmony_generator.start_listening()
                return f"실시간 화성 생성 시작됨 (입력: {input_port or 'auto'}, 출력: {output_port or 'auto'})"
            else:
                return "MIDI 포트 설정 실패"
        except Exception as e:
            return f"오류: {e}"
    
    @mcp.tool()
    def stop_harmony_listening():
        """실시간 화성 생성 중지"""
        try:
            harmony_generator.stop_listening()
            return "실시간 화성 생성 중지됨"
        except Exception as e:
            return f"오류: {e}"
    
    @mcp.tool()
    def get_harmony_status():
        """현재 화성 생성 상태"""
        return {
            "listening": harmony_generator.is_listening,
            "current_chord": sorted(list(harmony_generator.current_chord_notes)),
            "harmony_notes": harmony_generator.harmony_notes,
            "input_connected": harmony_generator.input_port is not None,
            "output_connected": harmony_generator.output_port is not None
        }
    
    @mcp.tool()
    def test_harmony(chord_notes_str: str):
        """화성 테스트 (실시간 모드가 아닐 때)"""
        try:
            chord_notes = set(int(n.strip()) for n in chord_notes_str.split(','))
            harmony_notes = harmony_generator.generate_harmony_melody(chord_notes)
            
            if harmony_generator.output_port:
                harmony_generator.send_harmony_to_fl(harmony_notes)
            
            return f"테스트 화성 생성: {harmony_notes}"
        except Exception as e:
            return f"오류: {e}"
    
    if __name__ == "__main__":
        debug_log("실시간 화성 MCP 서버 실행 중...")
        mcp.run(transport='stdio')

except Exception as e:
    debug_log(f"서버 초기화 오류: {e}")
    sys.exit(1)