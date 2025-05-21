# fl_bebop_controller.py
# name=비밥 솔로 & 코드 컨트롤러

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
MELODY_CHANNEL = 0  # 솔로 라인용 채널
CHORD_CHANNEL = 1   # 코드 컴핑용 채널

# 노트 수신 모드 열거형
class ReceiveMode:
    IDLE = 0        # 대기 상태
    MELODY = 1      # 멜로디/솔로 노트 수신 중
    CHORDS = 2      # 코드 노트 수신 중

# 노트 수신 관련 변수
receive_mode = ReceiveMode.IDLE
note_count = 0
values_received = 0
midi_data = []
melody_notes = []   # 멜로디/솔로 노트 저장
chord_notes = []    # 코드 노트 저장

# 초기화 함수: 스크립트가 로드될 때 호출
def OnInit():
    """FL Studio에서 스크립트가 로드될 때 호출"""
    print("비밥 솔로 & 코드 컨트롤러 초기화됨")
    # 채널 0을 멜로디용, 채널 1을 코드용으로 설정
    try:
        channels.setChannelName(MELODY_CHANNEL, "비밥 솔로")
        channels.setChannelName(CHORD_CHANNEL, "코드 컴핑")
        print(f"채널 설정 완료: 채널 {MELODY_CHANNEL}=비밥 솔로, 채널 {CHORD_CHANNEL}=코드 컴핑")
    except:
        print("채널 이름 설정 실패")
    return

# 종료 함수: 스크립트가 언로드될 때 호출
def OnDeInit():
    """FL Studio에서 스크립트가 언로드될 때 호출"""
    print("비밥 솔로 & 코드 컨트롤러 종료됨")
    return

# 상태 변경 시 호출되는 함수
def OnRefresh(flags):
    """FL Studio의 상태가 변경되거나 새로고침이 필요할 때 호출"""
    return

