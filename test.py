import mido

max_values = {}

def print_max_values():
    print("\nCurrent max values:")
    for fader, value in max_values.items():
        print(f"Fader {fader}: {value}")

with mido.open_input() as inport:
    print("Listening for MIDI messages. Move all faders to their maximum positions.")
    print("Press Ctrl+C to stop.")
    
    try:
        for msg in inport:
            if msg.type == 'pitchwheel':
                fader = msg.channel
                value = msg.pitch + 8192  # Convert from -8192..8191 to 0..16383
                
                if fader not in max_values or value > max_values[fader]:
                    max_values[fader] = value
                    print(f"New max for Fader {fader}: {value}")
                    print_max_values()
    except KeyboardInterrupt:
        print("\nFinal max values:")
        print_max_values()
        print(f"\nOverall maximum value: {max(max_values.values())}")