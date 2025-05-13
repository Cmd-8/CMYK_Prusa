import customtkinter as ctk
from PIL import Image
from tkinter import filedialog, messagebox
import os
import re
import sys


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class GCodeToolSwitcher:
    def __init__(self, tool_names, tool_change_commands):
        self.layer_markers = ";LAYER_CHANGE"
        self.tool_change_commands = tool_change_commands
        self.tool_names = tool_names
        self.m104_pattern = re.compile(r'M104\.1\s+T(\d+)')
        self.tool_pattern = re.compile(r'\bT(\d+)\s+S\d+\s+L\d+\s+D\d+')
        self.simple_tool_pattern = re.compile(r'^T(\d+)\s*;')
        self.park_pattern = re.compile(r'P0\s+S1\s+L2\s+D0')
        self.pickup_pattern = re.compile(r'T(\d+)\s+S1\s+L0\s+D0')

    def parse_layers(self, gcode_content):
        """Parse G-code content and identify layer positions."""
        layers = []
        lines = gcode_content.split('\n')
        for i, line in enumerate(lines):
            if self.layer_markers in line:
                layers.append(i)
        return layers, lines

    def calculate_tool_distribution(self, total_layers, ratio_pattern):
        """Calculate which tool to use for each layer based on sequential layer-by-layer printing."""
        tool_sequence = []
        while len(tool_sequence) < total_layers:
            for tool_idx, count in enumerate(ratio_pattern):
                for _ in range(int(count)):
                    if len(tool_sequence) < total_layers:
                        tool_sequence.append(tool_idx)
                    else:
                        break
                if count % 1 > 0 and len(tool_sequence) < total_layers:
                    tool_sequence.append(tool_idx)
                if len(tool_sequence) >= total_layers:
                    break
        return tool_sequence

    def modify_gcode(self, gcode_lines, layer_positions, tool_sequence):
        """Modify G-code to update tool commands with appropriate tool numbers."""
        modified_gcode = gcode_lines.copy()
        current_layer = -1
        current_tool = None
        active_tool = None  # Track which tool is currently active
        for i, line in enumerate(modified_gcode):
            if i in layer_positions:
                current_layer += 1
                if current_layer < len(tool_sequence):
                    current_tool = tool_sequence[current_layer]
            if current_tool is not None:
                park_match = self.park_pattern.search(line)
                if park_match and active_tool == current_tool:
                    modified_gcode[
                        i] = f"; {line} - skipped parking as T{current_tool} ({self.tool_names[current_tool]}) is already active"
                    continue
                pickup_match = self.pickup_pattern.search(line)
                if pickup_match:
                    tool_to_pickup = int(pickup_match.group(1))
                    if tool_to_pickup != current_tool:
                        modified_gcode[i] = re.sub(r'T\d+', f'T{current_tool}', line)
                        active_tool = current_tool
                    elif active_tool == current_tool:
                        modified_gcode[
                            i] = f"; {line} - skipped pickup as T{current_tool} ({self.tool_names[current_tool]}) is already active"
                        continue
                    else:
                        active_tool = current_tool
                m104_match = self.m104_pattern.search(line)
                if m104_match:
                    old_tool = int(m104_match.group(1))
                    if old_tool != current_tool:
                        if active_tool != current_tool:
                            p_match = re.search(r'P(\d+)', line)
                            q_match = re.search(r'Q(\d+)', line)
                            s_match = re.search(r'S(\d+)', line)
                            p_value = p_match.group(1) if p_match else "120"
                            q_value = q_match.group(1) if q_match else str(int(p_value) + current_tool + 1)
                            s_value = s_match.group(1) if s_match else "210"
                            new_command = f"M104.1 T{current_tool} P{p_value} Q{q_value} S{s_value}"
                            comment_match = re.search(r';.*$', line)
                            if comment_match:
                                new_command += f" {comment_match.group(0)}"
                            else:
                                new_command += f" ; switched from T{old_tool} ({self.tool_names[old_tool]}) to T{current_tool} ({self.tool_names[current_tool]})"
                            modified_gcode[i] = new_command
                            active_tool = current_tool
                        else:
                            modified_gcode[
                                i] = f"; {line} - skipped as T{current_tool} ({self.tool_names[current_tool]}) is already active"
                            continue
                tool_match = self.tool_pattern.search(line)
                if tool_match:
                    old_tool = int(tool_match.group(1))
                    if old_tool != current_tool:
                        new_line = re.sub(r'\bT\d+\b', f'T{current_tool}', line)
                        modified_gcode[i] = new_line
                        active_tool = current_tool
                simple_match = self.simple_tool_pattern.search(line)
                if simple_match:
                    old_tool = int(simple_match.group(1))
                    if old_tool != current_tool:
                        new_line = re.sub(r'^T\d+', f'T{current_tool}', line)
                        modified_gcode[i] = new_line
                        active_tool = current_tool
        return modified_gcode

    def process_file(self, input_file, output_file, ratio_pattern):
        with open(input_file, 'r') as f:
            gcode_content = f.read()
        layer_positions, gcode_lines = self.parse_layers(gcode_content)
        total_layers = len(layer_positions)
        tool_sequence = self.calculate_tool_distribution(total_layers, ratio_pattern)
        modified_lines = self.modify_gcode(gcode_lines, layer_positions, tool_sequence)
        with open(output_file, 'w') as f:
            f.write('\n'.join(modified_lines))
        return total_layers, tool_sequence


