# bebop_solo_mcp.py

import sys
import time
import threading
import random
import os
import json
import pickle
import numpy as np
from typing import List, Tuple, Dict, Set, Optional
from mcp.server.fastmcp import FastMCP
import mido
from mido import Message, MidiFile
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
from collections import defaultdict
import glob

def debug_log(message):
    print(message, file=sys.stderr, flush=True)

class MidiRAGAnalyzer:
    """MIDI 파일 분석 및 RAG 시스템"""
    
    def __init__(self, midi_folder_path: str = "./midi_data"):
        self.midi_folder = midi_folder_path
        self.melody_database = []  # 멜로디 데이터베이스
        self.chord_database = []   # 화성 데이터베이스
        self.embeddings = None     # 임베딩 벡터들
        self.scaler = StandardScaler()
        self.index_to_melody = {}  # 인덱스에서 멜로디로 매핑
        
        # MIDI 데이터베이스 파일 경로
        self.db_file = "midi_rag_database.pkl"
        
        # 폴더가 없으면 생성
        os.makedirs(midi_folder_path, exist_ok=True)
    
    def analyze_midi_file(self, midi_path: str) -> Dict:
        """MIDI 파일 분석하여 화성과 멜로디 추출"""
        try:
            midi_file = MidiFile(midi_path)
            
            # 트랙별로 노트 이벤트 수집
            melody_track = []
            chord_track = []
            
            for track in midi_file.tracks:
                notes = []
                current_time = 0
                
                for msg in track:
                    current_time += msg.time
                    
                    if msg.type == 'note_on' and msg.velocity > 0:
                        notes.append({
                            'note': msg.note,
                            'time': current_time,
                            'velocity': msg.velocity,
                            'channel': msg.channel
                        })
                    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                        # 노트 종료 처리
                        for note in reversed(notes):
                            if note['note'] == msg.note and 'duration' not in note:
                                note['duration'] = current_time - note['time']
                                break
                
                # 멜로디와 화성 분리 (채널 또는 음역대 기준)
                if len(notes) > 0:
                    avg_pitch = sum(n['note'] for n in notes) / len(notes)
                    if avg_pitch > 60:  # C4 이상은 멜로디로 간주
                        melody_track.extend(notes)
                    else:  # C4 이하는 화성으로 간주
                        chord_track.extend(notes)
            
            return {
                'melody': sorted(melody_track, key=lambda x: x['time']),
                'chords': sorted(chord_track, key=lambda x: x['time']),
                'filename': os.path.basename(midi_path)
            }
        
        except Exception as e:
            debug_log(f"MIDI 파일 분석 오류 {midi_path}: {e}")
            return None
    
    def extract_chord_progression(self, chords: List[Dict]) -> List[List[int]]:
        """화성 진행 패턴 추출"""
        if not chords:
            return []
        
        # 시간별로 동시에 연주되는 노트들을 그룹화
        chord_groups = []
        current_group = []
        current_time = chords[0]['time']
        time_tolerance = 100  # 100ms 이내는 같은 화성으로 간주
        
        for chord in chords:
            if abs(chord['time'] - current_time) <= time_tolerance:
                current_group.append(chord['note'] % 12)  # 옥타브 정규화
            else:
                if current_group:
                    chord_groups.append(sorted(list(set(current_group))))
                current_group = [chord['note'] % 12]
                current_time = chord['time']
        
        if current_group:
            chord_groups.append(sorted(list(set(current_group))))
        
        return chord_groups
    
    def extract_melody_features(self, melody: List[Dict]) -> np.ndarray:
        """멜로디에서 특징 벡터 추출"""
        if not melody:
            return np.zeros(20)  # 기본 특징 벡터 크기
        
        notes = [n['note'] for n in melody]
        durations = [n.get('duration', 100) for n in melody]
        velocities = [n['velocity'] for n in melody]
        
        features = [
            # 기본 통계
            np.mean(notes), np.std(notes), np.min(notes), np.max(notes),
            np.mean(durations), np.std(durations),
            np.mean(velocities), np.std(velocities),
            
            # 음정 간격 분석
            np.mean(np.diff(notes)) if len(notes) > 1 else 0,
            np.std(np.diff(notes)) if len(notes) > 1 else 0,
            
            # 리듬 패턴
            len(melody),  # 노트 개수
            np.sum(durations),  # 총 길이
            
            # 음계 분석 (12개 음에 대한 히스토그램)
            *[notes.count(i % 12) / len(notes) for i in range(12)]
        ]
        
        return np.array(features, dtype=np.float32)
    
    def build_database(self):
        """MIDI 폴더의 모든 파일을 분석하여 데이터베이스 구축"""
        debug_log(f"MIDI 데이터베이스 구축 시작: {self.midi_folder}")
        
        midi_files = glob.glob(os.path.join(self.midi_folder, "*.mid")) + \
                    glob.glob(os.path.join(self.midi_folder, "*.midi"))
        
        if not midi_files:
            debug_log("MIDI 파일을 찾을 수 없습니다. 예시 파일을 생성합니다.")
            self.create_example_midi_files()
            return
        
        all_features = []
        
        for midi_file in midi_files:
            debug_log(f"분석 중: {midi_file}")
            analysis = self.analyze_midi_file(midi_file)
            
            if analysis:
                chord_progression = self.extract_chord_progression(analysis['chords'])
                melody_features = self.extract_melody_features(analysis['melody'])
                
                entry = {
                    'filename': analysis['filename'],
                    'melody': analysis['melody'],
                    'chord_progression': chord_progression,
                    'features': melody_features
                }
                
                self.melody_database.append(entry)
                all_features.append(melody_features)
                self.index_to_melody[len(self.melody_database) - 1] = analysis['melody']
        
        if all_features:
            # 특징 벡터 정규화 및 임베딩 생성
            self.embeddings = self.scaler.fit_transform(all_features)
            debug_log(f"데이터베이스 구축 완료: {len(self.melody_database)}개 파일")
            
            # 데이터베이스 저장
            self.save_database()
        else:
            debug_log("분석 가능한 MIDI 파일이 없습니다.")
    
    def create_example_midi_files(self):
        """예시 MIDI 파일들 생성"""
        debug_log("예시 MIDI 파일 생성 중...")
        
        # 간단한 재즈 스탠다드 패턴들
        patterns = [
            {
                'name': 'cmajor_scale.mid',
                'melody': [60, 62, 64, 65, 67, 69, 71, 72],
                'chords': [[60, 64, 67], [65, 69, 72], [67, 71, 62], [60, 64, 67]]
            },
            {
                'name': 'blues_pattern.mid', 
                'melody': [60, 63, 65, 66, 67, 70, 72],
                'chords': [[60, 64, 67], [60, 64, 67, 70], [65, 69, 72], [60, 64, 67]]
            },
            {
                'name': 'jazz_ii_v_i.mid',
                'melody': [67, 69, 71, 72, 74, 76, 77, 79],
                'chords': [[62, 65, 69, 72], [67, 70, 74, 77], [60, 64, 67, 71]]
            }
        ]
        
        for pattern in patterns:
            self.create_midi_file(pattern['name'], pattern['melody'], pattern['chords'])
    
    def create_midi_file(self, filename: str, melody_notes: List[int], chord_notes: List[List[int]]):
        """프로그래밍적으로 MIDI 파일 생성"""
        mid = MidiFile()
        
        # 멜로디 트랙
        melody_track = mido.MidiTrack()
        mid.tracks.append(melody_track)
        
        melody_track.append(mido.MetaMessage('set_tempo', tempo=120))
        
        for note in melody_notes:
            melody_track.append(mido.Message('note_on', note=note, velocity=80, time=0))
            melody_track.append(mido.Message('note_off', note=note, velocity=0, time=480))
        
        # 화성 트랙
        chord_track = mido.MidiTrack()
        mid.tracks.append(chord_track)
        
        for chord in chord_notes:
            # 화성 시작
            for i, note in enumerate(chord):
                chord_track.append(mido.Message('note_on', note=note, velocity=60, time=0 if i > 0 else 0))
            
            # 화성 지속
            chord_track.append(mido.Message('note_off', note=chord[0], velocity=0, time=960))
            for note in chord[1:]:
                chord_track.append(mido.Message('note_off', note=note, velocity=0, time=0))
        
        # 파일 저장
        filepath = os.path.join(self.midi_folder, filename)
        mid.save(filepath)
        debug_log(f"예시 MIDI 파일 생성: {filepath}")
    
    def save_database(self):
        """데이터베이스를 파일로 저장"""
        data = {
            'melody_database': self.melody_database,
            'embeddings': self.embeddings,
            'scaler': self.scaler,
            'index_to_melody': self.index_to_melody
        }
        
        with open(self.db_file, 'wb') as f:
            pickle.dump(data, f)
        debug_log(f"데이터베이스 저장됨: {self.db_file}")
    
    def load_database(self) -> bool:
        """저장된 데이터베이스 로드"""
        if not os.path.exists(self.db_file):
            return False
        
        try:
            with open(self.db_file, 'rb') as f:
                data = pickle.load(f)
            
            self.melody_database = data['melody_database']
            self.embeddings = data['embeddings']
            self.scaler = data['scaler']
            self.index_to_melody = data['index_to_melody']
            
            debug_log(f"데이터베이스 로드됨: {len(self.melody_database)}개 항목")
            return True
        except Exception as e:
            debug_log(f"데이터베이스 로드 오류: {e}")
            return False
    
    def find_similar_melodies(self, target_chords: Set[int], top_k: int = 3) -> List[Tuple[List[Dict], float]]:
        """입력 화성과 유사한 멜로디 검색"""
        if not self.melody_database or self.embeddings is None:
            return []
        
        # 입력 화성을 특징 벡터로 변환
        target_features = self.chord_to_features(target_chords)
        target_vector = self.scaler.transform([target_features])
        
        # 코사인 유사도 계산
        similarities = cosine_similarity(target_vector, self.embeddings)[0]
        
        # 상위 k개 결과 반환
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            if similarities[idx] > 0.1:  # 최소 유사도 임계값
                melody = self.index_to_melody[idx]
                results.append((melody, similarities[idx]))
        
        return results
    
    def chord_to_features(self, chord_notes: Set[int]) -> np.ndarray:
        """화성을 특징 벡터로 변환"""
        # 화성 분석
        notes = sorted(list(chord_notes))
        if not notes:
            return np.zeros(20)
        
        # 기본 통계
        root = notes[0] % 12
        chord_type = self.analyze_chord_type(notes)
        
        # 특징 벡터 생성 (멜로디 특징과 유사한 형태)
        features = [
            np.mean(notes), np.std(notes), np.min(notes), np.max(notes),
            len(notes), 0, 0, 0,  # duration, velocity 관련은 0으로
            0, 0, len(notes), 0,  # 음정간격, 리듬 관련
            
            # 12개 음에 대한 히스토그램
            *[1 if i in [n % 12 for n in notes] else 0 for i in range(12)]
        ]
        
        return np.array(features, dtype=np.float32)
    
    def analyze_chord_type(self, notes: List[int]) -> str:
        """화성 타입 분석"""
        if len(notes) < 2:
            return 'major'
        
        intervals = [(note - notes[0]) % 12 for note in notes[1:]]
        
        if 3 in intervals and 7 in intervals:
            return 'minor'
        elif 4 in intervals and 10 in intervals:
            return 'dominant'
        elif 4 in intervals and 7 in intervals:
            return 'major'
        else:
            return 'other'


