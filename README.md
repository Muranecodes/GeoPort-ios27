# 🌸 花徑漫步 | GeoPort (iOS 17–27 Edition)

<p align="center">
  <strong><a href="#-english">🌍 English</a></strong> &nbsp;|&nbsp; <strong><a href="#-繁體中文">🌸 繁體中文</a></strong>
</p>

> Based on [GeoPort](https://github.com/davesc63/GeoPort) by davesc63, licensed under [GPL-3.0](LICENSE).  
> Heavily redesigned and maintained at [Muranecodes/GeoPort-ios27](https://github.com/Muranecodes/GeoPort-ios27).

---

## 🌍 English

**GeoPort (花徑漫步)** is a minimalist iOS location simulation, automated pedestrian navigation, and flower-planting workbench supporting **iOS 17 through iOS 27**.

Redesigned from the ground up with a cozy Japanese botanical interface, it lets you teleport anywhere on the globe, stroll along real pedestrian footpaths at configurable speeds, or steer in real time with your keyboard—all from a single, clutter-free browser window.

### ✨ Key Features

- **🌸 Minimalist Botanical Workbench (`花徑漫步` UI)**
  - **Single-Screen Bento Layout**: Top device bar, central map canvas, and bottom coordinate bar fit into a single viewport without vertical scrolling.
  - **Light & Cozy Forest Night Themes**: Switch seamlessly between warm botanical cream and a low-glare dark mode (`🌙 深色模式`).
  - **Zero-Config Map Tiles**: Powered out of the box by **Stadia Maps** on `localhost`—no API key registration required and no watermark clutter.
- **🌸 Speed Presets & Planting Mode**
  - Switch speeds anytime—even mid-journey—using quick presets or the `0.1 – 120.0 km/h` slider & numeric input:

| Preset | Speed | Best For |
| :--- | :--- | :--- |
| **🚶 Walk (`散步`)** | `5.0 km/h` | Casual strolling and egg hatching |
| **🌸 Planting (`種花`)** | `19.1 km/h` | Maximizing flower planting efficiency under game speed caps (features a signature blossom-pink theme) |
| **🚗 Drive (`開車`)** | `60.0 km/h` | Fast city-to-city transit and road navigation testing |

- **🧭 Auto Navigation (`自動導航`)**
  - Click **`🧭 自動導航`** on the top-left of the map, then click any destination on the map.
  - Automatically plans a pedestrian route along real sidewalks and footpaths (via OpenStreetMap OSRM, with automatic straight-line fallback when off-road).
  - A floating HUD displays live status (`運行中` / `已暫停`), current speed, remaining distance, and ETA, with **Pause / Resume (`暫停` / `繼續`)** and **Stop (`停止導航`)** controls.
  - Continues walking smoothly in the background even when the browser tab is minimized.
- **⌨️ Real-Time Keyboard Steering (`WASD` / Arrow Keys)**
  - Hold `W` / `A` / `S` / `D` or `↑` / `←` / `↓` / `→` to move in cardinal directions at your currently selected speed; release the key to stop immediately.
  - Pressing movement keys during active Auto Navigation cleanly interrupts the route and hands immediate manual control to you.
- **🎯 Camera Tracking & 📌 Custom Starting Point**
  - **Camera Tracking (`🎯 鏡頭跟隨`)**: Keeps your moving marker centered on the map, and automatically unlocks if you manually drag the map.
  - **Custom Default Start (`📌 設為預設起點`)**: Right-click anywhere on the map to save that coordinate and zoom level as your default home location on startup.

---

### 🚀 Prerequisites & Quick Start

#### Prerequisites
1. **iOS Device**: Running iOS 17 – iOS 27 connected to your computer via USB cable, with **Developer Mode** enabled.
2. **Windows Users**:
   - Install **iTunes** (or **Apple Devices** / Apple Mobile Device Service) so Windows can communicate with your iPhone/iPad over USB.
   - Install **Python 3.12+** (installing [`uv`](https://docs.astral.sh/uv/) is optional and speeds up first-time environment creation).

#### Windows One-Click Launch (Recommended)
Run `start-geoport.ps1` in PowerShell from the repository root:

```powershell
.\start-geoport.ps1
```

What the launcher does automatically:
1. Requests **Administrator** privileges (required for iOS 17+ developer tunnels).
2. Creates `.venv-legacy` and `.venv-modern` on first launch and installs all required dependencies.
3. Starts the local workbench server and opens your default browser at `http://localhost:54321`.

<details>
<summary><strong>🍎 macOS Manual Setup (Click to expand)</strong></summary>

On macOS, create the primary environment and (for iOS 27 USB devices) the modern bridge environment, then run with `sudo`:

```bash
python3.12 -m venv .venv-legacy
.venv-legacy/bin/python -m pip install -r requirements-legacy.txt

python3.13 -m venv .venv-modern
.venv-modern/bin/python -m pip install 'pymobiledevice3>=11.17,<12'

sudo GEOPORT_MODERN_PMD3_PYTHON="$PWD/.venv-modern/bin/python" .venv-legacy/bin/python src/main.py
```
</details>

---

### 📖 How to Use

1. **Connect Your Device**
   - Plug in your iOS device via USB, unlock the screen, and trust the computer if prompted.
   - In the top bar, click **`🔄 重新整理` (Refresh)**, select your device from **`📱 選擇裝置`**, and click **`🔗 連線裝置` (Connect)**. Wait until the button turns into **`✅ 已連線`**.
2. **Set Your Initial Location (Teleport)**
   - Click anywhere on the map (or enter `lat, lng` / a place name in the bottom search bar and click **`🔍 搜尋`**).
   - Click **`📍 開始定位` (Start Location)** in the bottom bar to lock in your starting GPS position on the device.
3. **Move Around**
   - **Choose a Speed**: In the top-right floating card, pick **`🚶 散步 (5 km/h)`**, **`🌸 種花 (19.1 km/h)`**, **`🚗 開車 (60 km/h)`**, or drag the slider.
   - **Auto Navigate**: Click **`🧭 自動導航`** on the top-left of the map, then click your destination on the map to start walking along footpaths.
   - **Manual Walk**: Simply hold `W` / `A` / `S` / `D` or the Arrow keys on your keyboard to walk in any direction.
4. **Restore Real GPS Location**
   - When finished, click **`🛑 停止定位` (Stop Location)** in the bottom bar and **`🔌 中斷連線` (Disconnect)** in the top bar.

---

### 💡 FAQ & Troubleshooting

- **How do I enable Developer Mode on my iOS device?**
  - Go to **Settings ➔ Privacy & Security ➔ Developer Mode** on your iPhone/iPad, toggle it on, and restart the device.
  - If the Developer Mode menu is hidden on your device, GeoPort can reveal it for you—note that iOS requires you to temporarily disable your device passcode if GeoPort enables Developer Mode automatically.
- **I unplugged my phone without clicking "Stop Location" (`🛑 停止定位`). How do I get my real GPS back?**
  - Reconnect your phone to GeoPort and click **`🛑 停止定位`**, or simply restart your iPhone/iPad to reset location services immediately.
- **Why does Auto Navigation pause on its own?**
  - If the USB cable or iOS developer tunnel disconnects mid-journey, GeoPort's failsafe automatically pauses navigation and freezes your last known coordinates so your avatar never jumps unexpectedly. Reconnect your device and click **`繼續` (Resume)**.

---

## 🌸 繁體中文

**「🌸 花徑漫步」(GeoPort iOS 17–27 Edition)** 是一款專為 **iOS 17 至 iOS 27** 打造的極簡虛擬定位、自動人行道導航與種花漫步工具。

本專案大幅重構了原版 GeoPort，換上溫潤舒適的日系植物風單頁介面，並針對 LBS 位置遊戲（如 Pikmin Bloom、Pokémon GO、Monster Hunter Now）與導航測試，提供穩定的背景移動模擬與即時鍵盤操控體驗。

### ✨ 核心功能特色

- **🌸「花徑漫步」極簡三層卡片介面**
  - **單一畫面免捲動 (Bento Layout)**：頂部裝置連線列、中央大圓角地圖畫布、底部搜尋與定位控制列完美收納於單一瀏覽器視窗。
  - **暖白日系與森林夜色深色模式**：一鍵切換護眼的暖白鼠尾草綠主題與柔和的 **`🌙 深色模式`**。
  - **零配置高質感底圖**：預設採用 **Stadia Maps** 底圖，於本機端免申請 API Key、無浮水印干擾，開箱即用。
- **🌸 專屬「種花模式」與動態時速控制**
  - 支援在移動途中隨時切換預設時速，或透過滑桿與數字框微調（`0.1 – 120.0 km/h`），無須中斷行程：

| 時速模式 | 速度設定 | 適用情境 |
| :--- | :--- | :--- |
| **🚶 散步 (Walk)** | `5.0 km/h` | 一般日常步行模擬、孵蛋與慢速探索 |
| **🌸 種花 (Planting)** | `19.1 km/h` | **專屬櫻花粉主題配色**；貼齊種花限速上限，最大化撒花與步數效益 |
| **🚗 開車 (Drive)** | `60.0 km/h` | 跨區快速移動與車行導航測試 |

- **🧭 自動導航 (Auto Navigation)**
  - 點擊地圖左上角的 **`🧭 自動導航`** 按鈕進入點選模式，再點擊地圖上任一目的地即可自動出發（出發後自動退出點選模式，方便自由拖曳瀏覽地圖）。
  - 自動沿真實世界的人行道與步道規劃路徑（採用 OpenStreetMap OSRM 步行路由；若遇無道路區域則自動以直線平滑推進）。
  - 右上角浮動導航面板即時顯示狀態（`運行中`／`已暫停`）、當前時速、剩餘距離與預估抵達時間 (ETA)，並提供 **`暫停` / `繼續`** 與 **`停止導航`** 按鈕。
  - 由本機伺服器背景持續推進，即使將瀏覽器分頁縮小或切換至其他視窗，定位移動也不會中斷。
- **⌨️ 鍵盤 WASD / 方向鍵即時手動操控**
  - 按住鍵盤 `W` / `A` / `S` / `D` 或方向鍵（`↑` / `←` / `↓` / `→`）即可依目前設定的時速朝北、西、南、東平滑移動，放開按鍵立即停止。
  - 若在「自動導航」途中按下方向鍵，系統會自動中斷導航並無縫切換為手動操控。
- **🎯 鏡頭跟隨與 📌 自訂預設起點**
  - **鏡頭跟隨 (`🎯 鏡頭跟隨`)**：開啟後地圖視角會自動跟隨移動中的定位標記；手動拖曳地圖時會自動解除鎖定，方便查看周邊地圖。
  - **設為預設起點 (`📌 設為預設起點`)**：在地圖任意位置按**滑鼠右鍵**即可儲存該座標與縮放層級，下次開啟時自動定位於常用起點。

---

### 🚀 環境需求與快速啟動

#### 前置準備
1. **iOS 裝置**：支援 iOS 17 至 iOS 27，請使用 USB 傳輸線連接電腦，並確認手機已開啟 **「開發者模式 (Developer Mode)」**。
2. **Windows 電腦環境**：
   - 請先安裝 **iTunes**（或 **Apple 裝置 / Apple Mobile Device Service**），以提供 Windows 辨識 iOS 裝置所需的 USB 驅動服務。
   - 安裝 **Python 3.12+**（若已安裝 [`uv`](https://docs.astral.sh/uv/)，首次建立環境的速度會大幅加快）。

#### Windows 一鍵啟動（推薦）
在專案根目錄開啟 PowerShell，執行啟動腳本：

```powershell
.\start-geoport.ps1
```

啟動腳本會自動完成以下步驟：
1. 自動申請 **系統管理員權限 (Administrator)**（建立 iOS 17+ 開發者通道的必要權限）。
2. 首次執行時自動建立 `.venv-legacy` 與 `.venv-modern` 雙虛擬環境並安裝所有相依套件。
3. 啟動本機伺服器並自動開啟瀏覽器前往 `http://localhost:54321`。

<details>
<summary><strong>🍎 macOS 手動啟動說明（點擊展開）</strong></summary>

於 macOS 終端機建立主環境與（供 iOS 27 USB 使用的）橋接環境，並以 `sudo` 啟動：

```bash
python3.12 -m venv .venv-legacy
.venv-legacy/bin/python -m pip install -r requirements-legacy.txt

python3.13 -m venv .venv-modern
.venv-modern/bin/python -m pip install 'pymobiledevice3>=11.17,<12'

sudo GEOPORT_MODERN_PMD3_PYTHON="$PWD/.venv-modern/bin/python" .venv-legacy/bin/python src/main.py
```
</details>

---

### 📖 操作指南

1. **連線 iOS 裝置**
   - 將 iPhone / iPad 以 USB 連接電腦、解鎖螢幕，若手機跳出「要信任這部電腦嗎？」請點選信任。
   - 在網頁頂部列點擊 **`🔄 重新整理`**，於 **`📱 選擇裝置`** 下拉選單選取你的裝置，再點擊 **`🔗 連線裝置`**。等待狀態變為 **`✅ 已連線`**。
2. **設定初始定位（瞬移／定點）**
   - 直接在中央地圖點擊想前往的位置（或在底部搜尋欄輸入 `緯度, 經度` 或地名後點擊 **`🔍 搜尋`**）。
   - 點擊底部列的 **`📍 開始定位`**，手機定位即會切換至該座標。
3. **開始移動（散步／種花／導航）**
   - **切換時速**：在右上角時速卡片點選 **`🚶 散步 (5 km/h)`**、**`🌸 種花 (19.1 km/h)`** 或 **`🚗 開車 (60 km/h)`**，或拖曳滑桿自訂速度。
   - **自動導航**：點擊地圖左上角 **`🧭 自動導航`** 使其亮起，接著點擊地圖上的目的地，即可沿人行道自動前進。
   - **鍵盤漫步**：直接按住鍵盤 `W` / `A` / `S` / `D` 或方向鍵，即可即時控制移動方向。
4. **結束並還原真實定位**
   - 使用完畢後，請點擊底部列的 **`🛑 停止定位`** 還原手機真實 GPS，再點擊頂部列的 **`🔌 中斷連線`** 或 **`🚪 離開`**。

---

### 💡 常見問題與排解 (FAQ)

- **如何開啟 iOS「開發者模式 (Developer Mode)」？**
  - 請至手機的 **「設定 ➔ 隱私權與安全性 ➔ 開發者模式」** 將開關打開，並依提示重新啟動手機。
  - 若設定中沒有出現「開發者模式」選項，連線時系統會自動協助啟用（注意：若由程式自動開啟開發者模式，iOS 系統限制需先暫時關閉手機螢幕鎖定密碼）。
- **忘記點選「🛑 停止定位」就直接拔掉傳輸線怎麼辦？**
  - 只需重新插上連回電腦並點擊 **`🛑 停止定位`**，或是直接**將 iPhone / iPad 重新開機**，即可立即恢復真實 GPS 定位。
- **為什麼自動導航途中會自動暫停？**
  - 當 USB 連線晃動或開發者通道異常中斷時，安全保護機制會自動暫停導航並凍結最後座標，防止定位發生異常跳動。請重新確認裝置連線後，點擊導航面板上的 **`繼續`** 即可恢復行程。

---

## 🙏 Credits & License

- Original project: [davesc63/GeoPort](https://github.com/davesc63/GeoPort)
- Core device communication powered by [pymobiledevice3](https://github.com/doronz88/pymobiledevice3)
- Licensed under the [GNU General Public License v3.0](LICENSE).
