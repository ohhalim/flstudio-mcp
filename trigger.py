from typing import Any
import httpx
import sys
from mcp.server.fastmcp import FastMCP
import mido
from mido import Message
import time

# 디버깅 로그 함수
def debug_log(message):
    print(message, file=sys.stderr, flush=True)

try:
    debug_log("Starting FL Studio MCP server...")
    
    # 사용 가능한 MIDI 포트 확인 및 로깅
    available_ports = mido.get_output_names()
    debug_log(f"Available MIDI ports: {available_ports}")
    
    # Initialize FastMCP server
    mcp = FastMCP("flstudio")
    
    # 첫 번째 사용 가능한 포트 사용 (인코딩 문제 회피)
    if available_ports:
        # 정확한 이름을 사용합니다 - 출력된 이름 그대로 복사
        midi_port = available_ports[0]  # 'IAC ÎìúÎùºÏù¥Î≤Ñ Î≤ÑÏä§ 1' 
        debug_log(f"Using MIDI port: {midi_port}")
    else:
        debug_log("ERROR: No MIDI output ports available!")
        sys.exit(1)
    
    # 실제 포트 목록에서 찾은 이름 사용
    output_port = mido.open_output(midi_port)
    debug_log(f"Successfully opened MIDI port: {midi_port}")
    
    # MIDI Note mappings for FL Studio commands
    NOTE_PLAY = 60          # C3
    NOTE_STOP = 61          # C#3
    NOTE_RECORD = 62        # D3
    NOTE_NEW_PROJECT = 63   # D#3
    NOTE_SET_BPM = 64       # E3
    NOTE_NEW_PATTERN = 65   # F3
    NOTE_SELECT_PATTERN = 66  # F#3
    NOTE_ADD_CHANNEL = 67   # G3
    NOTE_NAME_CHANNEL = 68  # G#3
    NOTE_ADD_NOTE = 69      # A3
    NOTE_ADD_TO_PLAYLIST = 70  # A#3
    NOTE_SET_PATTERN_LEN = 71  # B3
    NOTE_CHANGE_TEMPO = 72   

    # Define custom MIDI CC messages for direct step sequencer grid control
    CC_SELECT_CHANNEL = 100  # Select which channel to edit
    CC_SELECT_STEP = 110     # Select which step to edit
    CC_TOGGLE_STEP = 111     # Toggle the selected step on/off
    CC_STEP_VELOCITY = 112   # Set velocity for the selected step

    # Drum sound MIDI notes
    KICK = 36      # C1
    SNARE = 38     # D1
    CLAP = 39      # D#1
    CLOSED_HAT = 42  # F#1
    OPEN_HAT = 46  # A#1

    @mcp.tool()
    def list_midi_ports():
        """List all available MIDI input ports"""
        debug_log("\nAvailable MIDI Input Ports:")
        input_ports = mido.get_output_names()
        if not input_ports:
            debug_log("  No MIDI input ports found")
        else:
            for i, port in enumerate(input_ports):
                debug_log(f"  {i}: {port}")
        
        return input_ports

    @mcp.tool()
    def play():
        """Send MIDI message to start playback in FL Studio""" 
        # Send Note On for C3 (note 60)
        output_port.send(mido.Message('note_on', note=60, velocity=100))
        time.sleep(0.1)  # Small delay
        output_port.send(mido.Message('note_off', note=60, velocity=0))
        debug_log("Sent Play command")

    @mcp.tool()
    def stop():
        """Send MIDI message to stop playback in FL Studio"""
        # Send Note On for C#3 (note 61)
        output_port.send(mido.Message('note_on', note=61, velocity=100))
        time.sleep(0.1)  # Small delay
        output_port.send(mido.Message('note_off', note=61, velocity=0))
        debug_log("Sent Stop command")

    def int_to_midi_bytes(value):
        """
        Convert an integer value into an array of MIDI-compatible bytes (7-bit values)
        
        Args:
            value (int): The integer value to convert
            
        Returns:
            list: Array of MIDI bytes (each 0-127)
        """
        if value < 0:
            debug_log("Warning: Negative values not supported, converting to positive")
            value = abs(value)
        
        # Special case for zero
        if value == 0:
            return [0]
        
        # Convert to MIDI bytes (7-bit values, MSB first)
        midi_bytes = []
        while value > 0:
            # Extract the lowest 7 bits and prepend to array
            midi_bytes.insert(0, value & 0x7F)  # 0x7F = 127 (binary: 01111111)
            # Shift right by 7 bits
            value >>= 7
        
        return midi_bytes

    def change_tempo(bpm):
        """
        Change the tempo in FL Studio using a sequence of MIDI notes
        
        This function converts a BPM value to an array of MIDI notes,
        sends a start marker, the notes, and an end marker to trigger
        a tempo change in FL Studio.
        
        Args:
            bpm (float): The desired tempo in beats per minute
        """
        # Ensure BPM is within a reasonable range
        if bpm < 20 or bpm > 999:
            debug_log(f"Warning: BPM value {bpm} is outside normal range (20-999)")
            bpm = max(20, min(bpm, 999))
        
        # Convert BPM to integer
        bpm_int = int(bpm)
        
        # Convert to MIDI bytes
        midi_notes = int_to_midi_bytes(bpm_int)
        
        debug_log(f"Setting tempo to {bpm_int} BPM using note array: {midi_notes}")
        
        # Send start marker (note 72)
        send_midi_note(72)
        time.sleep(0.2)
        
        # Send each note in the array
        for note in midi_notes:
            send_midi_note(note)
            time.sleep(0.1)
        
        # Send end marker (note 73)
        send_midi_note(73)
        time.sleep(0.2)
        
        debug_log(f"Tempo change to {bpm_int} BPM sent successfully using {len(midi_notes)} notes")

    @mcp.tool()
    def send_melody(notes_data):
        """
        Send a sequence of MIDI notes with timing information to FL Studio for recording
        
        Args:
            notes_data (str): String containing note data in format "note,velocity,length,position"
                            with each note on a new line
        """
        # Parse the notes_data string into a list of note tuples
        notes = []
        for line in notes_data.strip().split('\n'):
            if not line.strip():
                continue
                
            parts = line.strip().split(',')
            if len(parts) != 4:
                debug_log(f"Warning: Skipping invalid line: {line}")
                continue
                
            try:
                note = min(127, max(0, int(parts[0])))
                velocity = min(127, max(0, int(parts[1])))
                length = max(0, float(parts[2]))
                position = max(0, float(parts[3]))
                notes.append((note, velocity, length, position))
            except ValueError:
                debug_log(f"Warning: Skipping line with invalid values: {line}")
                continue
        
        if not notes:
            return "No valid notes found in input data"
        
        # Create the MIDI data array (6 values per note)
        midi_data = []
        for note, velocity, length, position in notes:
            # 1. Note value (0-127)
            midi_data.append(note)
            
            # 2. Velocity value (0-127)
            midi_data.append(velocity)
            
            # 3. Length whole part (0-127)
            length_whole = min(127, int(length))
            midi_data.append(length_whole)
            
            # 4. Length decimal part (0-9)
            length_decimal = int(round((length - length_whole) * 10)) % 10
            midi_data.append(length_decimal)
            
            # 5. Position whole part (0-127)
            position_whole = min(127, int(position))
            midi_data.append(position_whole)
            
            # 6. Position decimal part (0-9)
            position_decimal = int(round((position - position_whole) * 10)) % 10
            midi_data.append(position_decimal)
        
        # Start MIDI transfer
        debug_log(f"Transferring {len(notes)} notes ({len(midi_data)} MIDI values)...")
        
        # Initial toggle signal (note 0)
        send_midi_note(0)
        time.sleep(0.01)
        
        # Send total count of notes
        send_midi_note(min(127, len(notes)))
        time.sleep(0.01)
        
        # Send all MIDI data values
        for i, value in enumerate(midi_data):
            send_midi_note(value)
            #time.sleep(0.1)
            #debug_log(f"Sent MIDI value {i+1}/{len(midi_data)}: {value}")
        
        send_midi_note(127)

        #debug_log(f"Melody transfer complete: {len(notes)} notes sent")
        return f"Melody successfully transferred: {len(notes)} notes ({len(midi_data)} MIDI values) sent to FL Studio"

    @mcp.tool()
    def receive_midi_note(note_data):
        """
        Receive MIDI note data from an external keyboard and process it.
        
        Args:
            note_data (str): String containing note data in format "note,velocity,length,position"
                            with each note on a new line
        """
        notes = []
        for line in note_data.strip().split('\n'):
            if not line.strip():
                continue

            parts = line.strip().split(',')
            if len(parts) != 4:
                debug_log(f"Warning: Skipping invalid line: {line}")
                continue
            
            try:
                note = min(127, max(0, int(parts[0])))
                velocity = min(127, max(0, int(parts[1])))
                length = max(0, float(parts[2]))
                position = max(0, float(parts[3]))
                notes.append((note, velocity, length, position))
            except ValueError:
                debug_log(f"Warning: Skipping line with invalid values: {line}")
                continue

        if not notes:
            return "No valid notes found in input data"
        
        # Process the received notes (예: MIDI 노트를 재생하거나 다른 작업 수행)
        for note, velocity, length, position in notes:
            send_midi_note(note, velocity, length)  # send_midi_note 함수를 사용하여 노트를 전송

    # RAG 에 접속 해서 백터 데이터 가져오는 것
    # 저장되는 데이터의 형태를 알아야해 
    # 바이너리인데 ??? 



    # Send a MIDI note message
    @mcp.tool()
    def send_midi_note(note, velocity=1, duration=0.01):
        """Send a MIDI note on/off message with specified duration"""
        note_on = Message('note_on', note=note, velocity=velocity)
        output_port.send(note_on)
        #debug_log(f"Sent MIDI note {note} (on), velocity {velocity}")
        time.sleep(duration)
        note_off = Message('note_off', note=note, velocity=0)
        output_port.send(note_off)
        debug_log(f"Sent MIDI note {note} (off)")
        #time.sleep(0.1)  # Small pause between messages
        
    if __name__ == "__main__":
        # Initialize and run the server
        debug_log("Running MCP server with stdio transport...")
        mcp.run(transport='stdio')

except Exception as e:
    debug_log(f"ERROR initializing FL Studio MCP: {e}")
    sys.exit(1)