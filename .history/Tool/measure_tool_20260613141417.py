import cv2

def measure_by_manual_selection(image_path, reference_length=20.0):
    # 1. 读取图像
    img = cv2.imread(image_path)
    if img is None:
        print("错误：无法读取图像，请检查文件路径是否正确。")
        return

    print("=== 第一步：框选【已知尺寸】区域 ===")
    print("请在弹出的窗口中，按住鼠标左键拖拽，框选高度为 20 的部分。")
    print("框选完成后，按空格键 (SPACE) 或回车键 (ENTER) 确认。")
    
    # 调出交互式窗口，让用户选取 ROI (Region of Interest)
    # 返回值为 (x, y, w, h)，其中 h 为像素高度
    roi_known = cv2.selectROI("Step 1: Select Known Dimension (20)", img, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow("Step 1: Select Known Dimension (20)")
    
    h_known = roi_known[3]
    if h_known <= 0:
        print("未能获取有效的已知尺寸像素高度，程序退出。")
        return
    print(f"-> 获取到已知尺寸(20)的像素高度为: {h_known} px\n")

    print("=== 第二步：框选【未知尺寸】区域 ===")
    print("请在弹出的窗口中，按住鼠标左键拖拽，框选您需要测量的目标高度。")
    print("框选完成后，按空格键 (SPACE) 或回车键 (ENTER) 确认。")
    
    roi_unknown = cv2.selectROI("Step 2: Select Unknown Dimension", img, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow("Step 2: Select Unknown Dimension")
    
    h_unknown = roi_unknown[3]
    if h_unknown <= 0:
        print("未能获取有效的未知尺寸像素高度，程序退出。")
        return
    print(f"-> 获取到未知尺寸的像素高度为: {h_unknown} px\n")

    # 3. 依据比例计算实际长度
    calculated_length = (h_unknown / h_known) * reference_length

    # 4. 输出结果
    print("=" * 45)
    print(f"已知参考长度: {reference_length}")
    print(f"通过比例换算，未标注的垂直长度为: {calculated_length:.2f}")
    print("=" * 45)

if __name__ == "__main__":
    # 请将 'image_fded9d.png' 替换为实际图片在您本地的存储路径
    measure_by_manual_selection('./image/image1.png', reference_length=20.0)