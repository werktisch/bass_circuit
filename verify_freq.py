import numpy as np
from circuit_model import BassCircuit

def verify():
    circuit = BassCircuit()
    
    # Standard Params (Match defaults in app.py)
    # L=3.0H, R=7k, Pot=250k, Cable=3m (300pF)
    params = {
        'L1': 3.0, 'L2': 3.5,
        'R1': 7000, 'R2': 7500,
        'Rv1_total': 250000, 'Rv2_total': 250000, 'Rt_total': 250000,
        'vol1_pos': 1.0, 'vol2_pos': 1.0, 'tone_pos': 1.0, # Full Ten
        'Ct': 0.047e-6,
        'Ccable': 300e-12, # 3m
        'Rgnd': 0.0,
    }
    circuit.params.update(params)
    
    freqs = np.logspace(1.3, 4.3, 500) # 20Hz to 20kHz
    _, mag, _, _ = circuit.solve_circuit(freqs)
    
    # Analyze
    ref_level = mag[0]
    peak_idx = np.argmax(mag)
    peak_freq = freqs[peak_idx]
    peak_level = mag[peak_idx]
    
    cutoff_level = ref_level - 3.0
    below = np.where(mag < cutoff_level)[0]
    
    print(f"Reference (20Hz): {ref_level:.2f} dB")
    print(f"Resonant Peak: {peak_freq:.0f} Hz @ {peak_level:.2f} dB")
    
    if len(below) > 0:
        cutoff_freq = freqs[below[0]]
        print(f"Cutoff (-3dB): {cutoff_freq:.0f} Hz")
    else:
        print("Cutoff (-3dB): > 20kHz")

    # Check with Tone 0
    circuit.params['tone_pos'] = 0.0
    _, mag0, _, _ = circuit.solve_circuit(freqs)
    
    below0 = np.where(mag0 < (mag0[0] - 3.0))[0]
    if len(below0) > 0:
        print(f"Tone=0 Cutoff: {freqs[below0[0]]:.0f} Hz")

if __name__ == "__main__":
    verify()
