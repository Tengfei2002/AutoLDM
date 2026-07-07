import argparse
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.widgets import CheckButtons, Button

class LayoutViewer:
    def __init__(self, txt_path):
        self.txt_path = Path(txt_path)
        self.boxes = []
        self.layers = set()
        self.layer_patches = {}
        self.visibility_state = {}
        
        self.load_data()
        
        if not self.boxes:
            print("Warning: No valid data found in the file.")
            return
            
        self.setup_ui()

    def load_data(self):
        print(f"Reading and parsing {self.txt_path} ...")
        if not self.txt_path.exists():
            print(f"Error: File {self.txt_path} not found")
            return

        with open(self.txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    x1, y1, x2, y2, layer = map(float, parts)
                    layer = int(layer)
                    self.boxes.append((x1, y1, x2, y2, layer))
                    self.layers.add(layer)

        self.unique_layers = sorted(list(self.layers))
        for layer in self.unique_layers:
            self.layer_patches[layer] = []
            self.visibility_state[layer] = True

    def setup_ui(self):
        self.fig, self.ax = plt.subplots(figsize=(14, 10))
        plt.subplots_adjust(left=0.05, right=0.78, bottom=0.05, top=0.95)

        cmap = plt.get_cmap('tab20')
        self.color_map = {layer: cmap(i % 20) for i, layer in enumerate(self.unique_layers)}

        # Render bounding boxes
        for x1, y1, x2, y2, layer in self.boxes:
            width = x2 - x1
            height = y2 - y1
            
            rect = patches.Rectangle(
                (x1, y1), width, height,
                linewidth=1, 
                edgecolor=self.color_map[layer], 
                facecolor=self.color_map[layer], 
                alpha=0.4
            )
            self.ax.add_patch(rect)
            self.layer_patches[layer].append(rect)

        # Calculate global axis bounds
        boxes_arr = np.array(self.boxes)
        margin_x = (boxes_arr[:, 2].max() - boxes_arr[:, 0].min()) * 0.05
        margin_y = (boxes_arr[:, 3].max() - boxes_arr[:, 1].min()) * 0.05
        
        self.ax.set_xlim(boxes_arr[:, 0].min() - margin_x, boxes_arr[:, 2].max() + margin_x)
        self.ax.set_ylim(boxes_arr[:, 1].min() - margin_y, boxes_arr[:, 3].max() + margin_y)
        self.ax.set_aspect('equal', adjustable='box')
        self.ax.set_title(f'Layout Visualization: {self.txt_path.name}')
        self.ax.set_xlabel('X-axis (um)')
        self.ax.set_ylabel('Y-axis (um)')
        self.ax.grid(True, linestyle=':', alpha=0.7)

        self.setup_widgets()
        self.setup_hover_events()

        print("Rendering completed, opening interactive visualization window...")
        plt.show()

    def setup_widgets(self):
        # Layer Checkboxes
        ax_check = plt.axes([0.82, 0.2, 0.15, 0.6])
        labels = [f"Layer {layer}" for layer in self.unique_layers]
        actives = [True] * len(self.unique_layers)
        
        self.check = CheckButtons(ax_check, labels, actives)
        
        # Color match checkbox text to layer colors
        for i, label in enumerate(self.check.labels):
            label.set_color(self.color_map[self.unique_layers[i]])
            label.set_fontweight('bold')

        def on_check_clicked(label):
            layer = int(label.replace("Layer ", ""))
            idx = labels.index(label)
            is_visible = self.check.get_status()[idx]
            self.visibility_state[layer] = is_visible
            for patch in self.layer_patches[layer]:
                patch.set_visible(is_visible)
            self.fig.canvas.draw_idle()

        self.check.on_clicked(on_check_clicked)

        # Select All / None Buttons
        ax_btn_all = plt.axes([0.82, 0.85, 0.07, 0.04])
        self.btn_all = Button(ax_btn_all, 'Select All')
        
        ax_btn_none = plt.axes([0.90, 0.85, 0.07, 0.04])
        self.btn_none = Button(ax_btn_none, 'Clear All')

        def select_all(event):
            for i, status in enumerate(self.check.get_status()):
                if not status:
                    self.check.set_active(i)

        def select_none(event):
            for i, status in enumerate(self.check.get_status()):
                if status:
                    self.check.set_active(i)

        self.btn_all.on_clicked(select_all)
        self.btn_none.on_clicked(select_none)

    def setup_hover_events(self):
        # Setup annotation box and snapping line for hover
        self.annot = self.ax.annotate(
            "", xy=(0,0), xytext=(15, 15), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", lw=1, alpha=0.9),
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3")
        )
        self.annot.set_visible(False)

        self.snap_line, = self.ax.plot([], [], color='red', lw=2.5, linestyle='--')

        self.fig.canvas.mpl_connect("motion_notify_event", self.on_hover)

    def on_hover(self, event):
        if event.inaxes != self.ax:
            if self.annot.get_visible():
                self.annot.set_visible(False)
                self.snap_line.set_data([], [])
                self.fig.canvas.draw_idle()
            return

        ex, ey = event.xdata, event.ydata
        
        # Dynamic tolerance based on current view zoom level
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        tol_x = (xlim[1] - xlim[0]) * 0.015
        tol_y = (ylim[1] - ylim[0]) * 0.015

        min_dist = float('inf')
        best_edge = None
        best_snap_pt = None

        for (x1, y1, x2, y2, layer) in self.boxes:
            if not self.visibility_state[layer]:
                continue
            
            # Quick bounding box filter to optimize performance
            if not (x1 - tol_x <= ex <= x2 + tol_x and y1 - tol_y <= ey <= y2 + tol_y):
                continue

            # Define the 4 edges of the bounding box
            # Format: ('orientation', constant_axis_val, min_axis_val, max_axis_val)
            edges = [
                ('v', x1, y1, y2), # Left
                ('v', x2, y1, y2), # Right
                ('h', y1, x1, x2), # Bottom
                ('h', y2, x1, x2)  # Top
            ]

            for orient, c_val, min_val, max_val in edges:
                if orient == 'v':
                    if min_val <= ey <= max_val:
                        dist = abs(ex - c_val)
                        if dist < tol_x and dist < min_dist:
                            min_dist = dist
                            best_edge = ((c_val, min_val), (c_val, max_val), max_val - min_val)
                            best_snap_pt = (c_val, ey)
                else:
                    if min_val <= ex <= max_val:
                        dist = abs(ey - c_val)
                        if dist < tol_y and dist < min_dist:
                            min_dist = dist
                            best_edge = ((min_val, c_val), (max_val, c_val), max_val - min_val)
                            best_snap_pt = (ex, c_val)

        if best_edge:
            # Update snap line coordinates
            self.snap_line.set_data([best_edge[0][0], best_edge[1][0]], [best_edge[0][1], best_edge[1][1]])
            
            # Update annotation position and text
            self.annot.xy = best_snap_pt
            text = f"X: {best_snap_pt[0]:.4f}\nY: {best_snap_pt[1]:.4f}\nLength: {best_edge[2]:.4f} um"
            self.annot.set_text(text)
            self.annot.set_visible(True)
            self.fig.canvas.draw_idle()
        else:
            if self.annot.get_visible():
                self.annot.set_visible(False)
                self.snap_line.set_data([], [])
                self.fig.canvas.draw_idle()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Read TXT file and display interactive layout visualization")
    parser.add_argument("input_txt", type=str, help="Path to input TXT file (e.g., ./gds/test_gds.txt)")
    
    args = parser.parse_args()
    viewer = LayoutViewer(args.input_txt)