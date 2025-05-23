# bebop_generator.py
# FL Studio 비밥 솔로 및 코드 생성기

import random
import json

# 비밥 스케일 및 아르페지오 정의
BEBOP_SCALES = {
    'Bebop_Dominant': [0, 2, 4, 5, 7, 9, 10, 11], # C, D, E, F, G, A, Bb, B
    'Bebop_Major': [0, 2, 4, 5, 7, 8, 9, 11],     # C, D, E, F, G, Ab, A, B
    'Bebop_Minor': [0, 2, 3, 5, 7, 9, 10, 11],    # C, D, Eb, F, G, A, Bb, B
    'Bebop_Melodic_Minor': [0, 2, 3, 5, 7, 9, 10, 11]  # C, D, Eb, F, G, A, Bb, B
}

# 재즈 코드 타입 정의
JAZZ_CHORDS = {
    'maj7': [0, 4, 7, 11],       # 1, 3, 5, 7
    'dom7': [0, 4, 7, 10],       # 1, 3, 5, b7
    'min7': [0, 3, 7, 10],       # 1, b3, 5, b7
    'min7b5': [0, 3, 6, 10],     # 1, b3, b5, b7
    'dim7': [0, 3, 6, 9],        # 1, b3, b5, bb7
    'maj9': [0, 4, 7, 11, 14],   # 1, 3, 5, 7, 9
    'dom9': [0, 4, 7, 10, 14],   # 1, 3, 5, b7, 9
    'min9': [0, 3, 7, 10, 14],   # 1, b3, 5, b7, 9
    'dom7b9': [0, 4, 7, 10, 13], # 1, 3, 5, b7, b9
    'dom7#11': [0, 4, 7, 10, 18] # 1, 3, 5, b7, #11
}

# 일반적인 재즈 코드 진행
JAZZ_PROGRESSIONS = {
    'ii-V-I': ['min7', 'dom7', 'maj7'],
    'ii-V-i': ['min7b5', 'dom7b9', 'min7'],
    'I-vi-ii-V': ['maj7', 'min7', 'min7', 'dom7'],
    'iii-VI-ii-V': ['min7', 'dom7', 'min7', 'dom7'],
    'Bird_Blues': ['dom7', 'dom7', 'dom7', 'dom7', 'dom7', 'dom7', 'dom7', 'dom7', 'min7', 'dom7', 'maj7', 'dom7']
}

