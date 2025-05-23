from typing import Any, List, Dict
import httpx
import sys
import os
import json
import threading
import time
from mcp.server.fastmcp import FastMCP
import mido
from mido import Message
from queue import Queue
from collections import defaultdict

# 디버깅 로그 함수
def debug_log(message):
    print(message, file=sys.stderr, flush=True)

# 코드 인식을 위한 음악 이론 클래스
class ChordRecognizer:
    def __init__(self):
        # 코드 패턴 정의 (반음 간격)
        self.chord_patterns = {
            'maj': [0, 4, 7],           # 메이저
            'min': [0, 3, 7],           # 마이너
            'dom7': [0, 4, 7, 10],      # 도미넌트 7
            'maj7': [0, 4, 7, 11],      # 메이저 7
            'min7': [0, 3, 7, 10],      # 마이너 7
            'min7b5': [0, 3, 6, 10],    # 하프 디미니쉬드
            'dim7': [0, 3, 6, 9],       # 디미니쉬드 7
            'aug': [0, 4, 8],           # 오그먼트
            'sus2': [0, 2, 7],          # 서스펜드 2
            'sus4': [0, 5, 7],          # 서스펜드 4
            'add9': [0, 4, 7, 14],      # 애드 9
            'dom9': [0, 4, 7, 10, 14],  # 도미넌트 9
            'maj9': [0, 4, 7, 11, 14],  # 메이저 9
            'min9': [0, 3, 7, 10, 14],  # 마이너 9
        }
        
        # 노트 이름 매핑
        self.note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    def normalize_notes(self, notes):
        """노트들을 0-11 범위로 정규화"""
        return sorted(list(set([note % 12 for note in notes])))
    
    def recognize_chord(self, notes):
        """노트 배열에서 코드 인식"""
        if len(notes) < 2:
            return None
            
        normalized = self.normalize_notes(notes)
        
        # 각 노트를 루트로 가정하고 코드 패턴 매칭
        for root in normalized:
            intervals = [(note - root) % 12 for note in normalized]
            intervals.sort()
            
            # 패턴 매칭
            for chord_type, pattern in self.chord_patterns.items():
                if self.pattern_matches(intervals, pattern):
                    root_name = self.note_names[root]
                    return {
                        'root': root,
                        'root_name': root_name,
                        'type': chord_type,
                        'name': f"{root_name}{chord_type}",
                        'notes': normalized,
                        'intervals': intervals
                    }
        
        # 인식되지 않은 경우 기본 정보 반환
        root = normalized[0]
        return {
            'root': root,
            'root_name': self.note_names[root],
            'type': 'unknown',
            'name': f"{self.note_names[root]}?",
            'notes': normalized,
            'intervals': [(note - root) % 12 for note in normalized]
        }
    
    def pattern_matches(self, intervals, pattern):
        """인터벌 패턴이 코드 패턴과 일치하는지 확인"""
        if len(intervals) < len(pattern):
            return False
        
        # 정확한 매칭
        if intervals[:len(pattern)] == pattern:
            return True
        
        # 부분 매칭 (기본 3화음은 허용)
        if len(pattern) >= 3 and intervals[:3] == pattern[:3]:
            return True
            
        return False

