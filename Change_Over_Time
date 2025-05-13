import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import math


class GCodeToolSwitcher:
    def __init__(self):
        self.layer_markers = ";LAYER_CHANGE"
        # Updated to use M104.1 commands for 5 tools
        self.tool_change_commands = {
            0: "M104.1 T0 P120 Q122 S210 ; switch to tool 0 (Cyan)",
            1: "M104.1 T1 P120 Q121 S210 ; switch to tool 1 (Magenta)",
            2: "M104.1 T2 P120 Q123 S210 ; switch to tool 2 (Yellow)",
            3: "M104.1 T3 P120 Q124 S210 ; switch to tool 3 (White)",
            4: "M104.1 T4 P120 Q125 S210 ; switch to tool 4 (Black)"
        }
        # Regular expressions to match different tool commands
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
        """Calculate which tool to use for each layer based on the ratio pattern for 5 tools.

        ratio_pattern is a list of tuples, each containing 5 values representing
        the ratios for Cyan, Magenta, Yellow, White, and Black tools.
        """
        tool_sequence = []

        # Calculate how many layers per section
        num_sections = len(ratio_pattern)
        layers_per_section = math.ceil(total_layers / num_sections)

        # For each layer, determine which tool to use
        for current_layer in range(total_layers):
            # Calculate which section we're in
            section_index = int(current_layer / layers_per_section)
            if section_index >= len(ratio_pattern):
                section_index = len(ratio_pattern) - 1

            # Get current ratio (C:M:Y:W:BL)
            cyan_ratio, magenta_ratio, yellow_ratio, white_ratio, black_ratio = ratio_pattern[section_index]

            # Calculate total ratio and cumulative distribution
            total_ratio = cyan_ratio + magenta_ratio + yellow_ratio + white_ratio + black_ratio

            # If all ratios are zero, default to black (tool 4)
            if total_ratio <= 0:
                tool = 4  # Default to black
            else:
                # Create cumulative thresholds for tool selection
                cumulative = [
                    cyan_ratio,  # Tool 0 (Cyan)
                    cyan_ratio + magenta_ratio,  # Tool 1 (Magenta)
                    cyan_ratio + magenta_ratio + yellow_ratio,  # Tool 2 (Yellow)
                    cyan_ratio + magenta_ratio + yellow_ratio + white_ratio  # Tool 3 (White)
                    # Anything else is Tool 4 (Black)
                ]

                # Normalize cumulative thresholds
                cumulative = [c / total_ratio for c in cumulative]

                # Within each section, calculate position of current layer
                relative_position = (current_layer % layers_per_section) / layers_per_section

                # Determine which tool to use based on the relative position
                tool = 4  # Default to black (tool 4)
                for i, threshold in enumerate(cumulative):
                    if relative_position < threshold:
                        tool = i
                        break

            tool_sequence.append(tool)

        return tool_sequence

    def modify_gcode(self, gcode_lines, layer_positions, tool_sequence):
        """Modify G-code to update tool commands with appropriate tool numbers."""
        modified_gcode = gcode_lines.copy()
        current_layer = -1
        current_tool = None
        active_tool = None  # Track which tool is currently active

        # Process each line of the G-code
        for i, line in enumerate(modified_gcode):
            # Check if we've entered a new layer
            if i in layer_positions:
                current_layer += 1
                if current_layer < len(tool_sequence):
                    current_tool = tool_sequence[current_layer]

            # If we have a current tool, replace tool commands
            if current_tool is not None:
                # Check for parking commands (P0 S1 L2 D0)
                park_match = re.search(r'P0\s+S1\s+L2\s+D0', line)
                if park_match and active_tool == current_tool:
                    # Skip parking if the tool we want is already active
                    modified_gcode[i] = f"; {line} - skipped parking as T{current_tool} is already active"
                    continue

                # Check for tool pickup commands
                pickup_match = re.search(r'T(\d+)\s+S1\s+L0\s+D0', line)
                if pickup_match:
                    tool_to_pickup = int(pickup_match.group(1))
                    # If we're supposed to pick up a tool, but should be using a different one
                    if tool_to_pickup != current_tool:
                        modified_gcode[i] = re.sub(r'T\d+', f'T{current_tool}', line)
                        active_tool = current_tool
                    # If we're already using this tool, skip the pickup
                    elif active_tool == current_tool:
                        modified_gcode[i] = f"; {line} - skipped pickup as T{current_tool} is already active"
                        continue
                    else:
                        active_tool = current_tool

                # Check for M104.1 commands
                m104_match = self.m104_pattern.search(line)
                if m104_match:
                    old_tool = int(m104_match.group(1))
                    if old_tool != current_tool:
                        # Only change the tool if it's different
                        if active_tool != current_tool:
                            # Preserve the P and Q values from the original command
                            p_match = re.search(r'P(\d+)', line)
                            q_match = re.search(r'Q(\d+)', line)
                            s_match = re.search(r'S(\d+)', line)

                            p_value = p_match.group(1) if p_match else "120"
                            q_value = q_match.group(1) if q_match else str(
                                int(p_value) + (1 if current_tool == 0 else 2))
                            s_value = s_match.group(1) if s_match else "210"

                            # Create the new command
                            new_command = f"M104.1 T{current_tool} P{p_value} Q{q_value} S{s_value}"

                            # Preserve any comment if it exists
                            comment_match = re.search(r';.*$', line)
                            if comment_match:
                                new_command += f" {comment_match.group(0)}"
                            else:
                                new_command += f" ; switched from T{old_tool} to T{current_tool}"

                            modified_gcode[i] = new_command
                            active_tool = current_tool
                        else:
                            # Skip tool change if already using this tool
                            modified_gcode[i] = f"; {line} - skipped as T{current_tool} is already active"
                            continue

                # Check for T# S# L# D# format
                tool_match = self.tool_pattern.search(line)
                if tool_match:
                    old_tool = int(tool_match.group(1))
                    if old_tool != current_tool:
                        # Replace just the tool number
                        new_line = re.sub(r'\bT\d+\b', f'T{current_tool}', line)
                        modified_gcode[i] = new_line
                        active_tool = current_tool

                # Check for simple T# commands at the start of line
                simple_match = self.simple_tool_pattern.search(line)
                if simple_match:
                    old_tool = int(simple_match.group(1))
                    if old_tool != current_tool:
                        # Replace the tool command
                        new_line = re.sub(r'^T\d+', f'T{current_tool}', line)
                        modified_gcode[i] = new_line
                        active_tool = current_tool

        return modified_gcode

    def process_file(self, input_file, output_file, ratio_pattern):
        """Process G-code file with the specified ratio pattern."""
        with open(input_file, 'r') as f:
            gcode_content = f.read()

        layer_positions, gcode_lines = self.parse_layers(gcode_content)
        total_layers = len(layer_positions)

        tool_sequence = self.calculate_tool_distribution(total_layers, ratio_pattern)
        modified_lines = self.modify_gcode(gcode_lines, layer_positions, tool_sequence)

        with open(output_file, 'w') as f:
            f.write('\n'.join(modified_lines))

        return total_layers, tool_sequence


class ToolSwitcherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Prusa XL Tool Switcher - 5 Color")
        self.root.geometry("750x750")
        self.root.resizable(True, True)

        self.tool_switcher = GCodeToolSwitcher()
        # Default patterns with 5 values (C:M:Y:W:BL)
        self.ratio_patterns = [
            (3, 0, 0, 0, 0), (3, 0, 0, 0, 0), (3, 0, 0, 0, 0), (3, 0, 0, 0, 0),

            # Transition S to H
            (3, 0.25, 0, 0, 0), (3, 0.5, 0, 0, 0), (3, 0.75, 0, 0, 0), (3, 1, 0, 0, 0),
            (2.75, 1, 0, 0, 0), (2.5, 1, 0, 0, 0), (2.25, 1, 0, 0, 0), (2, 1, 0, 0, 0),
            (1.75, 1, 0, 0, 0), (1.5, 1, 0, 0, 0), (1.25, 1, 0, 0, 0), (1, 1, 0, 0, 0),
            (1, 1.25, 0, 0, 0), (1, 1.5, 0, 0, 0), (1, 1.75, 0, 0, 0), (1, 2, 0, 0, 0),
            (1, 2.25, 0, 0, 0), (1, 2.5, 0, 0, 0), (1, 2.75, 0, 0, 0), (1, 3, 0, 0, 0),
            (0, 3, 0, 0, 0), (0, 3, 0, 0, 0), (0, 3, 0, 0, 0), (0, 3, 0, 0, 0),

            # Transition H to A
            (0, 3, 0.25, 0, 0), (0, 3, 0.5, 0, 0), (0, 3, 0.75, 0, 0), (0, 3, 1, 0, 0),
            (0, 2.75, 1, 0, 0), (0, 2.5, 1, 0, 0), (0, 2.25, 1, 0, 0), (0, 2, 1, 0, 0),
            (0, 1.75, 1, 0, 0), (0, 1.5, 1, 0, 0), (0, 1.25, 1, 0, 0), (0, 1, 1, 0, 0),
            (0, 1, 1.25, 0, 0), (0, 1, 1.5, 0, 0), (0, 1, 1.75, 0, 0), (0, 1, 2, 0, 0),
            (0, 1, 2.25, 0, 0), (0, 1, 2.5, 0, 0), (0, 1, 2.75, 0, 0), (0, 1, 3, 0, 0),
            (0, 0, 3, 0, 0), (0, 0, 3, 0, 0), (0, 0, 3, 0, 0), (0, 0, 3, 0, 0),

            # Transition A to D
            (0, 0, 3, 0.25, 0), (0, 0, 3, 0.5, 0), (0, 0, 3, 0.75, 0), (0, 0, 3, 1, 0),
            (0, 0, 2.75, 1, 0), (0, 0, 2.5, 1, 0), (0, 0, 2.25, 1, 0), (0, 0, 2, 1, 0),
            (0, 0, 1.75, 1, 0), (0, 0, 1.5, 1, 0), (0, 0, 1.25, 1, 0), (0, 0, 1, 1, 0),
            (0, 0, 1, 1.25, 0), (0, 0, 1, 1.5, 0), (0, 0, 1, 1.75, 0), (0, 0, 1, 2, 0),
            (0, 0, 1, 2.25, 0), (0, 0, 1, 2.5, 0), (0, 0, 1, 2.75, 0), (0, 0, 1, 3, 0),
            (0, 0, 0, 3, 0), (0, 0, 0, 3, 0), (0, 0, 0, 3, 0), (0, 0, 0, 3, 0),

            # Transition D to E
            (0, 0, 0, 3, 0.25), (0, 0, 0, 3, 0.5), (0, 0, 0, 3, 0.75), (0, 0, 0, 3, 1),
            (0, 0, 0, 2.75, 1), (0, 0, 0, 2.5, 1), (0, 0, 0, 2.25, 1), (0, 0, 0, 2, 1),
            (0, 0, 0, 1.75, 1), (0, 0, 0, 1.5, 1), (0, 0, 0, 1.25, 1), (0, 0, 0, 1, 1),
            (0, 0, 0, 1, 1.25), (0, 0, 0, 1, 1.5), (0, 0, 0, 1, 1.75), (0, 0, 0, 1, 2),
            (0, 0, 0, 1, 2.25), (0, 0, 0, 1, 2.5), (0, 0, 0, 1, 2.75), (0, 0, 0, 1, 3),
            (0, 0, 0, 0, 3), (0, 0, 0, 0, 3), (0, 0, 0, 0, 3), (0, 0, 0, 0, 3),
            (0, 0, 0, 0, 3), (0, 0, 0, 0, 3), (0, 0, 0, 0, 3), (0, 0, 0, 0, 3),
        ]

        self.create_widgets()

    def create_widgets(self):
        # Input file section
        input_frame = ttk.LabelFrame(self.root, text="Input G-code File")
        input_frame.pack(fill="x", expand=True, padx=10, pady=5)

        self.input_file_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.input_file_var, width=50).pack(side=tk.LEFT, padx=5, pady=5,
                                                                                expand=True, fill="x")
        ttk.Button(input_frame, text="Browse...", command=self.browse_input).pack(side=tk.RIGHT, padx=5, pady=5)

        # Output file section
        output_frame = ttk.LabelFrame(self.root, text="Output G-code File")
        output_frame.pack(fill="x", expand=True, padx=10, pady=5)

        self.output_file_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.output_file_var, width=50).pack(side=tk.LEFT, padx=5, pady=5,
                                                                                  expand=True, fill="x")
        ttk.Button(output_frame, text="Browse...", command=self.browse_output).pack(side=tk.RIGHT, padx=5, pady=5)

        # Ratio pattern section
        pattern_frame = ttk.LabelFrame(self.root, text="Tool Ratio Pattern (C:M:Y:W:BL)")
        pattern_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Create a canvas with scrollbar for the pattern entries
        canvas = tk.Canvas(pattern_frame)
        scrollbar = ttk.Scrollbar(pattern_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Add pattern entries with default values
        self.ratio_entries = []
        for i, (cyan, magenta, yellow, white, black) in enumerate(self.ratio_patterns):
            row_frame = ttk.Frame(scrollable_frame)
            row_frame.pack(fill="x", padx=5, pady=2)

            ttk.Label(row_frame, text=f"Pattern {i + 1}:").pack(side=tk.LEFT, padx=5)

            cyan_var = tk.StringVar(value=str(cyan))
            magenta_var = tk.StringVar(value=str(magenta))
            yellow_var = tk.StringVar(value=str(yellow))
            white_var = tk.StringVar(value=str(white))
            black_var = tk.StringVar(value=str(black))

            ttk.Label(row_frame, text="C:").pack(side=tk.LEFT, padx=2)
            cyan_entry = ttk.Entry(row_frame, textvariable=cyan_var, width=5)
            cyan_entry.pack(side=tk.LEFT, padx=2)

            ttk.Label(row_frame, text="M:").pack(side=tk.LEFT, padx=2)
            magenta_entry = ttk.Entry(row_frame, textvariable=magenta_var, width=5)
            magenta_entry.pack(side=tk.LEFT, padx=2)

            ttk.Label(row_frame, text="Y:").pack(side=tk.LEFT, padx=2)
            yellow_entry = ttk.Entry(row_frame, textvariable=yellow_var, width=5)
            yellow_entry.pack(side=tk.LEFT, padx=2)

            ttk.Label(row_frame, text="W:").pack(side=tk.LEFT, padx=2)
            white_entry = ttk.Entry(row_frame, textvariable=white_var, width=5)
            white_entry.pack(side=tk.LEFT, padx=2)

            ttk.Label(row_frame, text="BL:").pack(side=tk.LEFT, padx=2)
            black_entry = ttk.Entry(row_frame, textvariable=black_var, width=5)
            black_entry.pack(side=tk.LEFT, padx=2)

            # Add button to remove this pattern
            ttk.Button(row_frame, text="−", width=3,
                       command=lambda idx=i: self.remove_pattern(idx)).pack(side=tk.RIGHT, padx=2)

            self.ratio_entries.append((cyan_var, magenta_var, yellow_var, white_var, black_var, row_frame))

        # Add buttons to manage patterns
        pattern_buttons_frame = ttk.Frame(pattern_frame)
        pattern_buttons_frame.pack(fill="x", padx=5, pady=5)

        ttk.Button(pattern_buttons_frame, text="Add Pattern",
                   command=self.add_pattern).pack(side=tk.LEFT, padx=5)

        ttk.Button(pattern_buttons_frame, text="Reset to Default",
                   command=self.reset_patterns).pack(side=tk.LEFT, padx=5)

        # Process button
        process_frame = ttk.Frame(self.root)
        process_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(process_frame, text="Process G-code",
                   command=self.process_gcode).pack(side=tk.RIGHT, padx=5)

        # Status and log section
        log_frame = ttk.LabelFrame(self.root, text="Status Log")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = tk.Text(log_frame, height=10, wrap=tk.WORD)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    def browse_input(self):
        filename = filedialog.askopenfilename(
            title="Select G-code file",
            filetypes=[("G-code files", "*.gcode"), ("All files", "*.*")]
        )
        if filename:
            self.input_file_var.set(filename)
            # Auto-generate output filename
            basename = os.path.basename(filename)
            name, ext = os.path.splitext(basename)
            output_name = f"{name}_5color{ext}"
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

    def add_pattern(self):
        row_frame = ttk.Frame(self.ratio_entries[0][5].master)
        row_frame.pack(fill="x", padx=5, pady=2)

        idx = len(self.ratio_entries) + 1
        ttk.Label(row_frame, text=f"Pattern {idx}:").pack(side=tk.LEFT, padx=5)

        cyan_var = tk.StringVar(value="1")
        magenta_var = tk.StringVar(value="1")
        yellow_var = tk.StringVar(value="1")
        white_var = tk.StringVar(value="1")
        black_var = tk.StringVar(value="1")

        ttk.Label(row_frame, text="C:").pack(side=tk.LEFT, padx=2)
        cyan_entry = ttk.Entry(row_frame, textvariable=cyan_var, width=5)
        cyan_entry.pack(side=tk.LEFT, padx=2)

        ttk.Label(row_frame, text="M:").pack(side=tk.LEFT, padx=2)
        magenta_entry = ttk.Entry(row_frame, textvariable=magenta_var, width=5)
        magenta_entry.pack(side=tk.LEFT, padx=2)

        ttk.Label(row_frame, text="Y:").pack(side=tk.LEFT, padx=2)
        yellow_entry = ttk.Entry(row_frame, textvariable=yellow_var, width=5)
        yellow_entry.pack(side=tk.LEFT, padx=2)

        ttk.Label(row_frame, text="W:").pack(side=tk.LEFT, padx=2)
        white_entry = ttk.Entry(row_frame, textvariable=white_var, width=5)
        white_entry.pack(side=tk.LEFT, padx=2)

        ttk.Label(row_frame, text="BL:").pack(side=tk.LEFT, padx=2)
        black_entry = ttk.Entry(row_frame, textvariable=black_var, width=5)
        black_entry.pack(side=tk.LEFT, padx=2)

        # Add button to remove this pattern
        ttk.Button(row_frame, text="−", width=3,
                   command=lambda: self.remove_pattern_by_frame(row_frame)).pack(side=tk.RIGHT, padx=2)

        self.ratio_entries.append((cyan_var, magenta_var, yellow_var, white_var, black_var, row_frame))

    def remove_pattern(self, idx):
        if len(self.ratio_entries) > 1:  # Keep at least one pattern
            if 0 <= idx < len(self.ratio_entries):
                _, _, _, _, _, frame = self.ratio_entries.pop(idx)
                frame.destroy()
                # Update pattern numbers
                self.renumber_patterns()

    def remove_pattern_by_frame(self, frame):
        if len(self.ratio_entries) > 1:  # Keep at least one pattern
            for i, (_, _, _, _, _, f) in enumerate(self.ratio_entries):
                if f == frame:
                    self.ratio_entries.pop(i)
                    frame.destroy()
                    # Update pattern numbers
                    self.renumber_patterns()
                    break

    def renumber_patterns(self):
        for i, (_, _, _, _, _, frame) in enumerate(self.ratio_entries):
            # Find the label in this frame
            for child in frame.winfo_children():
                if isinstance(child, ttk.Label) and child.cget("text").startswith("Pattern"):
                    child.config(text=f"Pattern {i + 1}:")
                    break

    def reset_patterns(self):
        # Clear existing patterns
        for _, _, _, _, _, frame in self.ratio_entries:
            frame.destroy()

        self.ratio_entries = []

        # Rebuild with default patterns
        master_frame = None
        for i, (cyan, magenta, yellow, white, black) in enumerate(self.ratio_patterns):
            row_frame = ttk.Frame(master_frame or self.root)
            if not master_frame:
                master_frame = row_frame.master
            row_frame.pack(fill="x", padx=5, pady=2)

            ttk.Label(row_frame, text=f"Pattern {i + 1}:").pack(side=tk.LEFT, padx=5)

            cyan_var = tk.StringVar(value=str(cyan))
            magenta_var = tk.StringVar(value=str(magenta))
            yellow_var = tk.StringVar(value=str(yellow))
            white_var = tk.StringVar(value=str(white))
            black_var = tk.StringVar(value=str(black))

            ttk.Label(row_frame, text="C:").pack(side=tk.LEFT, padx=2)
            cyan_entry = ttk.Entry(row_frame, textvariable=cyan_var, width=5)
            cyan_entry.pack(side=tk.LEFT, padx=2)

            ttk.Label(row_frame, text="M:").pack(side=tk.LEFT, padx=2)
            magenta_entry = ttk.Entry(row_frame, textvariable=magenta_var, width=5)
            magenta_entry.pack(side=tk.LEFT, padx=2)

            ttk.Label(row_frame, text="Y:").pack(side=tk.LEFT, padx=2)
            yellow_entry = ttk.Entry(row_frame, textvariable=yellow_var, width=5)
            yellow_entry.pack(side=tk.LEFT, padx=2)

            ttk.Label(row_frame, text="W:").pack(side=tk.LEFT, padx=2)
            white_entry = ttk.Entry(row_frame, textvariable=white_var, width=5)
            white_entry.pack(side=tk.LEFT, padx=2)

            ttk.Label(row_frame, text="BL:").pack(side=tk.LEFT, padx=2)
            black_entry = ttk.Entry(row_frame, textvariable=black_var, width=5)
            black_entry.pack(side=tk.LEFT, padx=2)

            # Add button to remove this pattern
            ttk.Button(row_frame, text="−", width=3,
                       command=lambda idx=i: self.remove_pattern(idx)).pack(side=tk.RIGHT, padx=2)

            self.ratio_entries.append((cyan_var, magenta_var, yellow_var, white_var, black_var, row_frame))

    def get_current_patterns(self):
        patterns = []
        for cyan_var, magenta_var, yellow_var, white_var, black_var, _ in self.ratio_entries:
            try:
                cyan = float(cyan_var.get())
                magenta = float(magenta_var.get())
                yellow = float(yellow_var.get())
                white = float(white_var.get())
                black = float(black_var.get())
                patterns.append((cyan, magenta, yellow, white, black))
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid numbers for all patterns")
                return None
        return patterns

    def process_gcode(self):
        input_file = self.input_file_var.get()
        output_file = self.output_file_var.get()

        if not input_file or not output_file:
            messagebox.showerror("Error", "Please specify both input and output files")
            return

        if not os.path.exists(input_file):
            messagebox.showerror("Error", f"Input file not found: {input_file}")
            return

        patterns = self.get_current_patterns()
        if patterns is None:
            return

        try:
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(tk.END, f"Processing file: {input_file}\n")
            self.log_text.insert(tk.END, f"Output file: {output_file}\n")
            self.log_text.insert(tk.END, f"Using {len(patterns)} ratio patterns\n")
            self.log_text.update()

            total_layers, tool_sequence = self.tool_switcher.process_file(input_file, output_file, patterns)

            self.log_text.insert(tk.END, f"\nProcessing complete!\n")
            self.log_text.insert(tk.END, f"Total layers: {total_layers}\n")

            # Count tool usage
            t0_count = tool_sequence.count(0)
            t1_count = tool_sequence.count(1)
            t2_count = tool_sequence.count(2)
            t3_count = tool_sequence.count(3)
            t4_count = tool_sequence.count(4)

            self.log_text.insert(tk.END,
                                 f"Tool 0 (Cyan) used for {t0_count} layers ({t0_count / total_layers * 100:.1f}%)\n")
            self.log_text.insert(tk.END,
                                 f"Tool 1 (Magenta) used for {t1_count} layers ({t1_count / total_layers * 100:.1f}%)\n")
            self.log_text.insert(tk.END,
                                 f"Tool 2 (Yellow) used for {t2_count} layers ({t2_count / total_layers * 100:.1f}%)\n")
            self.log_text.insert(tk.END,
                                 f"Tool 3 (White) used for {t3_count} layers ({t3_count / total_layers * 100:.1f}%)\n")
            self.log_text.insert(tk.END,
                                 f"Tool 4 (Black) used for {t4_count} layers ({t4_count / total_layers * 100:.1f}%)\n")

            messagebox.showinfo("Success", f"G-code processed successfully!\n{total_layers} layers modified.")

        except Exception as e:
            self.log_text.insert(tk.END, f"\nError: {str(e)}\n")
            messagebox.showerror("Error", f"Failed to process G-code: {str(e)}")


def main():
    root = tk.Tk()
    app = ToolSwitcherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
