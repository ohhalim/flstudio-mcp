from typing import Any
import httpx
import sys
import os
import json
from mcp.server.fastmcp import FastMCP
import mido
from mido import Message
import time

# 디버깅 로그 함수
def debug_log(message):
    print(message, file=sys.stderr, flush=True)

try:
    debug_log("Starting Bebop MCP server...")
    
    # 사용 가능한 MIDI 포트 확인 및 로깅
    available_ports = mido.get_output_names()
    debug_log(f"Available MIDI ports: {available_ports}")
    
    # Initialize FastMCP server
    mcp = FastMCP("flstudio_bebop")
    
    # 첫 번째 사용 가능한 포트 사용
    if available_ports:
        midi_port = available_ports[0]
        debug_log(f"Using MIDI port: {midi_port}")
    else:
        debug_log("ERROR: No MIDI output ports available!")
        sys.exit(1)
    
    # 실제 포트 목록에서 찾은 이름 사용
    output_port = mido.open_output(midi_port)
    debug_log(f"Successfully opened MIDI port: {midi_port}")
    
    # MIDI Note 정의
    # 컨트롤 명령어
    NOTE_START_MELODY = 0    # 멜로디 수신 모드 시작
    NOTE_START_CHORDS = 1    # 코드 수신 모드 시작
    NOTE_RECORD_BOTH = 2     # 멜로디+코드 함께 녹음
    NOTE_RECORD_MELODY = 3   # 멜로디만 녹음
    NOTE_RECORD_CHORDS = 4   # 코드만 녹음
    NOTE_RESET_DATA = 5      # 데이터 초기화
    
    # 비밥 생성 명령어
    NOTE_GENERATE = 0        # 비밥 솔로 및 코드 생성
    NOTE_LOAD_SOLO = 1       # 솔로 데이터 불러오기
    NOTE_LOAD_CHORDS = 2     # 코드 데이터 불러오기
    NOTE_RECORD_SOLO = 10    # 솔로 녹음
    NOTE_RECORD_CHORD = 11   # 코드 녹음
    NOTE_RECORD_BOTH = 12    # 솔로+코드 함께 녹음
    
    # 설정 변경 명령어
    NOTE_SET_ROOT = 20       # 루트 노트 변경
    NOTE_SET_TEMPO = 21      # 템포 변경
    NOTE_SET_COMPLEXITY = 22 # 복잡도 변경
    NOTE_PRINT_SETTINGS = 30 # 현재 설정 출력

    @mcp.tool()
    def list_midi_ports():
        """사용 가능한 MIDI 포트 목록 표시"""
        debug_log("\nAvailable MIDI Input Ports:")
        input_ports = mido.get_output_names()
        if not input_ports:
            debug_log("  No MIDI input ports found")
        else:
            for i, port in enumerate(input_ports):
                debug_log(f"  {i}: {port}")
        
        return input_ports

    @mcp.tool()
    def play():
        """FL Studio 재생 시작"""
        output_port.send(mido.Message('note_on', note=60, velocity=100))
        time.sleep(0.1)
        output_port.send(mido.Message('note_off', note=60, velocity=0))
        debug_log("Sent Play command")

    @mcp.tool()
    def stop():
        """FL Studio 재생 정지"""
        output_port.send(mido.Message('note_on', note=61, velocity=100))
        time.sleep(0.1)
        output_port.send(mido.Message('note_off', note=61, velocity=0))
        debug_log("Sent Stop command")

    @mcp.tool()
    def send_note(note, velocity=100, duration=0.01):
        """
        MIDI 노트 전송
        
        Args:
            note (str): MIDI 노트 번호
            velocity (str, optional): 노트 벨로시티 (0-127)
            duration (str, optional): 노트 길이 (초)
        """
        note_value = int(note)
        velocity_value = int(velocity)
        duration_value = float(duration)
        
        note_on = Message('note_on', note=note_value, velocity=velocity_value)
        output_port.send(note_on)
        time.sleep(duration_value)
        note_off = Message('note_off', note=note_value, velocity=0)
        output_port.send(note_off)
        debug_log(f"Sent MIDI note {note_value} (velocity: {velocity_value}, duration: {duration_value}s)")
        
        return f"Note {note_value} sent successfully"

    @mcp.tool()
    def send_melody(notes_data):
        """
        멜로디 노트 시퀀스 전송
        
        Args:
            notes_data (str): "note,velocity,length,position" 형식의 노트 데이터
                            (각 노트는 새 줄로 구분)
        """
        # 노트 데이터 문자열 파싱
        notes = []
        for line in notes_data.strip().split('\n'):
            if not line.strip():
                continue
                
            parts = line.strip().split(',')
            if len(parts) != 4:
                debug_log(f"Warning: Skipping invalid line: {line}")
                continue
                
            try:
                note = min(127, max(0, int(parts[0])))
                velocity = min(127, max(0, int(parts[1])))
                length = max(0, float(parts[2]))
                position = max(0, float(parts[3]))
                notes.append((note, velocity, length, position))
            except ValueError:
                debug_log(f"Warning: Skipping line with invalid values: {line}")
                continue
        
        if not notes:
            return "No valid notes found in input data"
        
        # 비밥 솔로 수신 모드 시작 (노트 0)
        send_midi_note(0)
        time.sleep(0.1)
        
        # 노트 수 전송
        send_midi_note(min(127, len(notes)))
        time.sleep(0.1)
        
        # MIDI 데이터 배열 생성 (노트당 6개 값)
        midi_data = []
        for note, velocity, length, position in notes:
            # 1. 노트 값 (0-127)
            midi_data.append(note)
            
            # 2. 벨로시티 값 (0-127)
            midi_data.append(velocity)
            
            # 3. 길이 정수부 (0-127)
            length_whole = min(127, int(length))
            midi_data.append(length_whole)
            
            # 4. 길이 소수부 (0-9)
            length_decimal = int(round((length - length_whole) * 10)) % 10
            midi_data.append(length_decimal)
            
            # 5. 위치 정수부 (0-127)
            position_whole = min(127, int(position))
            midi_data.append(position_whole)
            
            # 6. 위치 소수부 (0-9)
            position_decimal = int(round((position - position_whole) * 10)) % 10
            midi_data.append(position_decimal)
        
        # 모든 MIDI 데이터 값 전송
        for value in midi_data:
            send_midi_note(value)
            time.sleep(0.01)
        
        # 종료 신호 (노트 127)
        send_midi_note(127)

        return f"멜로디 전송 완료: {len(notes)}개 노트 ({len(midi_data)}개 MIDI 값)"

    @mcp.tool()
    def send_chord_progression(notes_data):
        """
        코드 진행 노트 시퀀스 전송
        
        Args:
            notes_data (str): "note,velocity,length,position" 형식의 노트 데이터
                            (각 노트는 새 줄로 구분)
        """
        # 노트 데이터 문자열 파싱
        notes = []
        for line in notes_data.strip().split('\n'):
            if not line.strip():
                continue
                
            parts = line.strip().split(',')
            if len(parts) != 4:
                debug_log(f"Warning: Skipping invalid line: {line}")
                continue
                
            try:
                note = min(127, max(0, int(parts[0])))
                velocity = min(127, max(0, int(parts[1])))
                length = max(0, float(parts[2]))
                position = max(0, float(parts[3]))
                notes.append((note, velocity, length, position))
            except ValueError:
                debug_log(f"Warning: Skipping line with invalid values: {line}")
                continue
        
        if not notes:
            return "No valid notes found in input data"
        
        # 코드 수신 모드 시작 (노트 1)
        send_midi_note(1)
        time.sleep(0.1)
        
        # 노트 수 전송
        send_midi_note(min(127, len(notes)))
        time.sleep(0.1)
        
        # MIDI 데이터 배열 생성 (노트당 6개 값)
        midi_data = []
        for note, velocity, length, position in notes:
            # 1. 노트 값 (0-127)
            midi_data.append(note)
            
            # 2. 벨로시티 값 (0-127)
            midi_data.append(velocity)
            
            # 3. 길이 정수부 (0-127)
            length_whole = min(127, int(length))
            midi_data.append(length_whole)
            
            # 4. 길이 소수부 (0-9)
            length_decimal = int(round((length - length_whole) * 10)) % 10
            midi_data.append(length_decimal)
            
            # 5. 위치 정수부 (0-127)
            position_whole = min(127, int(position))
            midi_data.append(position_whole)
            
            # 6. 위치 소수부 (0-9)
            position_decimal = int(round((position - position_whole) * 10)) % 10
            midi_data.append(position_decimal)
        
        # 모든 MIDI 데이터 값 전송
        for value in midi_data:
            send_midi_note(value)
            time.sleep(0.01)
        
        # 종료 신호 (노트 127)
        send_midi_note(127)

        return f"코드 진행 전송 완료: {len(notes)}개 노트 ({len(midi_data)}개 MIDI 값)"

    @mcp.tool()
    def generate_bebop(root_note=60, scale_type="Bebop_Dominant", progression_type="ii-V-I", 
                       solo_complexity=0.7, chord_complexity=0.5, measures=8):
        """
        비밥 솔로 및 코드 진행 생성 및 전송
        
        Args:
            root_note (str): 루트 노트 MIDI 값 (기본값: 60 = C4)
            scale_type (str): 비밥 스케일 타입 (Bebop_Dominant, Bebop_Major, Bebop_Minor, Bebop_Melodic_Minor)
            progression_type (str): 코드 진행 타입 (ii-V-I, ii-V-i, I-vi-ii-V, iii-VI-ii-V, Bird_Blues)
            solo_complexity (str): 솔로 복잡도 (0.0-1.0)
            chord_complexity (str): 코드 복잡도 (0.0-1.0)
            measures (str): 생성할 마디 수
        """
        # 설정 값 변환
        root = int(root_note)
        solo_comp = float(solo_complexity)
        chord_comp = float(chord_complexity)
        measures_count = int(measures)
        
        # 노트 20 (루트 노트 설정) 전송
        send_midi_note(20)
        time.sleep(0.1)
        send_midi_note(root)
        time.sleep(0.1)
        
        # 노트 22 (복잡도 설정) 전송
        send_midi_note(22)
        time.sleep(0.1)
        solo_comp_midi = int(solo_comp * 127)
        send_midi_note(solo_comp_midi)
        time.sleep(0.1)
        chord_comp_midi = int(chord_comp * 127)
        send_midi_note(chord_comp_midi)
        time.sleep(0.1)
        
        # 비밥 생성 노트 (0) 전송
        send_midi_note(0)
        time.sleep(0.1)
        
        return f"비밥 생성 명령 전송 완료. 루트: {root}, 솔로 복잡도: {solo_comp}, 코드 복잡도: {chord_comp}"

    @mcp.tool()
    def record_melody():
        """솔로 멜로디 녹음 명령 전송"""
        send_midi_note(10)
        return "솔로 멜로디 녹음 명령 전송 완료"

    @mcp.tool()
    def record_chords():
        """코드 진행 녹음 명령 전송"""
        send_midi_note(11)
        return "코드 진행 녹음 명령 전송 완료"

    @mcp.tool()
    def record_both():
        """솔로와 코드 함께 녹음 명령 전송"""
        send_midi_note(12)
        return "솔로와 코드 함께 녹음 명령 전송 완료"

    @mcp.tool()
    def print_settings():
        """현재 설정 출력 명령 전송"""
        send_midi_note(30)
        return "현재 설정 출력 명령 전송 완료"

    def send_midi_note(note, velocity=100, duration=0.01):
        """MIDI 노트 온/오프 메시지 전송"""
        note_on = Message('note_on', note=note, velocity=velocity)
        output_port.send(note_on)
        time.sleep(duration)
        note_off = Message('note_off', note=note, velocity=0)
        output_port.send(note_off)
        debug_log(f"Sent MIDI note {note} (velocity: {velocity})")
        
    if __name__ == "__main__":
        # 서버 초기화 및 실행
        debug_log("Running Bebop MCP server with stdio transport...")
        mcp.run(transport='stdio')

except Exception as e:
    debug_log(f"ERROR initializing Bebop MCP: {e}")
    sys.exit(1)