# MIDI 입력 처리 함수
def OnMidiMsg(event, timestamp=0):
    """MIDI 메시지가 수신될 때 호출"""
    global receive_mode, note_count, values_received, midi_data, melody_notes, chord_notes
    
    # 노트 온 메시지만 처리 (벨로시티 > 0)
    if event.status >= midi.MIDI_NOTEON and event.status < midi.MIDI_NOTEON + 16 and event.data2 > 0:
        note_value = event.data1
        
        # === 컨트롤 노트 처리 (0-10 범위의 노트) ===
        
        # 노트 0: 멜로디 수신 모드 시작
        if note_value == 0 and receive_mode == ReceiveMode.IDLE:
            receive_mode = ReceiveMode.MELODY
            print("비밥 솔로 노트 수신 시작")
            midi_data = []
            note_count = 0
            values_received = 0
            melody_notes = []
            event.handled = True
            return
            
        # 노트 1: 코드 수신 모드 시작
        if note_value == 1 and receive_mode == ReceiveMode.IDLE:
            receive_mode = ReceiveMode.CHORDS
            print("코드 노트 수신 시작")
            midi_data = []
            note_count = 0
            values_received = 0
            chord_notes = []
            event.handled = True
            return
            
        # 노트 2: 모든 수신된 노트 녹음 (멜로디 + 코드 함께)
        if note_value == 2 and receive_mode == ReceiveMode.IDLE:
            if melody_notes and chord_notes:
                print("멜로디와 코드 함께 녹음 시작")
                record_melody_and_chords()
            else:
                print("녹음할 멜로디 또는 코드 데이터가 없습니다")
            event.handled = True
            return
            
        # 노트 3: 멜로디만 녹음
        if note_value == 3 and receive_mode == ReceiveMode.IDLE:
            if melody_notes:
                print("멜로디만 녹음 시작")
                record_notes_batch(melody_notes, MELODY_CHANNEL)
            else:
                print("녹음할 멜로디 데이터가 없습니다")
            event.handled = True
            return
            
        # 노트 4: 코드만 녹음
        if note_value == 4 and receive_mode == ReceiveMode.IDLE:
            if chord_notes:
                print("코드만 녹음 시작")
                record_notes_batch(chord_notes, CHORD_CHANNEL)
            else:
                print("녹음할 코드 데이터가 없습니다")
            event.handled = True
            return
            
        # 노트 5: 모든 데이터 초기화
        if note_value == 5 and receive_mode == ReceiveMode.IDLE:
            melody_notes = []
            chord_notes = []
            print("모든 노트 데이터가 초기화되었습니다")
            event.handled = True
            return
        
        # === 수신 모드 상태에 따른 데이터 처리 ===
        
        # 수신 모드가 아니면 종료
        if receive_mode == ReceiveMode.IDLE:
            return
        
        # 두 번째 메시지: 노트 수 지정
        if note_count == 0:
            note_count = note_value
            print(f"{note_count}개 노트 수신 예정")
            event.handled = True
            return
        
        # 노트 127: 수신 종료 신호
        if note_value == 127:
            current_mode = "비밥 솔로" if receive_mode == ReceiveMode.MELODY else "코드"
            print(f"{current_mode} 종료 신호 수신")
            
            notes_array = melody_notes if receive_mode == ReceiveMode.MELODY else chord_notes
            if notes_array:
                print(f"모든 {len(notes_array)}개 {current_mode} 노트 수신 완료")
            
            receive_mode = ReceiveMode.IDLE
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
            
            # 노트 데이터 추가
            note_data = (note, velocity, length, position)
            
            # 현재 모드에 따라 적절한 배열에 추가
            if receive_mode == ReceiveMode.MELODY:
                melody_notes.append(note_data)
                print(f"솔로 노트 추가: 노트={note}, 벨로시티={velocity}, 길이={length:.1f}, 위치={position:.1f}")
            else:
                chord_notes.append(note_data)
                print(f"코드 노트 추가: 노트={note}, 벨로시티={velocity}, 길이={length:.1f}, 위치={position:.1f}")
            
            # 모든 예상 노트를 받았으면 수신 모드 종료
            current_notes = melody_notes if receive_mode == ReceiveMode.MELODY else chord_notes
            if len(current_notes) >= note_count:
                mode_name = "비밥 솔로" if receive_mode == ReceiveMode.MELODY else "코드"
                print(f"모든 {note_count}개 {mode_name} 노트 수신 완료")
                receive_mode = ReceiveMode.IDLE
        
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
def record_notes_batch(notes_array, channel_index):
    """
    FL Studio에 노트 일괄 녹음 (동시 노트 처리)
    
    Args:
        notes_array: (노트, 벨로시티, 길이_비트, 위치_비트) 튜플 목록
        channel_index: 녹음할 채널 인덱스
    """
    if not notes_array:
        print("녹음할 노트가 없습니다")
        return
        
    # 시작 위치별로 노트 정렬
    sorted_notes = sorted(notes_array, key=lambda x: x[3])
    
    # 시작 위치별로 노트 그룹화
    position_groups = {}
    for note in sorted_notes:
        position = note[3]  # 위치_비트는 4번째 요소 (인덱스 3)
        if position not in position_groups:
            position_groups[position] = []
        position_groups[position].append(note)
    
    # 채널 선택
    channels.selectOneChannel(channel_index)
    
    # 각 위치 그룹 처리
    positions = sorted(position_groups.keys())
    for position in positions:
        notes_at_position = position_groups[position]
        
        # 이 그룹에서 가장 긴 노트 찾기
        max_length = max(note[2] for note in notes_at_position)
        
        # 재생 중이면 먼저 정지
        if transport.isPlaying():
            transport.stop()
        
        # 프로젝트의 PPQ(분기별 펄스) 가져오기
        ppq = general.getRecPPQ()
        
        # 비트를 틱으로 변환
        position_ticks = int(position * ppq)
        
        # 재생 위치 설정
        transport.setSongPos(position_ticks, 2)  # 2 = SONGLENGTH_ABSTICKS
        
        # 필요시 녹음 모드 전환
        if not transport.isRecording():
            transport.record()
        
        print(f"채널 {channel_index}의 위치 {position}에서 {len(notes_at_position)}개 노트 녹음")
        
        # 녹음 시작을 위한 재생 시작
        transport.start()
        
        # 이 위치의 모든 노트 동시 녹음
        for note, velocity, length, _ in notes_at_position:
            channels.midiNoteOn(channel_index, note, velocity)
        
        # 현재 템포 가져오기
        try:
            import mixer
            tempo = mixer.getCurrentTempo() / 1000
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
            channels.midiNoteOn(channel_index, note, 0)
        
        # 재생 정지
        transport.stop()
        
        # 녹음 모드 활성화된 경우 종료
        if transport.isRecording():
            transport.record()
        
        # 녹음 간 짧은 일시 정지
        time.sleep(0.2)
    
    print(f"채널 {channel_index}에 모든 노트 녹음 완료")

