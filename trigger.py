import sys
import time
import mido
from mido import Message
from typing import List, Tuple, Optional

# FastMCP 서버 클래스
class FastMCP:
    def __init__(self, name="flstudio"):
        self.name = name
        self.tools = {}
        self.output_port = None
        self.midi_port_name = None
        
    def tool(self):
        """도구 등록 데코레이터"""
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator
        
    def run(self, transport='stdio'):
        """서버 실행"""
        if transport == 'stdio':
            self._run_stdio()
            
    def _run_stdio(self):
        """표준 입출력을 통한 서버 실행"""
        import json
        import sys
        
        # 사용 가능한 도구 목록 출력
        sys.stderr.write(f"MCP 서버 실행 중: {self.name}\n")
        sys.stderr.write(f"사용 가능한 도구: {list(self.tools.keys())}\n")
        sys.stderr.flush()
        
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                    
                request = json.loads(line)
                function_name = request.get('name')
                arguments = request.get('arguments', {})
                
                if function_name in self.tools:
                    result = self.tools[function_name](**arguments)
                    response = {
                        'result': result
                    }
                    sys.stdout.write(json.dumps(response) + '\n')
                    sys.stdout.flush()
                else:
                    sys.stderr.write(f"함수를 찾을 수 없음: {function_name}\n")
                    sys.stderr.flush()
                    
            except Exception as e:
                sys.stderr.write(f"오류 발생: {e}\n")
                sys.stderr.flush()

