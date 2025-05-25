# device_test.py
# name=Test Controller
# 간단한 비밥 솔로 전용 FL Studio 컨트롤러

import transport
import channels
import midi
import general
import time

# 전역 변수
receiving_notes = False
note_count = 0
midi_data = []
notes_array = []

def OnInit():
    """FL Studio 로드 시 초기화"""
    print("Simple Bebop Controller initialized")
    return

def OnDeInit():
    """FL Studio 종료 시"""
    print("Simple Bebop Controller deinitialized")
    return

def OnRefresh(flags):
    """상태 변경 시"""
    return

def OnMidiIn(event):
    """MIDI 입력 처리 (사용 안 함)"""
    return

def OnMidiMsg(event, timestamp=0):
    """MCP 서버에서 보낸 MIDI 메시지 처리"""
    global receiving_notes, note_count, midi_data, notes_array
    
    # 노트 온 메시지만 처리
    if event.status >= midi.MIDI_NOTEON and event.status < midi.MIDI_NOTEON + 16 and event.data2 > 0:
        note_value = event.data1
        
        # 시작 신호 (노트 0)
        if note_value == 0 and not receiving_notes:
            receiving_notes = True
            midi_data = []
            note_count = 0
            notes_array = []
            print("비밥 솔로 수신 시작")
            event.handled = True
            return
        
        # 수신 모드가 아니면 무시
        if not receiving_notes:
            return
        
        # 노트 개수 설정 (두 번째 메시지)
        if note_count == 0:
            note_count = note_value
            print(f"{note_count}개 노트 수신 예정")
            event.handled = True
            return
        
        # 종료 신호 (노트 127)
        if note_value == 127:
            print("비밥 솔로 수신 완료")
            receiving_notes = False
            
            if notes_array:
                print(f"총 {len(notes_array)}개 노트 녹음 시작")
                record_bebop_solo(notes_array)
            
            event.handled = True
            return
        
        # MIDI 데이터 수집
        midi_data.append(note_value)
        
        # 6개 값마다 노트 완성 (노트, 벨로시티, 길이_정수, 길이_소수, 위치_정수, 위치_소수)
        if len(midi_data) % 6 == 0:
            i = len(midi_data) - 6
            note = midi_data[i]
            velocity = midi_data[i+1]
            length_whole = midi_data[i+2]
            length_decimal = midi_data[i+3]
            position_whole = midi_data[i+4]
            position_decimal = midi_data[i+5]
            
            # 길이와 위치 계산
            length = length_whole + (length_decimal / 10.0)
            position = position_whole + (position_decimal / 10.0)
            
            # 노트 배열에 추가
            notes_array.append((note, velocity, length, position))
            print(f"노트 추가: {note} (vel={velocity}, len={length:.1f}, pos={position:.1f})")
        
        event.handled = True

def record_bebop_solo(notes_data):
    """비밥 솔로를 FL Studio 피아노 롤에 녹음"""
    # 재생 중이면 정지
    if transport.isPlaying():
        transport.stop()
    
    # 시작 위치로 이동
    transport.setSongPos(0, 2)
    
    # 현재 선택된 채널 사용
    channel = channels.selectedChannel()
    print(f"채널 {channel}에 녹음 중...")
    
    # 위치별로 노트 그룹화
    position_groups = {}
    for note_data in notes_data:
        position = note_data[3]  # 위치
        if position not in position_groups:
            position_groups[position] = []
        position_groups[position].append(note_data)
    
    # 각 위치에서 노트 녹음
    for position in sorted(position_groups.keys()):
        notes_at_position = position_groups[position]
        record_notes_at_position(notes_at_position, position, channel)
    
    print("비밥 솔로 녹음 완료!")

def record_notes_at_position(notes_at_position, position, channel):
    """특정 위치에서 노트들 녹음"""
    # 가장 긴 노트 길이 찾기
    max_length = max(note[2] for note in notes_at_position)
    
    # 재생 위치 설정
    ppq = general.getRecPPQ()
    position_ticks = int(position * ppq)
    transport.setSongPos(position_ticks, 2)
    
    # 녹음 모드 시작
    if not transport.isRecording():
        transport.record()
    
    # 재생 시작
    transport.start()
    
    # 모든 노트 동시 재생
    for note, velocity, length, _ in notes_at_position:
        channels.midiNoteOn(channel, note, velocity)
    
    # 템포 가져오기
    try:
        import mixer
        tempo = mixer.getCurrentTempo() / 1000
    except:
        tempo = 120  # 기본 템포
    
    # 대기 시간 계산
    wait_time = (max_length * 60) / tempo
    time.sleep(wait_time)
    
    # 노트 오프
    for note, _, _, _ in notes_at_position:
        channels.midiNoteOn(channel, note, 0)
    
    # 재생 정지
    transport.stop()
    
    # 녹음 모드 종료
    if transport.isRecording():
        transport.record()
    
    # 짧은 대기
    time.sleep(0.1)

def OnTransport(isPlaying):
    """재생 상태 변경"""
    return

def OnTempoChange(tempo):
    """템포 변경"""
    return