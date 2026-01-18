import tkinter as tk
from tkinter import ttk, messagebox
import pygame
import numpy as np
import random
import time
import threading

class EarTrainerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python 练耳程序 (Ear Trainer)")
        self.root.geometry("600x500")
        
        # 初始化 Pygame Mixer
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        
        # --- 数据配置 ---
        self.sample_rate = 44100
        self.base_freq = 261.63  # Middle C (C4)
        
        # 音程定义 (半音数: 名称)
        self.intervals = {
            1: "小二度 (m2)",
            2: "大二度 (M2)",
            3: "小三度 (m3)",
            4: "大三度 (M3)",
            5: "纯四度 (P4)",
            6: "增四/减五 (TT)",
            7: "纯五度 (P5)",
            8: "小六度 (m6)",
            9: "大六度 (M6)",
            10: "小七度 (m7)",
            11: "大七度 (M7)",
            12: "纯八度 (P8)"
        }
        
        # 乐器/波形定义
        self.instruments = {
            "正弦波 (类似风琴)": "sine",
            "三角波 (类似长笛)": "triangle",
            "锯齿波 (类似提琴/合成器)": "sawtooth",
            "方波 (类似游戏机/单簧管)": "square"
        }
        
        self.current_answer = None
        self.history_correct = 0
        self.history_total = 0
        
        # --- UI 布局 ---
        self.create_ui()

    def create_ui(self):
        # 1. 设置区域
        settings_frame = ttk.LabelFrame(self.root, text="设置")
        settings_frame.pack(pady=10, padx=10, fill="x")
        
        # 乐器选择
        ttk.Label(settings_frame, text="乐器音色:").pack(side="left", padx=5)
        self.inst_var = tk.StringVar(value="正弦波 (类似风琴)")
        inst_menu = ttk.OptionMenu(settings_frame, self.inst_var, self.inst_var.get(), *self.instruments.keys())
        inst_menu.pack(side="left", padx=5)
        
        # 播放模式
        ttk.Label(settings_frame, text="播放模式:").pack(side="left", padx=5)
        self.mode_var = tk.StringVar(value="上行 (Ascending)")
        mode_menu = ttk.OptionMenu(settings_frame, self.mode_var, "上行 (Ascending)", "上行 (Ascending)", "下行 (Descending)", "和声 (Harmonic)")
        mode_menu.pack(side="left", padx=5)

        # 2. 只有选中的音程才会出现
        interval_frame = ttk.LabelFrame(self.root, text="考察范围 (勾选想要练习的音程)")
        interval_frame.pack(pady=5, padx=10, fill="both", expand=True)
        
        self.check_vars = {}
        grid_frame = ttk.Frame(interval_frame)
        grid_frame.pack(padx=5, pady=5)
        
        r, c = 0, 0
        for semi, name in self.intervals.items():
            var = tk.BooleanVar(value=True) # 默认全选
            self.check_vars[semi] = var
            chk = ttk.Checkbutton(grid_frame, text=name, variable=var)
            chk.grid(row=r, column=c, sticky="w", padx=10, pady=2)
            c += 1
            if c > 2: # 每行3个
                c = 0
                r += 1

        # 3. 控制区域
        control_frame = ttk.Frame(self.root)
        control_frame.pack(pady=10)
        
        play_btn = ttk.Button(control_frame, text="播放新题目 (Play)", command=self.play_new_interval)
        play_btn.pack(side="left", padx=10)
        
        replay_btn = ttk.Button(control_frame, text="重听 (Replay)", command=self.replay)
        replay_btn.pack(side="left", padx=10)

        # 4. 答案按钮区域
        ans_frame = ttk.LabelFrame(self.root, text="选择答案")
        ans_frame.pack(pady=10, padx=10, fill="x")
        
        # 动态生成答案按钮容器
        self.btn_frame = ttk.Frame(ans_frame)
        self.btn_frame.pack()
        self.refresh_answer_buttons()

        # 5. 状态栏
        self.status_label = ttk.Label(self.root, text="准备就绪，点击“播放新题目”开始。", font=("Arial", 12))
        self.status_label.pack(side="bottom", pady=10)
        
        self.score_label = ttk.Label(self.root, text="得分: 0 / 0")
        self.score_label.pack(side="bottom")

    def refresh_answer_buttons(self):
        # 清除旧按钮
        for widget in self.btn_frame.winfo_children():
            widget.destroy()
            
        # 生成新按钮（只显示勾选的）
        r, c = 0, 0
        for semi, name in self.intervals.items():
            # 即使没勾选，为了界面整齐也可以显示禁用状态，或者直接隐藏
            # 这里选择：所有按钮都显示，但方便点击
            btn = ttk.Button(self.btn_frame, text=name, command=lambda s=semi: self.check_answer(s))
            btn.grid(row=r, column=c, padx=5, pady=5)
            c += 1
            if c > 3:
                c = 0
                r += 1

    def generate_wave(self, freq, duration=0.8, volume=0.5):
        """ 使用 Numpy 生成波形数据，添加简单的包络使其听起来不那么刺耳 """
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        
        wave_type = self.instruments[self.inst_var.get()]
        
        # 基础波形生成
        if wave_type == "sine":
            wave = np.sin(2 * np.pi * freq * t)
        elif wave_type == "square":
            wave = np.sign(np.sin(2 * np.pi * freq * t))
        elif wave_type == "sawtooth":
            wave = 2 * (t * freq - np.floor(t * freq + 0.5))
        elif wave_type == "triangle":
            wave = np.abs(2 * (t * freq - np.floor(t * freq + 0.5))) * 2 - 1
        else:
            wave = np.sin(2 * np.pi * freq * t)

        # ADSR 包络 (简单版：Attack + Decay)
        # 防止只有 "滴" 的一声，让它有淡入淡出
        attack = int(self.sample_rate * 0.05)
        release = int(self.sample_rate * 0.1)
        
        envelope = np.ones(n_samples)
        # 淡入
        envelope[:attack] = np.linspace(0, 1, attack)
        # 淡出
        envelope[-release:] = np.linspace(1, 0, release)
        
        wave = wave * envelope * volume
        
        # 转换为 16-bit 格式，立体声
        audio = (wave * 32767).astype(np.int16)
        stereo_audio = np.column_stack((audio, audio)) # 复制到双声道
        return stereo_audio

    def play_sound_data(self, sound_data):
        sound = pygame.sndarray.make_sound(sound_data)
        sound.play()
        return sound.get_length()

    def get_active_intervals(self):
        return [k for k, v in self.check_vars.items() if v.get()]

    def play_new_interval(self):
        active = self.get_active_intervals()
        if not active:
            messagebox.showwarning("提示", "请至少勾选一个音程进行练习！")
            return

        # 随机生成根音 (C3 到 C5 之间)
        # MIDI 音符: 48 (C3) - 72 (C5)
        root_midi = random.randint(48, 72)
        root_freq = 440.0 * (2.0 ** ((root_midi - 69.0) / 12.0))
        
        # 随机选择音程
        interval_semis = random.choice(active)
        self.current_answer = interval_semis
        
        target_midi = root_midi + interval_semis
        target_freq = 440.0 * (2.0 ** ((target_midi - 69.0) / 12.0))
        
        # 保存频率用于重播
        self.last_freqs = (root_freq, target_freq)
        
        self.status_label.config(text="听音中...", foreground="black")
        self.play_sequence(root_freq, target_freq)

    def replay(self):
        if self.current_answer is None:
            return
        self.play_sequence(*self.last_freqs)

    def play_sequence(self, f1, f2):
        # 根据模式播放
        mode = self.mode_var.get()
        
        # 创建音频数据
        sound1 = self.generate_wave(f1)
        sound2 = self.generate_wave(f2)
        
        def _play_thread():
            if "和声" in mode:
                # 同时播放
                sound_comb = pygame.sndarray.make_sound(self.generate_wave(f1, 1.0) + self.generate_wave(f2, 1.0))
                sound_comb.play()
            elif "下行" in mode:
                # 先高后低
                self.play_sound_data(sound2)
                time.sleep(0.6)
                self.play_sound_data(sound1)
            else:
                # 默认上行
                self.play_sound_data(sound1)
                time.sleep(0.6)
                self.play_sound_data(sound2)
                
        threading.Thread(target=_play_thread, daemon=True).start()

    def check_answer(self, user_input):
        if self.current_answer is None:
            return
            
        self.history_total += 1
        
        if user_input == self.current_answer:
            self.history_correct += 1
            msg = f"回答正确！是 {self.intervals[self.current_answer]}"
            self.status_label.config(text=msg, foreground="green")
            # 答对后自动播放下一个? 这里选择手动，避免太快
        else:
            correct_name = self.intervals[self.current_answer]
            msg = f"错误。正确答案是: {correct_name}"
            self.status_label.config(text=msg, foreground="red")
            
        self.score_label.config(text=f"得分: {self.history_correct} / {self.history_total} ({int(self.history_correct/self.history_total*100)}%)")
        self.current_answer = None # 防止重复刷分

if __name__ == "__main__":
    root = tk.Tk()
    app = EarTrainerApp(root)
    root.mainloop()