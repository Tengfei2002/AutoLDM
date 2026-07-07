import cv2
import math

# --- 全局状态变量 ---
points = []
calibration_factor = None  # 比例因子：物理单位 / 像素
image = None
clone = None

def calculate_distance(p1, p2):
    """计算两点之间的欧几里得距离（像素距离）"""
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

def mouse_callback(event, x, y, flags, param):
    global points, calibration_factor, image, clone

    # 监听鼠标左键点击事件
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        # 在点击位置绘制红色标记点
        cv2.circle(image, (x, y), 3, (0, 0, 255), -1)
        cv2.imshow("Image Measurement Tool", image)

        # 当收集到两个点时，构成一条线段
        if len(points) == 2:
            # 绘制绿色连线
            cv2.line(image, points[0], points[1], (0, 255, 0), 2)
            cv2.imshow("Image Measurement Tool", image)

            pixel_distance = calculate_distance(points[0], points[1])

            if calibration_factor is None:
                # --- 步骤 1: 标定模式 ---
                print(f"\n[标定] 获取到线段像素长度: {pixel_distance:.2f} px")
                real_length_str = input("请输入该线段对应的实际物理数值 (按回车取消): ")
                
                if real_length_str.strip():
                    try:
                        real_length = float(real_length_str)
                        calibration_factor = real_length / pixel_distance
                        print(f"[成功] 标定完成！比例尺为: 1 px = {calibration_factor:.4f} 物理单位")
                        print("-> 现在您可以继续在图像上点击两点，测量未知区域的长度。")
                    except ValueError:
                        print("[错误] 输入无效的数字，请按 'r' 重置后重新标定。")
            else:
                # --- 步骤 2: 测量模式 ---
                physical_distance = pixel_distance * calibration_factor
                print(f"[测量] 像素长度 = {pixel_distance:.2f} px, 物理计算长度 = {physical_distance:.2f}")

                # 在图像上的线段中点显示计算结果
                mid_point = ((points[0][0] + points[1][0]) // 2, (points[0][1] + points[1][1]) // 2)
                cv2.putText(image, f"{physical_distance:.2f}", mid_point,
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
                cv2.imshow("Image Measurement Tool", image)

            # 重置坐标点列表，为下一次点击（新线段）做准备
            points = []

def main(image_path):
    global image, clone, calibration_factor, points
    
    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
        print("[错误] 无法加载图像，请检查文件路径是否正确。")
        return

    clone = image.copy()
    cv2.namedWindow("Image Measurement Tool")
    cv2.setMouseCallback("Image Measurement Tool", mouse_callback)

    print("="*30)
    print("图像测量工具已启动")
    print("="*30)
    print("操作说明：")
    print("1. 标定基准：鼠标左键点击已知标注（如图中标注为 16 的高度）的起始点和终止点。")
    print("   并在控制台中输入对应的数值（例如输入 16）。")
    print("2. 目标测量：标定生效后，继续使用左键点击未标注特征的起始点和终止点。程序会自动在图中显示测算结果。")
    print("3. 按 'r' 键清除所有标记并重置比例尺。")
    print("4. 按 'q' 键或 'ESC' 退出程序。")
    print("="*30)

    # 保持窗口开启并监听键盘输入
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord("r"):
            # 恢复原始图像状态并清除标定数据
            image = clone.copy()
            calibration_factor = None
            points = []
            print("\n[系统] 图像和标定已重置，请重新进行基准标定。")
            cv2.imshow("Image Measurement Tool", image)
        elif key == ord("q") or key == 27:
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    # 在此处替换为您的图像实际路径
    # 例如: target_image = "semiconductor_cross_section.png"
    target_image = "your_image_path.png" 
    main(target_image)