# 메인 서버 구현
def run_server():
    try:
        # 서버 초기화
        log("FL Studio MCP 서버 시작...")
        
        # 사용 가능한 MIDI 포트 확인
        available_ports = mido.get_output_names()
        log(f"사용 가능한 MIDI 포트: {available_ports}")
        
        # FastMCP 서버 초기화
        mcp = FastMCP("flstudio")
        
        # MIDI 포트 연결
        if available_ports:
            midi_port = available_ports[0]
            log(f"MIDI 포트 사용: {midi_port}")
            output_port = mido.open_output(midi_port)
            log(f"MIDI 포트 연결 성공: {midi_port}")
        else:
            log("오류: 사용 가능한 MIDI 출력 포트가 없습니다!")
            sys.exit(1)
        
        # MIDI 노트 매핑
        NOTE_PLAY = 60          # C3
        NOTE_STOP = 61          # C#3
        
        # 도구 정의: MIDI 포트 목록
        @mcp.tool()
        def list_midi_ports():
            """사용 가능한 모든 MIDI 입력 포트 목록 표시"""
            return mido.get_output_names()
        
        # 도구 정의: 재생
        @mcp.tool()
        def play():
            """FL Studio에서 재생을 시작하는 MIDI 메시지 전송"""
            output_port.send(Message('note_on', note=NOTE_PLAY, velocity=100))
            time.sleep(0.1)
            output_port.send(Message('note_off', note=NOTE_PLAY, velocity=0))
            log("재생 명령 전송")
            return "재생 시작"
        
        # 도구 정의: 정지
        @mcp.tool()
        def stop():
            """FL Studio에서 재생을 정지하는 MIDI 메시지 전송"""
            output_port.send(Message('note_on', note=NOTE_STOP, velocity=100))
            time.sleep(0.1)
            output_port.send(Message('note_off', note=NOTE_STOP, velocity=0))
            log("정지 명령 전송")
            return "재생 정지"
        
        # 도구 정의: 멜로디 전송
        @mcp.tool()
        def send_melody(notes_data: str):
            """
            FL Studio로 타이밍 정보가 포함된 MIDI 노트 시퀀스 전송
            
            Args:
                notes_data (str): "노트,벨로시티,길이,위치" 형식의 노트 데이터 문자열
                                각 노트는 새 줄로 구분
            """
            # 노트 파싱
            notes = []
            for line in notes_data.strip().split('\n'):
                if not line.strip():
                    continue
                
                parts = line.strip().split(',')
                if len(parts) != 4:
                    log(f"경고: 유효하지 않은 줄 건너뜀: {line}")
                    continue
                
                try:
                    note = min(127, max(0, int(parts[0])))
                    velocity = min(127, max(0, int(parts[1])))
                    length = max(0, float(parts[2]))
                    position = max(0, float(parts[3]))
                    notes.append((note, velocity, length, position))
                except ValueError:
                    log(f"경고: 유효하지 않은 값이 있는 줄 건너뜀: {line}")
                    continue
            
            if not notes:
                return "입력 데이터에서 유효한 노트를 찾을 수 없음"
            
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
            
            # MIDI 전송 시작
            log(f"{len(notes)}개 노트 전송 ({len(midi_data)} MIDI 값)...")
            
            # 시작 신호 (노트 0)
            send_midi_note(output_port, 0)
            time.sleep(0.01)
            
            # 노트 총 개수 전송
            send_midi_note(output_port, min(127, len(notes)))
            time.sleep(0.01)
            
            # 모든 MIDI 데이터 값 전송
            for value in midi_data:
                send_midi_note(output_port, value)
            
            # 종료 신호 (노트 127)
            send_midi_note(output_port, 127)
            
            return f"멜로디 전송 완료: {len(notes)}개 노트({len(midi_data)} MIDI 값) FL Studio로 전송됨"
        
        # 도구 정의: MIDI 노트 수신
        @mcp.tool()
        def receive_midi_note(note_data: str):
            """
            외부 키보드에서 MIDI 노트 데이터를 수신하고 처리
            
            Args:
                note_data (str): "노트,벨로시티,길이,위치" 형식의 노트 데이터 문자열
                                각 노트는 새 줄로 구분
            """
            notes = []
            for line in note_data.strip().split('\n'):
                if not line.strip():
                    continue
                
                parts = line.strip().split(',')
                if len(parts) != 4:
                    log(f"경고: 유효하지 않은 줄 건너뜀: {line}")
                    continue
                
                try:
                    note = min(127, max(0, int(parts[0])))
                    velocity = min(127, max(0, int(parts[1])))
                    length = max(0, float(parts[2]))
                    position = max(0, float(parts[3]))
                    notes.append((note, velocity, length, position))
                except ValueError:
                    log(f"경고: 유효하지 않은 값이 있는 줄 건너뜀: {line}")
                    continue
            
            if not notes:
                return "입력 데이터에서 유효한 노트를 찾을 수 없음"
            
            # 수신된 노트 처리
            for note, velocity, length, _ in notes:
                send_midi_note(output_port, note, velocity, length)
                
            return f"{len(notes)}개 노트 처리됨"
        
        # 도구 정의: MIDI 노트 전송
        @mcp.tool()
        def send_midi_note(note, velocity=100, duration=0.01):
            """지정된 지속 시간으로 MIDI 노트 온/오프 메시지 전송"""
            output_port.send(Message('note_on', note=int(note), velocity=int(velocity)))
            time.sleep(float(duration))
            output_port.send(Message('note_off', note=int(note), velocity=0))
            log(f"MIDI 노트 {note} 전송됨")
            return f"노트 {note} 전송됨"
        
        # 서버 실행
        log("stdio 전송으로 MCP 서버 실행...")
        mcp.run(transport='stdio')
        
    except Exception as e:
        log(f"FL Studio MCP 초기화 오류: {e}")
        sys.exit(1)

# 유틸리티 함수: 디버그 로그
def log(message):
    """stderr에 디버그 메시지 출력"""
    print(message, file=sys.stderr, flush=True)

# MIDI 노트 전송 헬퍼 함수
def send_midi_note(port, note, velocity=100, duration=0.01):
    """MIDI 포트로 노트 온/오프 메시지 전송"""
    port.send(Message('note_on', note=note, velocity=velocity))
    time.sleep(duration)
    port.send(Message('note_off', note=note, velocity=0))

# 메인 실행 부분
if __name__ == "__main__":
    run_server()