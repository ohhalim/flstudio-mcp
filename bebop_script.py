# bebop_script.py
# name=비밥 솔로 & 코드 통합기

import transport
import ui
import midi
import channels
import patterns
import general
import time
import sys
import os
import json

# 비밥 생성기 가져오기 (같은 디렉토리에 있어야 함)
try:
    from bebop_generator import BebopGenerator
    HAS_GENERATOR = True
except ImportError:
    print("비밥 생성기를 불러올 수 없습니다. 기본 기능만 작동합니다.")
    HAS_GENERATOR = False

# 전역 변수
MELODY_CHANNEL = 0  # 솔로 라인용 채널
CHORD_CHANNEL = 1   # 코드 컴핑용 채널
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "bebop_settings.json")

# 기본 설정
settings = {
    "root_note": 60,     # C4
    "tempo": 160,        # 160 BPM
    "measures": 8,       # 8마디
    "scale_type": "Bebop_Dominant",
    "progression_type": "ii-V-I",
    "solo_complexity": 0.7,
    "chord_complexity": 0.5,
    "range_octaves": 2,
    "last_generated_file": ""
}

# 설정 저장 및 로드 함수
def save_settings():
    """설정을 JSON 파일로 저장"""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        print("설정이 저장되었습니다.")
    except Exception as e:
        print(f"설정 저장 오류: {e}")

def load_settings():
    """저장된 설정 불러오기"""
    global settings
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                loaded_settings = json.load(f)
                settings.update(loaded_settings)
            print("설정을 불러왔습니다.")
        else:
            print("저장된 설정이 없어 기본값을 사용합니다.")
    except Exception as e:
        print(f"설정 로드 오류: {e}")

# 노트 수신 관련 변수
receiving_mode = False
note_count = 0
values_received = 0
midi_data = []
solo_notes = []   # 멜로디/솔로 노트 저장
chord_notes = []  # 코드 노트 저장

# 초기화 함수
def OnInit():
    """FL Studio에서 스크립트가 로드될 때 호출"""
    print("비밥 솔로 & 코드 통합기 초기화됨")
    
    # 설정 로드
    load_settings()
    
    # 채널 설정
    try:
        channels.setChannelName(MELODY_CHANNEL, "비밥 솔로")
        channels.setChannelName(CHORD_CHANNEL, "코드 컴핑")
        print(f"채널 설정 완료: 채널 {MELODY_CHANNEL}=비밥 솔로, 채널 {CHORD_CHANNEL}=코드 컴핑")
    except:
        print("채널 이름 설정 실패")
    return

# 종료 함수
def OnDeInit():
    """FL Studio에서 스크립트가 언로드될 때 호출"""
    # 설정 저장
    save_settings()
    print("비밥 솔로 & 코드 통합기 종료됨")
    return

