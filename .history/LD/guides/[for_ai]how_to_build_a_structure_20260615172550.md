生成过程需要遵守的规则
- 需要优先确认所有enable项为True的版图信息的 end_z2-start_z1 == height，否则进行报错，并明确指明不匹配的版图编号和该行文件的信息，后续内容全部不执行。
- 所有结构的x,y均由版图的x,y决定方向：
  - $x$-axis: 源-栅-漏 (Source-Gate-Drain, S-G-D) 导电方向。
  - $y$-axis: 栅极物理延伸方向 (Gate width direction)。
  - $z$-axis: 晶圆外延生长的垂直法线方向 (Vertical stacking direction)。
- 下文中所提到的./rules/xxx_arch.txt文件中，"xxx"为用户输入的文件名，根据用户输入的文件名，从./rules文件夹中读对应的文件。


生成正确的结构需要按照下面的步骤顺序生成：
- 生成衬底，规定衬底范围的是版图中编号为1的层，厚度由对应的1号版图的height start_z1 end_z2决定；
- 生成Gate，共有2种情况：
  - common gate的情形：若7号版图存在，则规定Gate的范围是版图中编号为7的层，厚度由7号版图的height start_z1 end_z2决定；
  - split gate的情形：若7号版图不存在，且8，9，10号版图均存在，规定Gate由三个部分生成，分别对应8，9，10号版图的height start_z1 end_z2决定；
- 生成纳米片，和gate重合的部分由新生成的纳米片完全覆盖，且单独的每个纳米片在结构上是一个完整额整体。规定纳米片的体积相关量定义如下：纳米片的x宽度由./rules/xxx_arch.txt中的channel_length决定，y高度由./rules/xxx_arch.txt中的channel_width决定，而厚度由./rules/xxx_arch.txt中的channel_thickness决定；位置上，纳米片的几何位置由多个因素决定，生成的纳米片条数由./rules/xxx_arch.txt中的num_channel决定，num_channel代表上下的两个结构分别由num_channel条纳米片组成；自衬底顶部z=0开始，以num_channel = 2为例，分别为channel_mdi_thickness / channel_thickness / channel_mdi_thickness / channel_thickness /channel_mdi_thickness / mdi_thickness / channel_mdi_thickness / channel_thickness / channel_mdi_thickness / channel_thickness /channel_mdi_thickness 其中，channel_mdi_thickness和mdi_thickness不要对应结构，在这个结构中只关注channel的高度z; 所有channel的 x方向中心在 channel_center_x ，所有channel的 y 方向中心在 channel_center_y
  - 上述几个量若为-1，取num_channel_upeer、num_channel_lower、channel_upper_length、channel_upper_width、channel_lower_length、channel_lower_width等值
- 生成High-k介质，High-k的位置在channel的沿 y、z 方向环绕，前后上下的环绕厚度由 ./rules/xxx_arch.txt中的 high_k_thickness决定
  - high-k层的位置描述如下：High-k层作为一个厚度为 $t_{hk}$ 的保形介质层，构成了栅极金属在三维空间中的绝对外壳。它将栅极金属完全包络于其内侧体积中，作为栅极金属与外部结构的唯一交界面。在有效栅长（$L_g$）范围内，High-k层沿 $x$ 轴延伸，并在 $y-z$ 平面上正交闭合并紧密包裹住每一层悬浮的半导体硅纳米片沟道。在 $z$ 方向上相邻的纳米片间隙处，High-k层向 $x$ 轴的正负两端延伸，直到与内侧墙（Inner Spacer）直接接触，形成垂直于 $x$ 轴的物理截面。内侧墙在此充当了关键的空间阻挡层，确保High-k层与源漏外延材料（S/D Epi）保持绝对的物理隔离，使得该区域沿 $x$ 轴的材料相交排布严格遵循“栅极金属、High-k层、内侧墙、源漏外延”的拓扑序列。
- 生成内侧墙，内侧墙的位置在相邻