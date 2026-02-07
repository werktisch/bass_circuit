# ベース回路シミュレーター 要件定義書

## 1. 概要
Fender Jazz Bassのトーン回路をPythonでシミュレーションするアプリケーション。
Webベースのダッシュボードを通じて、各回路定数や配線の品質（アース抵抗など）が周波数特性や出力波形に与える影響を可視化する。

## 2. 技術スタック
- **言語:** Python
- **UIフレームワーク:** Panel (Holoviz)
- **可視化:** Bokeh
- **回路計算:** `numpy`/`scipy` を用いた解析的伝達関数または数値シミュレーション（SPICE的なノード解析）。

## 3. 回路モデル
ピックアップからアンプ入力までの信号経路全体をモデル化し、共振（レゾナンスピーク）や高域減衰（ハイ落ち）を正確に再現する。

### コンポーネントとパラメータ
| コンポーネント | パラメータ | 標準値 / 範囲 (目安) | 備考 |
| :--- | :--- | :--- | :--- |
| **PickUp (Neck/Bridge)** | インダクタンス ($L_{pu}$) | 2.0H - 5.0H (各PU独立設定) | フロント/リアで異なる値を設定可 |
| | 直流抵抗 ($R_{pu}$) | 6k$\Omega$ - 15k$\Omega$ | |
| | 静電容量 ($C_{pu}$) | 100pF - 200pF | |
| **Volume Pot 1 (Neck)** | 抵抗値 ($R_{vol1}$) | 250k$\Omega$, 500k$\Omega$ | **Aカーブ** |
| **Volume Pot 2 (Bridge)**| 抵抗値 ($R_{vol2}$) | 250k$\Omega$, 500k$\Omega$ | **Aカーブ** |
| **Tone Pot** | 抵抗値 ($R_{tone}$) | 250k$\Omega$, 500k$\Omega$ | **Aカーブ** |
| **Tone Cap** | 静電容量 ($C_{tone}$) | 0.022$\mu$F - 0.1$\mu$F | 代表値プリセット & **$\pm 10\%$ 許容差スライダ** |
| **Cable** | 静電容量 ($C_{cable}$) | 100pF - 1000pF | 「ケーブル長」として設定 (約100pF/m換算) |
| **Wiring/Ground**| アース抵抗 ($R_{gnd}$) | 0$\Omega$ - 5$\Omega$ | 「コントロールプレートのアース不良」vs「直結」。高いほど接触不良。 |
| **Amp Input** | 入力インピーダンス ($R_{in}$) | 1M$\Omega$ (固定) | 一般的な楽器用入力 |

### 回路構成 (トポロジー: 2 Vol, 1 Tone - Independent Wiring)
Jazz Bassの「インディペンデント・ボリューム（逆配線）」を採用。
各ボリュームのセンター端子（ワイパー）を入力、3番端子を出力とすることで、片方のボリュームを絞りきっても出力がグラウンドに短絡せず、他方のPUの音が出るようにする。

```
[Neck PU] -- [Vol 1 Wiper] -- [Vol 1 Pin3] --+
                                             |
[Bridge PU] -- [Vol 2 Wiper] -- [Vol 2 Pin3] --+--+-- [Tone Circuit] --+-- [Cable] -- [Amp Input]
                                             |
                                          (Output)
```
*   **Vol 1/2 Setting:**
    *   Pos = 10 (Max): WiperとPin3が導通 ($0\Omega$)。WiperとGnd(Pin1)は最大抵抗 ($250k\Omega$)。
    *   Pos = 0 (Min): WiperとGndが導通 ($0\Omega$ = PUショート)。WiperとPin3は最大抵抗 ($250k\Omega$)。出力ラインはGndから隔離される。

## 4. ユーザーインターフェース (UI)

### 操作パネル (サイドバー)
- **Pickup Specs:** Neck / Bridge それぞれ独立した $L, R$設定。
- **Potentiometers:**
    - Neck Volume: 0 - 10
    - Bridge Volume: 0 - 10
    - Tone: 0 - 10
    - ポット抵抗値選択ボタン (250k / 500k)
- **Tone Capacitor:**
    - 代表値ドロップダウン (0.022, 0.047, 0.1)
    - **Cap Tolerance (%):** $\pm 10\%$ の範囲で微調整。実際の容量値を計算表示。
- **Wiring / Environment:**
    - ケーブル長スライダ ($C_{cable}$ に換算)
    - "Wiring Quality" (配線品質) スライダ ($R_{gnd}$ に換算) - 表示ラベル: "Solid Copper" (良) <-> "Rusty Control Plate" (悪)

### 可視化 (メインエリア)
1.  **周波数特性 (Bode Plot):**
    - X軸: 周波数 (20Hz - 20kHz, 対数スケール)
    - Y軸: 振幅 (dB)
    - Master Tone Pot (with Curve A)
    - **Response Stats:** レゾナンスピーク（周波数/レベル）と -3dB帯域幅（High Limit）をリアルタイム表示。Pickup自身の特性が見えるようにする。
2.  **オシロスコープ (Waveform):**
    - 入力: 指定周波数の正弦波 (スライダで変更可、例: 440Hz)
    - 入力波形と出力波形を重ねて表示し、位相遅れや減衰を視覚的に確認可能にする。

## 5. 実装ステップ
1.  回路の伝達関数 $H(s) = V_{out}(s) / V_{in}(s)$ を導出（または行列計算式を定義）。
2.  Pythonで高速に再計算するロジックを実装。
3.  Panelを用いてインタラクティブなUIを構築。
4.  ローカルサーバー (`panel serve`) で動作確認。