class App(ctk.CTk):
    def __init__(self, tool_switcher, default_ratio, tool_names_ui):
        super().__init__()
        self.title("Prusa XL Color By Cmd.8")
        self.geometry('1000x800')

        self.tool_switcher = tool_switcher
        self.ratio_pattern = default_ratio
        self.tool_names_ui = tool_names_ui

        # Initialize the tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(side="top", anchor="w", padx=5, pady=5, expand=True, fill="both")
        # Create all the tabs
        self.create_tabs()

    def create_widgets(self, tab):
        main_frame = ctk.CTkFrame(tab)
        main_frame.pack(fill="both", expand=True, padx=10, pady=4)

        # Input file section
        input_frame = ctk.CTkFrame(main_frame)
        input_frame.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(input_frame, text="Input G-code File", font=("Arial", 14, "bold")).pack(anchor="w", padx=5, pady=2)

        input_file_frame = ctk.CTkFrame(input_frame)
        input_file_frame.pack(fill="x", padx=5, pady=2)

        self.input_file_var = ctk.StringVar()
        ctk.CTkEntry(input_file_frame, textvariable=self.input_file_var, width=400).pack(
            side=ctk.LEFT, padx=5, pady=2, fill="x", expand=True)
        ctk.CTkButton(input_file_frame, text="Browse...", command=self.browse_input, width=100).pack(
            side=ctk.RIGHT, padx=5, pady=2)

        # Output file section
        output_frame = ctk.CTkFrame(main_frame)
        output_frame.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(output_frame, text="Output G-code File", font=("Arial", 14, "bold")).pack(anchor="w", padx=5,
                                                                                               pady=2)

        output_file_frame = ctk.CTkFrame(output_frame)
        output_file_frame.pack(fill="x", padx=5, pady=2)

        self.output_file_var = ctk.StringVar()
        ctk.CTkEntry(output_file_frame, textvariable=self.output_file_var, width=400).pack(
            side=ctk.LEFT, padx=5, pady=2, fill="x", expand=True)
        ctk.CTkButton(output_file_frame, text="Browse...", command=self.browse_output, width=100).pack(
            side=ctk.RIGHT, padx=5, pady=2)

        # Ratio pattern section
        pattern_frame = ctk.CTkFrame(main_frame)
        pattern_frame.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(pattern_frame, text="Tool Ratio Pattern (C:M:Y:W:BL)", font=("Arial", 14, "bold")).pack(
            anchor="w", padx=5, pady=2)

        ratio_frame = ctk.CTkFrame(pattern_frame)
        ratio_frame.pack(fill="x", padx=5, pady=5)

        self.tool_entries = []
        for i, name in enumerate(self.tool_names_ui):
            ctk.CTkLabel(ratio_frame, text=f"{name}:").grid(row=0, column=i * 2, padx=5, pady=5, sticky="e")
            var = ctk.StringVar(value=str(self.ratio_pattern[i]))
            entry = ctk.CTkEntry(ratio_frame, textvariable=var, width=50)
            entry.grid(row=0, column=i * 2 + 1, padx=5, pady=5, sticky="w")
            self.tool_entries.append(var)

        # Help text
        help_text = (
            "Enter the number of layers to print consecutively with each tool.\n"
            "For example, (2:1) will print 2 layers with Tool 1, then 1 layer with Tool 2,\n"
            "and repeat this pattern until the print is finished."
        )
        ctk.CTkLabel(pattern_frame, text=help_text, wraplength=700, justify="left").pack(padx=10, pady=5, anchor="w")

        # Process button
        process_frame = ctk.CTkFrame(main_frame)
        process_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(process_frame, text="Process G-code", command=self.process_gcode).pack(
            side=ctk.RIGHT, padx=5)

        # Status and log section
        log_frame = ctk.CTkFrame(main_frame)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        ctk.CTkLabel(log_frame, text="Status Log", font=("Arial", 14, "bold")).pack(anchor="w", padx=5, pady=5)

        self.log_text = ctk.CTkTextbox(log_frame, height=15, wrap="word")
        self.log_text.pack(fill="both", expand=True, side=ctk.LEFT)

    def browse_input(self):
        filename = filedialog.askopenfilename(
            title="Select G-code file",
            filetypes=[("G-code files", "*.gcode"), ("All files", "*.*")]
        )
        if filename:
            self.input_file_var.set(filename)
            basename = os.path.basename(filename)
            name, ext = os.path.splitext(basename)
            output_name = f"{name}_modified{ext}"
            output_dir = os.path.dirname(filename)
            self.output_file_var.set(os.path.join(output_dir, output_name))

    def browse_output(self):
        filename = filedialog.asksaveasfilename(
            title="Save G-code file",
            filetypes=[("G-code files", "*.gcode"), ("All files", "*.*")],
            defaultextension=".gcode"
        )
        if filename:
            self.output_file_var.set(filename)

    def get_current_pattern(self):
        pattern = []
        for var in self.tool_entries:
            try:
                value = float(var.get())
                pattern.append(value)
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid numbers for all tools")
                return None
        return pattern

    def process_gcode(self):
        input_file = self.input_file_var.get()
        output_file = self.output_file_var.get()
        if not input_file or not output_file:
            messagebox.showerror("Error", "Please specify both input and output files")
            return
        if not os.path.exists(input_file):
            messagebox.showerror("Error", f"Input file not found: {input_file}")
            return
        pattern = self.get_current_pattern()
        if pattern is None:
            return
        if sum(pattern) <= 0:
            messagebox.showerror("Error", "At least one tool must have a value greater than zero")
            return
        try:
            self.log_text.delete(1.0, ctk.END)
            self.log_text.insert(ctk.END, f"Processing file: {input_file}\n")
            self.log_text.insert(ctk.END, f"Output file: {output_file}\n")
            tool_pattern_string = ", ".join([f"{name}:{count}" for name, count in zip(self.tool_names_ui, pattern)])
            self.log_text.insert(ctk.END, f"Using tool ratio pattern: {tool_pattern_string}\n")
            self.log_text.update()
            total_layers, tool_sequence = self.tool_switcher.process_file(input_file, output_file, pattern)
            self.log_text.insert(ctk.END, f"\nProcessing complete!\n")
            self.log_text.insert(ctk.END, f"Total layers: {total_layers}\n\n")
            tool_counts = [0] * len(self.tool_names_ui)
            for tool in tool_sequence:
                tool_counts[tool] += 1
            for i, (count, name) in enumerate(zip(tool_counts, self.tool_names_ui)):
                if count > 0:
                    self.log_text.insert(ctk.END,
                                         f"Tool {i} ({name}) used for {count} layers ({count / total_layers * 100:.1f}%)\n")
            if total_layers > 0:
                display_count = min(20, total_layers)
                self.log_text.insert(ctk.END, f"\nFirst {display_count} layers tool sequence:\n")
                for i in range(display_count):
                    tool_num = tool_sequence[i]
                    self.log_text.insert(ctk.END, f"Layer {i + 1}: Tool {tool_num} ({self.tool_names_ui[tool_num]})\n")
            messagebox.showinfo("Success", f"G-code processed successfully!\n{total_layers} layers modified.")
        except Exception as e:
            self.log_text.insert(ctk.END, f"\nError: {str(e)}\n")
            messagebox.showerror("Error", f"Failed to process G-code: {str(e)}")

    def hex_to_rgb(self, hex_value):
        """Convert hex to RGB"""
        hex_value = hex_value.lstrip('#')
        return tuple(int(hex_value[i:i + 2], 16) for i in (0, 2, 4))

    def rgb_to_hex(self, r, g, b):
        """Convert RGB to hex"""
        return "#{:02x}{:02x}{:02x}".format(r, g, b)

    def mix_colors(self, colors, weights):
        """Mix colors based on weighted contributions"""
        total_weight = sum(weights)
        r_mix = g_mix = b_mix = 0

        for i in range(len(colors)):
            r, g, b = self.hex_to_rgb(colors[i])
            r_mix += r * weights[i]
            g_mix += g * weights[i]
            b_mix += b * weights[i]

        r_mix = int(r_mix / total_weight)
        g_mix = int(g_mix / total_weight)
        b_mix = int(b_mix / total_weight)

        return self.rgb_to_hex(r_mix, g_mix, b_mix), r_mix, g_mix, b_mix

    def rgb_to_cmyk(self, r, g, b):
        """Convert RGB to CMYK"""
        r, g, b = r / 255.0, g / 255.0, b / 255.0
        k = min(1 - r, 1 - g, 1 - b)

        if k == 1:
            c = m = y = 0
        else:
            c = (1 - r - k) / (1 - k)
            m = (1 - g - k) / (1 - k)
            y = (1 - b - k) / (1 - k)

        return round(c * 100), round(m * 100), round(y * 100), round(k * 100)

    def apply_mixed_color(self):
        """Apply the mixed color and display CMYK values"""
        colors = []
        weights = []

        # Collect non-empty color entries and weights
        for i in range(5):
            color = self.color_entries[i].get()
            weight = self.weight_entries[i].get()

            if color:
                colors.append(color)
                weights.append(int(weight) if weight else 1)

        if len(colors) < 2:
            self.result_label.configure(text="Please enter at least two hex colors!")
            return

        # Mix the colors
        mixed_color_hex, r, g, b = self.mix_colors(colors, weights)

        # Convert the mixed RGB to CMYK
        c, m, y, k = self.rgb_to_cmyk(r, g, b)

        # Update the button's color and the CMYK result label
        self.color_button.configure(fg_color=mixed_color_hex)
        self.result_label.configure(text=f"CMYK: C={c} M={m} Y={y} K={k}")

    def create_tabs(self):
        # Add tabs to the tabview
        self.tab1 = self.tabview.add("Welcome")
        self.tab2 = self.tabview.add("Color Mixing")
        self.tab3 = self.tabview.add("CMYK")

        # Populate the tabs with content
        self.tab1_content(self.tab1)
        self.tab2_content(self.tab2)
        self.tab3_content(self.tab3)

    def tab1_content(self, tab):
        co_star = ctk.CTkLabel(tab, text="Co-Founder Mia")
        co_star.pack()

        # Load and display the image using resource_path
        image_path = resource_path(os.path.join("images", "Mia.png"))
        try:
            image = Image.open(image_path)
            ctk_image = ctk.CTkImage(light_image=image, size=(275, 325))
            label = ctk.CTkLabel(tab, image=ctk_image, text="")
            label.pack(padx=20, pady=20)
        except Exception as e:
            error_label = ctk.CTkLabel(tab, text=f"Error loading image: {str(e)}")
            error_label.pack(padx=20, pady=20)

        intro = ctk.CTkLabel(tab,
                             text="Welcome! For detailed instructions, please refer to 'How_To.pdf' and also take a look at my report paper."
                                  " Note that this has only been tested on Windows.")
        intro_2 = ctk.CTkLabel(tab,
                             text="The background changes depending on your system default background color like light or dark mode.")
        intro_3 = ctk.CTkLabel(tab,
                             text=
                                  "The background changes depending on your system's default background color, like light or dark mode."
                                  " You add two colors and weights for the color to show (you can use 0).")

        intro_4 = ctk.CTkLabel(tab,
                             text=
                                  "CMYK can run slowly on large objects."
                                  " Make sure that the file wasn't exported as binary G-Gode and only runs with Prusa XL")
        intro_5 = ctk.CTkLabel(tab,
                             text=
                                  "Input: Search and upload the G-Code."
                                  " Output: location of saved file."
                                  " Tool pattern: Is the color pattern."
                                  " Process: Switches the tool-head number."
                                  " Status: Output pattern text.")

        intro_6 = ctk.CTkLabel(tab,
                             text="Thanks to the Fab Lab for allowing me to test my project."
                                  " I've been coding for a year, so there’s still room for improvement, and some features—like color change over time still missing.")
        intro.pack()
        intro_2.pack()
        intro_3.pack()
        intro_4.pack()
        intro_5.pack()
        intro_6.pack()


    # Placeholder methods for other tabs
    def tab2_content(self, tab):
        """Content for Tab 1"""
        self.color_entries = []
        for row in range(5):
            color_entry = ctk.CTkEntry(tab, placeholder_text=f"Enter hex color {row + 1} (e.g., #ff5733)", height=10,
                                       width=300)
            color_entry.pack(pady=5, )
            self.color_entries.append(color_entry)

        # Create entry widgets for color weights
        self.weight_entries = []
        for i in range(5):
            weight_entry = ctk.CTkEntry(tab, placeholder_text=f"Weight for color {i + 1}", height=10, width=300)
            weight_entry.pack(pady=5)
            self.weight_entries.append(weight_entry)

        # Create button to mix colors
        self.apply_button = ctk.CTkButton(tab, text="Mix Colors", command=self.apply_mixed_color)
        self.apply_button.pack(pady=5)

        # Create button to display mixed color
        self.color_button = ctk.CTkButton(tab, text="", fg_color="gray", width=300, height=100)  # Initially gray
        self.color_button.pack(pady=0)

        # Create label for CMYK result
        self.result_label = ctk.CTkLabel(tab, text="")
        self.result_label.pack(pady=5)

    def tab3_content(self, tab):
        self.create_widgets(tab)
        # cyml_lay = self.CYMK(tab)