# 멜로디와 코드를 함께 녹음하는 함수
def record_melody_and_chords():
    """멜로디와 코드 데이터를 동기화하여 함께 녹음"""
    if not melody_notes or not chord_notes:
        print("멜로디 또는 코드 데이터가 없습니다")
        return
    
    # 모든 노트를 위치별로 병합하고 채널 정보 추가 (튜플: 노트, 벨로시티, 길이, 위치, 채널)
    all_notes = [(note, vel, length, pos, MELODY_CHANNEL) for note, vel, length, pos in melody_notes]
    all_notes.extend([(note, vel, length, pos, CHORD_CHANNEL) for note, vel, length, pos in chord_notes])
    
    # 위치별로 정렬
    all_notes.sort(key=lambda x: x[3])
    
    # 위치별로 그룹화
    position_groups = {}
    for note_data in all_notes:
        position = note_data[3]
        if position not in position_groups:
            position_groups[position] = []
        position_groups[position].append(note_data)
    
    # 각 위치 그룹 처리
    positions = sorted(position_groups.keys())
    for position in positions:
        notes_at_position = position_groups[position]
        
        # 이 그룹에서 가장 긴 노트 찾기
        max_length = max(note[2] for note in notes_at_position)
        
        # 재생 중이면 먼저 정지
        if transport.isPlaying():
            transport.stop()
        
        # 프로젝트의 PPQ(분기별 펄스) 가져오기
        ppq = general.getRecPPQ()
        
        # 비트를 틱으로 변환
        position_ticks = int(position * ppq)
        
        # 재생 위치 설정
        transport.setSongPos(position_ticks, 2)  # 2 = SONGLENGTH_ABSTICKS
        
        # 필요시 녹음 모드 전환
        if not transport.isRecording():
            transport.record()
        
        print(f"위치 {position}에서 {len(notes_at_position)}개 노트 녹음 (멜로디+코드)")
        
        # 녹음 시작을 위한 재생 시작
        transport.start()
        
        # 이 위치의 모든 노트 동시 녹음 (채널 구분)
        for note, velocity, length, _, channel in notes_at_position:
            channels.midiNoteOn(channel, note, velocity)
        
        # 현재 템포 가져오기
        try:
            import mixer
            tempo = mixer.getCurrentTempo() / 1000
        except (ImportError, AttributeError):
            tempo = 120  # 기본값
            
        # 가장 긴 노트 기준으로 대기 시간 계산
        seconds_to_wait = (max_length * 60) / tempo
        
        print(f"{seconds_to_wait:.2f}초 대기 중...")
        
        # 계산된 시간 대기
        time.sleep(seconds_to_wait)
        
        # 모든 노트에 대한 노트 오프 이벤트 전송 (채널 구분)
        for note, _, _, _, channel in notes_at_position:
            channels.midiNoteOn(channel, note, 0)
        
        # 재생 정지
        transport.stop()
        
        # 녹음 모드 활성화된 경우 종료
        if transport.isRecording():
            transport.record()
        
        # 녹음 간 짧은 일시 정지
        time.sleep(0.2)
    
    print("멜로디와 코드 함께 녹음 완료")

# 비밥 솔로 생성 도우미 함수
def generate_bebop_solo():
    """비밥 스타일의 솔로 라인을 자동 생성"""
    print("아직 구현되지 않은 기능입니다")
    # 향후 구현: 비밥 스케일, 패턴 등을 기반으로 솔로 자동 생성

# 코드 생성 도우미 함수
def generate_chord_comping():
    """재즈 코드 컴핑 패턴 자동 생성"""
    print("아직 구현되지 않은 기능입니다")
    # 향후 구현: 재즈 코드 진행과 리듬 패턴 자동 생성