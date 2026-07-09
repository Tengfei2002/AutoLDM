在项目根目录 `C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM` 运行：

```powershell
git status
```

如果确认所有改动都要提交：commit内容需要更新

```powershell
git add -A
git status
git commit -m "update git options"
git push
```

如果提交前要先同步远端：

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