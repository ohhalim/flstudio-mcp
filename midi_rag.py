# midi_rag.py - MIDI RAG 분석기

import sys
import os
import json
import pickle
import numpy as np
from typing import List, Tuple, Dict, Set, Optional
import mido
from mido import MidiFile
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