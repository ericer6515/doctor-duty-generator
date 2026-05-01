# 醫師病房值班排班系統（Flask 版）
**AI做的，方便管理故上傳
## 安裝
點選VENVset.bat 設定虛擬機和安裝flask, taiwan holiday

## 啟動
點選_windows.bat

開啟瀏覽器進入：
```text
http://127.0.0.1:5000/
```

## 功能
- Python 核心排班演算法
- GUI 獨立前端頁面
- 醫師特休設定
- 病房停班設定
- 手動假日設定
- 預設跳到下個月
- 每個病房獨立月曆
- 若已安裝 `taiwan-holidays`，可自動辨識台灣假日


## Windows 雙擊啟動
1. 解壓縮整個資料夾
2. 在 Windows 內直接雙擊 `start_windows.bat`
3. 第一次執行會自動建立虛擬環境並安裝套件
4. 瀏覽器會自動開啟 `http://127.0.0.1:5000/`

### 注意
- 需先安裝 Python 3，且安裝時建議勾選 **Add Python to PATH**
- 第一次啟動會比較久，因為要安裝 Flask 與 `taiwan-holidays`


## 打包成免安裝 EXE
1. 在已安裝 Python 3 的 Windows 機器上，進入此資料夾
2. 雙擊 `build_exe.bat`
3. 會自動建 venv、安裝依賴與 PyInstaller，並產生 `dist/app.exe`
4. 之後可將 `dist/app.exe` 複製到其他 Windows 機器，直接雙擊執行（不需安裝 Python）

> 備註：EXE 內部仍是啟動 Flask 本機伺服器，第一次執行時可能會跳出防火牆詢問。允許本機連線即可。
