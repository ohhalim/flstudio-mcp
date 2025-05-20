# device_test.py
# name=간결한 FL Studio 컨트롤러

import transport
import ui
import midi
import channels
import patterns
import general
import time
import sys

# 전역 변수
current_pattern = 0
current_channel = 0

# 노트 수신 관련 변수
receiving_mode = False
note_count = 0
values_received = 0
midi_data = []
midi_notes_array = []

# 초기화 함수: 스크립트가 로드될 때 호출
def OnInit():
    """FL Studio에서 스크립트가 로드될 때 호출"""
    print("FL Studio MIDI 컨트롤러 초기화됨")
    return

# 종료 함수: 스크립트가 언로드될 때 호출
def OnDeInit():
    """FL Studio에서 스크립트가 언로드될 때 호출"""
    print("FL Studio MIDI 컨트롤러 종료됨")
    return

# 상태 변경 시 호출되는 함수
def OnRefresh(flags):
    """FL Studio의 상태가 변경되거나 새로고침이 필요할 때 호출"""
    return

# MIDI 입력 처리 함수
def OnMidiMsg(event, timestamp=0):
    """MIDI 메시지가 수신될 때 호출"""
    global receiving_mode, note_count, values_received, midi_data, midi_notes_array
    
    # 노트 온 메시지만 처리 (벨로시티 > 0)
    if event.status >= midi.MIDI_NOTEON and event.status < midi.MIDI_NOTEON + 16 and event.data2 > 0:
        note_value = event.data1
        
        # 노트 0: 수신 모드 시작
        if note_value == 0 and not receiving_mode:
            receiving_mode = True
            print("MIDI 노트 수신 시작")
            midi_data = []
            note_count = 0
            values_received = 0
            midi_notes_array = []
            event.handled = True
            return
        
        # 수신 모드가 아니면 종료
        if not receiving_mode:
            return
        
        # 두 번째 메시지: 노트 수 지정
        if note_count == 0:
            note_count = note_value
            print(f"{note_count}개 노트 수신 예정")
            event.handled = True
            return
        
        # 노트 127: 수신 종료 신호
        if note_value == 127:
            print(f"종료 신호 수신")
            receiving_mode = False
            if midi_notes_array:
                print(f"모든 {len(midi_notes_array)}개 노트 수신 완료")
                record_notes_batch(midi_notes_array)
            event.handled = True
            return
        
        # 모든 후속 메시지는 MIDI 값 (노트당 6개)
        midi_data.append(note_value)
        values_received += 1
        
        # 완성된 노트 처리 (6개 값마다)
        if len(midi_data) >= 6 and len(midi_data) % 6 == 0:
            # 마지막 완성 노트 처리
            i = len(midi_data) - 6
            note = midi_data[i]
            velocity = midi_data[i+1]
            length_whole = midi_data[i+2]
            length_decimal = midi_data[i+3]
            position_whole = midi_data[i+4]
            position_decimal = midi_data[i+5]
            
            # 전체 값 계산
            length = length_whole + (length_decimal / 10.0)
            position = position_whole + (position_decimal / 10.0)
            
            # 노트 배열에 추가
            midi_notes_array.append((note, velocity, length, position))
            print(f"노트 추가: 노트={note}, 벨로시티={velocity}, 길이={length:.1f}, 위치={position:.1f}")
            
            # 모든 예상 노트를 받았으면 수신 모드 종료
            if len(midi_notes_array) >= note_count:
                print(f"모든 {note_count}개 노트 수신 완료")
                receiving_mode = False
                record_notes_batch(midi_notes_array)
                event.handled = True
                return
        
        event.handled = True

# 재생 상태 변화 처리 함수
def OnTransport(isPlaying):
    """재생 상태가 변경될 때 호출 (재생/정지)"""
    print(f"재생 상태 변경: {'재생 중' if isPlaying else '정지됨'}")
    return

# 템포 변경 처리 함수
def OnTempoChange(tempo):
    """템포가 변경될 때 호출"""
    print(f"템포 변경: {tempo} BPM")
    return

# 노트 일괄 녹음 함수
def record_notes_batch(notes_array):
    """
    FL Studio에 노트 일괄 녹음 (동시 노트 처리)
    
    Args:
        notes_array: (노트, 벨로시티, 길이_비트, 위치_비트) 튜플 목록
    """
    # 시작 위치별로 노트 정렬
    sorted_notes = sorted(notes_array, key=lambda x: x[3])
    
    # 시작 위치별로 노트 그룹화
    position_groups = {}
    for note in sorted_notes:
        position = note[3]  # 위치_비트는 4번째 요소 (인덱스 3)
        if position not in position_groups:
            position_groups[position] = []
        position_groups[position].append(note)
    
    # 각 위치 그룹 처리
    positions = sorted(position_groups.keys())
    for position in positions:
        notes_at_position = position_groups[position]
        
        # 이 그룹에서 가장 긴 노트 찾기
        max_length = max(note[2] for note in notes_at_position)
        
        # 재생 중이면 먼저 정지
        if transport.isPlaying():
            transport.stop()
        
        # 현재 채널 가져오기
        channel = channels.selectedChannel()
        
        # 프로젝트의 PPQ(분기별 펄스) 가져오기
        ppq = general.getRecPPQ()
        
        # 비트를 틱으로 변환
        position_ticks = int(position * ppq)
        
        # 재생 위치 설정
        transport.setSongPos(position_ticks, 2)  # 2 = SONGLENGTH_ABSTICKS
        
        # 필요시 녹음 모드 전환
        if not transport.isRecording():
            transport.record()
        
        print(f"위치 {position}에서 {len(notes_at_position)}개 동시 노트 녹음")
        
        # 녹음 시작을 위한 재생 시작
        transport.start()
        
        # 이 위치의 모든 노트 동시 녹음
        for note, velocity, length, _ in notes_at_position:
            channels.midiNoteOn(channel, note, velocity)
        
        # 현재 템포 가져오기
        try:
            import mixer
            tempo = mixer.getCurrentTempo()
            tempo = tempo/1000
        except (ImportError, AttributeError):
            tempo = 120  # 기본값
            
        print(f"템포 사용: {tempo} BPM")
        
        # 가장 긴 노트 기준으로 대기 시간 계산
        seconds_to_wait = (max_length * 60) / tempo
        
        print(f"{seconds_to_wait:.2f}초 대기 중...")
        
        # 계산된 시간 대기
        time.sleep(seconds_to_wait)
        
        # 모든 노트에 대한 노트 오프 이벤트 전송
        for note, _, _, _ in notes_at_position:
            channels.midiNoteOn(channel, note, 0)
        
        # 재생 정지
        transport.stop()
        
        # 녹음 모드 활성화된 경우 종료
        if transport.isRecording():
            transport.record()
        
        # 녹음 간 짧은 일시 정지
        time.sleep(0.2)
    
    print("모든 노트 녹음 완료")
    
    # 처음으로 돌아가기
    transport.setSongPos(0, 2)