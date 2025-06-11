# harmony_controller.py
# name=Harmony Controller
# 실시간 화성 멜로디 전용 FL Studio 컨트롤러

import transport
import channels
import midi
import general
import time

# 전역 변수
harmony_mode = False
current_harmony_notes = []
harmony_channel = 1  # 화성 전용 채널

def OnInit():
    """FL Studio 로드 시 초기화"""
    print("Harmony Controller initialized")
    return

def OnDeInit():
    """FL Studio 종료 시"""
    print("Harmony Controller deinitialized")
    return

def OnRefresh(flags):
    """상태 변경"""
    return

def OnMidiIn(event):
    """MIDI 입력 처리 (사용 안 함)"""
    return

def OnMidiMsg(event, timestamp=0):
    """MCP 서버에서 보낸 MIDI 메시지 처리"""
    global harmony_mode, current_harmony_notes, harmony_channel
    
    # 노트 온 메시지만 처리
    if event.status >= midi.MIDI_NOTEON and event.status < midi.MIDI_NOTEON + 16 and event.data2 > 0:
        note_value = event.data1
        
        # 화성 모드 시작 신호 (노트 1)
        if note_value == 1:
            harmony_mode = True
            stop_all_harmony()  # 이전 화성 정리
            print("화성 모드 시작")
            event.handled = True
            return
        
        # 화성 정지 신호 (노트 2)
        if note_value == 2:
            stop_all_harmony()
            print("화성 정지")
            event.handled = True
            return
        
        # 화성 모드가 아니면 무시
        if not harmony_mode:
            return
        
        # 화성 종료 신호 (노트 126)
        if note_value == 126:
            harmony_mode = False
            play_harmony_notes()
            print(f"화성 재생: {current_harmony_notes}")
            event.handled = True
            return
        
        # 노트 개수 받기 (화성 모드 시작 후 첫 번째)
        if len(current_harmony_notes) == 0 and note_value > 0:
            current_harmony_notes = []  # 초기화
            print(f"화성 노트 개수: {note_value}")
            event.handled = True
            return
        
        # 화성 노트 수집
        if harmony_mode and note_value > 10:  # 실제 노트 값
            current_harmony_notes.append(note_value)
            print(f"화성 노트 추가: {note_value}")
        
        event.handled = True

def play_harmony_notes():
    """화성 노트들 재생"""
    global current_harmony_notes, harmony_channel
    
    if not current_harmony_notes:
        return
    
    # 화성 전용 채널 선택
    channels.selectOneChannel(harmony_channel)
    
    # 모든 화성 노트 동시 재생
    for note in current_harmony_notes:
        if 0 <= note <= 127:
            channels.midiNoteOn(harmony_channel, note, 80)  # 적당한 볼륨
            print(f"화성 노트 온: {note}")
    
    # 0.1초 후 노트 오프 (짧은 화성)
    def note_off_delayed():
        time.sleep(0.1)
        for note in current_harmony_notes:
            if 0 <= note <= 127:
                channels.midiNoteOn(harmony_channel, note, 0)
    
    # 별도 스레드에서 노트 오프 실행
    import threading
    threading.Thread(target=note_off_delayed, daemon=True).start()

def stop_all_harmony():
    """모든 화성 노트 정지"""
    global current_harmony_notes, harmony_channel
    
    # 현재 재생 중인 모든 노트 끄기
    for note in range(128):
        channels.midiNoteOn(harmony_channel, note, 0)
    
    current_harmony_notes = []
    print("모든 화성 정지")

def play_harmony_arpeggio():
    """화성을 아르페지오로 재생"""
    global current_harmony_notes, harmony_channel
    
    if not current_harmony_notes:
        return
    
    channels.selectOneChannel(harmony_channel)
    
    # 아르페지오 재생 (순차적으로)
    def play_arpeggio():
        for i, note in enumerate(current_harmony_notes):
            if 0 <= note <= 127:
                channels.midiNoteOn(harmony_channel, note, 70)
                time.sleep(0.1)  # 100ms 간격
                channels.midiNoteOn(harmony_channel, note, 0)
                time.sleep(0.05)  # 50ms 쉼
    
    import threading
    threading.Thread(target=play_arpeggio, daemon=True).start()

def OnTransport(isPlaying):
    """재생 상태 변경"""
    return

def OnTempoChange(tempo):
    """템포 변경"""
    return

def OnChannelChange(channel):
    """채널 변경 시 화성 채널 업데이트"""
    global harmony_channel
    harmony_channel = channel
    print(f"화성 채널 변경: {harmony_channel}")
    return

def OnMixerChannelChange(channel):
    """믹서 채널 변경"""
    return

def OnStatusChange(status):
    """상태 변경"""
    return

# 추가 유틸리티 함수들
def get_harmony_info():
    """현재 화성 정보 반환"""
    return {
        "harmony_mode": harmony_mode,
        "current_notes": current_harmony_notes,
        "harmony_channel": harmony_channel
    }

def set_harmony_channel(channel):
    """화성 채널 설정"""
    global harmony_channel
    if 0 <= channel < channels.channelCount():
        harmony_channel = channel
        print(f"화성 채널 설정: {harmony_channel}")
        return True
    return False

def test_harmony_pattern():
    """테스트 화성 패턴 재생"""
    global current_harmony_notes
    
    # C major 코드 테스트
    current_harmony_notes = [60, 64, 67, 72]  # C, E, G, C
    play_harmony_notes()
    
    print("테스트 화성 재생 완료")