import sys
import os
import json
from dataclasses import dataclass
from typing import List, Dict, Any

# ---------------------------------------------------------
# 第一步：数据解析与结构化
# ---------------------------------------------------------

def parse_cfet_arch(filepath: str) -> Dict[str, float]:
    params = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.split('%')[0].strip()
            if '=' in line:
                key, val = line.split('=')
                params[key.strip()] = float(val.strip())
    
    override_rules = [
        ('num_channel', ['num_channel_n', 'num_channel_p']),
        ('gate_length', ['gate_upper_length', 'gate_lower_length']),
        ('gate_width', ['gate_upper_width', 'gate_lower_width']),
        ('channel_length', ['channel_upper_length', 'channel_lower_length']),
        ('channel_width', ['channel_upper_width', 'channel_lower_width']),
        ('sd_overgrowth_x', ['sd_upper_overgrowth_x', 'sd_lower_overgrowth_x'])
    ]
    
    for global_k, local_ks in override_rules:
        if global_k in params and params[global_k] != -1:
            for local_k in local_ks:
                params[local_k] = params[global_k]
                
    if params.get('sd_overgrowth_y_up', -1) != -1:
        params['sd_upper_overgrowth_y_up'] = params['sd_overgrowth_y_up']
        params['sd_lower_overgrowth_y_up'] = params['sd_overgrowth_y_up']
    if params.get('sd_overgrowth_y_down', -1) != -1:
        params['sd_upper_overgrowth_y_down'] = params['sd_overgrowth_y_down']
        params['sd_lower_overgrowth_y_down'] = params['sd_overgrowth_y_down']

    return params

def parse_layer_rules(filepath: str) -> List[Dict[str, Any]]:
    layers = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 9 and parts[0].isdigit():
                enable = parts[2].lower() == 'true'
                if enable:
                    layers.append({
                        'layer_num': int(parts[0]),
                        'layer_name': parts[1],
                        'enable': True,
                        'height': float(parts[3]),
                        'start_z1': float(parts[4]),
                        'end_z2': float(parts[5]),
                        'material': parts[6],
                        'boundary': parts[7],
                        'ILD': parts[8]
                    })
    return layers

# ---------------------------------------------------------
# 第二步：三维坐标计算与物理对齐
# ---------------------------------------------------------

@dataclass
class Block:
    name: str
    material: str
    bbox: List[float]  # [x_min, y_min, z_min, x_max, y_max, z_max]

class CFETGeometryCalculator:
    def __init__(self, params: Dict[str, float], active_layers: List[Dict[str, Any]]):
        self.p = params
        self.layers = active_layers

    def calc_bounds(self) -> List[Block]:
        blocks = []
        
        gate_l = self.p.get('gate_length', 0.029)
        gate_x_min, gate_x_max = -gate_l / 2, gate_l / 2
        gate_y_center = self.p.get('channel_center_y', 0.0315)
        gate_w = self.p.get('gate_width', 0.014)
        gate_y_min, gate_y_max = gate_y_center - gate_w / 2, gate_y_center + gate_w / 2
        
        gate_layer = next((l for l in self.layers if l['layer_name'] == 'gate'), None)
        if gate_layer:
            gate_z_min, gate_z_max = gate_layer['start_z1'], gate_layer['end_z2']
            blocks.append(Block('Gate_Stack', gate_layer['material'], 
                                [gate_x_min, gate_y_min, gate_z_min, gate_x_max, gate_y_max, gate_z_max]))

        chan_l = self.p.get('channel_length', 0.026)
        chan_w = self.p.get('channel_width', 0.021)
        chan_x_min, chan_x_max = -chan_l / 2, chan_l / 2
        chan_y_min, chan_y_max = gate_y_center - chan_w / 2, gate_y_center + chan_w / 2
        
        chan_thick = self.p.get('channel_thickness', 0.006)
        mdi_thick = self.p.get('mdi_thickness', 0.040)
        
        if gate_layer:
            center_z = (gate_z_min + gate_z_max) / 2
            # Lower Channel
            l_chan_z_max = center_z - mdi_thick / 2
            l_chan_z_min = l_chan_z_max - chan_thick
            blocks.append(Block('Lower_Channel', 'Silicon', 
                                [chan_x_min, chan_y_min, l_chan_z_min, chan_x_max, chan_y_max, l_chan_z_max]))
            
            # Upper Channel
            u_chan_z_min = center_z + mdi_thick / 2
            u_chan_z_max = u_chan_z_min + chan_thick
            blocks.append(Block('Upper_Channel', 'Silicon', 
                                [chan_x_min, chan_y_min, u_chan_z_min, chan_x_max, chan_y_max, u_chan_z_max]))
            
            # Source/Drain Epi
            sd_over_x = self.p.get('sd_upper_overgrowth_x', 0.005)
            sd_over_y_up = self.p.get('sd_upper_overgrowth_y_up', 0.006)
            sd_over_y_down = self.p.get('sd_upper_overgrowth_y_down', 0.006)
            
            blocks.append(Block('Upper_Source_Epi', 'SiliconEpi', 
                                [chan_x_min - sd_over_x, chan_y_min - sd_over_y_down, u_chan_z_min,
                                 chan_x_min, chan_y_max + sd_over_y_up, u_chan_z_max]))
            blocks.append(Block('Upper_Drain_Epi', 'SiliconEpi', 
                                [chan_x_max, chan_y_min - sd_over_y_down, u_chan_z_min,
                                 chan_x_max + sd_over_x, chan_y_max + sd_over_y_up, u_chan_z_max]))

        return blocks

