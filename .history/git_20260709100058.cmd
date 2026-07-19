在项目根目录 `C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM` 运行：

```powershell
git status
```

如果确认所有改动都要提交：

```powershell
git add -A
git status
git commit -m "add hspice sram rc flow and iv plots"
git push
```

如果提交前要先同步远端，推荐这样：

```powershell
git pull --rebase
git add -A
git commit -m "add hspice sram rc flow and iv plots"
git push
```

如果 `git pull --rebase` 提示有未提交改动不能拉，就先提交再 pull：

```powershell
git add -A
git commit -m "add hspice sram rc flow and iv plots"
git pull --rebase
git push
```

注意：`git add -A` 会提交所有变更，包括新生成的 `.lis/.sw0/png` 等结果文件。如果你不想提交仿真结果，只提交代码和 deck，先发我 `git status` 输出，我帮你筛命令。