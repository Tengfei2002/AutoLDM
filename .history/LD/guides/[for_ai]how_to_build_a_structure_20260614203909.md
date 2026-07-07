生成过程需要遵守的规则
- 需要优先确认所有enable项为True的版图信息的 end_z2-start_z1 == height，否则进行报错，并明确指明不匹配的版图编号和该行文件的信息，后续内容全部不执行。
- 所有结构的x,y均由版图的x,y决定方向，通俗理解为S-G-D的方向为版图的x方向，Gate延申的方向为版图的y方向；


生成正确的结构需要按照下面的步骤顺序生成：
- 生成衬底，规定衬底范围的是版图中编号为1的层，厚度由对应的1号版图的height start_z1 end_z2决定；
- 生成Gate，共有2种情况：
  - common gate的情形：若7号版图存在，则规定Gate的范围是版图中编号为7的层，厚度由7号版图的height start_z1 end_z2决定；
  - split gate的情形：若7号版图不存在，且8，9，10号版图均存在，规定Gate由三个部分生成，分别对应8，9，10号版图的height start_z1 end_z2决定；
- 生成纳米片，和gate重合的部分由新生成的纳米片完全覆盖，且单独的每个纳米片在结构上是一个完整额整体。规定纳米片的体积相关量定义如下：纳米片的x宽度由./rules/xxx_arch.txt中的channel_length决定，y高度由./rules/xxx_arch.txt中的channel_width决定，而厚度由./rules/xxx_arch.txt中的channel_thickness决定；位置上，纳米片的几何位置由多个因素决定，生成的纳米片条数由./rules/xxx_arch.txt中的num_channel决定，num_channel代表上下的两个结构分别由num_channel条纳米片组成；自衬底顶部z=0开始，以num_channel = 2为例，分别为channel_mdi_thickness / channel_thickness / channel_mdi_thickness / channel_thickness /channel_mdi_thickness / mdi_thickness / channel_mdi_thickness / channel_thickness / channel_mdi_thickness / channel_thickness /channel_mdi_thickness 其中，channel_mdi_thickness和mdi_thickness不要对应结构，在这个结构中只关注channel的高度z; x方向的
  - 上述几个量若为-1，取num_channel_upeer、num_channel_lower、channel_upper_length、channel_upper_width、channel_lower_length、channel_lower_width等值
- 