# MIDI 입력 처리 함수
def OnMidiMsg(event, timestamp=0):
    """
    MIDI 메시지가 수신될 때 호출
    
    MIDI 컨트롤러에서 다음 노트를 사용하여 스크립트 제어:
    - 노트 0: 솔로/코드 생성 모드 시작
    - 노트 1: 솔로 데이터 불러오기 모드
    - 노트 2: 코드 데이터 불러오기 모드 
    - 노트 10: 솔로 녹음
    - 노트 11: 코드 녹음
    - 노트 12: 솔로+코드 함께 녹음
    - 노트 20: 루트 노트 변경 모드
    - 노트 21: 템포 변경 모드
    - 노트 22: 복잡도 변경 모드
    - 노트 30: 현재 설정 출력
    """
    global receiving_mode, note_count, values_received, midi_data, solo_notes, chord_notes
    
    # 노트 온 메시지만 처리 (벨로시티 > 0)
    if event.status >= midi.MIDI_NOTEON and event.status < midi.MIDI_NOTEON + 16 and event.data2 > 0:
        note_value = event.data1
        
        # === 컨트롤 노트 처리 ===
        
        # 노트 0: 비밥 솔로 및 코드 생성
        if note_value == 0 and not receiving_mode and HAS_GENERATOR:
            print("비밥 솔로 및 코드 생성 시작...")
            generate_bebop_data()
            event.handled = True
            return
            
        # 노트 1: 솔로 데이터 불러오기
        if note_value == 1 and not receiving_mode:
            print("솔로 데이터 불러오기...")
            if settings["last_generated_file"] and os.path.exists(settings["last_generated_file"]):
                load_solo_from_file(settings["last_generated_file"])
            else:
                print("불러올 파일이 없습니다. 먼저 비밥 솔로를 생성하세요.")
            event.handled = True
            return
            
        # 노트 2: 코드 데이터 불러오기
        if note_value == 2 and not receiving_mode:
            print("코드 데이터 불러오기...")
            if settings["last_generated_file"] and os.path.exists(settings["last_generated_file"]):
                load_chords_from_file(settings["last_generated_file"])
            else:
                print("불러올 파일이 없습니다. 먼저 비밥 솔로를 생성하세요.")
            event.handled = True
            return
            
        # 노트 10: 솔로 녹음
        if note_value == 10 and not receiving_mode:
            if solo_notes:
                print("솔로 라인 녹음 시작...")
                record_notes_batch(solo_notes, MELODY_CHANNEL)
            else:
                print("녹음할 솔로 데이터가 없습니다. 먼저 비밥 솔로를 생성하거나 불러오세요.")
            event.handled = True
            return
            
        # 노트 11: 코드 녹음
        if note_value == 11 and not receiving_mode:
            if chord_notes:
                print("코드 컴핑 녹음 시작...")
                record_notes_batch(chord_notes, CHORD_CHANNEL)
            else:
                print("녹음할 코드 데이터가 없습니다. 먼저 비밥 코드를 생성하거나 불러오세요.")
            event.handled = True
            return
            
        # 노트 12: 솔로+코드 함께 녹음
        if note_value == 12 and not receiving_mode:
            if solo_notes and chord_notes:
                print("솔로와 코드 함께 녹음 시작...")
                record_melody_and_chords()
            else:
                print("녹음할 솔로 또는 코드 데이터가 없습니다.")
            event.handled = True
            return
            
        # 노트 20: 루트 노트 변경 (다음 노트가 루트 노트가 됨)
        if note_value == 20 and not receiving_mode:
            print("루트 노트 변경 모드. 다음 노트가 새 루트 노트가 됩니다...")
            receiving_mode = "root_note"
            event.handled = True
            return
            
        # 노트 21: 템포 변경 (다음 노트 값이 템포의 약수가 됨)
        if note_value == 21 and not receiving_mode:
            print("템포 변경 모드. 다음 노트 값 * 2가 템포가 됩니다...")
            receiving_mode = "tempo"
            event.handled = True
            return
            
        # 노트 22: 복잡도 변경 (다음 노트 값이 복잡도 지정)
        if note_value == 22 and not receiving_mode:
            print("복잡도 변경 모드. 다음 두 노트가 각각 솔로와 코드 복잡도를 지정합니다...")
            receiving_mode = "complexity_solo"
            event.handled = True
            return
            
        # 노트 30: 현재 설정 출력
        if note_value == 30 and not receiving_mode:
            print_current_settings()
            event.handled = True
            return
        
        # === 수신 모드별 처리 ===
        
        if receiving_mode == "root_note":
            settings["root_note"] = note_value
            print(f"루트 노트가 {note_value}로 변경되었습니다. ({midi_note_name(note_value)})")
            receiving_mode = False
            event.handled = True
            return
            
        elif receiving_mode == "tempo":
            # 노트 값 * 2 = 템포 (템포 범위 확장)
            new_tempo = note_value * 2
            settings["tempo"] = new_tempo
            print(f"템포가 {new_tempo} BPM으로 변경되었습니다.")
            receiving_mode = False
            event.handled = True
            return
            
        elif receiving_mode == "complexity_solo":
            # 솔로 복잡도 설정 (노트 값을 0-1 범위로 변환)
            settings["solo_complexity"] = note_value / 127.0
            print(f"솔로 복잡도가 {settings['solo_complexity']:.2f}로 설정되었습니다.")
            receiving_mode = "complexity_chord"
            event.handled = True
            return
            
        elif receiving_mode == "complexity_chord":
            # 코드 복잡도 설정 (노트 값을 0-1 범위로 변환)
            settings["chord_complexity"] = note_value / 127.0
            print(f"코드 복잡도가 {settings['chord_complexity']:.2f}로 설정되었습니다.")
            receiving_mode = False
            event.handled = True
            return
        
        event.handled = True

# 재생 상태 변화 처리 함수
def OnTransport(isPlaying):
    """재생 상태가 변경될 때 호출 (재생/정지)"""
    return

