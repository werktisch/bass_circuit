import numpy as np
from scipy import signal

class BassCircuit:
    def __init__(self):
        # Default Parameters
        self.params = {
            # Pickup 1 (Neck)
            'L1': 3.0,       # Henries
            'R1': 7000.0,    # Ohms
            'C1': 150e-12,   # Farads
            
            # Pickup 2 (Bridge)
            'L2': 3.5,
            'R2': 7500.0,
            'C2': 150e-12,

            # Volume Pots (A-Curve simulated by user input mapping)
            # R_vol_total is the total resistance of the pot
            'Rv1_total': 250000.0,
            'Rv2_total': 250000.0,
            # pos is 0.0 to 1.0. 
            # We will calculate R_upper and R_lower based on pos and taper.
            'vol1_pos': 1.0, 
            'vol2_pos': 1.0,

            # Tone Pot
            'Rt_total': 250000.0,
            'tone_pos': 1.0,
            'Ct': 0.047e-6,

            # Cable / Load
            'Ccable': 400e-12, # 100pF/m * 4m
            'Ramp': 1.0e6,     # 1 MegOhm
            
            # Ground Wiring Resistance
            'Rgnd': 0.01       # Close to 0 for good wiring
        }

    def _get_pot_resistance(self, total_r, pos, taper='log'):
        """
        Calculate wiper division resistances.
        Returns (R_upper, R_lower)
        R_upper: resistance between Input(Pin3) and Wiper(Pin2)
        R_lower: resistance between Wiper(Pin2) and Ground(Pin1)
        """
        # Avoid division by zero or infinite conductance
        pos = max(0.001, min(0.999, pos))
        
        if taper == 'log':
            # Simple approximation of Audio Taper (10% res at 50% rotation)
            # Normalized R (0-1) vs Position (0-1)
            # A common approximation is y = x^a. For 10% at 50%, 0.1 = 0.5^a => a ~ 3.32
            # Let's use a slightly gentler curve or standard equation.
            # Using exponential approximation for smoother feel: R = R_tot * (exp(b*pos)-1)/(exp(b)-1)
            # But simple power law works well enough for visual simulation.
            alpha = 3.0 
            factor = pos ** alpha
        else:
            factor = pos

        r_lower = total_r * factor
        # In a real pot, the total resistance is constant.
        # Pin3-Pin2 = Total - R_lower
        r_upper = total_r - r_lower
        
        return r_upper, r_lower

    def solve_circuit(self, freqs):
        """
        Calculate frequency response for an array of frequencies.
        Returns: 
            freqs (array): Reference
            mag (array): Magnitude in dB
            phase (array): Phase in degrees
            h (array): Complex transfer function V_out / V_source
        """
        # Constants
        freqs = np.asarray(freqs)
        w_arr = 2 * np.pi * freqs
        n_freqs = len(freqs)
        
        # Pre-calculate Potentiometer Resistors
        Rv1_up, Rv1_down = self._get_pot_resistance(self.params['Rv1_total'], self.params['vol1_pos'])
        Rv2_up, Rv2_down = self._get_pot_resistance(self.params['Rv2_total'], self.params['vol2_pos'])
        Rt_val, _ = self._get_pot_resistance(self.params['Rt_total'], self.params['tone_pos']) 
        # Note: Tone pot is rheostat mode (variable resistor), usually Pin 2+3 tied or Pin 2 used.
        # Actually in guitar tone control, it's used as a variable resistor in series with Cap.
        # So Resistance = Rt_total * (1 - factor) if we turn knob "down" for more bass? 
        # "Tone 10" means 0 resistance in path? No, Tone 10 means max resistance (open circuit), minimal capacitor effect (Pass through).
        # Tone 0 means 0 resistance (capacitor fully to ground).
        # Let's stick to: tone_pos 1.0 (Open/Max Res) -> tone_pos 0.0 (Short/0 Res).
        # So R_tone_current = Rt_total * (1.0 - factor_of_pos) ?
        # Standard: 250k Pot. Full CW (10) = 250k resistance -> Cap is isolated. Full CCW (0) = 0 resistance -> Cap dumps treble.
        
        # Let's re-verify A-curve behavior for Tone.
        # Usually Log pot. At 10, resistance is Max. At 0, resistance is 0.
        # _get_pot_resistance returns (Total-R_lower, R_lower).
        # We need the resistance value itself.
        # Let's use the 'factor' from the _get_pot_resistance logic directly logic
        # If pos=1.0 (Full), we want Max Resistance. If pos=0.0, we want 0.
        # The 'factor' calculated goes 0->1 as pos goes 0->1.
        # So we want Resistance = Total_R * factor? 
        # If pos=1 (knob 10), factor=1, R=250k. Correct.
        # If pos=0 (knob 0), factor=0, R=0. Correct.
        # So correct variable method:
        _, Rt_use = self._get_pot_resistance(self.params['Rt_total'], self.params['tone_pos'], taper='log')

        # Components values
        L1, R1, C1 = self.params['L1'], self.params['R1'], self.params['C1']
        L2, R2, C2 = self.params['L2'], self.params['R2'], self.params['C2']
        Ct = self.params['Ct']
        Ccable = self.params['Ccable']
        Ramp = self.params['Ramp']
        Rgnd = self.params['Rgnd'] + 1e-9 # Avoid singular matrix if 0

        # Output arrays
        v_out_complex = np.zeros(n_freqs, dtype=complex)

        # Nodal Analysis
        # Nodes:
        # 1: Neck PU Hot (Input to Vol1)
        # 2: Bridge PU Hot (Input to Vol2)
        # 3: Output Bus (Junction of Vol1_Wiper, Vol2_Wiper, Tone, Output)
        # 4: Tone Cap Junction (between Rt and Ct)
        # 5: Ground Return (Components' ground reference)
        # Reference Node 0: True Earth Ground
        
        # Matrix size: 5x5
        
        for i in range(n_freqs):
            w = w_arr[i]
            jw = 1j * w
            
            # Admittances (Y = 1/Z)
            Y_pu1_series = 1.0 / (R1 + jw*L1)
            Y_pu1_para = jw * C1
            
            Y_pu2_series = 1.0 / (R2 + jw*L2)
            Y_pu2_para = jw * C2
            
            Y_v1_up = 1.0 / Rv1_up
            Y_v1_down = 1.0 / Rv1_down
            
            Y_v2_up = 1.0 / Rv2_up
            Y_v2_down = 1.0 / Rv2_down
            
            Y_t_res = 1.0 / max(1.0, Rt_use) # Avoid div/0
            Y_t_cap = jw * Ct
            
            Y_cable = jw * Ccable
            Y_amp = 1.0 / Ramp
            
            Y_gnd = 1.0 / Rgnd

            # Initialize Y matrix and I vector
            Y = np.zeros((5, 5), dtype=complex)
            I = np.zeros(5, dtype=complex)

            # Node 1: Neck PU Hot = Vol1 Wiper (Pin 2)
            # Connected: PU1_Series(to Src), PU1_Para(to 5), V1_Down(to 5), V1_Up(to 3)
            # Independent Wiring: Input to Wiper. Wiper connected to Ground via R_lower. Wiper connected to Output via R_upper.
            # Kirchhoff: (V1 - Vsrc)/Zseries + (V1 - V5)*Ypara + (V1 - V5)*Y_v1_down + (V1 - V3)*Y_v1_up = 0
            # V1 * (Yseries + Ypara + Y_v1_down + Y_v1_up) - V3*Y_v1_up - V5*(Ypara + Y_v1_down) = Vsrc*Yseries
            
            Vsrc1 = 1.0
            Vsrc2 = 1.0 # Assuming in phase

            Y[0, 0] = Y_pu1_series + Y_pu1_para + Y_v1_down + Y_v1_up
            Y[0, 2] = -Y_v1_up
            Y[0, 4] = -(Y_pu1_para + Y_v1_down)
            I[0] = Vsrc1 * Y_pu1_series

            # Node 2: Bridge PU Hot = Vol2 Wiper (Pin 2)
            # Connected: PU2_Series(to Src), PU2_Para(to 5), V2_Down(to 5), V2_Up(to 3)
            Y[1, 1] = Y_pu2_series + Y_pu2_para + Y_v2_down + Y_v2_up
            Y[1, 2] = -Y_v2_up
            Y[1, 4] = -(Y_pu2_para + Y_v2_down)
            I[1] = Vsrc2 * Y_pu2_series

            # Node 3: Output Bus (Pin 3 of both Vols)
            # Connected: V1_Up(to 1), V2_Up(to 2), Tone(to 4), Cable(to 5), Amp(to 5)
            # Note: In Independent wiring, Output is connected to Pin 3.
            # Pin 3 connects to Wiper(Node1/2) via R_upper.
            # V1_Down connects Wiper to Gnd. It is handled at Node 1/2.
            # So Node 3 has NO direct connection to V1_Down/V2_Down.
            
            Y[2, 0] = -Y_v1_up
            Y[2, 1] = -Y_v2_up
            Y[2, 2] = Y_v1_up + Y_v2_up + Y_t_res + Y_cable + Y_amp
            Y[2, 3] = -Y_t_res
            Y[2, 4] = -(Y_cable + Y_amp)
            
            # Node 4: Tone Cap Junction
            # Connected: T_Res(to 3), T_Cap(to 5)
            Y[3, 2] = -Y_t_res
            Y[3, 3] = Y_t_res + Y_t_cap
            Y[3, 4] = -Y_t_cap
            
            # Node 5: Control Ground
            # Connected to: PU1_Para, PU2_Para, V1_Down, V2_Down, T_Cap, Cable, Amp, Rgnd
            Y[4, 0] = -(Y_pu1_para + Y_v1_down)
            Y[4, 1] = -(Y_pu2_para + Y_v2_down)
            Y[4, 2] = -(Y_cable + Y_amp)
            Y[4, 3] = -Y_t_cap
            Y[4, 4] = Y_pu1_para + Y_pu2_para + Y_v1_down + Y_v2_down + Y_t_cap + Y_cable + Y_amp + Y_gnd
            
            # Solve
            try:
                V = np.linalg.solve(Y, I)
                v_out_complex[i] = V[2] - V[4]
            except np.linalg.LinAlgError:
                v_out_complex[i] = 0.0

        mag = 20 * np.log10(np.abs(v_out_complex) + 1e-12)
        phase = np.angle(v_out_complex, deg=True)
        
        return freqs, mag, phase, v_out_complex

    def generate_waveform(self, freq_hz, num_cycles=4, points=1000):
        """
        Generate input (sine) and output waveforms.
        """
        if freq_hz <= 0: return np.array([]), np.array([]), np.array([])
        
        duration = num_cycles / freq_hz
        t = np.linspace(0, duration, points)
        
        sig_in = np.sin(2 * np.pi * freq_hz * t)
        
        # Calculate response at this specific frequency
        # Note: solve_circuit takes a list/array of freqs
        _, _, _, h_complex = self.solve_circuit(np.array([freq_hz]))
        h = h_complex[0]
        
        # Apply magnitude and phase
        amp = np.abs(h)
        phase_rad = np.angle(h)
        
        sig_out = amp * np.sin(2 * np.pi * freq_hz * t + phase_rad)
        
        return t, sig_in, sig_out