# 실시간 MIDI 모니터링 클래스
class RealTimeMIDIMonitor:
    def __init__(self, chord_callback=None):
        self.input_port = None
        self.output_port = None
        self.chord_recognizer = ChordRecognizer()
        self.chord_callback = chord_callback
        self.current_notes = set()
        self.last_chord = None
        self.monitoring = False
        self.monitor_thread = None
        
        # 코드 안정성을 위한 타이머
        self.chord_stable_time = 0.5  # 0.5초간 안정적이어야 코드로 인식
        self.last_change_time = 0
        
    def list_midi_devices(self):
        """사용 가능한 MIDI 장치 목록"""
        input_ports = mido.get_input_names()
        output_ports = mido.get_output_names()
        
        debug_log("=== MIDI 장치 목록 ===")
        debug_log("입력 장치:")
        for i, port in enumerate(input_ports):
            debug_log(f"  {i}: {port}")
        debug_log("출력 장치:")
        for i, port in enumerate(output_ports):
            debug_log(f"  {i}: {port}")
        
        return {
            'input_ports': input_ports,
            'output_ports': output_ports
        }
    
    def connect_midi(self, input_port_name=None, output_port_name=None):
        """MIDI 포트 연결"""
        try:
            # 입력 포트 연결
            if input_port_name:
                self.input_port = mido.open_input(input_port_name)
                debug_log(f"MIDI 입력 포트 연결: {input_port_name}")
            else:
                # 첫 번째 사용 가능한 입력 포트 사용
                input_ports = mido.get_input_names()
                if input_ports:
                    self.input_port = mido.open_input(input_ports[0])
                    debug_log(f"자동 MIDI 입력 포트 연결: {input_ports[0]}")
            
            # 출력 포트 연결
            if output_port_name:
                self.output_port = mido.open_output(output_port_name)
                debug_log(f"MIDI 출력 포트 연결: {output_port_name}")
            else:
                # 첫 번째 사용 가능한 출력 포트 사용
                output_ports = mido.get_output_names()
                if output_ports:
                    self.output_port = mido.open_output(output_ports[0])
                    debug_log(f"자동 MIDI 출력 포트 연결: {output_ports[0]}")
            
            return True
        except Exception as e:
            debug_log(f"MIDI 연결 오류: {e}")
            return False
    
    def start_monitoring(self):
        """MIDI 모니터링 시작"""
        if not self.input_port:
            debug_log("MIDI 입력 포트가 연결되지 않았습니다")
            return False
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        debug_log("MIDI 모니터링 시작")
        return True
    
    def stop_monitoring(self):
        """MIDI 모니터링 중지"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        debug_log("MIDI 모니터링 중지")
    
    def _monitor_loop(self):
        """MIDI 모니터링 루프"""
        while self.monitoring:
            try:
                # MIDI 메시지 처리
                for msg in self.input_port.iter_pending():
                    self._process_midi_message(msg)
                
                # 코드 안정성 체크
                self._check_chord_stability()
                
                time.sleep(0.01)  # 10ms 대기
                
            except Exception as e:
                debug_log(f"MIDI 모니터링 오류: {e}")
                time.sleep(0.1)
    
    def _process_midi_message(self, msg):
        """MIDI 메시지 처리"""
        if msg.type == 'note_on' and msg.velocity > 0:
            self.current_notes.add(msg.note)
            self.last_change_time = time.time()
            debug_log(f"노트 온: {msg.note} ({self._note_to_name(msg.note)})")
            
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            self.current_notes.discard(msg.note)
            self.last_change_time = time.time()
            debug_log(f"노트 오프: {msg.note} ({self._note_to_name(msg.note)})")
    
    def _check_chord_stability(self):
        """코드 안정성 확인 및 인식"""
        current_time = time.time()
        
        # 노트가 안정적으로 유지되었는지 확인
        if (current_time - self.last_change_time) >= self.chord_stable_time and len(self.current_notes) >= 2:
            # 코드 인식
            chord = self.chord_recognizer.recognize_chord(list(self.current_notes))
            
            # 새로운 코드인지 확인
            if chord and (not self.last_chord or chord['name'] != self.last_chord['name']):
                self.last_chord = chord
                debug_log(f"코드 인식: {chord['name']} - {[self._note_to_name(n) for n in chord['notes']]}")
                
                # 콜백 함수 호출
                if self.chord_callback:
                    self.chord_callback(chord)
    
    def _note_to_name(self, note):
        """MIDI 노트 번호를 노트 이름으로 변환"""
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = note // 12 - 1
        note_name = note_names[note % 12]
        return f"{note_name}{octave}"
    
    def send_to_fl_studio(self, notes_data):
        """FL Studio로 노트 데이터 전송"""
        if not self.output_port:
            debug_log("MIDI 출력 포트가 연결되지 않았습니다")
            return False
        
        try:
            # 멜로디 수신 모드 시작 (노트 0)
            self._send_midi_note(0)
            time.sleep(0.1)
            
            # 노트 수 전송
            self._send_midi_note(min(127, len(notes_data)))
            time.sleep(0.1)
            
            # 노트 데이터 전송 (6개 값 per 노트)
            for note, velocity, length, position in notes_data:
                # 1. 노트 값
                self._send_midi_note(min(127, max(0, int(note))))
                # 2. 벨로시티 값
                self._send_midi_note(min(127, max(0, int(velocity))))
                # 3. 길이 정수부
                length_whole = min(127, int(length))
                self._send_midi_note(length_whole)
                # 4. 길이 소수부
                length_decimal = int(round((length - length_whole) * 10)) % 10
                self._send_midi_note(length_decimal)
                # 5. 위치 정수부
                position_whole = min(127, int(position))
                self._send_midi_note(position_whole)
                # 6. 위치 소수부
                position_decimal = int(round((position - position_whole) * 10)) % 10
                self._send_midi_note(position_decimal)
                
                time.sleep(0.01)
            
            # 종료 신호 (노트 127)
            self._send_midi_note(127)
            
            # 자동 녹음 (노트 10)
            time.sleep(0.2)
            self._send_midi_note(10)
            
            debug_log(f"FL Studio로 {len(notes_data)}개 노트 전송 완료")
            return True
            
        except Exception as e:
            debug_log(f"FL Studio 전송 오류: {e}")
            return False
    
    def _send_midi_note(self, note, velocity=100, duration=0.01):
        """MIDI 노트 전송"""
        if self.output_port:
            note_on = Message('note_on', note=int(note), velocity=int(velocity))
            self.output_port.send(note_on)
            time.sleep(duration)
            note_off = Message('note_off', note=int(note), velocity=0)
            self.output_port.send(note_off)

# 비밥 솔로 생성기 (간단 버전)
class SimpleBebopGenerator:
    def __init__(self):
        # 비밥 스케일 정의
        self.bebop_scales = {
            'major': [0, 2, 4, 5, 7, 8, 9, 11],      # 메이저 비밥
            'dominant': [0, 2, 4, 5, 7, 9, 10, 11],  # 도미넌트 비밥
            'minor': [0, 2, 3, 5, 7, 9, 10, 11],     # 마이너 비밥
        }
        
        # 코드 타입별 선호 스케일
        self.chord_to_scale = {
            'maj': 'major', 'maj7': 'major', 'maj9': 'major',
            'dom7': 'dominant', 'dom9': 'dominant',
            'min': 'minor', 'min7': 'minor', 'min9': 'minor',
            'min7b5': 'minor', 'dim7': 'minor'
        }
    
    def generate_solo_for_chord(self, chord_info, measures=2, complexity=0.7):
        """코드에 맞는 비밥 솔로 생성"""
        # 사용할 스케일 결정
        scale_type = self.chord_to_scale.get(chord_info['type'], 'dominant')
        scale = self.bebop_scales[scale_type]
        
        # 루트 노트 조정
        root = chord_info['root'] + 60  # C4 기준
        scale_notes = [(root + interval) for interval in scale]
        
        # 솔로 노트 생성
        notes = []
        beats_per_measure = 4
        total_beats = measures * beats_per_measure
        
        current_position = 0.0
        note_lengths = [0.25, 0.5, 0.75, 1.0] if complexity > 0.6 else [0.5, 1.0]
        
        while current_position < total_beats:
            # 랜덤 스케일 노트 선택
            scale_degree = random.choice(range(len(scale_notes)))
            note = scale_notes[scale_degree]
            
            # 옥타브 변경 (가끔)
            if random.random() < 0.3:
                note += random.choice([-12, 12])
            
            # 노트가 범위를 벗어나지 않도록 조정
            note = max(48, min(84, note))  # C3 ~ C6
            
            # 벨로시티와 길이 설정
            velocity = random.randint(70, 110)
            length = random.choice(note_lengths)
            
            # 남은 시간보다 길면 조정
            if current_position + length > total_beats:
                length = total_beats - current_position
            
            notes.append((note, velocity, length, current_position))
            current_position += length
            
            # 가끔 쉼표 추가
            if random.random() < 0.2 and current_position < total_beats:
                rest_length = random.choice([0.25, 0.5])
                if current_position + rest_length <= total_beats:
                    current_position += rest_length
        
        return notes

# 메인 서버 클래스
try:
    import random  # SimpleBebopGenerator에서 사용
    
    debug_log("실시간 비밥 MCP 서버 시작...")
    
    # FastMCP 서버 초기화
    mcp = FastMCP("realtime_bebop")
    
    # MIDI 모니터 초기화
    midi_monitor = None
    
    def on_chord_detected(chord_info):
        """코드가 감지되었을 때 호출되는 콜백"""
        debug_log(f"코드 감지됨: {chord_info['name']}")
        
        # 비밥 솔로 생성
        generator = SimpleBebopGenerator()
        solo_notes = generator.generate_solo_for_chord(chord_info, measures=2, complexity=0.8)
        
        debug_log(f"비밥 솔로 생성됨: {len(solo_notes)}개 노트")
        
        # FL Studio로 전송
        if midi_monitor:
            success = midi_monitor.send_to_fl_studio(solo_notes)
            if success:
                debug_log("FL Studio로 솔로 전송 완료")
            else:
                debug_log("FL Studio 전송 실패")

    @mcp.tool()
    def list_midi_devices():
        """사용 가능한 MIDI 장치 목록 표시"""
        monitor = RealTimeMIDIMonitor()
        devices = monitor.list_midi_devices()
        return devices

    @mcp.tool()
    def start_realtime_monitoring(input_port_name=None, output_port_name=None):
        """실시간 MIDI 모니터링 시작"""
        global midi_monitor
        
        midi_monitor = RealTimeMIDIMonitor(chord_callback=on_chord_detected)
        
        # MIDI 연결
        if midi_monitor.connect_midi(input_port_name, output_port_name):
            # 모니터링 시작
            if midi_monitor.start_monitoring():
                return "실시간 MIDI 모니터링이 시작되었습니다. 키보드에서 코드를 연주해보세요!"
            else:
                return "MIDI 모니터링 시작에 실패했습니다."
        else:
            return "MIDI 장치 연결에 실패했습니다."

    @mcp.tool()
    def stop_realtime_monitoring():
        """실시간 MIDI 모니터링 중지"""
        global midi_monitor
        
        if midi_monitor:
            midi_monitor.stop_monitoring()
            midi_monitor = None
            return "실시간 MIDI 모니터링이 중지되었습니다."
        else:
            return "모니터링이 실행 중이 아닙니다."

    @mcp.tool()
    def get_monitoring_status():
        """현재 모니터링 상태 확인"""
        global midi_monitor
        
        if midi_monitor and midi_monitor.monitoring:
            status = {
                "monitoring": True,
                "current_notes": list(midi_monitor.current_notes),
                "last_chord": midi_monitor.last_chord['name'] if midi_monitor.last_chord else None
            }
        else:
            status = {
                "monitoring": False,
                "current_notes": [],
                "last_chord": None
            }
        
        return status

    @mcp.tool()
    def test_chord_recognition(notes_str):
        """코드 인식 테스트 (예: "60,64,67" for C major)"""
        try:
            notes = [int(n.strip()) for n in notes_str.split(',')]
            recognizer = ChordRecognizer()
            chord = recognizer.recognize_chord(notes)
            
            if chord:
                return f"인식된 코드: {chord['name']} (루트: {chord['root_name']}, 타입: {chord['type']})"
            else:
                return "코드를 인식할 수 없습니다."
        except Exception as e:
            return f"오류: {e}"

    @mcp.tool()
    def generate_solo_for_chord_manual(chord_name, measures=2, complexity=0.7):
        """수동으로 코드 이름을 입력하여 솔로 생성 (예: "Cmaj7")"""
        try:
            # 간단한 코드 파싱
            root_name = chord_name[0].upper()
            chord_type = chord_name[1:].lower()
            
            # 루트 노트 변환
            note_map = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
            if '#' in chord_name:
                root_name = chord_name[:2]
                chord_type = chord_name[2:].lower()
                note_map.update({'C#': 1, 'D#': 3, 'F#': 6, 'G#': 8, 'A#': 10})
            
            root = note_map.get(root_name, 0)
            
            chord_info = {
                'root': root,
                'root_name': root_name,
                'type': chord_type if chord_type else 'maj',
                'name': chord_name
            }
            
            generator = SimpleBebopGenerator()
            solo_notes = generator.generate_solo_for_chord(chord_info, int(measures), float(complexity))
            
            # FL Studio로 전송
            if midi_monitor:
                success = midi_monitor.send_to_fl_studio(solo_notes)
                if success:
                    return f"{chord_name} 코드에 대한 비밥 솔로 ({len(solo_notes)}개 노트)가 FL Studio로 전송되었습니다."
                else:
                    return "FL Studio 전송에 실패했습니다."
            else:
                return "MIDI 모니터가 초기화되지 않았습니다. 먼저 start_realtime_monitoring을 실행하세요."
                
        except Exception as e:
            return f"오류: {e}"

    if __name__ == "__main__":
        # 서버 실행
        debug_log("실시간 비밥 MCP 서버 실행 중...")
        mcp.run(transport='stdio')

except Exception as e:
    debug_log(f"서버 초기화 오류: {e}")
    sys.exit(1)