# 현재 설정 출력
def print_current_settings():
    """현재 설정 정보 출력"""
    print("\n=== 현재 비밥 설정 ===")
    print(f"루트 노트: {settings['root_note']} ({midi_note_name(settings['root_note'])})")
    print(f"템포: {settings['tempo']} BPM")
    print(f"마디 수: {settings['measures']}")
    print(f"스케일 타입: {settings['scale_type']}")
    print(f"코드 진행: {settings['progression_type']}")
    print(f"솔로 복잡도: {settings['solo_complexity']:.2f}")
    print(f"코드 복잡도: {settings['chord_complexity']:.2f}")
    print(f"옥타브 범위: {settings['range_octaves']}")
    if settings["last_generated_file"]:
        print(f"마지막 생성 파일: {settings['last_generated_file']}")
    print("===================\n")

# MIDI 노트 번호를 노트 이름으로 변환
def midi_note_name(note_number):
    """MIDI 노트 번호를 노트 이름으로 변환 (예: 60 -> C4)"""
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = note_number // 12 - 1
    note = note_number % 12
    return f"{note_names[note]}{octave}"

# 비밥 데이터 생성
def generate_bebop_data():
    """비밥 생성기를 사용해 솔로와 코드 데이터 생성"""
    if not HAS_GENERATOR:
        print("비밥 생성기 모듈이 없습니다. 'bebop_generator.py' 파일이 스크립트와 같은 디렉토리에 있는지 확인하세요.")
        return
    
    try:
        # 비밥 생성기 초기화
        generator = BebopGenerator(
            root_note=settings["root_note"],
            tempo=settings["tempo"]
        )
        
        # 마디 수 설정
        generator.set_measures(settings["measures"])
        
        # 비밥 솔로 및 코드 생성
        data = generator.generate_bebop_solo_and_chords(
            scale_type=settings["scale_type"],
            progression_type=settings["progression_type"],
            solo_complexity=settings["solo_complexity"],
            chord_complexity=settings["chord_complexity"],
            range_octaves=settings["range_octaves"]
        )
        
        # 데이터 저장 (임시 파일에)
        temp_file = os.path.join(os.path.dirname(__file__), "temp_bebop_data.json")
        generator.save_to_json(data, temp_file)
        
        # 설정 업데이트
        settings["last_generated_file"] = temp_file
        
        # 노트 데이터 저장
        global solo_notes, chord_notes
        solo_notes = data["solo"]["notes"]
        chord_notes = data["chords"]["notes"]
        
        print(f"비밥 솔로 ({len(solo_notes)}개 노트)와 코드 ({len(chord_notes)}개 노트)가 생성되었습니다.")
        print("- 노트 10을 눌러 솔로 녹음")
        print("- 노트 11을 눌러 코드 녹음")
        print("- 노트 12를 눌러 솔로와 코드 함께 녹음")
    
    except Exception as e:
        print(f"비밥 데이터 생성 오류: {e}")

# 파일에서 솔로 데이터 로드
def load_solo_from_file(file_path):
    """파일에서 솔로 데이터 불러오기"""
    global solo_notes
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # 솔로 노트 데이터 변환
        solo_notes = []
        for note_data in data["solo"]["notes"]:
            solo_notes.append(tuple(note_data))
        
        print(f"{len(solo_notes)}개 솔로 노트를 불러왔습니다.")
    except Exception as e:
        print(f"솔로 데이터 로드 오류: {e}")

# 파일에서 코드 데이터 로드
def load_chords_from_file(file_path):
    """파일에서 코드 데이터 불러오기"""
    global chord_notes
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # 코드 노트 데이터 변환
        chord_notes = []
        for note_data in data["chords"]["notes"]:
            chord_notes.append(tuple(note_data))
        
        print(f"{len(chord_notes)}개 코드 노트를 불러왔습니다.")
    except Exception as e:
        print(f"코드 데이터 로드 오류: {e}")

# 노트 일괄 녹음 함수
def record_notes_batch(notes_array, channel_index):
    """
    FL Studio에 노트 일괄 녹음 (동시 노트 처리)
    
    Args:
        notes_array: (노트, 벨로시티, 길이, 위치) 튜플 목록
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
            tempo = settings["tempo"]  # 설정된 템포 사용
            
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
    if not solo_notes or not chord_notes:
        print("멜로디 또는 코드 데이터가 없습니다")
        return
    
    # 모든 노트를 위치별로 병합하고 채널 정보 추가 (튜플: 노트, 벨로시티, 길이, 위치, 채널)
    all_notes = [(note, vel, length, pos, MELODY_CHANNEL) for note, vel, length, pos in solo_notes]
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
            tempo = settings["tempo"]  # 설정된 템포 사용
            
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

# 스크립트가 독립 실행될 경우
if __name__ == "__main__":
    print("FL Studio에서 실행해주세요.")