class BebopSoloGenerator:
    """비밥 솔로라인 생성기 (RAG 기능 포함)"""
    
    def __init__(self, midi_folder: str = "./midi_data"):
        # RAG 시스템 초기화
        self.rag_analyzer = MidiRAGAnalyzer(midi_folder)
        self.use_rag = True  # RAG 사용 여부
        
        self.current_chord_notes = set()  # 현재 눌린 노트들
        self.solo_notes = []  # 생성된 솔로라인 노트들
        self.is_listening = False
        self.input_port = None
        self.output_port = None
        
        # 비밥 스케일 정의
        self.bebop_scales = {
            'major': [0, 2, 4, 5, 7, 8, 9, 11],      # 메이저 비밥 (크로매틱 패싱톤 추가)
            'minor': [0, 2, 3, 5, 7, 8, 9, 10],      # 마이너 비밥
            'dominant': [0, 2, 4, 5, 7, 9, 10, 11],  # 도미넌트 비밥 (b7과 natural 7 모두)
            'diminished': [0, 2, 3, 5, 6, 8, 9, 11], # 디미니쉬드
            'chromatic': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]  # 크로매틱
        }
        
        # 비밥 리듬 패턴 (16분음표 기준)
        self.bebop_rhythms = {
            'straight': [1, 1, 1, 1],           # 고른 16분음표
            'swing': [1.5, 0.5, 1.5, 0.5],     # 스윙 리듬
            'syncopated': [0.5, 1, 0.5, 2],    # 싱코페이션
            'triplet': [1, 1, 1],              # 3연음표
        }
        
        # 비밥 멜로디 패턴 (방향성)
        self.bebop_patterns = {
            'ascending_run': 'up',      # 상행 런
            'descending_run': 'down',   # 하행 런
            'chromatic_approach': 'chromatic',  # 크로매틱 어프로치
            'enclosure': 'around',      # 인클로저 (위아래에서 타겟 노트로)
            'arpeggiated': 'arpeggio'   # 아르페지오
        }
    
    def setup_midi_ports(self, input_port_name=None, output_port_name=None):
        """MIDI 포트 설정"""
        try:
            # 입력 포트 설정 (외부 키보드)
            input_ports = mido.get_input_names()
            if input_port_name and input_port_name in input_ports:
                self.input_port = mido.open_input(input_port_name, callback=self.on_midi_input)
            elif input_ports:
                # 첫 번째 사용가능한 입력 포트 사용
                self.input_port = mido.open_input(input_ports[0], callback=self.on_midi_input)
                debug_log(f"입력 포트 연결: {input_ports[0]}")
            
            # 출력 포트 설정 (FL Studio로)
            output_ports = mido.get_output_names()
            if output_port_name and output_port_name in output_ports:
                self.output_port = mido.open_output(output_port_name)
            elif output_ports:
                self.output_port = mido.open_output(output_ports[0])
                debug_log(f"출력 포트 연결: {output_ports[0]}")
                
            return True
        except Exception as e:
            debug_log(f"MIDI 포트 설정 오류: {e}")
            return False
    
    def on_midi_input(self, message):
        """외부 키보드에서 MIDI 입력 받을 때"""
        if not self.is_listening:
            return
            
        if message.type == 'note_on' and message.velocity > 0:
            # 노트 온: 코드에 추가
            self.current_chord_notes.add(message.note)
            debug_log(f"노트 추가: {message.note}, 현재 코드: {sorted(self.current_chord_notes)}")
            
            # 비밥 솔로라인 생성 및 전송
            if len(self.current_chord_notes) >= 2:  # 최소 2개 노트
                self.generate_and_send_bebop_solo()
                
        elif message.type == 'note_off' or (message.type == 'note_on' and message.velocity == 0):
            # 노트 오프: 코드에서 제거
            self.current_chord_notes.discard(message.note)
            debug_log(f"노트 제거: {message.note}, 현재 코드: {sorted(self.current_chord_notes)}")
            
            # 남은 노트가 있으면 다시 솔로라인 생성
            if len(self.current_chord_notes) >= 2:
                self.generate_and_send_bebop_solo()
            else:
                # 모든 솔로 노트 끄기
                self.stop_all_solo_notes()
    
    def detect_chord_type(self, notes: Set[int]) -> str:
        """코드 타입 감지"""
        if len(notes) < 2:
            return 'major'
        
        notes_list = sorted(list(notes))
        root = notes_list[0] % 12
        
        # 루트 기준 상대 음정 계산
        intervals = [(note - root) % 12 for note in notes_list]
        intervals = sorted(list(set(intervals)))
        
        # 패턴 매칭
        if 3 in intervals:  # 단3도 포함
            return 'minor'
        elif 10 in intervals:  # 단7도 포함
            return 'dominant'
        elif len(intervals) >= 4:  # 복잡한 코드
            return 'diminished'
        else:
            return 'major'
    
    def generate_bebop_solo(self, chord_notes: Set[int], pattern_type='ascending_run') -> List[Tuple[int, float]]:
        """비밥 솔로라인 생성 (노트, 리듬) 튜플 리스트 반환"""
        if not chord_notes:
            return []
        
        root = min(chord_notes) % 12
        chord_type = self.detect_chord_type(chord_notes)
        
        # 코드에 맞는 비밥 스케일 선택
        scale_type = self.get_bebop_scale_for_chord(chord_type)
        bebop_scale = self.bebop_scales[scale_type]
        
        # 비밥 리듬 선택
        rhythm_pattern = self.bebop_rhythms['swing']  # 기본 스윙 리듬
        
        # 솔로라인 생성
        solo_line = self.create_bebop_line(root, bebop_scale, pattern_type, chord_notes)
        
        # 리듬과 노트 조합
        solo_with_rhythm = []
        for i, note in enumerate(solo_line):
            rhythm_value = rhythm_pattern[i % len(rhythm_pattern)]
            solo_with_rhythm.append((note, rhythm_value))
        
        return solo_with_rhythm
    
    def get_bebop_scale_for_chord(self, chord_type: str) -> str:
        """코드 타입에 맞는 비밥 스케일 선택"""
        chord_to_scale = {
            'major': 'major',
            'minor': 'minor', 
            'dominant': 'dominant',
            'diminished': 'diminished'
        }
        return chord_to_scale.get(chord_type, 'major')
    
    def create_bebop_line(self, root: int, scale: List[int], pattern: str, chord_notes: Set[int]) -> List[int]:
        """비밥 라인 생성"""
        base_octave = max(chord_notes) + 12  # 코드보다 한 옥타브 위
        
        # 패턴에 따른 노트 생성
        if pattern == 'ascending_run':
            notes = self.generate_ascending_run(root, scale, base_octave)
        elif pattern == 'descending_run':
            notes = self.generate_descending_run(root, scale, base_octave)
        elif pattern == 'chromatic_approach':
            notes = self.generate_chromatic_approach(root, scale, base_octave)
        elif pattern == 'enclosure':
            notes = self.generate_enclosure(root, scale, base_octave)
        else:
            notes = self.generate_ascending_run(root, scale, base_octave)  # 기본
        
        return notes[:8]  # 최대 8개 노트
    
    def generate_ascending_run(self, root: int, scale: List[int], base_octave: int) -> List[int]:
        """상행 런 생성"""
        notes = []
        for i, interval in enumerate(scale):
            note = base_octave + interval
            if 48 <= note <= 96:  # C3~C7 범위
                notes.append(note)
            if len(notes) >= 8:
                break
        return notes
    
    def generate_descending_run(self, root: int, scale: List[int], base_octave: int) -> List[int]:
        """하행 런 생성"""
        notes = []
        for i, interval in enumerate(reversed(scale)):
            note = base_octave + interval
            if 48 <= note <= 96:
                notes.append(note)
            if len(notes) >= 8:
                break
        return notes
    
    def generate_chromatic_approach(self, root: int, scale: List[int], base_octave: int) -> List[int]:
        """크로매틱 어프로치 생성"""
        target_note = base_octave + scale[0]  # 스케일의 첫 번째 노트
        notes = [
            target_note - 1,  # 크로매틱 어프로치
            target_note,      # 타겟 노트
            target_note + 2,  # 스케일 내 다음 노트
            target_note + 4,
            target_note + 7,
            target_note + 9,
        ]
        return [n for n in notes if 48 <= n <= 96]
    
    def generate_enclosure(self, root: int, scale: List[int], base_octave: int) -> List[int]:
        """인클로저 패턴 생성"""
        target_note = base_octave + scale[2]  # 스케일의 3번째 노트를 타겟으로
        notes = [
            target_note + 1,  # 위에서 어프로치
            target_note - 1,  # 아래에서 어프로치
            target_note,      # 타겟 노트
            target_note + 4,  # 다음 스케일 노트들
            target_note + 7,
            target_note + 9,
        ]
        return [n for n in notes if 48 <= n <= 96]
    
    def generate_and_send_bebop_solo(self):
        """비밥 솔로라인 생성 및 FL Studio 전송 (RAG 기능 포함)"""
        if not self.current_chord_notes or not self.output_port:
            return
        
        # 이전 솔로 노트들 끄기
        self.stop_all_solo_notes()
        
        # RAG를 사용할지 결정
        if self.use_rag and self.rag_analyzer.melody_database:
            # RAG로 유사한 멜로디 검색
            rag_melody = self.generate_rag_melody()
            if rag_melody:
                self.solo_notes = rag_melody
                debug_log(f"RAG 멜로디 사용: {[note for note, rhythm in self.solo_notes]}")
            else:
                # RAG 실패 시 기본 비밥 생성
                self.solo_notes = self.generate_fallback_bebop_solo()
                debug_log("기본 비밥 생성 사용")
        else:
            # 기본 비밥 솔로라인 생성
            self.solo_notes = self.generate_fallback_bebop_solo()
            debug_log("기본 비밥 생성 사용")
        
        # FL Studio로 솔로라인 전송
        self.send_bebop_solo_to_fl(self.solo_notes)
    
    def generate_rag_melody(self) -> Optional[List[Tuple[int, float]]]:
        """유사한 멜로디를 RAG로 검색하여 생성"""
        try:
            # 현재 화성과 유사한 멜로디 검색
            similar_melodies = self.rag_analyzer.find_similar_melodies(self.current_chord_notes, top_k=3)
            
            if not similar_melodies:
                return None
            
            # 가장 유사한 멜로디 선택
            best_melody, similarity = similar_melodies[0]
            debug_log(f"RAG 매칭 유사도: {similarity:.3f}")
            
            # MIDI 노트를 리듬과 함께 변환
            melody_with_rhythm = []
            rhythm_pattern = self.bebop_rhythms['swing']
            
            for i, note_data in enumerate(best_melody[:8]):  # 최대 8개 노트
                note = note_data['note']
                # 원래 리듬 또는 기본 리듬 사용
                rhythm = rhythm_pattern[i % len(rhythm_pattern)]
                melody_with_rhythm.append((note, rhythm))
            
            return melody_with_rhythm
            
        except Exception as e:
            debug_log(f"RAG 멜로디 생성 오류: {e}")
            return None
    
    def generate_fallback_bebop_solo(self) -> List[Tuple[int, float]]:
        """기본 비밥 솔로라인 생성 (기존 로직)"""
        pattern_types = ['ascending_run', 'descending_run', 'chromatic_approach', 'enclosure']
        selected_pattern = random.choice(pattern_types)
        return self.generate_bebop_solo(self.current_chord_notes, selected_pattern)
    
    def send_bebop_solo_to_fl(self, solo_notes: List[Tuple[int, float]]):
        """FL Studio로 비밥 솔로라인 전송"""
        if not self.output_port:
            return
        
        # 시작 신호
        self.send_midi_note(3)  # 비밥 솔로 모드 신호
        time.sleep(0.01)
        
        # 노트 개수
        self.send_midi_note(len(solo_notes))
        time.sleep(0.01)
        
        # 각 솔로 노트와 리듬 전송
        for note, rhythm in solo_notes:
            self.send_midi_note(note)
            time.sleep(0.01)
            # 리듬 정보를 CC 로 전송 (CC1 사용)
            rhythm_cc = int(rhythm * 64)  # 0-127 범위로 정규화
            cc_msg = Message('control_change', control=1, value=rhythm_cc)
            self.output_port.send(cc_msg)
            time.sleep(0.01)
        
        # 종료 신호
        self.send_midi_note(126)
        time.sleep(0.01)
    
    def stop_all_solo_notes(self):
        """모든 솔로 노트 끄기"""
        if not self.output_port:
            return
        
        # 정지 신호
        self.send_midi_note(4)  # 솔로 정지 신호
        time.sleep(0.01)
    
    def send_midi_note(self, note: int, velocity: int = 100):
        """MIDI 노트 전송"""
        if self.output_port:
            note_on = Message('note_on', note=note, velocity=velocity)
            self.output_port.send(note_on)
            time.sleep(0.01)
            note_off = Message('note_off', note=note, velocity=0)
            self.output_port.send(note_off)
    
    def start_listening(self):
        """외부 키보드 듣기 시작"""
        self.is_listening = True
        debug_log("비밥 솔로라인 생성 시작")
    
    def stop_listening(self):
        """외부 키보드 듣기 중지"""
        self.is_listening = False
        self.stop_all_solo_notes()
        self.current_chord_notes.clear()
        debug_log("비밥 솔로라인 생성 중지")

