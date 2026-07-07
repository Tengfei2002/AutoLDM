import sys
import os
import json
from dataclasses import dataclass
from typing import List, Dict, Any

# ---------------------------------------------------------
# 第一步：数据解析与结构化
# ---------------------------------------------------------

def parse_cfet_arch(filepath: str) -> Dict[str, float]:
    """
    解析 CFET 架构参数文件。
    将全局变量与独立变量解析为键值对，处理未激活全局变量的覆盖逻辑。
    """
    params = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            # 剔除注释与空白
            line = line.split('%')[0].strip()
            if '=' in line:
                key, val = line.split('=')
                params[key.strip()] = float(val.strip())
    
    # 全局变量覆盖逻辑
    # 结构：(global_key, [local_keys])
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
                
    # 针对 Y 轴方向源漏外延的特殊处理
    if params.get('sd_overgrowth_y_up', -1) != -1:
        params['sd_upper_overgrowth_y_up'] = params['sd_overgrowth_y_up']
        params['sd_lower_overgrowth_y_up'] = params['sd_overgrowth_y_up']
    if params.get('sd_overgrowth_y_down', -1) != -1:
        params['sd_upper_overgrowth_y_down'] = params['sd_overgrowth_y_down']
        params['sd_lower_overgrowth_y_down'] = params['sd_overgrowth_y_down']

    return params

def parse_layer_rules(filepath: str) -> List[Dict[str, Any]]:
    """
    解析层规则文件，剔除 enable == false 的层，提取有效属性。
    """
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
    """
    负责计算 CFET 各核心结构的 3D 绝对坐标包络盒。
    原点设定：栅极中心线设定为 X 轴原点 (X=0)。
    """
    def __init__(self, params: Dict[str, float], active_layers: List[Dict[str, Any]]):
        self.p = params
        self.layers = active_layers

    def calc_bounds(self) -> List[Block]:
        blocks = []
        
        # 1. 计算栅极 (Gate) 坐标包络
        # X 边界：[-L/2, L/2]
        gate_l = self.p.get('gate_length', 0.029)
        gate_x_min, gate_x_max = -gate_l / 2, gate_l / 2
        gate_y_center = self.p.get('channel_center_y', 0.0315)
        gate_w = self.p.get('gate_width', 0.014)
        gate_y_min, gate_y_max = gate_y_center - gate_w / 2, gate_y_center + gate_w / 2
        
        # Z 轴边界：由 layer 中 name 为 'gate' 的层决定
        gate_layer = next((l for l in self.layers if l['layer_name'] == 'gate'), None)
        if gate_layer:
            gate_z_min, gate_z_max = gate_layer['start_z1'], gate_layer['end_z2']
            blocks.append(Block('Gate_Stack', gate_layer['material'], 
                                [gate_x_min, gate_y_min, gate_z_min, gate_x_max, gate_y_max, gate_z_max]))

        # 2. 计算沟道 (Channel) 坐标包络
        chan_l = self.p.get('channel_length', 0.026)
        chan_w = self.p.get('channel_width', 0.021)
        chan_x_min, chan_x_max = -chan_l / 2, chan_l / 2
        chan_y_min, chan_y_max = gate_y_center - chan_w / 2, gate_y_center + chan_w / 2
        
        # Z 轴高程推导：根据 mdi_thickness 与器件位置估算上下沟道
        # 假定沟道位于 gate Z 轴中心附近对称分布（具体依赖工艺定义，此处提供通用推导）
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
            
            # 3. 计算源漏外延 (S/D Epi)
            sd_over_x = self.p.get('sd_upper_overgrowth_x', 0.005)
            sd_over_y_up = self.p.get('sd_upper_overgrowth_y_up', 0.006)
            sd_over_y_down = self.p.get('sd_upper_overgrowth_y_down', 0.006)
            
            # Source (Left)
            blocks.append(Block('Upper_Source_Epi', 'SiliconEpi', 
                                [chan_x_min - sd_over_x, chan_y_min - sd_over_y_down, u_chan_z_min,
                                 chan_x_min, chan_y_max + sd_over_y_up, u_chan_z_max]))
            # Drain (Right)
            blocks.append(Block('Upper_Drain_Epi', 'SiliconEpi', 
                                [chan_x_max, chan_y_min - sd_over_y_down, u_chan_z_min,
                                 chan_x_max + sd_over_x, chan_y_max + sd_over_y_up, u_chan_z_max]))

        return blocks

# ---------------------------------------------------------
# 第三步与第四步：几何建模代码生成与输出接口
# ---------------------------------------------------------

def build_cfet_mesh(params: Dict[str, float], active_layers: List[Dict[str, Any]]) -> List[Block]:
    """
    主函数：实例化所有几何块，生成背景层间介质（ILD）。
    """
    calculator = CFETGeometryCalculator(params, active_layers)
    geometry_blocks = calculator.calc_bounds()

    # 提取全局边界以生成 ILD 背景块
    # 遍历所有激活层以确定全局最小和最大 Z 轴
    if active_layers:
        global_z_min = min(layer['start_z1'] for layer in active_layers)
        global_z_max = max(layer['end_z2'] for layer in active_layers)
        
        # 定义一个覆盖整体架构的全局边界框作为 ILD 背景（假定 XY 区域包含整体标准单元）
        cell_h = params.get('cell_height', 0.062)
        cpp = params.get('cpp', 0.042)
        
        ild_block = Block('ILD_Background', active_layers[0].get('ILD', 'SiO2'), 
                          [-cpp/2, 0.0, global_z_min, cpp/2, cell_h, global_z_max])
        geometry_blocks.insert(0, ild_block) # 将 ILD 放在结构首位，表示基底填充

    return geometry_blocks

def export_to_json(blocks: List[Block], output_dir: str):
    """
    遍历生成的几何块，并转化为严格区分材料、尺寸、坐标的 JSON 文件结构。
    """
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
        
    print(f"✅ 三维几何结构数据已成功导出至：{output_file}")

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
    
    # 1. 解析参数
    cfet_params = parse_cfet_arch(arch_file)
    layer_rules = parse_layer_rules(layer_file)
    
    # 2. 生成几何结构
    cfet_mesh = build_cfet_mesh(cfet_params, layer_rules)
    
    # 3. 导出至 ./output/
    export_to_json(cfet_mesh, './output')