class TwoToolApp(App):
    def __init__(self):
        tool_names = ["T1", "T2"]
        tool_change_commands = {
            0: "M104.1 T0 P120 Q122 S210 ; switch to tool 0 (T1)",
            1: "M104.1 T1 P120 Q121 S210 ; switch to tool 1 (T2)"
        }
        tool_switcher = GCodeToolSwitcher(tool_names, tool_change_commands)
        super().__init__(tool_switcher, [1, 1], tool_names)


# 3-Tool (RGB) Version
class ThreeToolApp(App):
    def __init__(self):
        tool_names = ["Red", "Green", "Blue"]
        tool_change_commands = {
            0: "M104.1 T0 P120 Q122 S210 ; switch to tool 0 (Red)",
            1: "M104.1 T1 P120 Q121 S210 ; switch to tool 1 (Green)",
            2: "M104.1 T2 P120 Q123 S210 ; switch to tool 2 (Blue)"
        }
        tool_switcher = GCodeToolSwitcher(tool_names, tool_change_commands)
        super().__init__(tool_switcher, [1, 1, 1], tool_names)


# 4-Tool (CMYK) Version
class FourToolApp(App):
    def __init__(self):
        tool_names = ["Cyan", "Magenta", "Yellow", "Black"]
        tool_change_commands = {
            0: "M104.1 T0 P120 Q122 S210 ; switch to tool 0 (Cyan)",
            1: "M104.1 T1 P120 Q121 S210 ; switch to tool 1 (Magenta)",
            2: "M104.1 T2 P120 Q123 S210 ; switch to tool 2 (Yellow)",
            3: "M104.1 T3 P120 Q124 S210 ; switch to tool 3 (Black)"
        }
        tool_switcher = GCodeToolSwitcher(tool_names, tool_change_commands)
        super().__init__(tool_switcher, [1, 1, 1, 1], tool_names)