# MCP 서버 초기화
try:
    debug_log("비밥 솔로라인 MCP 서버 시작...")
    
    # FastMCP 서버 생성
    mcp = FastMCP("bebop_solo")
    
    # 비밥 솔로 생성기 인스턴스 (RAG 기능 포함)
    bebop_generator = BebopSoloGenerator("./midi_data")
    
    # RAG 데이터베이스 초기화
    debug_log("RAG 데이터베이스 초기화 중...")
    if not bebop_generator.rag_analyzer.load_database():
        debug_log("기존 데이터베이스가 없어 새로 구축합니다...")
        bebop_generator.rag_analyzer.build_database()
    
    @mcp.tool()
    def list_midi_ports():
        """사용 가능한 MIDI 포트 목록"""
        input_ports = mido.get_input_names()
        output_ports = mido.get_output_names()
        
        return {
            "input_ports": input_ports,
            "output_ports": output_ports,
            "status": "listening" if bebop_generator.is_listening else "stopped"
        }
    
    @mcp.tool()
    def start_bebop_listening(input_port: str = None, output_port: str = None):
        """외부 키보드에서 화성 입력을 듣고 비밥 솔로라인 생성 시작"""
        try:
            # MIDI 포트 설정
            if bebop_generator.setup_midi_ports(input_port, output_port):
                bebop_generator.start_listening()
                return f"비밥 솔로라인 생성 시작됨 (입력: {input_port or 'auto'}, 출력: {output_port or 'auto'})"
            else:
                return "MIDI 포트 설정 실패"
        except Exception as e:
            return f"오류: {e}"
    
    @mcp.tool()
    def stop_bebop_listening():
        """비밥 솔로라인 생성 중지"""
        try:
            bebop_generator.stop_listening()
            return "비밥 솔로라인 생성 중지됨"
        except Exception as e:
            return f"오류: {e}"
    
    @mcp.tool()
    def get_bebop_status():
        """현재 비밥 솔로라인 생성 상태"""
        return {
            "listening": bebop_generator.is_listening,
            "current_chord": sorted(list(bebop_generator.current_chord_notes)),
            "solo_notes": [note for note, rhythm in bebop_generator.solo_notes] if bebop_generator.solo_notes else [],
            "input_connected": bebop_generator.input_port is not None,
            "output_connected": bebop_generator.output_port is not None
        }
    
    @mcp.tool()
    def test_bebop_solo(chord_notes_str: str, pattern: str = 'ascending_run'):
        """비밥 솔로라인 테스트 (실시간 모드가 아닐 때)"""
        try:
            chord_notes = set(int(n.strip()) for n in chord_notes_str.split(','))
            solo_notes = bebop_generator.generate_bebop_solo(chord_notes, pattern)
            
            if bebop_generator.output_port:
                bebop_generator.send_bebop_solo_to_fl(solo_notes)
            
            solo_note_list = [note for note, rhythm in solo_notes]
            return f"테스트 비밥 솔로라인 생성 ({pattern}): {solo_note_list}"
        except Exception as e:
            return f"오류: {e}"
    
    @mcp.tool()
    def build_midi_database(midi_folder: str = "./midi_data"):
        """지정된 폴더의 MIDI 파일들로 RAG 데이터베이스 구축"""
        try:
            bebop_generator.rag_analyzer.midi_folder = midi_folder
            bebop_generator.rag_analyzer.build_database()
            return f"데이터베이스 구축 완료: {midi_folder}"
        except Exception as e:
            return f"데이터베이스 구축 오류: {e}"
    
    @mcp.tool()
    def toggle_rag_mode(use_rag: bool = True):
        """RAG 모드 온/오프 전환"""
        bebop_generator.use_rag = use_rag
        mode = "RAG 모드" if use_rag else "기본 비밥 모드"
        return f"{mode}로 전환됨"
    
    @mcp.tool()
    def search_similar_melodies(chord_notes_str: str, top_k: int = 3):
        """입력 화성과 유사한 멜로디 검색"""
        try:
            chord_notes = set(int(n.strip()) for n in chord_notes_str.split(','))
            similar_melodies = bebop_generator.rag_analyzer.find_similar_melodies(chord_notes, top_k)
            
            if not similar_melodies:
                return "유사한 멜로디를 찾을 수 없습니다."
            
            results = []
            for i, (melody, similarity) in enumerate(similar_melodies):
                melody_notes = [note_data['note'] for note_data in melody[:8]]
                results.append(f"{i+1}. 유사도: {similarity:.3f}, 노트: {melody_notes}")
            
            return "\n".join(results)
        except Exception as e:
            return f"오류: {e}"
    
    @mcp.tool() 
    def get_database_info():
        """RAG 데이터베이스 정보 확인"""
        db_size = len(bebop_generator.rag_analyzer.melody_database)
        rag_status = "활성" if bebop_generator.use_rag else "비활성"
        
        return {
            "database_size": db_size,
            "rag_status": rag_status,
            "midi_folder": bebop_generator.rag_analyzer.midi_folder,
            "database_file": bebop_generator.rag_analyzer.db_file
        }
    
    if __name__ == "__main__":
        debug_log("비밥 솔로라인 MCP 서버 실행 중... (RAG 기능 포함)")
        mcp.run(transport='stdio')

except Exception as e:
    debug_log(f"서버 초기화 오류: {e}")
    sys.exit(1)