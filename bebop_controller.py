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

# 패턴 관리 변수
current_pattern_index = 1  # 현재 사용할 패턴 인덱스
pattern_names = {
    'solo': [],      # 솔로 패턴 이름들
    'chord': [],     # 코드 패턴 이름들
    'both': []       # 솔로+코드 패턴 이름들
}

# 노트 수신 모드 열거형
class ReceiveMode:
    IDLE = 0        # 대기 상태
    MELODY = 1      # 멜로디/솔로 노트 수신 중
    CHORDS = 2      # 코드 노트 수신 중

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
    "last_generated_file": "",
    "current_pattern_index": 1,  # 현재 패턴 인덱스
    "pattern_history": {         # 패턴 히스토리
        "solo": [],
        "chord": [],
        "both": []
    }
}

# 노트 수신 관련 변수
receive_mode = ReceiveMode.IDLE
note_count = 0
values_received = 0
midi_data = []
solo_notes = []   # 멜로디/솔로 노트 저장
chord_notes = []  # 코드 노트 저장

# 설정 변경 모드
changing_setting = False
setting_type = ""

# 설정 저장 및 로드 함수
def save_settings():
    """설정을 JSON 파일로 저장"""
    global current_pattern_index, pattern_names
    try:
        # 현재 패턴 인덱스와 패턴 히스토리 업데이트
        settings["current_pattern_index"] = current_pattern_index
        settings["pattern_history"] = pattern_names
        
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        print("설정이 저장되었습니다.")
    except Exception as e:
        print(f"설정 저장 오류: {e}")

def load_settings():
    """저장된 설정 불러오기"""
    global settings, current_pattern_index, pattern_names
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                loaded_settings = json.load(f)
                settings.update(loaded_settings)
                
            # 패턴 관련 변수 복원
            current_pattern_index = settings.get("current_pattern_index", 1)
            pattern_names = settings.get("pattern_history", {
                'solo': [],
                'chord': [],
                'both': []
            })
            
            print("설정을 불러왔습니다.")
            print(f"다음 패턴 인덱스: {current_pattern_index}")
        else:
            print("저장된 설정이 없어 기본값을 사용합니다.")
    except Exception as e:
        print(f"설정 로드 오류: {e}")

# 초기화 함수
def OnInit():
    """FL Studio에서 스크립트가 로드될 때 호출"""
    print("비밥 솔로 & 코드 컨트롤러 초기화됨")
    
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
    print("비밥 솔로 & 코드 컨트롤러 종료됨")
    return

# 상태 변경 시 호출되는 함수
def OnRefresh(flags):
    """FL Studio의 상태가 변경되거나 새로고침이 필요할 때 호출"""
    return

