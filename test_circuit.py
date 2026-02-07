import unittest
import numpy as np
from circuit_model import BassCircuit

class TestBassCircuit(unittest.TestCase):
    def setUp(self):
        self.circuit = BassCircuit()

    def test_direct_bypass(self):
        """
        Test with Volume=10, Tone=10 (Open), Cable=0, Amp=Infinity.
        Should be close to 0dB at low frequencies (ignoring L resonance).
        """
        self.circuit.params['vol1_pos'] = 1.0
        self.circuit.params['vol2_pos'] = 1.0
        self.circuit.params['tone_pos'] = 1.0 # Max Res (No Tone Cut)
        self.circuit.params['Ccable'] = 1e-12 # Minimal
        self.circuit.params['Rgnd'] = 1e-9    # Minimal
        
        freqs = np.array([100.0])
        _, mag, _, _ = self.circuit.solve_circuit(freqs)
        
        # Check if mag is reasonably close to 0dB (or slightly less due to source impedance voltage divider)
        # Source Impedance: Z_pu (Low freq ~ R_pu = 7k)
        # Load Impedance: R_amp (1M) // Pot (250k/2 approx?)
        # Vol Pot at 10: Input connected to Output. Parallel Pot resistance to ground?
        # Vol Pot (250k) is in parallel with output.
        # Two 250k Vol Pots in parallel = 125k.
        # Tone Pot (250k) also in parallel. Total Load ~ 83k.
        # Divider: 7k (Source) vs 83k (Load).
        # V_out = V_src * 83 / (83 + 7) = 0.92 * V_src.
        # 20*log10(0.92) = -0.7dB.
        
        print(f"Bypass Mag at 100Hz: {mag[0]:.2f} dB")
        self.assertTrue(mag[0] > -3.0, "Output should not be attenuated much in bypass")

    def test_tone_cut(self):
        """
        Test Tone Pot at 0. Spectrum should roll off.
        """
        self.circuit.params['tone_pos'] = 0.0 # Min Res (Max Cut)
        
        freqs = np.array([100.0, 5000.0])
        _, mag, _, _ = self.circuit.solve_circuit(freqs)
        
        print(f"Tone Cut Mag - 100Hz: {mag[0]:.2f} dB, 5kHz: {mag[1]:.2f} dB")
        self.assertTrue(mag[1] < mag[0] - 10.0, "High freq should be significantly attenuated")

    def test_independent_vol(self):
        """
        Test if turning down Vol1 affects Output but leaves Vol2 signal (if strictly parallel).
        Wait, in JB wiring, Vol pots are parallel.
        If I turn Vol1 to 0 (Wiper grounded), does it kill everything?
        Standard Jazz Bass Wiring (Decoupled? No, Standard is Coupled).
        In Standard JB (Input to Wiper? No, Input to Outer Lug).
        Input to Outer Lug (Pin 3). Wiper to Output.
        If Vol1 Wiper is at Ground (0):
        Pin 2 is Grounded.
        Pin 2 is connected to Output Bus.
        So Output Bus is Grounded.
        So Vol1 = 0 kills EVERYTHING (Master Mute).
        
        This is a known "feature" of Jazz Basses if wired standardly (Input to Output reversed allows independent?).
        "Independent Wiring": Input to Wiper, Output from Outer Lug.
        Standard Wiring: Input to Outer Lug, Output from Wiper.
        In Standard Wiring, Vol 0 shorts the Output Jack. Mutes everything.
        
        Let's check my model's behavior.
        My model:
        Node 1 (Pin 3/Input) -- R_up -- Node 3 (Pin 2/Output) -- R_down -- Node 5 (Gnd).
        If pos=0, R_up=Total, R_down=0.
        Node 3 shorted to Node 5.
        Yes, it should mute everything.
        
        Let's verify this "Standard JB Behavior".
        """
        self.circuit.params['vol1_pos'] = 0.0 # Mute entire bass?
        self.circuit.params['vol2_pos'] = 1.0 
        
        freqs = np.array([100.0])
        _, mag, _, _ = self.circuit.solve_circuit(freqs)
        
        print(f"Vol1=0, Vol2=10 Mag: {mag[0]:.2f} dB")
        # In Independent Wiring:
        # Vol1=0 means PU1 is grounded (inputs grounded).
        # Vol1 Pin3 is connected to Out via R_upper (250k).
        # Vol2=10 means PU2 connected to Out via R_upper (0 ohm).
        # So we have PU2 -> Out. And Out has 250k load to Ground (from Vol1).
        # Plus Amp Load (1M).
        # Source Impedance (PU2) ~ 7.5k.
        # Load Impedance ~ 250k // 1M ~ 200k.
        # Divider: 200 / (200 + 7.5) ~ 0.96.
        # So loss should be minimal (< 1dB).
        self.assertTrue(mag[0] > -3.0, "Independent Wiring: Vol 0 should NOT mute everything. Signal should pass from Vol2.")

    def test_waveform_generation(self):
        """
        Test generate_waveform to ensure solve_circuit handles list input correctly.
        """
        try:
            t, sig_in, sig_out = self.circuit.generate_waveform(440.0)
            self.assertEqual(len(t), len(sig_out))
            print("Waveform generation successful")
        except TypeError as e:
            self.fail(f"generate_waveform raised TypeError: {e}")

if __name__ == '__main__':
    unittest.main()