# 5-Tool Version
class FiveToolApp(App):
    def __init__(self):
        tool_names = ["Cyan", "Magenta", "Yellow", "White", "Black"]
        tool_change_commands = {
            0: "M104.1 T0 P120 Q122 S210 ; switch to tool 0 (Cyan)",
            1: "M104.1 T1 P120 Q121 S210 ; switch to tool 1 (Magenta)",
            2: "M104.1 T2 P120 Q123 S210 ; switch to tool 2 (Yellow)",
            3: "M104.1 T3 P120 Q124 S210 ; switch to tool 3 (White)",
            4: "M104.1 T4 P120 Q125 S210 ; switch to tool 4 (Black)"
        }
        tool_switcher = GCodeToolSwitcher(tool_names, tool_change_commands)
        super().__init__(tool_switcher, [2, 0, 1, 0, 0], tool_names)


if __name__ == "__main__":
    tool_names = ["Cyan", "Magenta", "Yellow", "White", "Black"]
    tool_change_commands = {
        0: "M104.1 T0 P120 Q122 S210 ; switch to tool 0 (Cyan)",
        1: "M104.1 T1 P120 Q121 S210 ; switch to tool 1 (Magenta)",
        2: "M104.1 T2 P120 Q123 S210 ; switch to tool 2 (Yellow)",
        3: "M104.1 T3 P120 Q124 S210 ; switch to tool 3 (White)",
        4: "M104.1 T4 P120 Q125 S210 ; switch to tool 4 (Black)"
    }
    # Initialize the GCodeToolSwitcher with tool names and commands
    tool_switcher = GCodeToolSwitcher(tool_names, tool_change_commands)

    default_ratio = [2, 1, 2, 1, 1]  # Default tool usage pattern
    tool_names_ui = ["C", "M", "Y", "W", "BL"]  # UI names for tools

    # Create the App instance with the tool_switcher
    app = App(tool_switcher, default_ratio, tool_names_ui)
    app.mainloop()