# ---------------------------------------------------------
# 第三步与第四步：几何建模代码生成与输出接口
# ---------------------------------------------------------

def build_cfet_mesh(params: Dict[str, float], active_layers: List[Dict[str, Any]]) -> List[Block]:
    calculator = CFETGeometryCalculator(params, active_layers)
    geometry_blocks = calculator.calc_bounds()

    if active_layers:
        global_z_min = min(layer['start_z1'] for layer in active_layers)
        global_z_max = max(layer['end_z2'] for layer in active_layers)
        
        cell_h = params.get('cell_height', 0.062)
        cpp = params.get('cpp', 0.042)
        
        ild_block = Block('ILD_Background', active_layers[0].get('ILD', 'SiO2'), 
                          [-cpp/2, 0.0, global_z_min, cpp/2, cell_h, global_z_max])
        geometry_blocks.insert(0, ild_block) 

    return geometry_blocks

def export_to_json(blocks: List[Block], output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'cfet_mesh_data.json')
    
    export_data = {"components": []}
    for block in blocks:
        x_min, y_min, z_min, x_max, y_max, z_max = block.bbox
        dimensions = {
            "dx": round(x_max - x_min, 6),
            "dy": round(y_max - y_min, 6),
            "dz": round(z_max - z_min, 6)
        }
        origin_coordinates = {
            "x": round(x_min, 6),
            "y": round(y_min, 6),
            "z": round(z_min, 6)
        }
        
        component_data = {
            "name": block.name,
            "material": block.material,
            "dimensions": dimensions,
            "origin_coordinates": origin_coordinates,
            "bounding_box": block.bbox
        }
        export_data["components"].append(component_data)
        
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=4)
        
    print(f"三维数据已成功导出至：{output_file}")

def export_to_obj(blocks: List[Block], output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'cfet_mesh_visual.obj')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# CFET 3D Geometry generated by TCAD script\n")
        
        vertex_offset = 1
        
        for block in blocks:
            x_min, y_min, z_min, x_max, y_max, z_max = block.bbox
            
            vertices = [
                (x_min, y_min, z_min), (x_max, y_min, z_min), (x_max, y_max, z_min), (x_min, y_max, z_min),
                (x_min, y_min, z_max), (x_max, y_min, z_max), (x_max, y_max, z_max), (x_min, y_max, z_max)
            ]
            
            f.write(f"\no {block.name}_{block.material}\n")
            
            for v in vertices:
                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
                
            faces = [
                (1, 4, 3), (1, 3, 2), (5, 6, 7), (5, 7, 8),
                (1, 2, 6), (1, 6, 5), (3, 4, 8), (3, 8, 7),
                (1, 5, 8), (1, 8, 4), (2, 3, 7), (2, 7, 6)
            ]
            
            for face in faces:
                f.write(f"f {face[0] + vertex_offset - 1} {face[1] + vertex_offset - 1} {face[2] + vertex_offset - 1}\n")
                
            vertex_offset += 8
            
    print(f"三维可视化模型已成功导出至：{output_file}")

# ---------------------------------------------------------
# 执行入口
# ---------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python gen_arch.py <gds_file> <cfet_arch_file> <layer_rule_file>")
        sys.exit(1)
        
    gds_file = sys.argv[1]
    arch_file = sys.argv[2]
    layer_file = sys.argv[3]
    
    cfet_params = parse_cfet_arch(arch_file)
    layer_rules = parse_layer_rules(layer_file)
    
    cfet_mesh = build_cfet_mesh(cfet_params, layer_rules)
    
    # 这里是核心：同时调用两个导出函数
    export_to_json(cfet_mesh, './output')
    export_to_obj(cfet_mesh, './output')