# MIDI 입력 처리 함수
def OnMidiMsg(event, timestamp=0):
    """MIDI 메시지가 수신될 때 호출"""
    global receive_mode, note_count, values_received, midi_data, solo_notes, chord_notes
    global changing_setting, setting_type
    
    # 노트 온 메시지만 처리 (벨로시티 > 0)
    if event.status >= midi.MIDI_NOTEON and event.status < midi.MIDI_NOTEON + 16 and event.data2 > 0:
        note_value = event.data1
        
        # === 설정 변경 모드 처리 ===
        if changing_setting:
            if setting_type == "root_note":
                settings["root_note"] = note_value
                print(f"루트 노트가 {note_value}로 변경되었습니다. ({midi_note_name(note_value)})")
                changing_setting = False
            elif setting_type == "tempo":
                # 노트 값 * 2 = 템포 (템포 범위 확장)
                new_tempo = note_value * 2
                settings["tempo"] = new_tempo
                print(f"템포가 {new_tempo} BPM으로 변경되었습니다.")
                changing_setting = False
            elif setting_type == "solo_complexity":
                # 솔로 복잡도 설정 (노트 값을 0-1 범위로 변환)
                settings["solo_complexity"] = note_value / 127.0
                print(f"솔로 복잡도가 {settings['solo_complexity']:.2f}로 설정되었습니다.")
                setting_type = "chord_complexity"
                print("코드 복잡도를 설정하려면 노트를 입력하세요.")
            elif setting_type == "chord_complexity":
                # 코드 복잡도 설정 (노트 값을 0-1 범위로 변환)
                settings["chord_complexity"] = note_value / 127.0
                print(f"코드 복잡도가 {settings['chord_complexity']:.2f}로 설정되었습니다.")
                changing_setting = False
            
            # 설정이 끝나면 이벤트 처리 완료
            if not changing_setting:
                save_settings()
            
            event.handled = True
            return
        
        # === 컨트롤 노트 처리 (0-30 범위의 노트) ===
        
        # 노트 0: 멜로디 수신 모드 시작
        if note_value == 0 and receive_mode == ReceiveMode.IDLE:
            receive_mode = ReceiveMode.MELODY
            print("비밥 솔로 노트 수신 시작")
            midi_data = []
            note_count = 0
            values_received = 0
            solo_notes = []
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
            if solo_notes and chord_notes:
                print("멜로디와 코드를 새 패턴에 함께 녹음 시작...")
                pattern_num, pattern_name = record_melody_and_chords()
                print(f"멜로디+코드 녹음 완료: 패턴 {pattern_num} ({pattern_name})")
            else:
                print("녹음할 멜로디 또는 코드 데이터가 없습니다")
            event.handled = True
            return
            
        # 노트 3: 멜로디만 녹음
        if note_value == 3 and receive_mode == ReceiveMode.IDLE:
            if solo_notes:
                print("솔로 라인만 새 패턴에 녹음 시작...")
                pattern_num, pattern_name = record_notes_batch(solo_notes, MELODY_CHANNEL, "solo")
                print(f"솔로 녹음 완료: 패턴 {pattern_num} ({pattern_name})")
            else:
                print("녹음할 멜로디 데이터가 없습니다")
            event.handled = True
            return
            
        # 노트 4: 코드만 녹음
        if note_value == 4 and receive_mode == ReceiveMode.IDLE:
            if chord_notes:
                print("코드 진행만 새 패턴에 녹음 시작...")
                pattern_num, pattern_name = record_notes_batch(chord_notes, CHORD_CHANNEL, "chord")
                print(f"코드 녹음 완료: 패턴 {pattern_num} ({pattern_name})")
            else:
                print("녹음할 코드 데이터가 없습니다")
            event.handled = True
            return
            
        # 노트 5: 모든 데이터 초기화
        if note_value == 5 and receive_mode == ReceiveMode.IDLE:
            solo_notes = []
            chord_notes = []
            # 패턴 히스토리도 초기화
            global pattern_names
            pattern_names = {
                'solo': [],
                'chord': [],
                'both': []
            }
            print("모든 노트 데이터와 패턴 히스토리가 초기화되었습니다")
            event.handled = True
            return
            
        # 노트 6: 비밥 생성
        if note_value == 6 and receive_mode == ReceiveMode.IDLE and HAS_GENERATOR:
            print("비밥 솔로 및 코드 생성 시작...")
            generate_bebop_data()
            event.handled = True
            return
            
        # 비밥 생성 기능
        
        # 노트 10: 솔로 녹음
        if note_value == 10 and receive_mode == ReceiveMode.IDLE:
            if solo_notes:
                print("비밥 솔로를 새 패턴에 녹음 시작...")
                pattern_num, pattern_name = record_notes_batch(solo_notes, MELODY_CHANNEL, "solo")
                print(f"비밥 솔로 녹음 완료: 패턴 {pattern_num} ({pattern_name})")
            else:
                print("녹음할 솔로 데이터가 없습니다. 먼저 비밥 솔로를 생성하거나 불러오세요.")
            event.handled = True
            return
            
        # 노트 11: 코드 녹음
        if note_value == 11 and receive_mode == ReceiveMode.IDLE:
            if chord_notes:
                print("비밥 코드를 새 패턴에 녹음 시작...")
                pattern_num, pattern_name = record_notes_batch(chord_notes, CHORD_CHANNEL, "chord")
                print(f"비밥 코드 녹음 완료: 패턴 {pattern_num} ({pattern_name})")
            else:
                print("녹음할 코드 데이터가 없습니다. 먼저 비밥 코드를 생성하거나 불러오세요.")
            event.handled = True
            return
            
        # 노트 12: 솔로+코드 함께 녹음
        if note_value == 12 and receive_mode == ReceiveMode.IDLE:
            if solo_notes and chord_notes:
                print("비밥 솔로와 코드를 새 패턴에 함께 녹음 시작...")
                pattern_num, pattern_name = record_melody_and_chords()
                print(f"비밥 솔로+코드 녹음 완료: 패턴 {pattern_num} ({pattern_name})")
            else:
                print("녹음할 솔로 또는 코드 데이터가 없습니다.")
            event.handled = True
            return
            
        # 노트 20: 루트 노트 변경 (다음 노트가 루트 노트가 됨)
        if note_value == 20 and receive_mode == ReceiveMode.IDLE:
            print("루트 노트 변경 모드. 다음 노트가 새 루트 노트가 됩니다...")
            changing_setting = True
            setting_type = "root_note"
            event.handled = True
            return
            
        # 노트 21: 템포 변경 (다음 노트 값이 템포의 약수가 됨)
        if note_value == 21 and receive_mode == ReceiveMode.IDLE:
            print("템포 변경 모드. 다음 노트 값 * 2가 템포가 됩니다...")
            changing_setting = True
            setting_type = "tempo"
            event.handled = True
            return
            
        # 노트 22: 복잡도 변경 (다음 노트 값이 복잡도 지정)
        if note_value == 22 and receive_mode == ReceiveMode.IDLE:
            print("복잡도 변경 모드. 다음 두 노트가 각각 솔로와 코드 복잡도를 지정합니다...")
            changing_setting = True
            setting_type = "solo_complexity"
            event.handled = True
            return
            
        # 노트 30: 현재 설정 출력
        if note_value == 30 and receive_mode == ReceiveMode.IDLE:
            print_current_settings()
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
            
            notes_array = solo_notes if receive_mode == ReceiveMode.MELODY else chord_notes
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
                solo_notes.append(note_data)
                print(f"솔로 노트 추가: 노트={note}, 벨로시티={velocity}, 길이={length:.1f}, 위치={position:.1f}")
            else:
                chord_notes.append(note_data)
                print(f"코드 노트 추가: 노트={note}, 벨로시티={velocity}, 길이={length:.1f}, 위치={position:.1f}")
            
            # 모든 예상 노트를 받았으면 수신 모드 종료
            current_notes = solo_notes if receive_mode == ReceiveMode.MELODY else chord_notes
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
    settings["tempo"] = tempo
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
    print(f"현재 패턴 인덱스: {current_pattern_index}")
    if settings["last_generated_file"]:
        print(f"마지막 생성 파일: {settings['last_generated_file']}")
    
    # 생성된 패턴 목록 출력
    if pattern_names['solo']:
        print(f"솔로 패턴들: {', '.join(pattern_names['solo'])}")
    if pattern_names['chord']:
        print(f"코드 패턴들: {', '.join(pattern_names['chord'])}")
    if pattern_names['both']:
        print(f"솔로+코드 패턴들: {', '.join(pattern_names['both'])}")
    print("===================\n")

