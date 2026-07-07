import os
import sys

class SDEBuilder:
    def __init__(self, layout_file, rules_file, arch_file):
        self.layout_file = layout_file
        self.rules_file = rules_file
        self.arch_file = arch_file
        
        self.layout_data = {}
        self.rules_data = {}
        self.arch_data = {}
        
        self.sde_commands = []
        self.region_groups = {} # 用于记录同类结构以进行布尔合并
        self.metal_regions = [] # 记录金属区域以便后续添加 Contact

    def parse_inputs(self):
        # 1. 解析版图文件
        with open(self.layout_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    x1, y1, x2, y2, layer_id = map(float, parts[:5])
                    self.layout_data[int(layer_id)] = {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}

        # 2. 解析规则文件并执行严格校验
        with open(self.rules_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('%') or line.startswith('['):
                    continue
                parts = line.split()
                if len(parts) >= 8:
                    layer_id = int(parts[0])
                    enable = parts[2].lower() == 'true'
                    if not enable:
                        continue
                    
                    height, start_z, end_z = map(float, parts[3:6])
                    # 规则校验：厚度与坐标严格匹配
                    if abs((end_z - start_z) - height) > 1e-5:
                        raise ValueError(f"校验失败：版图层级 {layer_id} 的几何高度与坐标不匹配 (height={height}, start_z={start_z}, end_z={end_z})。停止执行。")
                        
                    material = parts[6]
                    self.rules_data[layer_id] = {
                        'height': height, 'start_z': start_z, 'end_z': end_z, 'material': material
                    }

        # 3. 解析架构参数
        with open(self.arch_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('%') or line.startswith('['):
                    continue
                if '=' in line:
                    key, val = line.split('=')
                    key = key.strip()
                    val = val.split('%')[0].strip() # 忽略行内注释
                    self.arch_data[key] = float(val)

    def add_cmd(self, cmd):
        self.sde_commands.append(cmd)

    def create_cuboid(self, x1, y1, z1, x2, y2, z2, material, region_name):
        """生成实体，并记录同名组用于后续合并"""
        cmd = f'(sdegeo:create-cuboid (position {x1:.5f} {y1:.5f} {z1:.5f}) (position {x2:.5f} {y2:.5f} {z2:.5f}) "{material}" "{region_name}")'
        self.add_cmd(cmd)
        
        base_name = region_name.split('_')[0]
        if base_name not in self.region_groups:
            self.region_groups[base_name] = []
        self.region_groups[base_name].append(region_name)
        
        # 判断是否为金属，记录其边界与名称，便于上下表面添加 Contact
        metal_materials = ["Tungsten", "Copper", "Metal"]
        if material in metal_materials:
            self.metal_regions.append({
                'name': region_name,
                'x_center': (x1 + x2) / 2.0,
                'y_center': (y1 + y2) / 2.0,
                'z_min': min(z1, z2),
                'z_max': max(z1, z2)
            })

    def build_substrate(self):
        if 1 in self.layout_data and 1 in self.rules_data:
            l = self.layout_data[1]
            r = self.rules_data[1]
            self.create_cuboid(l['x1'], l['y1'], r['start_z'], l['x2'], l['y2'], r['end_z'], "Silicon", "Substrate_1")

    def build_gate(self):
        # 处理 common gate (7号版图) 或 split gate (8,9,10号版图)
        if 7 in self.layout_data and 7 in self.rules_data:
            l = self.layout_data[7]
            r = self.rules_data[7]
            self.create_cuboid(l['x1'], l['y1'], r['start_z'], l['x2'], l['y2'], r['end_z'], r['material'], "Gate_Common")
            self.gate_bounds = {'x1': l['x1'], 'y1': l['y1'], 'x2': l['x2'], 'y2': l['y2']}
        else:
            # 扩展逻辑：检测8, 9, 10号层实现 Split Gate
            pass 

    def build_cfet_core(self):
        """计算并生成 Channel, High-K, Inner Spacer 及 S/D Epi"""
        # 参数提取与缺省值处理
        num_u = int(self.arch_data.get('num_channel_upeer', 2))
        num_l = int(self.arch_data.get('num_channel_lower', 2))
        
        ch_t = self.arch_data['channel_thickness']
        ch_mdi_t = self.arch_data['channel_mdi_thickness']
        mdi_t = self.arch_data['mdi_thickness']
        
        ch_cx = self.arch_data['channel_center_x']
        ch_cy = self.arch_data['channel_center_y']
        ch_w = self.arch_data['channel_width']
        ch_l = self.arch_data['channel_length']
        
        hk_t = self.arch_data['high_k_thickness']
        isp_t = self.arch_data['inner_spacer_thickness']
        
        # 外延扩充参数
        sd_oy = self.arch_data.get('sd_overgrowth_y', 0.005)
        sd_oz_up = self.arch_data.get('sd_overgrowth_z_up', 0.006)
        sd_oz_down = self.arch_data.get('sd_overgrowth_z_down', 0.006)

        # 纳米片 X-Y 绝对边界
        ch_x1 = ch_cx - ch_l / 2.0
        ch_x2 = ch_cx + ch_l / 2.0
        ch_y1 = ch_cy - ch_w / 2.0
        ch_y2 = ch_cy + ch_w / 2.0

        current_z = 0.0 # 根据规则，自基底顶部 z=0 开始堆叠
        
        # 记录所有生成的沟道高度区间，用于生成拓扑隔离与外延
        channel_z_bounds = []

        def stack_channels(num_channels, region_prefix):
            nonlocal current_z
            for i in range(num_channels):
                current_z += ch_mdi_t
                z_start = current_z
                current_z += ch_t
                z_end = current_z
                
                c_name = f"{region_prefix}_{i}"
                # 1. 生成 Channel
                self.create_cuboid(ch_x1, ch_y1, z_start, ch_x2, ch_y2, z_end, "Silicon", c_name)
                channel_z_bounds.append((z_start, z_end))
                
                # 2. 生成保形 High-K (HfO2) - 在栅长范围内包络 Channel
                hk_x1 = ch_cx - self.arch_data['gate_length']/2.0
                hk_x2 = ch_cx + self.arch_data['gate_length']/2.0
                self.create_cuboid(hk_x1, ch_y1 - hk_t, z_start - hk_t, hk_x2, ch_y2 + hk_t, z_end + hk_t, "HfO2", f"HighK_{region_prefix}_{i}")
                
        # Lower Channels
        stack_channels(num_l, "ChannelLower")
        
        # MDI (介电隔离层)
        current_z += ch_mdi_t
        current_z += mdi_t
        
        # Upper Channels
        stack_channels(num_u, "ChannelUpper")
        current_z += ch_mdi_t
        
        # 3. 统一合并重叠区域 (SDE 将由后序 bool-unite 和优先级解决相交穿透)
        
        # 4. 生成源漏外延 (S/D Epi)
        # S/D X方向占据版图边界未被沟道、栅极、内侧墙等占据的区域
        boundary = self.layout_data[1]
        
        # 左侧源漏
        sd_l_x1 = boundary['x1']
        sd_l_x2 = ch_x1 - isp_t - hk_t # 接触到 Inner Spacer 外缘
        
        # 右侧源漏
        sd_r_x1 = ch_x2 + isp_t + hk_t
        sd_r_x2 = boundary['x2']

        # Y 和 Z 膨胀
        sd_y1 = ch_y1 - sd_oy
        sd_y2 = ch_y2 + sd_oy

        # Lower S/D
        low_z_min = channel_z_bounds[0][0] - sd_oz_down
        low_z_max = channel_z_bounds[num_l-1][1] + sd_oz_up
        self.create_cuboid(sd_l_x1, sd_y1, low_z_min, sd_l_x2, sd_y2, low_z_max, "SiGe", "SD_Lower_Left")
        self.create_cuboid(sd_r_x1, sd_y1, low_z_min, sd_r_x2, sd_y2, low_z_max, "SiGe", "SD_Lower_Right")

        # Upper S/D
        up_z_min = channel_z_bounds[num_l][0] - sd_oz_down
        up_z_max = channel_z_bounds[-1][1] + sd_oz_up
        self.create_cuboid(sd_l_x1, sd_y1, up_z_min, sd_l_x2, sd_y2, up_z_max, "Silicon", "SD_Upper_Left")
        self.create_cuboid(sd_r_x1, sd_y1, up_z_min, sd_r_x2, sd_y2, up_z_max, "Silicon", "SD_Upper_Right")

    def perform_boolean_operations(self):
        """对相邻且同质的结构进行布尔合并，满足命名合并原则"""
        self.add_cmd("\n; --- 布尔合并操作 ---")
        for base_name, regions in self.region_groups.items():
            if len(regions) > 1:
                region_list_str = " ".join([f'(car (find-region-id "{r}"))' for r in regions])
                self.add_cmd(f'(sdegeo:bool-unite (list {region_list_str}) "{base_name}_Merged")')
                # 更新名称映射表，以便后续网格或掺杂引用
                self.region_groups[base_name] = [f"{base_name}_Merged"]

    def add_contacts(self):
        """严格在金属上下表面添加 Contact 属性"""
        self.add_cmd("\n; --- 添加电极接触 (Contacts) ---")
        for idx, metal in enumerate(self.metal_regions):
            region_name = metal['name']
            
            # 由于可能发生了布尔合并，检索其实际存在的名称
            base_name = region_name.split('_')[0]
            if base_name in self.region_groups:
                active_name = self.region_groups[base_name][0]
            else:
                active_name = region_name
                
            contact_top = f"Contact_{active_name}_Top_{idx}"
            contact_bot = f"Contact_{active_name}_Bot_{idx}"
            
            # 定义 Contact
            self.add_cmd(f'(sdegeo:define-contact-set "{contact_top}" 4 (color:rgb 1 0 0) "##")')
            self.add_cmd(f'(sdegeo:define-contact-set "{contact_bot}" 4 (color:rgb 1 0 0) "##")')
            
            # 依附于 Z 轴极值表面
            self.add_cmd(f'(sdegeo:set-contact-boundary-faces (find-face-id (position {metal["x_center"]} {metal["y_center"]} {metal["z_max"]})) "{contact_top}")')
            self.add_cmd(f'(sdegeo:set-contact-boundary-faces (find-face-id (position {metal["x_center"]} {metal["y_center"]} {metal["z_min"]})) "{contact_bot}")')

    def add_doping(self):
        """配置合理的物理掺杂类型：定义 P型底底、N型/P型外延及轻掺杂沟道"""
        self.add_cmd("\n; --- 定义掺杂特性 ---")
        
        # 1. 衬底轻掺杂 P-type
        self.add_cmd('(sdedr:define-constant-profile "Substrate_Doping" "BoronActiveConcentration" 1e15)')
        self.add_cmd('(sdedr:define-constant-profile-region "Place_Sub_Doping" "Substrate_Doping" "Substrate_1")')
        
        # 2. CFET 上层源漏 (例如 N-type)
        self.add_cmd('(sdedr:define-constant-profile "SD_Upper_Doping" "PhosphorusActiveConcentration" 2e20)')
        self.add_cmd('(sdedr:define-constant-profile-region "Place_SD_U_L" "SD_Upper_Doping" "SD_Upper_Left")')
        self.add_cmd('(sdedr:define-constant-profile-region "Place_SD_U_R" "SD_Upper_Doping" "SD_Upper_Right")')

        # 3. CFET 下层源漏 (例如 P-type)
        self.add_cmd('(sdedr:define-constant-profile "SD_Lower_Doping" "BoronActiveConcentration" 2e20)')
        self.add_cmd('(sdedr:define-constant-profile-region "Place_SD_L_L" "SD_Lower_Doping" "SD_Lower_Left")')
        self.add_cmd('(sdedr:define-constant-profile-region "Place_SD_L_R" "SD_Lower_Doping" "SD_Lower_Right")')

    def add_meshing(self):
        """定义全域离散精度及局部网格自适应细化原则"""
        self.add_cmd("\n; --- 设定网格离散精度 (Meshing) ---")
        
        # 全局基础网格
        self.add_cmd('(sdedr:define-refinement-size "Global_Mesh_Size" 0.02 0.02 0.02 0.01 0.01 0.01)')
        self.add_cmd('(sdedr:define-refinement-placement "Global_Mesh_Place" "Global_Mesh_Size" (get-body-list))')
        
        # 沟道与 High-K 核心区高精度网格
        b = self.layout_data[1]
        self.add_cmd('(sdedr:define-refeval-window "Core_Win" "Cuboid" '
                     f'(position {b["x1"]} {b["y1"]} 0.0) '
                     f'(position {b["x2"]} {b["y2"]} 0.2))') # Z范围根据器件厚度调整
        
        self.add_cmd('(sdedr:define-refinement-size "Core_Mesh_Size" 0.002 0.002 0.002 0.001 0.001 0.001)')
        self.add_cmd('(sdedr:define-refinement-placement "Core_Mesh_Place" "Core_Mesh_Size" "Core_Win")')
        
        # 触发网格生成引擎
        self.add_cmd('(sde:build-mesh "snmesh" "-a -c boxmethod" "cfet_structure")')

    def generate(self, output_file):
        self.parse_inputs()
        
        self.add_cmd('; SDE Build Script for CFET Generated by SDEBuilder')
        self.add_cmd('(sde:clear)')
        
        self.build_substrate()
        self.build_gate()
        self.build_cfet_core()
        
        self.perform_boolean_operations()
        self.add_contacts()
        self.add_doping()
        self.add_meshing()
        
        with open(output_file, 'w') as f:
            f.write("\n".join(self.sde_commands))
            
        print(f"SDE 脚本已成功导出至：{output_file}")


if __name__ == "__main__":
    # 执行实例化和导出。适配其他文件时，只需将文件路径更改至此处对应的参数位置。
    builder = SDEBuilder(
        layout_file="./test1_gds.txt", 
        rules_file="./layer_rule_1.txt", 
        arch_file="./cfet_arch.txt"
    )
    builder.generate("build_sde.cmd")