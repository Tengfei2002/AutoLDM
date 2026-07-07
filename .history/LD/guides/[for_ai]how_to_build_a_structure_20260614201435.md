生成过程需要遵守的规则
- 需要优先确认所有enable项为True的版图信息的 end_z2-start_z1 == height，否则进行报错，并明确指明不匹配的版图编号和该行文件的信息，后续内容全部不执行。
- 所有结构的x,y均由版图的x,y决定方向，通俗理解为S-G-D的方向为版图的x方向，Gate延申的方向为版图的y方向；


生成正确的结构需要按照下面的步骤顺序生成：
- 生成衬底，规定衬底范围的是版图中编号为1的层，厚度由对应的1号版图的height start_z1 end_z2决定；
- 生成Gate，共有2种情况：
  - common gate的情形：若7号版图存在，则规定Gate的范围是版图中编号为7的层，厚度由7号版图的height start_z1 end_z2决定；
  - split gate的情形：若7号版图不存在，且8，9，10号版图均存在，规定Gate由三个部分生成，分别对应8，9，10号版图的height start_z1 end_z2
- 生成纳米片，规定纳米片的x宽度由./rules/xxx_arch.txt中的channel_length决定，y高度由./rules/xxx_arch.txt中的channel_width决定，而厚度由./rules/xxx_arch.txt中的channel_thickness决定，生成的纳米片条数由./rules/xxx_arch.txt中的num_channel决定；
  - 上述几个量若为-1，取num_channel_upeer、num_channel_lower、channel_upper_length、channel_upper_width、channel_lower_length、channel_lower_width