# 비밥 리듬 패턴 (1 = 4분음표, 0.5 = 8분음표, 0.25 = 16분음표)
BEBOP_RHYTHMS = {
    'standard': [0.5, 0.5, 0.5, 0.5, 1, 0.5, 0.5],
    'syncopated': [0.75, 0.25, 0.5, 0.5, 1],
    'fast': [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
    'triplet': [0.33, 0.33, 0.33, 0.5, 0.5],
    'mixed': [0.25, 0.25, 0.5, 0.75, 0.25],
    'chromatic_run': [0.125, 0.125, 0.125, 0.125, 0.125, 0.125, 0.125, 0.125]
}

# 비밥 프레이즈 패턴 (스케일 간격)
BEBOP_PHRASES = {
    'ascending': [0, 1, 2, 3, 4, 5, 6, 7],
    'descending': [7, 6, 5, 4, 3, 2, 1, 0],
    'arpeggios': [0, 2, 4, 6, 7, 6, 4, 2],
    'approach_notes': [0, -1, 0, 2, 1, 2, 4, 3],
    'enclosure': [1, -1, 0, 2, 1, 3, 2, 4]
}

# 코드 컴핑 리듬 패턴
COMPING_RHYTHMS = {
    'basic': [1, 1, 1, 1],
    'syncopated': [1.5, 0.5, 1, 1],
    'charleston': [0.75, 0.25, 1, 1, 1],
    'bossa': [1, 0.5, 0.5, 1, 1],
    'modern': [1.25, 0.75, 1, 1]
}

class BebopGenerator:
    """비밥 솔로와 코드 컴핑 생성기"""
    
    def __init__(self, root_note=60, tempo=160):
        """
        초기화
        
        Args:
            root_note (int): 루트 노트 MIDI 값 (기본값: 60 = C4)
            tempo (int): 템포 BPM (기본값: 160)
        """
        self.root_note = root_note
        self.tempo = tempo
        self.measures = 4  # 기본 마디 수
        self.beats_per_measure = 4  # 4/4 박자
        
    def set_key(self, root_note):
        """키 설정"""
        self.root_note = root_note
    
    def set_tempo(self, tempo):
        """템포 설정"""
        self.tempo = tempo
    
    def set_measures(self, measures):
        """마디 수 설정"""
        self.measures = measures
    
    def generate_solo(self, scale_type='Bebop_Dominant', complexity=0.7, range_octaves=2):
        """
        비밥 솔로 생성
        
        Args:
            scale_type (str): 사용할 비밥 스케일 타입
            complexity (float): 솔로 복잡도 (0.0-1.0)
            range_octaves (int): 사용할 옥타브 범위
            
        Returns:
            list: MIDI 노트 데이터 목록 (노트, 벨로시티, 길이, 위치)
        """
        # 사용할 스케일 가져오기
        scale = BEBOP_SCALES.get(scale_type, BEBOP_SCALES['Bebop_Dominant'])
        
        # 총 비트 수 계산
        total_beats = self.measures * self.beats_per_measure
        
        # 결과 노트 배열
        notes = []
        
        # 현재 위치 (비트)
        current_position = 0.0
        
        # 사용할 리듬 패턴 선택 (복잡도에 따라)
        available_rhythms = list(BEBOP_RHYTHMS.keys())
        if complexity < 0.3:
            rhythm_patterns = ['standard', 'syncopated']
        elif complexity < 0.6:
            rhythm_patterns = ['standard', 'syncopated', 'fast', 'triplet']
        else:
            rhythm_patterns = available_rhythms
            
        # 사용할 프레이즈 패턴 선택 (복잡도에 따라)
        available_phrases = list(BEBOP_PHRASES.keys())
        if complexity < 0.3:
            phrase_patterns = ['ascending', 'descending']
        elif complexity < 0.6:
            phrase_patterns = ['ascending', 'descending', 'arpeggios']
        else:
            phrase_patterns = available_phrases
        
        # 솔로 생성 (마디 단위)
        while current_position < total_beats:
            # 마디 내에서의 위치
            beat_in_measure = current_position % self.beats_per_measure
            
            # 랜덤 리듬 패턴과 프레이즈 패턴 선택
            rhythm_pattern = BEBOP_RHYTHMS[random.choice(rhythm_patterns)]
            phrase_pattern = BEBOP_PHRASES[random.choice(phrase_patterns)]
            
            # 현재 마디가 얼마나 남았는지 계산
            beats_left_in_measure = self.beats_per_measure - beat_in_measure
            
            # 리듬 패턴의 총 길이 계산
            rhythm_length = sum(rhythm_pattern)
            
            # 패턴이 마디를 넘어가면 조정
            if rhythm_length > beats_left_in_measure:
                # 마디에 맞게 리듬 패턴 조정
                adjusted_rhythm = []
                remaining = beats_left_in_measure
                for r in rhythm_pattern:
                    if r <= remaining:
                        adjusted_rhythm.append(r)
                        remaining -= r
                    else:
                        if remaining > 0:
                            adjusted_rhythm.append(remaining)
                        break
                rhythm_pattern = adjusted_rhythm
            
            # 프레이즈 시작 음표 결정 (스케일 내)
            start_degree = random.randint(0, len(scale) - 1)
            
            # 랜덤 시작 옥타브 (-1 ~ +1)
            octave_shift = random.randint(-1, 1) * 12
            
            # 리듬과 프레이즈 패턴을 기반으로 노트 생성
            for i, note_length in enumerate(rhythm_pattern):
                if i >= len(phrase_pattern):
                    # 프레이즈 패턴이 리듬 패턴보다 짧으면 랜덤 움직임
                    degree_change = random.choice([-2, -1, 0, 1, 2])
                else:
                    # 프레이즈 패턴 따라가기
                    degree_change = phrase_pattern[i]
                
                # 현재 스케일 정도 계산
                current_degree = (start_degree + degree_change) % len(scale)
                
                # 음표 계산
                note_value = self.root_note + scale[current_degree] + octave_shift
                
                # 음표가 범위를 벗어나면 조정
                while note_value < self.root_note - 12:
                    note_value += 12
                while note_value > self.root_note + range_octaves * 12:
                    note_value -= 12
                
                # 벨로시티 변화 (약간의 다이내믹스)
                velocity = random.randint(70, 110)
                
                # 약간의 재즈 느낌을 위한 스윙감 추가
                swing_offset = 0
                if i % 2 == 1 and complexity > 0.4:  # 짝수번째 노트에 스윙 적용
                    swing_offset = random.uniform(0.01, 0.1)
                
                # 크로매틱 접근음 추가 (complexity에 따라)
                chromatic_approach = False
                if complexity > 0.6 and random.random() < 0.3:
                    chromatic_approach = True
                    # 원래 노트 저장
                    original_note = note_value
                    # 접근음 추가 (반음 위 또는 아래)
                    approach_offset = random.choice([-1, 1])
                    approach_note = note_value + approach_offset
                    approach_length = note_length / 2
                    
                    # 접근음 추가
                    notes.append((approach_note, velocity - 10, approach_length, current_position))
                    
                    # 실제 노트 위치와 길이 조정
                    current_position += approach_length
                    note_length -= approach_length
                    note_value = original_note
                
                # 노트 정보 추가
                notes.append((note_value, velocity, note_length, current_position + swing_offset))
                
                # 비밥 특유의 변박을 위한 랜덤 길이 조정 (높은 복잡도에서만)
                if complexity > 0.8 and random.random() < 0.2:
                    note_length *= random.choice([0.9, 1.1])
                
                # 현재 위치 업데이트
                current_position += note_length
                
                # 만약 다음 노트가 마디를 넘어가면 새 마디로 이동
                if current_position > total_beats:
                    break
                    
            # 상황에 맞는 경우 가끔 쉼표 추가
            if random.random() < 0.2 and current_position < total_beats:
                rest_length = random.choice([0.5, 1.0])
                if current_position + rest_length <= total_beats:
                    current_position += rest_length
        
        return notes
    
    def generate_chord_comping(self, progression_type='ii-V-I', complexity=0.5):
        """
        코드 컴핑 생성
        
        Args:
            progression_type (str): 사용할 코드 진행 유형
            complexity (float): 코드 컴핑 복잡도 (0.0-1.0)
            
        Returns:
            list: MIDI 노트 데이터 목록 (노트, 벨로시티, 길이, 위치)
        """
        # 코드 진행 가져오기
        progression = JAZZ_PROGRESSIONS.get(progression_type, JAZZ_PROGRESSIONS['ii-V-I'])
        
        # 루트 노트에 따른 코드 루트 계산 (ii-V-I의 경우 루트 노트가 I에 해당)
        root_notes = []
        
        if progression_type == 'ii-V-I':
            # 2-5-1 진행: 2도는 D, 5도는 G, 1도는 C (기준이 C인 경우)
            root_notes = [(self.root_note + 2) % 12, (self.root_note + 7) % 12, self.root_note % 12]
        elif progression_type == 'ii-V-i':
            # 단조 2-5-1: 2도는 D, 5도는 G, 1도는 C (기준이 c인 경우)
            root_notes = [(self.root_note + 2) % 12, (self.root_note + 7) % 12, self.root_note % 12]
        elif progression_type == 'I-vi-ii-V':
            # 1-6-2-5: C, A, D, G (기준이 C인 경우)
            root_notes = [self.root_note % 12, (self.root_note + 9) % 12, (self.root_note + 2) % 12, (self.root_note + 7) % 12]
        elif progression_type == 'iii-VI-ii-V':
            # 3-6-2-5: E, A, D, G (기준이 C인 경우)
            root_notes = [(self.root_note + 4) % 12, (self.root_note + 9) % 12, (self.root_note + 2) % 12, (self.root_note + 7) % 12]
        elif progression_type == 'Bird_Blues':
            # 버드 블루스 진행 (12마디)
            root_notes = [self.root_note % 12] * 4 + [(self.root_note + 5) % 12] * 2 + [self.root_note % 12] * 2 + [(self.root_note + 2) % 12, (self.root_note + 7) % 12, self.root_note % 12, (self.root_note + 7) % 12]
        else:
            # 기본 2-5-1 진행
            root_notes = [(self.root_note + 2) % 12, (self.root_note + 7) % 12, self.root_note % 12]
        
        # root_notes가 progression보다 짧으면 반복
        while len(root_notes) < len(progression):
            root_notes.extend(root_notes[:len(progression) - len(root_notes)])
        
        # 사용할 리듬 패턴 선택 (복잡도에 따라)
        if complexity < 0.3:
            rhythm_patterns = ['basic']
        elif complexity < 0.6:
            rhythm_patterns = ['basic', 'syncopated', 'bossa']
        else:
            rhythm_patterns = list(COMPING_RHYTHMS.keys())
        
        # 결과 노트 배열
        notes = []
        
        # 코드당 마디 수 계산
        measures_per_chord = max(1, self.measures // len(progression))
        
        # 현재 위치 (비트)
        current_position = 0.0
        
        # 각 코드에 대해 컴핑 생성
        for i, (chord_type, root_note) in enumerate(zip(progression, root_notes)):
            chord_intervals = JAZZ_CHORDS.get(chord_type, JAZZ_CHORDS['maj7'])
            
            # 이 코드의 비트 수 계산
            chord_beats = measures_per_chord * self.beats_per_measure
            
            # 이 코드의 시작 위치
            chord_start = current_position
            
            # 코드 구성음 계산
            chord_notes = [(root_note + interval) % 12 + 48 for interval in chord_intervals]  # 48 = C3
            
            # 코드 보이싱 변경 (복잡도에 따라)
            if complexity > 0.5:
                # Drop-2 보이싱 (두 번째 음을 한 옥타브 내림)
                if len(chord_notes) > 3 and random.random() < 0.6:
                    chord_notes[1] -= 12
                
                # 9, 11, 13 등 텐션 추가
                if random.random() < 0.4:
                    # 9도 추가
                    tension = (root_note + 14) % 12 + 60  # 14 = 9도
                    if tension not in chord_notes:
                        chord_notes.append(tension)
                
                # 코드 음 순서 섞기
                if random.random() < 0.3:
                    root = chord_notes[0]
                    other_notes = chord_notes[1:]
                    random.shuffle(other_notes)
                    chord_notes = [root] + other_notes
            
            # 마디 내 균등 분배를 위한 컴핑 리듬 계산
            remaining_beats = chord_beats
            chord_position = chord_start
            
            while remaining_beats > 0:
                # 랜덤 리듬 패턴 선택
                rhythm_pattern = COMPING_RHYTHMS[random.choice(rhythm_patterns)]
                
                # 리듬 패턴의 총 길이 계산
                rhythm_length = sum(rhythm_pattern)
                
                # 남은 비트보다 길면 조정
                if rhythm_length > remaining_beats:
                    # 비트에 맞게 리듬 패턴 조정
                    adjusted_rhythm = []
                    remaining = remaining_beats
                    for r in rhythm_pattern:
                        if r <= remaining:
                            adjusted_rhythm.append(r)
                            remaining -= r
                        else:
                            if remaining > 0:
                                adjusted_rhythm.append(remaining)
                            break
                    rhythm_pattern = adjusted_rhythm
                
                # 리듬 패턴에 따라 코드 노트 추가
                for note_length in rhythm_pattern:
                    # 코드의 모든 노트 동시에 연주
                    if random.random() < 0.8:  # 가끔 쉼표도 추가
                        velocity = random.randint(60, 90)  # 멜로디보다 약간 작은 볼륨
                        
                        # 스윙 느낌 추가
                        swing_offset = random.uniform(0, 0.05) if complexity > 0.3 else 0
                        
                        # 모든 코드 노트 추가
                        for note in chord_notes:
                            notes.append((note, velocity, note_length, chord_position + swing_offset))
                    
                    # 위치 업데이트
                    chord_position += note_length
                    remaining_beats -= note_length
                    
                    if remaining_beats <= 0:
                        break
            
            # 다음 코드의 시작 위치 업데이트
            current_position = chord_start + chord_beats
        
        return notes
    
    def convert_to_midi_data_format(self, notes):
        """
        노트 데이터를 FL Studio MIDI 데이터 형식으로 변환
        
        Args:
            notes: (노트, 벨로시티, 길이, 위치) 튜플 목록
            
        Returns:
            list: FL Studio MIDI 데이터 형식의 값 목록 (6개 값 묶음)
        """
        midi_data = []
        
        for note, velocity, length, position in notes:
            # 정수 노트 값
            note_value = int(note)
            
            # 정수 벨로시티 값
            velocity_value = int(velocity)
            
            # 길이 정수부와 소수부 분리
            length_whole = int(length)
            length_decimal = int((length - length_whole) * 10)
            
            # 위치 정수부와 소수부 분리
            position_whole = int(position)
            position_decimal = int((position - position_whole) * 10)
            
            # 6개 값 추가
            midi_data.extend([note_value, velocity_value, length_whole, length_decimal, position_whole, position_decimal])
        
        return midi_data
        
    def generate_bebop_solo_and_chords(self, scale_type='Bebop_Dominant', progression_type='ii-V-I', 
                                       solo_complexity=0.7, chord_complexity=0.5, range_octaves=2):
        """
        비밥 솔로와 코드 컴핑을 함께 생성
        
        Args:
            scale_type (str): 사용할 비밥 스케일 타입
            progression_type (str): 사용할 코드 진행 유형
            solo_complexity (float): 솔로 복잡도 (0.0-1.0)
            chord_complexity (float): 코드 컴핑 복잡도 (0.0-1.0)
            range_octaves (int): 솔로에 사용할 옥타브 범위
            
        Returns:
            dict: 솔로와 코드 MIDI 데이터 정보
        """
        # 솔로 생성
        solo_notes = self.generate_solo(scale_type, solo_complexity, range_octaves)
        
        # 코드 컴핑 생성
        chord_notes = self.generate_chord_comping(progression_type, chord_complexity)
        
        # MIDI 데이터 형식으로 변환
        solo_midi_data = self.convert_to_midi_data_format(solo_notes)
        chord_midi_data = self.convert_to_midi_data_format(chord_notes)
        
        return {
            'solo': {
                'notes': solo_notes,
                'midi_data': solo_midi_data,
                'count': len(solo_notes)
            },
            'chords': {
                'notes': chord_notes,
                'midi_data': chord_midi_data,
                'count': len(chord_notes)
            },
            'info': {
                'root_note': self.root_note,
                'tempo': self.tempo,
                'measures': self.measures,
                'scale_type': scale_type,
                'progression_type': progression_type
            }
        }
    
    def save_to_json(self, data, filename="bebop_data.json"):
        """데이터를 JSON 파일로 저장"""
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"데이터가 {filename}에 저장되었습니다.")

# 테스트 코드
if __name__ == "__main__":
    # 비밥 생성기 초기화 (루트 노트 = C4, 템포 = 160bpm)
    generator = BebopGenerator(root_note=60, tempo=160)
    
    # 마디 수 설정 (4/4 박자 기준)
    generator.set_measures(8)
    
    # ii-V-I 진행으로 비밥 솔로와 코드 생성
    data = generator.generate_bebop_solo_and_chords(
        scale_type='Bebop_Dominant',
        progression_type='ii-V-I',
        solo_complexity=0.8,  # 높은 복잡도의 솔로
        chord_complexity=0.6,  # 중간 복잡도의 코드 컴핑
        range_octaves=2        # 2옥타브 범위
    )
    
    # JSON 파일로 저장
    generator.save_to_json(data, "bebop_ii_V_I.json")
    
    print(f"비밥 솔로 노트 수: {data['solo']['count']}")
    print(f"코드 컴핑 노트 수: {data['chords']['count']}")