# 패턴 관리 함수들
def get_next_pattern_number():
    """사용 가능한 다음 패턴 번호를 반환"""
    global current_pattern_index
    
    # 현재 총 패턴 수 확인
    total_patterns = patterns.patternCount()
    
    # 패턴 인덱스가 총 패턴 수를 넘으면 새 패턴 생성
    if current_pattern_index >= total_patterns:
        # FL Studio에서는 패턴을 자동으로 추가할 수 없으므로 기존 패턴 사용
        # 사용자가 수동으로 패턴을 추가해야 함
        print(f"경고: 패턴 {current_pattern_index}가 존재하지 않습니다. 패턴 {total_patterns - 1}를 사용합니다.")
        current_pattern_index = total_patterns - 1
    
    return current_pattern_index

def create_pattern_name(pattern_type, root_note, complexity=None):
    """패턴 이름 생성"""
    root_name = midi_note_name(root_note)
    timestamp = time.strftime("%H%M%S")
    
    if pattern_type == "solo":
        name = f"Bebop_Solo_{root_name}_{int(complexity*100):02d}_{timestamp}"
    elif pattern_type == "chord":
        name = f"Bebop_Chord_{root_name}_{int(complexity*100):02d}_{timestamp}"
    elif pattern_type == "both":
        name = f"Bebop_Full_{root_name}_{timestamp}"
    else:
        name = f"Bebop_{pattern_type}_{timestamp}"
    
    return name

def switch_to_new_pattern(pattern_type, root_note=None, complexity=None):
    """새로운 패턴으로 전환하고 이름 설정"""
    global current_pattern_index
    
    # 다음 패턴 번호 가져오기
    pattern_num = get_next_pattern_number()
    
    # 패턴으로 전환
    patterns.jumpToPattern(pattern_num)
    
    # 패턴 이름 생성 및 설정
    if root_note is None:
        root_note = settings.get('root_note', 60)
    
    pattern_name = create_pattern_name(pattern_type, root_note, complexity)
    
    try:
        # FL Studio API에 패턴 이름 설정 함수가 없을 수 있으므로 try-except 사용
        patterns.setPatternName(pattern_num, pattern_name)
        print(f"패턴 {pattern_num}으로 전환: {pattern_name}")
    except AttributeError:
        print(f"패턴 {pattern_num}으로 전환 (이름 자동 설정 불가)")
    
    # 패턴 이름 기록
    pattern_names[pattern_type].append(f"P{pattern_num}: {pattern_name}")
    
    # 다음 사용할 패턴 인덱스 증가
    current_pattern_index += 1
    
    return pattern_num, pattern_name

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

