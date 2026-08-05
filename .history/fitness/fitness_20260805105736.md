请你优先修改刚才提到的内容，并在后续拟合中保留。
此外需要针对文件夹内的va文件对乘系数后的曲线进行拟合，需要通过hspice将va文件中的器件进行拟合，需要注意的是csv中的参数都是经过处理的，单位为A/um的电流。请你

va模型中，parameter参数需要进行修改，parameter real需要增加几个，新增的参数并放到va模型现有的parameter real中后面。拟合后要求生成两个完整的va模型。原va中的注释无需全部保留，标题需要写清楚必要的引用参考并描述本次拟合所做的工作。

NFET
parameter real L=1.6e-8; （拟合时不可变）
parameter real W=2.5e-8; （拟合时不可变）
parameter real NF=1;     （拟合时不可变）

parameter real U0 = 3.0e-2; （拟合时可变）
parameter real XL=1.2e-8;	（拟合时可变,数量级和L相同）
parameter real DVTSHIFT=0.0; （拟合时可变）
parameter real DeltaWGAA = 0; （拟合时可变,数量级和W相同）
parameter real DeltaTGAA = 0;（拟合时可变,数量级和TGAA相同）
parameter real EOT_0 = 7.9e-10; （拟合时可变）

parameter real TGAA = 6e-9; （拟合时不可变）
parameter real NGAA = 3; （拟合时不可变）
parameter real NBODY = 1e21 （拟合时不可变）
parameter real NSD = 3e26; （拟合时不可变）
parameter real PHIG = 4.38; （拟合时不可变）

PFET
parameter real L=1.6e-8; （拟合时不可变）
parameter real W=2.5e-8; （拟合时不可变）
parameter real NF=1;     （拟合时不可变）

parameter real U0 = 3.0e-2; （拟合时可变）
parameter real XL=1.2e-8;	（拟合时可变,数量级和L相同）
parameter real DVTSHIFT=0.0; （拟合时可变）
parameter real DeltaWGAA = 0; （拟合时可变）
parameter real DeltaTGAA = 0;（拟合时可变）
parameter real EOT_0 = 7.9e-10; （拟合时可变）

parameter real TGAA = 6e-9; （拟合时不可变）
parameter real NGAA = 3; （拟合时不可变）
parameter real NBODY = 1e21 （拟合时不可变）
parameter real NSD = 3e26; （拟合时不可变）
parameter real PHIG = 4.67; （拟合时不可变）

最终需要生成两套va模型，分别对应44nm和48nmCPP