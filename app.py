import panel as pn
import param
import numpy as np
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool
from circuit_model import BassCircuit

pn.extension(sizing_mode="stretch_width")

class BassApp(param.Parameterized):
    # --- Prams: Pickup ---
    L_neck = param.Number(default=3.0, bounds=(1.0, 6.0), step=0.1, label="Neck L (H)")
    L_bridge = param.Number(default=3.5, bounds=(1.0, 6.0), step=0.1, label="Bridge L (H)")
    R_neck = param.Number(default=7.0, bounds=(4.0, 15.0), step=0.1, label="Neck R (kΩ)")
    R_bridge = param.Number(default=7.5, bounds=(4.0, 15.0), step=0.1, label="Bridge R (kΩ)")

    # --- Params: Controls ---
    vol1_pot = param.Number(default=10.0, bounds=(0.0, 10.0), step=0.1, label="Neck Vol")
    vol2_pot = param.Number(default=10.0, bounds=(0.0, 10.0), step=0.1, label="Bridge Vol")
    tone_pot = param.Number(default=10.0, bounds=(0.0, 10.0), step=0.1, label="Master Tone")
    
    pot_resistance = param.Selector(default=250, objects=[250, 500], label="Pot Resistance (kΩ)")
    
    cap_value = param.Selector(default=0.047, objects=[0.022, 0.047, 0.1], label="Tone Cap (μF)")
    cap_fine = param.Number(default=0.0, bounds=(-10.0, 10.0), step=0.1, label="Cap Tolerance (%)")

    # --- Params: Environment ---
    cable_len = param.Number(default=3.0, bounds=(0.0, 10.0), step=0.5, label="Cable Length (m)")
    ground_qual = param.Number(default=0.0, bounds=(0.0, 5.0), step=0.1, label="Gnd Resistance (Ω)")

    # --- Params: Oscilloscope ---
    test_freq = param.Number(default=440, bounds=(20, 5000), step=10, label="Test Freq (Hz)")

    # --- Display Params ---
    cutoff_text = param.String(default="Cutoff: --- Hz")

    def __init__(self, **params):
        super().__init__(**params)
        self.circuit = BassCircuit()
        self.freqs = np.logspace(1.3, 4.3, 500) # 20Hz to 20kHz
        
        # Initialize DataSources
        self.freq_source = ColumnDataSource(data={'x': [], 'y': []})
        self.wave_source = ColumnDataSource(data={'t': [], 'in': [], 'out': []})
        
        # Initialize Plots
        self.freq_plot = self._init_freq_plot()
        self.wave_plot = self._init_wave_plot()
        
        # Trigger initial update
        self._update_plots()

    def _update_circuit_params(self):
        # Update circuit object based on current params
        self.circuit.params['L1'] = self.L_neck
        self.circuit.params['L2'] = self.L_bridge
        self.circuit.params['R1'] = self.R_neck * 1000.0
        self.circuit.params['R2'] = self.R_bridge * 1000.0
        
        pot_val = self.pot_resistance * 1000.0
        self.circuit.params['Rv1_total'] = pot_val
        self.circuit.params['Rv2_total'] = pot_val
        self.circuit.params['Rt_total'] = pot_val
        
        self.circuit.params['vol1_pos'] = self.vol1_pot / 10.0
        self.circuit.params['vol2_pos'] = self.vol2_pot / 10.0
        self.circuit.params['tone_pos'] = self.tone_pot / 10.0
        
        c_val = self.cap_value * (1.0 + self.cap_fine / 100.0) * 1e-6
        self.circuit.params['Ct'] = max(1e-10, c_val) # Safety
        
        # Cable: 100pF/m approx
        self.circuit.params['Ccable'] = (self.cable_len * 100e-12) + 1e-12
        
        self.circuit.params['Rgnd'] = self.ground_qual

    @param.depends('cap_value', 'cap_fine')
    def calculated_cap_text(self):
        val = self.cap_value * (1.0 + self.cap_fine / 100.0)
        return f"**Resulting Cap:** {val:.4f} μF"

    def _init_freq_plot(self):
        p = figure(
            title="Frequency Response", 
            x_axis_type="log", 
            y_range=(-60, 10),
            height=400,
            x_axis_label="Frequency (Hz)",
            y_axis_label="Magnitude (dB)",
            tools="pan,box_zoom,reset,save"
        )
        p.line('x', 'y', source=self.freq_source, line_width=2, color="navy")
        p.add_tools(HoverTool(tooltips=[("Freq", "@x{0.0} Hz"), ("Mag", "@y{0.1} dB")]))
        return p

    def _init_wave_plot(self):
        p = figure(
            title="Oscilloscope", 
            height=400,
            x_axis_label="Time (ms)",
            y_axis_label="Amplitude",
            y_range=(-1.5, 1.5),
            tools="pan,box_zoom,reset,save"
        )
        p.line('t', 'in', source=self.wave_source, legend_label="Input", line_width=2, color="gray", line_dash="dashed", alpha=0.6)
        p.line('t', 'out', source=self.wave_source, legend_label="Output", line_width=2, color="firebrick")
        p.legend.location = "top_right"
        return p

    @param.depends('L_neck', 'L_bridge', 'R_neck', 'R_bridge', 
                   'vol1_pot', 'vol2_pot', 'tone_pot', 
                   'pot_resistance', 'cap_value', 'cap_fine', 
                   'cable_len', 'ground_qual', 'test_freq', watch=True)
    def _update_plots(self):
        self._update_circuit_params()
        
        # CalcFreq Response
        f = self.freqs
        _, mag, _, _ = self.circuit.solve_circuit(f)
        self.freq_source.data = {'x': f, 'y': mag}
        
        # Calc Resonant Peak (Max)
        peak_idx = np.argmax(mag)
        peak_freq = f[peak_idx]
        peak_val = mag[peak_idx]
        
        # Calc -3dB Limit (Bandwidth)
        # Reference is low freq level
        ref_mag = mag[0] 
        limit_mag = ref_mag - 3.0
        
        # Find where it drops below limit
        # Use reversed array to find the *last* crossing if there are multiple?
        # Usually looking for the point where it leaves the passband. 
        # Since it's lowpass, we look for index > peak_idx where mag < limit_mag
        
        below_indices = np.where((f > peak_freq) & (mag < limit_mag))[0]
        
        if len(below_indices) > 0:
            limit_hz = f[below_indices[0]]
            limit_str = f"{limit_hz:.0f} Hz"
        else:
            limit_str = "> 20 kHz"

        self.cutoff_text = f"**Peak:** {peak_freq:.0f}Hz ({peak_val:+.1f}dB) | **Cutoff:** {limit_str}"

        # Calc Waveform
        t, sig_in, sig_out = self.circuit.generate_waveform(self.test_freq)
        self.wave_source.data = {'t': t*1000, 'in': sig_in, 'out': sig_out}
        
        # Update Titles (Optional, requires handle on plot title property which is not reactive by default in basic bokeh)
        self.wave_plot.title.text = f"Waveform at {self.test_freq} Hz"

    @param.depends('tone_pot', 'pot_resistance', 'cap_value', 'cap_fine')
    def cutoff_text_value(self):
        return self.cutoff_text

    def view(self):
        sidebar = pn.Column(
            "## Circuit Controls",
            pn.Tabs(
                ("Pickups", pn.Column(self.param.L_neck, self.param.R_neck, self.param.L_bridge, self.param.R_bridge)),
                ("Controls", pn.Column(
                    self.param.vol1_pot, 
                    self.param.vol2_pot, 
                    self.param.tone_pot,
                    self.cutoff_text_value,
                    "### Tone Circuit Components",
                    self.param.pot_resistance,
                    self.param.cap_value,
                    self.param.cap_fine,
                    self.calculated_cap_text
                )),
                ("Wiring", pn.Column(self.param.cable_len, self.param.ground_qual))
            ),
            "### Oscilloscope",
            self.param.test_freq,
        )
        
        main = pn.Column(
            "### Frequency Response",
            self.freq_plot,
            "### Oscilloscope",
            self.wave_plot
        )
        
        return pn.template.FastListTemplate(
            title="Bass Circuit Simulator",
            sidebar=[sidebar],
            main=[main],
            accent_base_color="#2F4F4F",
            header_background="#2F4F4F",
        )

# Serve the app
if __name__ == "__main__.py":
    BassApp().view().servable()
elif __name__.startswith("bokeh"):
    BassApp().view().servable()
else:
    # For manual testing or direct execution
    pass