# 녹음 헬퍼 함수
def _record_notes_at_position(notes_at_position, position, is_multi_channel=False, channel_index=0):
    """특정 위치에서 노트 녹음을 처리하는 내부 헬퍼 함수"""
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
    
    # 녹음 시작을 위한 재생 시작
    transport.start()
    
    # 이 위치의 모든 노트 동시 녹음
    if is_multi_channel:
        # 멀티 채널 녹음 (채널 정보 포함)
        for note, velocity, length, _, channel in notes_at_position:
            channels.midiNoteOn(channel, note, velocity)
    else:
        # 단일 채널 녹음
        for note, velocity, length, _ in notes_at_position:
            channels.midiNoteOn(channel_index, note, velocity)
    
    # 현재 템포 가져오기
    try:
        import mixer
        tempo = mixer.getCurrentTempo() / 1000
    except (ImportError, AttributeError):
        tempo = settings["tempo"]  # 설정된 템포 사용
        
    # 안전을 위한 최대 대기 시간 설정
    MAX_WAIT_TIME = 30
    seconds_to_wait = (max_length * 60) / tempo
    if seconds_to_wait > MAX_WAIT_TIME:
        print(f"경고: 계산된 대기 시간({seconds_to_wait:.2f}초)이 너무 깁니다. {MAX_WAIT_TIME}초로 제한합니다.")
        seconds_to_wait = MAX_WAIT_TIME
    
    print(f"{seconds_to_wait:.2f}초 대기 중...")
    
    # 계산된 시간 대기
    time.sleep(seconds_to_wait)
    
    # 모든 노트에 대한 노트 오프 이벤트 전송
    if is_multi_channel:
        # 멀티 채널 노트 오프
        for note, _, _, _, channel in notes_at_position:
            channels.midiNoteOn(channel, note, 0)
    else:
        # 단일 채널 노트 오프
        for note, _, _, _ in notes_at_position:
            channels.midiNoteOn(channel_index, note, 0)
    
    # 재생 정지
    transport.stop()
    
    # 녹음 모드 활성화된 경우 종료
    if transport.isRecording():
        transport.record()
    
    # 녹음 간 짧은 일시 정지
    time.sleep(0.2)

# 노트 일괄 녹음 함수
def record_notes_batch(notes_array, channel_index, pattern_type="solo"):
    """
    FL Studio에 노트 일괄 녹음 (동시 노트 처리)
    
    Args:
        notes_array: (노트, 벨로시티, 길이_비트, 위치_비트) 튜플 목록
        channel_index: 녹음할 채널 인덱스
        pattern_type: 패턴 타입 ("solo", "chord", "both")
    """
    if not notes_array:
        print("녹음할 노트가 없습니다")
        return
    
    # 복잡도 계산 (평균 노트 길이와 밀도 기반)
    avg_length = sum(note[2] for note in notes_array) / len(notes_array)
    note_density = len(notes_array) / (max(note[3] for note in notes_array) + 1) if notes_array else 0
    complexity = min(1.0, (note_density * 0.1 + (1/avg_length) * 0.1))
    
    # 새로운 패턴으로 전환
    pattern_num, pattern_name = switch_to_new_pattern(
        pattern_type, 
        settings.get('root_note', 60), 
        complexity
    )
        
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
        
        print(f"패턴 {pattern_num}, 채널 {channel_index}의 위치 {position}에서 {len(notes_at_position)}개 노트 녹음")
        
        # 헬퍼 함수를 사용하여 노트 녹음
        _record_notes_at_position(notes_at_position, position, is_multi_channel=False, channel_index=channel_index)
    
    print(f"패턴 {pattern_num} ({pattern_name})에 모든 노트 녹음 완료")
    print(f"총 {len(notes_array)}개 노트, 복잡도: {complexity:.2f}")
    
    return pattern_num, pattern_name

# 멜로디와 코드를 함께 녹음하는 함수
def record_melody_and_chords():
    """멜로디와 코드 데이터를 동기화하여 함께 녹음"""
    if not solo_notes or not chord_notes:
        print("멜로디 또는 코드 데이터가 없습니다")
        return
    
    # 새로운 패턴으로 전환 (솔로+코드 타입)
    pattern_num, pattern_name = switch_to_new_pattern(
        "both", 
        settings.get('root_note', 60)
    )
    
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
        
        print(f"패턴 {pattern_num}의 위치 {position}에서 {len(notes_at_position)}개 노트 녹음 (멜로디+코드)")
        
        # 헬퍼 함수를 사용하여 노트 녹음 (멀티 채널 모드)
        _record_notes_at_position(notes_at_position, position, is_multi_channel=True)
    
    print(f"패턴 {pattern_num} ({pattern_name})에 멜로디와 코드 함께 녹음 완료")
    print(f"솔로 노트: {len(solo_notes)}개, 코드 노트: {len(chord_notes)}개")
    
    return pattern_num, pattern_name